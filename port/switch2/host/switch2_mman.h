#ifndef SWITCH2_MMAN_H
#define SWITCH2_MMAN_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define SWITCH2_XBOX_WINDOW_LOW 0x40000000ULL
#define SWITCH2_XBOX_WINDOW_SIZE 0x60000000ULL
#define SWITCH2_PAGE_SIZE 0x1000ULL
#define SWITCH2_WINDOW_PAGES (SWITCH2_XBOX_WINDOW_SIZE / SWITCH2_PAGE_SIZE)
extern unsigned long long xbox_address_space_base;
bool switch2_mman_init(void);
int switch2_mman_ensure(void);
void switch2_mman_shutdown(void);
size_t switch2_mman_committed_bytes(void);
size_t switch2_mman_run_count(void);
/* Valid only while the containing run remains committed. Ranges crossing
   separate runs have no single backing allocation and return NULL. */
void *switch2_mman_heap_backing(uintptr_t address, size_t size);
#ifndef __SWITCH2__
size_t switch2_mman_simulated_map_count(void);
size_t switch2_mman_simulated_unmap_count(void);
#endif
#endif
