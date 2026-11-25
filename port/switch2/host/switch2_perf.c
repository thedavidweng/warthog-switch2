/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "switch2_perf.h"

#include <stdlib.h>
#include <string.h>
#if defined(__SWITCH2__)
#include <stdio.h>
#include <switch.h>
#include <switch2/memory/heap.h>
#include "nx2_platform.h"
#include "warthog_log.h"
#endif

#if defined(__SWITCH2__) && WARTHOG_DEV_PROFILING
static void set_console_clock(enum switch2_perf_clock_mode mode, void *context)
{
	(void)context;
	appletSetCpuBoostMode(mode == SWITCH2_PERF_FAST_LOAD ?
		ApmCpuBoostMode_FastLoad : ApmCpuBoostMode_Normal);
}

int switch2_perf_benchmark(switch2_perf_run_fn run, void *context)
{
	return switch2_perf_compare_clocks(run, set_console_clock, context);
}
#endif

int switch2_perf_add_frame(struct switch2_perf_stats *stats, double ms)
{
	if (stats->frame_count == stats->frame_capacity) {
		size_t capacity = stats->frame_capacity ? stats->frame_capacity * 2 : 256;
		double *frames = realloc(stats->frames, capacity * sizeof(*frames));
		if (!frames)
			return 0;
		stats->frames = frames;
		stats->frame_capacity = capacity;
	}
	stats->frames[stats->frame_count++] = ms;
	return 1;
}

void switch2_perf_add_shader(struct switch2_perf_stats *stats, double ms)
{
	stats->shader_count++;
	stats->shader_total_ms += ms;
	if (ms > stats->shader_max_ms)
		stats->shader_max_ms = ms;
}

void switch2_perf_add_memory(struct switch2_perf_stats *stats, uint64_t bytes)
{
	if (bytes > stats->memory_peak)
		stats->memory_peak = bytes;
}

void switch2_perf_record_frame(struct switch2_perf_stats *stats, double cpu_ms, double gpu_ms,
	uint32_t submit_wait_us, uint32_t acquire_max_us, uint32_t fence_max_us)
{
	switch2_perf_add_frame(stats, cpu_ms);
	stats->gpu_total_ms += gpu_ms;
	stats->submit_wait_us += submit_wait_us;
	if (acquire_max_us > stats->acquire_max_us)
		stats->acquire_max_us = acquire_max_us;
	if (fence_max_us > stats->fence_max_us)
		stats->fence_max_us = fence_max_us;
}

static int compare_frames(const void *a, const void *b)
{
	double left = *(const double *)a, right = *(const double *)b;
	return (left > right) - (left < right);
}

struct switch2_perf_summary switch2_perf_summary(const struct switch2_perf_stats *stats)
{
	struct switch2_perf_summary summary = {0};
	size_t count = stats->frame_count;
	if (count) {
		double *sorted = malloc(count * sizeof(*sorted));
		if (!sorted)
			return summary;
		memcpy(sorted, stats->frames, count * sizeof(*sorted));
		for (size_t i = 0; i < count; i++)
			summary.mean += sorted[i];
		summary.mean /= count;
		qsort(sorted, count, sizeof(*sorted), compare_frames);
		summary.p50 = sorted[(50 * count + 99) / 100 - 1];
		summary.p95 = sorted[(95 * count + 99) / 100 - 1];
		summary.p99 = sorted[(99 * count + 99) / 100 - 1];
		summary.max = sorted[count - 1];
		free(sorted);
	}
	return summary;
}

void switch2_perf_clear(struct switch2_perf_stats *stats)
{
	free(stats->frames);
	memset(stats, 0, sizeof(*stats));
}

int switch2_perf_compare_clocks(switch2_perf_run_fn run, switch2_perf_clock_fn set_clock,
	void *context)
{
	int result = 0;
	if (!run || !set_clock)
		return -1;
	set_clock(SWITCH2_PERF_NORMAL, context);
	if (run(SWITCH2_PERF_NORMAL, context) != 0)
		result = -1;
	if (result == 0) {
		set_clock(SWITCH2_PERF_FAST_LOAD, context);
		if (run(SWITCH2_PERF_FAST_LOAD, context) != 0)
			result = -1;
	}
	set_clock(SWITCH2_PERF_NORMAL, context);
	return result;
}

#if defined(__SWITCH2__) && WARTHOG_DEV_PROFILING
void switch2_perf_flush(struct switch2_perf_stats *stats, const char *scene, const char *mode,
	double map_load_ms)
{
	struct switch2_perf_summary summary = switch2_perf_summary(stats);
	uint64_t used = 0;
	const char *root = "sdmc:/switch/warthog/logs/perf_report.json";
	svcGetInfo(&used, InfoType_UsedMemorySize, CUR_PROCESS_HANDLE, 0);
	stats->heap_total = heapGetTotalSize();
	stats->heap_free = heapGetFreeSize();
	switch2_perf_add_memory(stats, used);
	FILE *file = fopen(root, "w");
	if (!file)
		return;
	fprintf(file, "{\"runs\":[{\"scene\":\"%s\",\"mode\":\"%s\",\"refresh_hz\":%d,"
		"\"cpu_ms\":{\"mean\":%.3f,\"p50\":%.3f,\"p95\":%.3f,\"p99\":%.3f,\"max\":%.3f},"
		"\"gpu_ms\":{\"mean\":%.3f},\"submit_wait_us\":%llu,\"acquire_max_us\":%llu,"
		"\"fence_max_us\":%llu,\"shader\":{\"count\":%llu,\"total_ms\":%.3f,\"mean_ms\":%.3f,"
		"\"max_ms\":%.3f},\"map_load_ms\":%.3f,\"memory_peak_bytes\":%llu,"
		"\"heap_total_bytes\":%llu,\"heap_free_bytes\":%llu}]}",
		scene, mode, switch2PlatformRefreshRate(), summary.mean, summary.p50, summary.p95,
		summary.p99, summary.max, stats->frame_count ? stats->gpu_total_ms / stats->frame_count : 0.0,
		(unsigned long long)stats->submit_wait_us, (unsigned long long)stats->acquire_max_us,
		(unsigned long long)stats->fence_max_us, (unsigned long long)stats->shader_count,
		stats->shader_total_ms, stats->shader_count ? stats->shader_total_ms / stats->shader_count : 0.0,
		stats->shader_max_ms, map_load_ms, (unsigned long long)stats->memory_peak,
		(unsigned long long)stats->heap_total, (unsigned long long)stats->heap_free);
	fclose(file);
	warthog_log("INFO", "perf: %s %s %.3f ms p95 %.3f ms peak %llu bytes",
		scene, mode, summary.mean, summary.p95, (unsigned long long)stats->memory_peak);
}
#endif

#if defined(__SWITCH2__) && WARTHOG_DEV_PROFILING
#include <pthread.h>
#include "../../switch/host/host.h"

static pthread_mutex_t shader_lock = PTHREAD_MUTEX_INITIALIZER;
static struct switch2_perf_stats shader_stats;

void switch2_perf_shader(double ms)
{
	pthread_mutex_lock(&shader_lock);
	switch2_perf_add_shader(&shader_stats, ms);
	pthread_mutex_unlock(&shader_lock);
}

void switch2_perf_log_shader(void)
{
	pthread_mutex_lock(&shader_lock);
	host_logf(HOST_LOG_INFO, "UAM2 compiles: %llu, total %.3f ms, mean %.3f ms, max %.3f ms",
		(unsigned long long)shader_stats.shader_count, shader_stats.shader_total_ms,
		shader_stats.shader_count ? shader_stats.shader_total_ms / shader_stats.shader_count : 0.0,
		shader_stats.shader_max_ms);
	pthread_mutex_unlock(&shader_lock);
}
#endif
