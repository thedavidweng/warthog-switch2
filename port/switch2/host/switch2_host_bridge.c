/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <pthread.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <switch.h>
#include "../../switch/host/host.h"
#include "nx2_platform.h"
#include "warthog_log.h"

int host_renderer_deko3d = 1;
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
