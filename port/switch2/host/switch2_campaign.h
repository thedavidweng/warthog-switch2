/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SWITCH2_CAMPAIGN_H
#define SWITCH2_CAMPAIGN_H

#include <stddef.h>
#include <stdint.h>

const char *switch2_campaign_mission_id(size_t index);
int switch2_campaign_validate_map(const char *path, char *message, size_t size);
int switch2_campaign_validate_resource(const char *path, unsigned type, char *message, size_t size);
int switch2_campaign_write_atomic(const char *path, const void *data, size_t size);
void switch2_campaign_cleanup_stale_part(const char *path);

struct switch2_campaign_pool_relocation
{
	void **base_address;
	void **first_block;
	void **last_block;
	void **block_references;
	void **reference_targets;
	void **next_blocks;
	void **previous_blocks;
	size_t block_count;
};

struct switch2_campaign_cache_relocation
{
	void **blocks;
};

int switch2_campaign_relocate_native_pointers(
	void *saved_base, void *live_base, size_t size,
	struct switch2_campaign_pool_relocation *pools, size_t pool_count,
	struct switch2_campaign_cache_relocation *caches, size_t cache_count);
int switch2_campaign_relocate_native_pointer(
	void **pointer, void *saved_base, void *live_base, size_t size);

#endif
