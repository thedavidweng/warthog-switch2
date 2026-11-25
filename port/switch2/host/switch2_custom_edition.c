/* SPDX-License-Identifier: GPL-3.0-or-later */
#define _POSIX_C_SOURCE 200809L
#include "switch2_custom_edition.h"

#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

#define CACHE_HEADER_SIZE 0x800u

static uint32_t u32(const unsigned char *p)
{
	return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static int message(int status, char *out, size_t size, const char *text)
{
	if (out && size) snprintf(out, size, "%s", text);
	return status;
}

int switch2_ce_validate_map(const char *path, uint32_t *version, char *out, size_t out_size)
{
	unsigned char header[CACHE_HEADER_SIZE];
	struct stat st;
	int fd;
	uint32_t found, length, tag_offset, tag_size;
	if (version) *version = 0;
	if (!path || stat(path, &st) || !S_ISREG(st.st_mode))
		return message(SWITCH2_CE_MAP_IO_ERROR, out, out_size, "Custom Edition map could not be opened.");
	if ((uint64_t)st.st_size < CACHE_HEADER_SIZE)
		return message(SWITCH2_CE_MAP_INVALID, out, out_size, "Unsupported map: truncated cache header (requires 0x800 bytes).");
	fd = open(path, O_RDONLY);
	if (fd < 0 || read(fd, header, sizeof(header)) != (ssize_t)sizeof(header))
	{
		if (fd >= 0) close(fd);
		return message(SWITCH2_CE_MAP_IO_ERROR, out, out_size, "Unsupported map: truncated or unreadable cache header.");
	}
	close(fd);
	if (memcmp(header, "head", 4) || memcmp(header + 0x7fc, "foot", 4))
		return message(SWITCH2_CE_MAP_INVALID, out, out_size, "Unsupported map: corrupt cache header or footer (expected head/foot).");
	found = u32(header + 4) & 0x7fffffffU;
	if (version) *version = found;
	if (found == 8)
		return message(SWITCH2_CE_MAP_UNSUPPORTED, out, out_size, "Unsupported map version 8: Halo 2 cache format is not supported.");
	if (found == 13)
		return message(SWITCH2_CE_MAP_UNSUPPORTED, out, out_size, "Unsupported map version 13: MCC cache requires the MCC package and converter.");
	if (found != 609 && found != 7)
	{
		if (found == 5)
			return message(SWITCH2_CE_MAP_UNSUPPORTED, out, out_size, "Unsupported map version 5: Xbox or Halo Trial data belongs in maps/.");
		snprintf(out, out_size, "Unsupported map version %u: only Custom Edition 609 and Halo PC 7 are accepted in maps_ce.", found);
		return SWITCH2_CE_MAP_UNSUPPORTED;
	}
	length = u32(header + 8);
	if (length && (length < CACHE_HEADER_SIZE || (uint64_t)length > (uint64_t)st.st_size))
		return message(SWITCH2_CE_MAP_INVALID, out, out_size, "Unsupported map: corrupt cache file length in header.");
	tag_offset = u32(header + 0x10);
	tag_size = u32(header + 0x14);
	if (tag_offset < CACHE_HEADER_SIZE || !tag_size ||
		(uint64_t)tag_offset + tag_size > (length ? length : (uint32_t)st.st_size))
		return message(SWITCH2_CE_MAP_INVALID, out, out_size, "Unsupported map: corrupt tag data range in cache header.");
	if (out && out_size) snprintf(out, out_size, "Supported Halo cache version %u.", found);
	return SWITCH2_CE_MAP_OK;
}

static int join(char *out, size_t size, const char *a, const char *b)
{
	int n = snprintf(out, size, "%s/%s", a, b);
	return n >= 0 && (size_t)n < size;
}

int switch2_ce_prepare_directory(const char *root, char *out, size_t out_size)
{
	char path[4096];
	struct stat st;
	if (!root || !join(path, sizeof(path), root, "maps_ce"))
		return message(SWITCH2_CE_MAP_IO_ERROR, out, out_size, "Custom Edition maps path is too long.");
	if (mkdir(path, 0755) && errno != EEXIST)
		return message(SWITCH2_CE_MAP_IO_ERROR, out, out_size, "Could not create maps_ce directory.");
	if (stat(path, &st) || !S_ISDIR(st.st_mode))
		return message(SWITCH2_CE_MAP_IO_ERROR, out, out_size, "maps_ce exists but is not a directory.");
	return 1;
}

static int enumerate_folder(const char *folder, switch2_ce_map_callback callback, void *ctx,
	int *found, char *out, size_t out_size)
{
	DIR *dir = opendir(folder);
	struct dirent *entry;
	if (!dir) return errno == ENOENT;
	while ((entry = readdir(dir)))
	{
		char path[4096], error[256];
		uint32_t version;
		size_t n = strlen(entry->d_name);
		if (n < 4 || strcasecmp(entry->d_name + n - 4, ".map") || !join(path, sizeof(path), folder, entry->d_name))
			continue;
		if (switch2_ce_validate_map(path, &version, error, sizeof(error)) != SWITCH2_CE_MAP_OK)
		{
			closedir(dir);
			snprintf(out, out_size, "%s: %s", entry->d_name, error);
			return 0;
		}
		(*found)++;
		if (callback && !callback(ctx, path, version))
		{
			closedir(dir);
			return message(SWITCH2_CE_MAP_IO_ERROR, out, out_size, "Custom Edition map listing was stopped by the caller.");
		}
	}
	closedir(dir);
	return 1;
}

int switch2_ce_enumerate(const char *root, const char *legacy, switch2_ce_map_callback callback,
	void *ctx, char *out, size_t out_size)
{
	char current[4096], old[4096];
	int found = 0;
	if (!root || !join(current, sizeof(current), root, "maps_ce"))
		return message(SWITCH2_CE_MAP_IO_ERROR, out, out_size, "Custom Edition maps path is too long.");
	if (!enumerate_folder(current, callback, ctx, &found, out, out_size))
		return SWITCH2_CE_MAP_INVALID;
	if (legacy && join(old, sizeof(old), legacy, "maps_ce") && strcmp(current, old) &&
		!enumerate_folder(old, callback, ctx, &found, out, out_size))
		return SWITCH2_CE_MAP_INVALID;
	if (out && out_size) snprintf(out, out_size, "Found %d supported Custom Edition map(s).", found);
	return found;
}
