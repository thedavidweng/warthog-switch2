/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <pthread.h>
#include <stdlib.h>
#include <uam2rt.h>
#include "../../switch/host/host.h"
#if WARTHOG_DEV_PROFILING
#include <switch.h>
#include "switch2_perf.h"
#endif

static pthread_once_t compiler_once = PTHREAD_ONCE_INIT;
static int compiler_ready;

static void compiler_init(void)
{
	compiler_ready = uam2rt_init();
}

int host_dk_compile_glsl(int fragment, const char *glsl, void **dksh, size_t *dksh_size)
{
	char *message = NULL;
	pthread_once(&compiler_once, compiler_init);
	if (!compiler_ready)
		return 0;
#if WARTHOG_DEV_PROFILING
	u64 start = armGetSystemTick();
#endif
	*dksh = uam2rt_compile_glsl(glsl, fragment ? Uam2rtStage_Fragment : Uam2rtStage_Vertex,
		dksh_size, &message);
#if WARTHOG_DEV_PROFILING
	switch2_perf_shader((double)armTicksToNs(armGetSystemTick() - start) / 1000000.0);
#endif
	if (message && *message)
		host_logf(*dksh ? HOST_LOG_INFO : HOST_LOG_ERROR, "uam2: %s", message);
	free(message);
	return *dksh != NULL;
}

void host_dk_compiler_shutdown(void)
{
#if WARTHOG_DEV_PROFILING
	switch2_perf_log_shader();
#endif
	if (compiler_ready)
	{
		uam2rt_exit();
		compiler_ready = 0;
	}
}
