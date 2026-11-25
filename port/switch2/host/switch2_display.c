#include "switch2_display.h"

static uint32_t even(uint32_t value)
{
	return value & ~1u;
}

uint32_t switch2_display_clamp_refresh(uint32_t width, uint32_t height, uint32_t requested)
{
	/* VI2 has no 120 Hz mode for output larger than 1440p. */
	if (width > 2560 || height > 1440)
		return 60;
	return requested > 60 ? 120 : 60;
}

uint32_t switch2_display_interval_hz(uint16_t numerator, uint16_t denominator)
{
	if (!numerator || !denominator)
		return 60;
	return (uint32_t)denominator / numerator;
}

void switch2_display_set_output(struct switch2_display_state *state, uint32_t width, uint32_t height,
	bool docked)
{
	if (!docked)
	{
		state->output_width = 1920;
		state->output_height = 1080;
	}
	else
	{
		state->output_width = width ? width : 1920;
		state->output_height = height ? height : 1080;
		if (state->output_width > 3840 || state->output_height > 2160)
		{
			state->output_width = 3840;
			state->output_height = 2160;
		}
	}
	state->requested_refresh = switch2_display_clamp_refresh(state->output_width, state->output_height,
		state->requested_refresh ? state->requested_refresh : 60);
	if (!state->granted_refresh)
		state->granted_refresh = 60;
}

void switch2_display_set_internal(struct switch2_display_state *state, uint32_t height)
{
	uint32_t clamped = height < 480 ? 480 : height;
	if (clamped > state->output_height)
		clamped = state->output_height;
	state->internal_height = clamped;
	state->internal_width = even(clamped * 16 / 9);
}
