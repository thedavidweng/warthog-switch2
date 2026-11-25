/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SWITCH2_CUSTOM_EDITION_H
#define SWITCH2_CUSTOM_EDITION_H

#include <stddef.h>
#include <stdint.h>

#define SWITCH2_CE_TAG_CACHE_BASE 0x40440000u
#define SWITCH2_CE_TAG_CACHE_SIZE 0x01700000u

enum switch2_ce_map_status
{
	SWITCH2_CE_MAP_OK = 0,
	SWITCH2_CE_MAP_IO_ERROR = -1,
	SWITCH2_CE_MAP_INVALID = -2,
	SWITCH2_CE_MAP_UNSUPPORTED = -3
};

typedef int (*switch2_ce_map_callback)(void *ctx, const char *path, uint32_t version);

int switch2_ce_validate_map(const char *path, uint32_t *version, char *message, size_t message_size);
int switch2_ce_enumerate(const char *root, const char *legacy, switch2_ce_map_callback callback,
	void *ctx, char *message, size_t message_size);
int switch2_ce_prepare_directory(const char *root, char *message, size_t message_size);

#endif
