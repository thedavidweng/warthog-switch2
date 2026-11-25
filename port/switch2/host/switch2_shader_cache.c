/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "switch2_shader_cache.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#define DKSH_MAGIC 0x48534b44u
#define DKSH_PACK_RECORD_MAGIC 0x52504b44u
#define DKSH_RECORD_LIMIT (4u * 1024u * 1024u)

uint32_t switch2_shader_cache_crc32(const void *data, size_t size)
{
	uint32_t crc = ~0u;
	const unsigned char *bytes = data;
	while (size--) {
		crc ^= *bytes++;
		for (unsigned bit = 0; bit != 8; ++bit)
			crc = crc & 1 ? (crc >> 1) ^ 0xedb88320u : crc >> 1;
	}
	return ~crc;
}

static uint64_t fnv1a(const void *data, size_t size, uint64_t hash)
{
	const unsigned char *bytes = data;
	while (size--) hash = (hash ^ *bytes++) * 1099511628211ull;
	return hash;
}

void switch2_shader_cache_key_init(struct switch2_shader_cache_key *key,
	uint32_t generator, uint32_t warp_blend, uint32_t compile_flags)
{
	memset(key, 0, sizeof(*key));
	memcpy(key->architecture, SWITCH2_SHADER_CACHE_ARCH, sizeof(SWITCH2_SHADER_CACHE_ARCH));
	key->deko3d = SWITCH2_SHADER_CACHE_DEKO3D;
	memcpy(key->uam2, SWITCH2_SHADER_CACHE_UAM2, sizeof(SWITCH2_SHADER_CACHE_UAM2));
	key->shader_abi = SWITCH2_SHADER_CACHE_SHADER_ABI;
	key->generator = generator;
	key->warp_blend = warp_blend;
	key->compile_flags = compile_flags;
	key->digest = switch2_shader_cache_key_digest(key);
}

uint64_t switch2_shader_cache_key_digest(const struct switch2_shader_cache_key *key)
{
	struct switch2_shader_cache_key copy = *key;
	copy.digest = 0;
	return fnv1a(&copy, sizeof(copy), 1469598103934665603ull);
}

int switch2_shader_cache_validate_dksh(const void *data, size_t size)
{
	const struct switch2_shader_cache_dksh_header *header = data;
	uint32_t crc;
	if (!data || size < sizeof(*header) || header->magic != DKSH_MAGIC ||
		header->deko3d != SWITCH2_SHADER_CACHE_DEKO3D ||
		header->header_size < 24 || header->header_size > size ||
		!header->control_size || !header->code_size ||
		header->control_size > size || header->code_size > size - header->control_size ||
		header->programs_offset > size || header->program_count > size / 16)
		return 0;
	crc = switch2_shader_cache_crc32((const unsigned char *)data + header->header_size,
		size - header->header_size);
	return header->crc32 == crc;
}

int switch2_shader_cache_validate_pack_record(const void *record_data, size_t record_size,
	const void *data, size_t data_size)
{
	const struct switch2_shader_cache_pack_record *record = record_data;
	if (!record_data || record_size < sizeof(*record) || !data ||
		record->magic != DKSH_PACK_RECORD_MAGIC || record->stage > 1 ||
		!record->size || record->size > DKSH_RECORD_LIMIT || record->size > data_size)
		return 0;
	return switch2_shader_cache_validate_dksh(data, record->size) &&
		record->crc32 == switch2_shader_cache_crc32(data, record->size);
}

int switch2_shader_cache_atomic_write(const char *path, const void *data, size_t size)
{
	char temporary[1024];
	int fd;
	size_t offset = 0;
	if (!path || !data || snprintf(temporary, sizeof(temporary), "%s.tmp", path) >= (int)sizeof(temporary))
		return 0;
	fd = open(temporary, O_WRONLY | O_CREAT | O_TRUNC, 0666);
	if (fd < 0) return 0;
	while (offset < size) {
		ssize_t written = write(fd, (const unsigned char *)data + offset, size - offset);
		if (written <= 0) {
			close(fd);
			unlink(temporary);
			return 0;
		}
		offset += (size_t)written;
	}
	if (fsync(fd) != 0 || close(fd) != 0) {
		close(fd);
		unlink(temporary);
		return 0;
	}
	if (rename(temporary, path) != 0) {
		unlink(temporary);
		return 0;
	}
	return 1;
}

unsigned switch2_shader_progress_percent(const struct switch2_shader_progress *progress)
{
	if (!progress || !progress->total) return 100;
	if (progress->completed >= progress->total) return 100;
	return (unsigned)((uint64_t)progress->completed * 100 / progress->total);
}

void switch2_shader_progress_format(char *buffer, size_t size,
	const struct switch2_shader_progress *progress)
{
	if (!buffer || !size) return;
	if (!progress) {
		snprintf(buffer, size, "Compiling shaders: 0 / 0");
		return;
	}
	snprintf(buffer, size, "Compiling shaders: %u / %u (%u%%)",
		progress->completed, progress->total, switch2_shader_progress_percent(progress));
}
