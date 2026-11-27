/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SWITCH2_DRAKO3D_H
#define SWITCH2_DRAKO3D_H

#include <stdbool.h>
#include <stdint.h>

/* The renderer keeps a resource alive until the serial that used it retires. */
struct switch2_drako3d_sync_stats {
	uint64_t upload_bytes;
	uint64_t upload_rollovers;
	uint64_t fence_waits;
	uint64_t fence_wait_us;
};

bool switch2_drako3d_fence_allows_reuse(uint32_t retired, uint32_t serial);
bool switch2_drako3d_resize_requires_idle(bool swapchain_exists);
bool switch2_drako3d_hud_requires_clean(bool cpu_cached);
uint32_t switch2_drako3d_copy_invalidate_flags(void);

void switch2_drako3d_record_upload(struct switch2_drako3d_sync_stats *stats, uint32_t bytes);
void switch2_drako3d_record_rollover(struct switch2_drako3d_sync_stats *stats);
void switch2_drako3d_record_fence_wait(struct switch2_drako3d_sync_stats *stats, uint64_t wait_us);

#endif
