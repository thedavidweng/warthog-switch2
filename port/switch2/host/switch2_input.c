/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "switch2_input.h"

void switch2_slots_init(struct switch2_controller_slots *slots)
{
	unsigned player;
	for (player = 0; player <= SWITCH2_NPAD_COUNT; player++) {
		slots->preferred[player] = SWITCH2_NPAD_INVALID;
		slots->active[player] = SWITCH2_NPAD_INVALID;
	}
	/* Player 0's logical slot starts with the console-held controller. */
	slots->preferred[0] = SWITCH2_NPAD_HANDHELD;
}

void switch2_slots_update(struct switch2_controller_slots *slots,
	int handheld_connected, const int wireless_connected[SWITCH2_NPAD_COUNT])
{
	unsigned player;
	int available;

	available = handheld_connected;
	for (player = 0; player < SWITCH2_NPAD_COUNT; player++)
		available |= wireless_connected[player] != 0;

	if (slots->active[0] == SWITCH2_NPAD_INVALID ||
		(slots->active[0] == SWITCH2_NPAD_HANDHELD && !handheld_connected) ||
		(slots->active[0] < SWITCH2_NPAD_COUNT && !wireless_connected[slots->active[0]])) {
		if (slots->preferred[0] == SWITCH2_NPAD_HANDHELD && handheld_connected)
			slots->active[0] = SWITCH2_NPAD_HANDHELD;
		else if (slots->preferred[0] < SWITCH2_NPAD_COUNT &&
			wireless_connected[slots->preferred[0]])
			slots->active[0] = slots->preferred[0];
		else if (handheld_connected)
			slots->active[0] = SWITCH2_NPAD_HANDHELD;
		else
			for (player = 0; player < SWITCH2_NPAD_COUNT; player++)
				if (wireless_connected[player]) {
					slots->active[0] = player;
					break;
				}
		if (!available)
			slots->active[0] = SWITCH2_NPAD_INVALID;
	}
	if (slots->active[0] != SWITCH2_NPAD_INVALID)
		slots->preferred[0] = slots->active[0];

	for (player = 1; player <= SWITCH2_NPAD_COUNT; player++) {
		unsigned wireless = player - 1;
		slots->active[player] = wireless_connected[wireless] ?
			wireless : SWITCH2_NPAD_INVALID;
		slots->preferred[player] = wireless;
	}
}

uint32_t switch2_slot_npad(const struct switch2_controller_slots *slots, unsigned player)
{
	return player <= SWITCH2_NPAD_COUNT ? slots->active[player] : SWITCH2_NPAD_INVALID;
}

int switch2_slot_connected(const struct switch2_controller_slots *slots, unsigned player)
{
	return switch2_slot_npad(slots, player) != SWITCH2_NPAD_INVALID;
}

void switch2_gyro_apply(const struct switch2_gyro_settings *settings, int zoomed,
	float yaw, float pitch, float *out_yaw, float *out_pitch)
{
	if (settings->mode == SWITCH2_GYRO_OFF ||
		(settings->mode == SWITCH2_GYRO_ZOOM_ONLY && !zoomed)) {
		*out_yaw = 0;
		*out_pitch = 0;
		return;
	}
	*out_yaw = (settings->invert_horizontal ? -yaw : yaw) *
		settings->sensitivity_horizontal;
	*out_pitch = (settings->invert_vertical ? -pitch : pitch) *
		settings->sensitivity_vertical;
}

uint16_t switch2_rumble_level(uint32_t level)
{
	return level > UINT16_MAX ? UINT16_MAX : (uint16_t)level;
}

void switch2_gyro_add(enum switch2_gyro_orientation orientation, int connected,
	float x, float y, uint64_t delta_ns, float *yaw, float *pitch)
{
	float seconds;
	if (!connected || !delta_ns || delta_ns > 100000000ULL)
		return;
	if (x < 0.01f && x > -0.01f) x = 0;
	if (y < 0.01f && y > -0.01f) y = 0;
	seconds = (float)delta_ns * 1.0e-9f;
	if (orientation == SWITCH2_GYRO_RIGHT) {
		*yaw -= x * seconds;
		*pitch += y * seconds;
	} else if (orientation == SWITCH2_GYRO_LEFT) {
		*yaw += x * seconds;
		*pitch -= y * seconds;
	} else {
		*yaw -= y * seconds;
		*pitch -= x * seconds;
	}
}
