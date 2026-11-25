/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SWITCH2_GAMEDATA_H
#define SWITCH2_GAMEDATA_H

#include <stddef.h>
#include <stdint.h>

enum switch2_gamedata_status
{
	SWITCH2_GAMEDATA_OK,
	SWITCH2_GAMEDATA_NO_IMAGE,
	SWITCH2_GAMEDATA_MISSING_UI_MAP,
	SWITCH2_GAMEDATA_INVALID_IMAGE,
	SWITCH2_GAMEDATA_INSUFFICIENT_SPACE,
	SWITCH2_GAMEDATA_IO_ERROR
};

typedef void (*switch2_gamedata_progress)(void *, int, int, const char *, uint64_t, uint64_t);

int switch2_gamedata_prepare(const char *root, const char *legacy, uint64_t free_bytes_override,
	switch2_gamedata_progress progress, void *ctx, char *message, size_t message_size);

int switch2_gamedata_prepare_limited(const char *root, const char *legacy, uint64_t free_bytes_override,
	uint64_t max_copy_bytes, switch2_gamedata_progress progress, void *ctx, char *message, size_t message_size);

#endif
