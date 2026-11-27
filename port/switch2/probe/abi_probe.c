/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <switch.h>
#include <switch2/memory/heap.h>
#include <kaihen.h>
#include <pthread.h>
#include <malloc.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include "warthog_build.h"

static __thread int tls_value = 7;

static void *thread_main(void *arg)
{
	(void)arg;
	if (tls_value != 7)
		return (void *)1;
	tls_value = 42;
	return 0;
}

static u64 info(FILE *log, const char *name, InfoType type)
{
	u64 value = 0;
	Result rc = svcGetInfo(&value, type, CUR_PROCESS_HANDLE, 0);
	fprintf(log, "info.%s.result=0x%x\ninfo.%s.value=0x%llx\n",
		name, rc, name, (unsigned long long)value);
	return value;
}

int main(void)
{
	mkdir("sdmc:/switch", 0777);
	mkdir("sdmc:/switch/warthog", 0777);
	mkdir("sdmc:/switch/warthog/logs", 0777);
	FILE *log = fopen("sdmc:/switch/warthog/logs/abi_probe.log", "w");
	if (!log)
		return 1;
	setvbuf(log, NULL, _IOLBF, 0);
	fprintf(log, "version=%s\nflavor=%s\nfirmware=0x%x\napplet_type=%d\nlibounce=%s\nlibkaihen=%s\n",
		WARTHOG_SWITCH2_VERSION, WARTHOG_SWITCH2_FLAVOR,
		hosversionGet(), appletGetAppletType(), WARTHOG_SWITCH2_LIBOUNCE_COMMIT,
		WARTHOG_SWITCH2_KAIHEN_COMMIT);
	for (unsigned i = 0; i < 0x80; ++i)
		fprintf(log, "svc.%02x.hinted=%d\n", i, envIsSyscallHinted(i));
	if (envIsSyscallHinted(0x29)) {
		info(log, "alias_address", InfoType_AliasRegionAddress);
		info(log, "alias_size", InfoType_AliasRegionSize);
		info(log, "heap_address", InfoType_HeapRegionAddress);
		info(log, "heap_size", InfoType_HeapRegionSize);
		info(log, "aslr_address", InfoType_AslrRegionAddress);
		info(log, "aslr_size", InfoType_AslrRegionSize);
		u64 stack = info(log, "stack_address", InfoType_StackRegionAddress);
		u64 size = info(log, "stack_size", InfoType_StackRegionSize);
		fprintf(log, "stack.below_4g=%d\n", stack < 0x100000000ULL && size != 0);
		info(log, "total", InfoType_TotalMemorySize);
		info(log, "used", InfoType_UsedMemorySize);
		info(log, "core_mask", InfoType_CoreMask);
	}
	fprintf(log, "heap.total=%llu\nheap.free=%llu\n",
		(unsigned long long)heapGetTotalSize(), (unsigned long long)heapGetFreeSize());
	if (envIsSyscallHinted(0x06)) {
		for (u64 addr = 0; addr < 0x100000000ULL;) {
			MemoryInfo mi;
			u32 page;
			Result rc = svcQueryMemory(&mi, &page, addr);
			if (R_FAILED(rc)) {
				fprintf(log, "query.result=0x%x\n", rc);
				break;
			}
			fprintf(log, "query=0x%llx,0x%llx,%u,%u\n",
				(unsigned long long)mi.addr, (unsigned long long)mi.size,
				mi.type, mi.perm);
			if (mi.addr + mi.size <= addr)
				break;
			addr = mi.addr + mi.size;
		}
	}
	if (envIsSyscallHinted(0x05) && envIsSyscallHinted(0x04)) {
		void *backing = memalign(0x1000, 0x1000);
		virtmemLock();
		void *slice = virtmemFindStack(0x50000000ULL, 0);
		VirtmemReservation *reservation = slice ? virtmemAddReservation(slice, 0x50000000ULL) : NULL;
		virtmemUnlock();
		int mapped = 0;
		fprintf(log, "slice=%p\nbase=%p\n", slice,
			slice ? (void *)((uintptr_t)slice - 0x40000000ULL) : NULL);
		if (backing && reservation) {
			*(volatile unsigned *)backing = 0x12345678;
			Result rc = svcMapMemory(slice, backing, 0x1000);
			fprintf(log, "map.result=0x%x\n", rc);
			if (R_SUCCEEDED(rc)) {
				mapped = 1;
				fprintf(log, "map.value=0x%x\n", *(volatile unsigned *)slice);
				rc = svcUnmapMemory(slice, backing, 0x1000);
				fprintf(log, "unmap.result=0x%x\n", rc);
				if (R_SUCCEEDED(rc))
					mapped = 0;
			}
		}
		if (reservation && !mapped) {
			virtmemLock();
			virtmemRemoveReservation(reservation);
			virtmemUnlock();
		}
		if (!mapped)
			free(backing);
	}
	Service ro;
	Result jit_rc = kaihenGetRoSession(&ro);
	fprintf(log, "jit.ro.result=0x%x\n", jit_rc);
	if (R_SUCCEEDED(jit_rc)) {
		Jit jit;
		jit_rc = jitCreate(&jit, 0x1000);
		fprintf(log, "jit.create=0x%x\n", jit_rc);
		if (R_SUCCEEDED(jit_rc)) {
			fprintf(log, "jit.rw=%p\njit.rx=%p\njit.rw.below_4g=%d\njit.rx.below_4g=%d\n",
				jit.rw_addr, jit.rx_addr, (uintptr_t)jit.rw_addr < 0x100000000ULL,
				(uintptr_t)jit.rx_addr < 0x100000000ULL);
			jit_rc = jitTransitionToWritable(&jit);
			fprintf(log, "jit.writable=0x%x\n", jit_rc);
			if (R_SUCCEEDED(jit_rc)) {
				u32 *code = jit.rw_addr;
				code[0] = 0x52800540; /* mov w0, #42 */
				code[1] = 0xd65f03c0; /* ret */
				armDCacheFlush(code, 8);
				jit_rc = jitTransitionToExecutable(&jit);
				fprintf(log, "jit.executable=0x%x\n", jit_rc);
				if (R_SUCCEEDED(jit_rc)) {
					armICacheInvalidate(jit.rx_addr, 8);
					fprintf(log, "jit.return=%d\n", ((int (*)(void))jit.rx_addr)());
				}
			}
			fprintf(log, "jit.close=0x%x\n", jitClose(&jit));
		}
	}
	pthread_t thread;
	pthread_attr_t attr;
	pthread_attr_init(&attr);
	pthread_attr_setstacksize(&attr, 0x10000);
	int rc = pthread_create(&thread, &attr, thread_main, NULL);
	fprintf(log, "pthread.create=%d\n", rc);
	pthread_attr_destroy(&attr);
	if (!rc) {
		void *result;
		rc = pthread_join(thread, &result);
		fprintf(log, "pthread.join=%d\ntls.thread=%d\ntls.main=%d\n", rc, result == NULL, tls_value);
	}
	fclose(log);
	return 0;
}
