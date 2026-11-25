/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once

#include <stdbool.h>
#include <stdint.h>

/* Conservative startup floor; this is not a guarantee of successful allocation. */
#define SWITCH2_MIN_AVAILABLE_MEMORY (512ULL * 1024 * 1024)

static inline bool switch2_lifecycle_refuse_launch(bool restricted, uint64_t available)
{
	return restricted || available < SWITCH2_MIN_AVAILABLE_MEMORY;
}

static inline bool switch2_lifecycle_size_changed(uint32_t width, uint32_t height,
	uint32_t previous_width, uint32_t previous_height)
{
	return width != previous_width || height != previous_height;
}
