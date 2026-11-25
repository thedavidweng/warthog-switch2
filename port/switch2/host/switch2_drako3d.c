/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "switch2_drako3d.h"

/* DkInvalidateFlags_Image | DkInvalidateFlags_L2Cache.  Keep this helper
   independent of the console headers so the ordering policy is host-testable. */
#define SWITCH2_DRAKO3D_INVALIDATE_IMAGE (1u << 0)
#define SWITCH2_DRAKO3D_INVALIDATE_L2_CACHE (1u << 1)

bool switch2_drako3d_fence_allows_reuse(uint32_t retired, uint32_t serial)
{
	return serial == 0 || retired >= serial;
}

bool switch2_drako3d_resize_requires_idle(bool swapchain_exists)
{
	return swapchain_exists;
}

bool switch2_drako3d_hud_requires_clean(bool cpu_cached)
{
	return cpu_cached;
}

uint32_t switch2_drako3d_copy_invalidate_flags(void)
{
	return SWITCH2_DRAKO3D_INVALIDATE_IMAGE | SWITCH2_DRAKO3D_INVALIDATE_L2_CACHE;
}

void switch2_drako3d_record_upload(struct switch2_drako3d_sync_stats *stats, uint32_t bytes)
{
	if (stats)
		stats->upload_bytes += bytes;
}

void switch2_drako3d_record_rollover(struct switch2_drako3d_sync_stats *stats)
{
	if (stats)
		stats->upload_rollovers++;
}

void switch2_drako3d_record_fence_wait(struct switch2_drako3d_sync_stats *stats, uint64_t wait_us)
{
	if (stats) {
		stats->fence_waits++;
		stats->fence_wait_us += wait_us;
	}
}
