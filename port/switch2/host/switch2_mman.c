#include "switch2_mman.h"
#include <sys/mman.h>
#include <errno.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#ifdef __SWITCH2__
#include <malloc.h>
#include <switch.h>
#else
static void *host_aligned_alloc(size_t size)
{
    void *p = NULL;
    return posix_memalign(&p, SWITCH2_PAGE_SIZE, size) ? NULL : p;
}
#endif

unsigned long long xbox_address_space_base;
struct mapped_run { uintptr_t va; void *backing; size_t size; };
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static void *slice;
#ifdef __SWITCH2__
/* Active sub-windows inside [0x40000000, 0xa0000000) when a random thread
   stack sits in the unused [0x50000000, 0x80000000) gap of the 2 GiB StackRegion. */
#define SWITCH2_LOW_SUBWINDOW_SIZE  0x10000000ULL /* [0x40000000, 0x50000000): CE cache + 224 MiB heap */
#define SWITCH2_HIGH_SUBWINDOW_OFF  0x40000000ULL /* 0x80000000 - 0x40000000 */
#define SWITCH2_HIGH_SUBWINDOW_SIZE 0x20000000ULL /* [0x80000000, 0xa0000000): 512 MiB contiguous */
#define SWITCH2_STACK_GUARD_MARGIN  0x00100000ULL /* 1 MiB guard around existing mappings */

static VirtmemReservation *reservation;
static VirtmemReservation *reservation_high;
static bool split_reservation;

static bool switch2_range_unmapped(u64 start, u64 end, u64 region_start, u64 region_end, u64 guard)
{
    MemoryInfo info;
    u32 page;
    u64 check_start = start > region_start + guard ? start - guard : region_start;
    u64 check_end = end + guard <= region_end ? end + guard : region_end;

    if (end < start || start < region_start || end > region_end)
        return false;
    for (u64 cursor = check_start; cursor < check_end; )
    {
        if (R_FAILED(svcQueryMemory(&info, &page, cursor)) ||
            info.type != MemType_Unmapped || info.addr > cursor)
            return false;
        u64 next = info.addr + info.size;
        if (next <= cursor)
            return false;
        cursor = next;
    }
    return true;
}

static void *switch2_fixed_window(void)
{
    u64 stack, size, address;

    if (R_FAILED(svcGetInfo(&stack, InfoType_StackRegionAddress, CUR_PROCESS_HANDLE, 0)) ||
        R_FAILED(svcGetInfo(&size, InfoType_StackRegionSize, CUR_PROCESS_HANDLE, 0)))
        return NULL;
    address = stack + 0x08000000ULL;
    if (switch2_range_unmapped(address, address + SWITCH2_XBOX_WINDOW_SIZE, stack, stack + size, 0))
        return (void *)(uintptr_t)address;
    return NULL;
}

static void *switch2_scan_split_window(bool *out_split)
{
    u64 stack, size;

    *out_split = false;
    if (R_FAILED(svcGetInfo(&stack, InfoType_StackRegionAddress, CUR_PROCESS_HANDLE, 0)) ||
        R_FAILED(svcGetInfo(&size, InfoType_StackRegionSize, CUR_PROCESS_HANDLE, 0)) ||
        size < SWITCH2_XBOX_WINDOW_SIZE)
        return NULL;
    u64 limit = stack + size - SWITCH2_XBOX_WINDOW_SIZE;
    for (u64 candidate = stack + 0x01000000ULL; candidate <= limit; candidate += 0x01000000ULL)
    {
        if (switch2_range_unmapped(candidate, candidate + SWITCH2_XBOX_WINDOW_SIZE,
                stack, stack + size, SWITCH2_STACK_GUARD_MARGIN))
            return (void *)(uintptr_t)candidate;
    }
    for (u64 candidate = stack + 0x01000000ULL; candidate <= limit; candidate += 0x00400000ULL)
    {
        if (switch2_range_unmapped(candidate, candidate + SWITCH2_LOW_SUBWINDOW_SIZE,
                stack, stack + size, SWITCH2_STACK_GUARD_MARGIN) &&
            switch2_range_unmapped(candidate + SWITCH2_HIGH_SUBWINDOW_OFF,
                candidate + SWITCH2_HIGH_SUBWINDOW_OFF + SWITCH2_HIGH_SUBWINDOW_SIZE,
                stack, stack + size, SWITCH2_STACK_GUARD_MARGIN))
        {
            *out_split = true;
            return (void *)(uintptr_t)candidate;
        }
    }
    return NULL;
}
#endif
static struct mapped_run *runs, *anon;
static size_t run_count, run_capacity, anon_count, anon_capacity, committed;
static uint8_t pages[SWITCH2_WINDOW_PAGES / 8];
#ifndef __SWITCH2__
static size_t simulated_maps, simulated_unmaps;
size_t switch2_mman_simulated_map_count(void) { return simulated_maps; }
size_t switch2_mman_simulated_unmap_count(void) { return simulated_unmaps; }
#endif

static void *aligned_buffer(size_t size)
{
#ifdef __SWITCH2__
    return memalign(SWITCH2_PAGE_SIZE, size);
#else
    return host_aligned_alloc(size);
#endif
}
static int push(struct mapped_run **array, size_t *count, size_t *capacity, struct mapped_run run)
{
    if (*count == *capacity) {
        size_t n = *capacity ? *capacity * 2 : 16;
        void *p = realloc(*array, n * sizeof(**array));
        if (!p) return 0;
        *array = p;
        *capacity = n;
    }
    (*array)[(*count)++] = run;
    return 1;
}
static int bit(size_t page) { return (pages[page / 8] >> (page % 8)) & 1; }
static void mark(size_t first, size_t count, int value)
{
    for (size_t i = first; i < first + count; i++) {
        if (value) pages[i / 8] |= 1u << (i % 8);
        else pages[i / 8] &= ~(1u << (i % 8));
    }
}
static int map_run(struct mapped_run r)
{
#ifdef __SWITCH2__
    return R_SUCCEEDED(svcMapMemory((void *)r.va, r.backing, r.size));
#else
    simulated_maps++;
    memset((void *)r.va, 0, r.size);
    return 1;
#endif
}
static void remove_run(size_t index)
{
    struct mapped_run r = runs[index];
#ifdef __SWITCH2__
    svcUnmapMemory((void *)r.va, r.backing, r.size);
#else
    simulated_unmaps++;
#endif
    mark((r.va - (uintptr_t)slice) / SWITCH2_PAGE_SIZE, r.size / SWITCH2_PAGE_SIZE, 0);
    committed -= r.size;
    free(r.backing);
    memmove(runs + index, runs + index + 1, (run_count - index - 1) * sizeof(*runs));
    run_count--;
}
bool switch2_mman_init(void)
{
    pthread_mutex_lock(&lock);
    if (!slice) {
#ifdef __SWITCH2__
        bool split = false;
        virtmemLock();
        void *p = switch2_fixed_window();
        if (!p)
            p = virtmemFindStack(SWITCH2_XBOX_WINDOW_SIZE, 0x10000);
        if (!p)
            p = switch2_scan_split_window(&split);
        if (p && !split) {
            reservation = virtmemAddReservation(p, SWITCH2_XBOX_WINDOW_SIZE);
            if (reservation) slice = p;
        } else if (p && split) {
            reservation = virtmemAddReservation(p, SWITCH2_LOW_SUBWINDOW_SIZE);
            reservation_high = reservation ? virtmemAddReservation(
                (char *)p + SWITCH2_HIGH_SUBWINDOW_OFF, SWITCH2_HIGH_SUBWINDOW_SIZE) : NULL;
            if (reservation && reservation_high) {
                slice = p;
                split_reservation = true;
            } else {
                if (reservation) { virtmemRemoveReservation(reservation); reservation = NULL; }
                if (reservation_high) { virtmemRemoveReservation(reservation_high); reservation_high = NULL; }
            }
        }
        virtmemUnlock();
#else
        slice = aligned_buffer(SWITCH2_XBOX_WINDOW_SIZE);
#endif
        if (slice) xbox_address_space_base = (uintptr_t)slice - SWITCH2_XBOX_WINDOW_LOW;
    }
    bool ok = slice != NULL;
    pthread_mutex_unlock(&lock);
    return ok;
}
int switch2_mman_ensure(void) { return switch2_mman_init(); }
void *mmap(void *addr, size_t len, int prot, int flags, int fd, off_t offset)
{
    (void)fd; (void)offset;
    if (!switch2_mman_init()) { errno = ENOMEM; return MAP_FAILED; }
    if (prot == PROT_NONE) return (flags & MAP_FIXED) || addr ? addr : slice;
    if (!len || len > SIZE_MAX - (SWITCH2_PAGE_SIZE - 1)) { errno = EINVAL; return MAP_FAILED; }
    size_t size = (len + SWITCH2_PAGE_SIZE - 1) & ~(size_t)(SWITCH2_PAGE_SIZE - 1);
    pthread_mutex_lock(&lock);
    uintptr_t start = (uintptr_t)addr, base = (uintptr_t)slice;
    if (addr && start >= base && start - base < SWITCH2_XBOX_WINDOW_SIZE &&
        size <= SWITCH2_XBOX_WINDOW_SIZE - (start - base) && !(start % SWITCH2_PAGE_SIZE)) {
#ifdef __SWITCH2__
        if (split_reservation &&
            !((start - base + size <= SWITCH2_LOW_SUBWINDOW_SIZE) ||
              (start - base >= SWITCH2_HIGH_SUBWINDOW_OFF))) {
            pthread_mutex_unlock(&lock);
            errno = ENOMEM;
            return MAP_FAILED;
        }
#endif
        size_t first = (start - base) / SWITCH2_PAGE_SIZE, end = first + size / SWITCH2_PAGE_SIZE;
        size_t original_count = run_count;
        for (size_t i = first; i < end;) {
            if (bit(i)) { memset((void *)(base + i * SWITCH2_PAGE_SIZE), 0, SWITCH2_PAGE_SIZE); i++; continue; }
            size_t begin = i;
            while (i < end && !bit(i)) i++;
            struct mapped_run r = { base + begin * SWITCH2_PAGE_SIZE, aligned_buffer((i - begin) * SWITCH2_PAGE_SIZE), (i - begin) * SWITCH2_PAGE_SIZE };
            if (!r.backing) goto fail;
            memset(r.backing, 0, r.size);
            if (!push(&runs, &run_count, &run_capacity, r)) { free(r.backing); goto fail; }
            if (!map_run(r)) { run_count--; free(r.backing); goto fail; }
            mark(begin, i - begin, 1);
            committed += r.size;
        }
        pthread_mutex_unlock(&lock);
        return addr;
fail:
        while (run_count > original_count) remove_run(run_count - 1);
        pthread_mutex_unlock(&lock);
        errno = ENOMEM;
        return MAP_FAILED;
    }
    if (!addr && !(flags & MAP_FIXED)) {
        void *p = aligned_buffer(size);
        if (p) {
            memset(p, 0, size);
            struct mapped_run r = { (uintptr_t)p, p, size };
            if (push(&anon, &anon_count, &anon_capacity, r)) { pthread_mutex_unlock(&lock); return p; }
            free(p);
        }
    }
    pthread_mutex_unlock(&lock);
    errno = ENOMEM;
    return MAP_FAILED;
}
int munmap(void *addr, size_t len)
{
    pthread_mutex_lock(&lock);
    if ((uintptr_t)addr == xbox_address_space_base && len == 0x100000000ULL) { pthread_mutex_unlock(&lock); return 0; }
    uintptr_t start = (uintptr_t)addr;
    for (size_t i = run_count; i > 0; i--) {
        struct mapped_run r = runs[i - 1];
        if (r.va >= start && r.va - start <= len && r.size <= len - (r.va - start)) remove_run(i - 1);
    }
    for (size_t i = 0; i < anon_count; i++) if (anon[i].va == start && anon[i].size == len) {
        free(anon[i].backing);
        anon[i] = anon[--anon_count];
        break;
    }
    pthread_mutex_unlock(&lock);
    return 0;
}
int mprotect(void *addr, size_t len, int prot) { (void)addr; (void)len; (void)prot; return 0; }
void switch2_mman_shutdown(void)
{
    pthread_mutex_lock(&lock);
    while (run_count) remove_run(run_count - 1);
    while (anon_count) free(anon[--anon_count].backing);
    free(runs); runs = NULL; run_capacity = 0;
    free(anon); anon = NULL; anon_capacity = 0;
    memset(pages, 0, sizeof(pages));
    if (slice) {
#ifdef __SWITCH2__
        virtmemLock();
        if (reservation_high) { virtmemRemoveReservation(reservation_high); reservation_high = NULL; }
        if (reservation) { virtmemRemoveReservation(reservation); reservation = NULL; }
        virtmemUnlock();
#else
        free(slice);
#endif
    }
#ifdef __SWITCH2__
    split_reservation = false;
#endif
    slice = NULL; xbox_address_space_base = 0;
    pthread_mutex_unlock(&lock);
}
size_t switch2_mman_committed_bytes(void) { pthread_mutex_lock(&lock); size_t n = committed; pthread_mutex_unlock(&lock); return n; }
size_t switch2_mman_run_count(void) { pthread_mutex_lock(&lock); size_t n = run_count; pthread_mutex_unlock(&lock); return n; }
void *switch2_mman_heap_backing(uintptr_t address, size_t size)
{
    void *backing = NULL;
    pthread_mutex_lock(&lock);
    for (size_t i = 0; size && i < run_count; i++) {
        struct mapped_run *run = &runs[i];
        if (address >= run->va && address - run->va < run->size &&
            size <= run->size - (address - run->va)) {
            backing = (char *)run->backing + (address - run->va);
            break;
        }
    }
    pthread_mutex_unlock(&lock);
    return backing;
}
