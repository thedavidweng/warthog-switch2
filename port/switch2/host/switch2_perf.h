/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once

#include <stddef.h>
#include <stdint.h>

struct switch2_perf_stats {
	double *frames;
	size_t frame_count, frame_capacity;
	uint64_t shader_count, memory_peak, heap_total, heap_free;
	double shader_total_ms, shader_max_ms;
	uint64_t shader_cache_hits, shader_cache_misses, shader_runtime_compiles;
	double shader_compile_total_ms, shader_compile_max_ms, shader_map_wait_ms;
	double gpu_total_ms;
	uint64_t submit_wait_us, acquire_max_us, fence_max_us;
	uint64_t upload_bytes, upload_rollovers, fence_waits, fence_wait_us;
};

struct switch2_perf_summary {
	double mean, p50, p95, p99, max;
};

enum switch2_perf_clock_mode { SWITCH2_PERF_NORMAL, SWITCH2_PERF_FAST_LOAD };
typedef int (*switch2_perf_run_fn)(enum switch2_perf_clock_mode mode, void *context);
typedef void (*switch2_perf_clock_fn)(enum switch2_perf_clock_mode mode, void *context);

int switch2_perf_add_frame(struct switch2_perf_stats *stats, double ms);
void switch2_perf_add_shader(struct switch2_perf_stats *stats, double ms);
void switch2_perf_shader_cache_hit(struct switch2_perf_stats *stats, int warm);
void switch2_perf_shader_cache_miss(struct switch2_perf_stats *stats);
void switch2_perf_shader_compile(struct switch2_perf_stats *stats, double ms);
void switch2_perf_shader_map_wait(struct switch2_perf_stats *stats, double ms);
void switch2_perf_add_memory(struct switch2_perf_stats *stats, uint64_t bytes);
void switch2_perf_add_upload(struct switch2_perf_stats *stats, uint64_t bytes);
void switch2_perf_add_upload_rollover(struct switch2_perf_stats *stats);
void switch2_perf_add_fence_wait(struct switch2_perf_stats *stats, uint64_t wait_us);
void switch2_perf_renderer_upload(uint64_t bytes);
void switch2_perf_renderer_rollover(void);
void switch2_perf_renderer_fence_wait(uint64_t wait_us);
void switch2_perf_renderer_shader_hit(int warm);
void switch2_perf_renderer_shader_miss(void);
void switch2_perf_renderer_shader_compile(double ms);
void switch2_perf_renderer_shader_map_wait(double ms);
struct switch2_perf_summary switch2_perf_summary(const struct switch2_perf_stats *stats);
void switch2_perf_clear(struct switch2_perf_stats *stats);
int switch2_perf_compare_clocks(switch2_perf_run_fn run, switch2_perf_clock_fn set_clock,
	void *context);
#if defined(__SWITCH2__) && WARTHOG_DEV_PROFILING
int switch2_perf_benchmark(switch2_perf_run_fn run, void *context);
#endif
void switch2_perf_record_frame(struct switch2_perf_stats *stats, double cpu_ms, double gpu_ms,
	uint32_t submit_wait_us, uint32_t acquire_max_us, uint32_t fence_max_us);
#if defined(__SWITCH2__) && WARTHOG_DEV_PROFILING
void switch2_perf_flush(struct switch2_perf_stats *stats, const char *scene, const char *mode,
	double map_load_ms);
#endif

#if defined(__SWITCH2__) && WARTHOG_DEV_PROFILING
void switch2_perf_shader(double ms);
void switch2_perf_log_shader(void);
#endif
