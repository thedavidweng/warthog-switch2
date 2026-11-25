/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <switch.h>
#include <switch2/memory/heap.h>
#include "../../switch/host/host.h"
#include "nx2_platform.h"
#include "warthog_log.h"

int host_renderer_deko3d = 1;
int __wrap_sdl2_host_SDL_VideoInit(const char *driver) { (void)driver; return 0; }
void __wrap_sdl2_host_SDL_VideoQuit(void) {}
static pthread_mutex_t sd_lock = PTHREAD_MUTEX_INITIALIZER;

void host_logf(int priority, const char *format, ...)
{
	char message[1024];
	va_list args;
	va_start(args, format);
	vsnprintf(message, sizeof(message), format, args);
	va_end(args);
	pthread_mutex_lock(&sd_lock);
	warthog_log(priority >= HOST_LOG_ERROR ? "ERROR" : priority == HOST_LOG_WARN ? "WARN" : "INFO",
		"%s", message);
	pthread_mutex_unlock(&sd_lock);
}

void host_fatal(const char *format, ...)
{
	char message[1024];
	va_list args;
	va_start(args, format);
	vsnprintf(message, sizeof(message), format, args);
	va_end(args);
	host_logf(HOST_LOG_ERROR, "%s", message);
	abort();
}

void host_sd_lock(void) { pthread_mutex_lock(&sd_lock); }
void host_sd_unlock(void) { pthread_mutex_unlock(&sd_lock); }
const char *host_data_root(void) { return "sdmc:/switch/warthog"; }
void host_thread_place_on_helper_core(void)
{
	u64 mask = nx2CoreMask();
	for (int core = 1; core < 64; ++core)
		if (mask & (1ULL << core)) {
			svcSetThreadCoreMask(CUR_THREAD_HANDLE, core, 1ULL << core);
			break;
		}
}
void host_debug_thread_backtrace(uint32_t handle, const char *who)
{
	host_logf(HOST_LOG_WARN, "%s: backtrace unavailable for thread %u", who, handle);
}

void host_debug_profile_spike(uint64_t frame_ns) { (void)frame_ns; }
void host_memory_report(const char *when)
{
	host_logf(HOST_LOG_INFO, "heap %s: %llu bytes free", when, (unsigned long long)heapGetFreeSize());
}
int host_microphone_open(void) { return 0; }
void host_microphone_close(void) {}
int host_ui_open(void) { return 0; }
void host_ui_close(void) {}
void host_ui_message(const char *title, const char *message, const char *const *keys)
{
	(void)keys;
	host_logf(HOST_LOG_WARN, "%s: %s", title, message);
}
void host_sdl_quit(void);
void host_exit(int code)
{
	host_dk_shutdown();
	host_sdl_quit();
	switch2PlatformRestoreClock();
	nx2ExitCleanupNow();
	warthog_log_close();
	exit(code);
}
int updater_gamescope(void) { return 0; }
void updater_poll(void) {}
int posix_crash_install(const char *a, const char *b, const char *c, const char *d)
{ (void)a; (void)b; (void)c; (void)d; return 0; }
int posix_crash_pending(void) { return 0; }
void posix_crash_discard(void) {}
void posix_crash_send(void) {}
void halo_test_screenshot(void) {}
int halo_ui_point_to_window(short x, short y, float *wx, float *wy)
{ (void)x; (void)y; (void)wx; (void)wy; return 0; }
