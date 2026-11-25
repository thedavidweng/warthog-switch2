/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "switch2_campaign.h"

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static char *part_path(const char *path)
{
	size_t length = strlen(path);
	char *part = malloc(length + sizeof(".part"));
	if (part)
	{
		memcpy(part, path, length);
		memcpy(part + length, ".part", sizeof(".part"));
	}
	return part;
}

void switch2_campaign_cleanup_stale_part(const char *path)
{
	char *part = part_path(path);
	if (part)
	{
		unlink(part);
		free(part);
	}
}

int switch2_campaign_write_atomic(const char *path, const void *data, size_t size)
{
	char *part = part_path(path);
	FILE *file;
	int ok;

	if (!part)
		return 0;
	file = fopen(part, "wb");
	if (!file)
	{
		free(part);
		return 0;
	}
	ok = fwrite(data, 1, size, file) == size && fflush(file) == 0 &&
		fsync(fileno(file)) == 0;
	if (fclose(file))
		ok = 0;
	if (ok)
		ok = rename(part, path) == 0;
	if (!ok)
		unlink(part);
	free(part);
	return ok;
}

static int in_image(uintptr_t pointer, uintptr_t base, size_t size)
{
	return pointer >= base && pointer <= base + size &&
		pointer <= UINTPTR_MAX - size && pointer + 1 <= base + size;
}

static void relocate(void **pointer, intptr_t delta)
{
	*pointer = (void *)((uintptr_t)*pointer + (uintptr_t)delta);
}

int switch2_campaign_relocate_native_pointer(
	void **pointer, void *saved_base, void *live_base, size_t size)
{
	uintptr_t value;
	uintptr_t base = (uintptr_t)saved_base;

	if (!pointer || !*pointer)
		return 1;
	value = (uintptr_t)*pointer;
	if (!in_image(value, base, size))
		return 0;
	*pointer = (void *)(value + ((uintptr_t)live_base - base));
	return 1;
}

int switch2_campaign_relocate_native_pointers(
	void *saved_base, void *live_base, size_t size,
	struct switch2_campaign_pool_relocation *pools, size_t pool_count,
	struct switch2_campaign_cache_relocation *caches, size_t cache_count)
{
	uintptr_t base = (uintptr_t)saved_base;
	intptr_t delta = (intptr_t)((uintptr_t)live_base - base);
	size_t i, j;

	if (saved_base == live_base)
		return 1;
	for (i = 0; i < pool_count; ++i)
	{
		struct switch2_campaign_pool_relocation *pool = &pools[i];
		void **values[] = { pool->base_address, pool->first_block, pool->last_block };
		for (j = 0; j < sizeof(values) / sizeof(values[0]); ++j)
			if (!values[j] || !*values[j] ||
				!in_image((uintptr_t)*values[j], base, size))
				return 0;
		for (j = 0; j < pool->block_count; ++j)
		{
			void **block_values[] = {
				&pool->block_references[j],
				&pool->next_blocks[j],
				&pool->previous_blocks[j]
			};
			if (!in_image((uintptr_t)pool->block_references[j], base, size) ||
				!in_image((uintptr_t)pool->reference_targets[j], base, size))
				return 0;
			for (size_t k = 0; k < sizeof(block_values) / sizeof(block_values[0]); ++k)
				if (*block_values[k] &&
					!in_image((uintptr_t)*block_values[k], base, size))
					return 0;
		}
		for (j = 0; j < sizeof(values) / sizeof(values[0]); ++j)
			relocate(values[j], delta);
		for (j = 0; j < pool->block_count; ++j)
		{
			if (pool->block_references[j])
				relocate(&pool->block_references[j], delta);
			if (pool->reference_targets[j])
				relocate(&pool->reference_targets[j], delta);
			if (pool->next_blocks[j])
				relocate(&pool->next_blocks[j], delta);
			if (pool->previous_blocks[j])
				relocate(&pool->previous_blocks[j], delta);
		}
	}
	for (i = 0; i < cache_count; ++i)
	{
		if (!caches[i].blocks || !*caches[i].blocks ||
			!in_image((uintptr_t)*caches[i].blocks, base, size))
			return 0;
		relocate(caches[i].blocks, delta);
	}
	return 1;
}

static uint32_t read_u32(const unsigned char *bytes)
{
	return (uint32_t)bytes[0] | (uint32_t)bytes[1] << 8 |
		(uint32_t)bytes[2] << 16 | (uint32_t)bytes[3] << 24;
}

const char *switch2_campaign_mission_id(size_t index)
{
	static const char *const missions[] = {
		"a10", "a30", "a50", "b30", "b40",
		"c10", "c20", "c40", "d20", "d40"
	};
	return index < sizeof(missions) / sizeof(missions[0]) ? missions[index] : NULL;
}

int switch2_campaign_validate_map(const char *path, char *message, size_t size)
{
	unsigned char header[2048];
	struct stat st;
	const char *problem = NULL;
	FILE *file = fopen(path, "rb");
	if (!file)
	{
		snprintf(message, size, "Cannot open map %s", path);
		return 0;
	}
	if (fstat(fileno(file), &st) || fread(header, 1, sizeof(header), file) != sizeof(header))
		problem = "truncated";
	else if (memcmp(header, "daeh", 4))
		problem = "bad header";
	else if (memcmp(header + 2044, "toof", 4))
		problem = "bad footer";
	else if (read_u32(header + 4) != 5 && read_u32(header + 4) != 7 &&
		read_u32(header + 4) != 609)
		problem = "unsupported version";
	else if (read_u32(header + 8) < sizeof(header) || read_u32(header + 8) > (uint64_t)st.st_size)
		problem = "truncated";
	fclose(file);
	if (problem)
	{
		snprintf(message, size, "Map %s: %s", path, problem);
		return 0;
	}
	if (size)
		message[0] = 0;
	return 1;
}

int switch2_campaign_validate_resource(const char *path, unsigned type, char *message, size_t size)
{
	unsigned char header[16];
	struct stat st;
	const char *problem = NULL;
	FILE *file = fopen(path, "rb");
	if (!file)
	{
		snprintf(message, size, "Cannot open resource map %s", path);
		return 0;
	}
	if (fstat(fileno(file), &st) || fread(header, 1, sizeof(header), file) != sizeof(header))
		problem = "truncated header";
	else if (read_u32(header) != type)
		problem = "incorrect resource type";
	else if (read_u32(header + 4) < sizeof(header) || read_u32(header + 4) > read_u32(header + 8) ||
		read_u32(header + 12) > 65536 ||
		(uint64_t)read_u32(header + 8) + (uint64_t)read_u32(header + 12) * 12 > (uint64_t)st.st_size)
		problem = "invalid resource table";
	fclose(file);
	if (problem)
	{
		snprintf(message, size, "Resource map %s: %s", path, problem);
		return 0;
	}
	if (size)
		message[0] = 0;
	return 1;
}
