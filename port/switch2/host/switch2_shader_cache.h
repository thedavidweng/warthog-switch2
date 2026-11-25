/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once

#include <stddef.h>
#include <stdint.h>

#define SWITCH2_SHADER_CACHE_ARCH "ampere"
#define SWITCH2_SHADER_CACHE_DEKO3D 200u
#define SWITCH2_SHADER_CACHE_UAM2 "11f145faa1c1"
#define SWITCH2_SHADER_CACHE_SHADER_ABI 1u

struct switch2_shader_cache_key {
	char architecture[8];
	uint32_t deko3d;
	char uam2[13];
	uint32_t shader_abi;
	uint32_t generator;
	uint32_t warp_blend;
	uint32_t compile_flags;
	uint64_t digest;
};

struct switch2_shader_cache_dksh_header {
	uint32_t magic;
	uint32_t header_size;
	uint32_t control_size;
	uint32_t code_size;
	uint32_t programs_offset;
	uint32_t program_count;
	uint32_t deko3d;
	uint32_t crc32;
};

struct switch2_shader_cache_pack_record {
	uint32_t magic;
	uint32_t stage;
	uint64_t hash;
	uint32_t size;
	uint32_t crc32;
};

struct switch2_shader_progress {
	uint32_t completed;
	uint32_t total;
};

void switch2_shader_cache_key_init(struct switch2_shader_cache_key *key,
	uint32_t generator, uint32_t warp_blend, uint32_t compile_flags);
uint64_t switch2_shader_cache_key_digest(const struct switch2_shader_cache_key *key);
int switch2_shader_cache_validate_dksh(const void *data, size_t size);
int switch2_shader_cache_validate_pack_record(const void *record, size_t record_size,
	const void *data, size_t data_size);
uint32_t switch2_shader_cache_crc32(const void *data, size_t size);
int switch2_shader_cache_atomic_write(const char *path, const void *data, size_t size);
void switch2_shader_progress_format(char *buffer, size_t size,
	const struct switch2_shader_progress *progress);
unsigned switch2_shader_progress_percent(const struct switch2_shader_progress *progress);
