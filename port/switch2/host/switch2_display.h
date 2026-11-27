/* Switch 2 display policy: pure calculations shared by the platform layer. */
/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#define SWITCH2_SIMULATION_HZ 30

struct switch2_display_state
{
	uint32_t internal_width;
	uint32_t internal_height;
	uint32_t output_width;
	uint32_t output_height;
	uint32_t requested_refresh;
	uint32_t granted_refresh;
	bool interpolation;
};

uint32_t switch2_display_clamp_refresh(uint32_t width, uint32_t height, uint32_t requested);
uint32_t switch2_display_interval_hz(uint16_t numerator, uint16_t denominator);
void switch2_display_set_output(struct switch2_display_state *state, uint32_t width, uint32_t height,
	bool docked);
void switch2_display_set_internal(struct switch2_display_state *state, uint32_t height);
