/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "switch2_input.h"
#include <math.h>

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
	unsigned player, wireless;
	uint32_t previous[SWITCH2_LOCAL_PLAYER_COUNT];
	int available;

	for (player = 0; player < SWITCH2_LOCAL_PLAYER_COUNT; player++)
		previous[player] = slots->active[player];
	available = handheld_connected;
	for (player = 0; player < SWITCH2_NPAD_COUNT; player++)
		available |= wireless_connected[player] != 0;

	if (slots->active[0] == SWITCH2_NPAD_INVALID ||
		(slots->active[0] == SWITCH2_NPAD_HANDHELD && !handheld_connected) ||
		(slots->active[0] < SWITCH2_NPAD_COUNT && !wireless_connected[slots->active[0]])) {
		slots->active[0] = SWITCH2_NPAD_INVALID;
		if (slots->preferred[0] == SWITCH2_NPAD_HANDHELD && handheld_connected)
			slots->active[0] = SWITCH2_NPAD_HANDHELD;
		else if (slots->preferred[0] < SWITCH2_NPAD_COUNT &&
			wireless_connected[slots->preferred[0]]) {
			int reserved = 0;
			for (player = 1; player < SWITCH2_LOCAL_PLAYER_COUNT; player++)
				reserved |= previous[player] == slots->preferred[0];
			if (!reserved)
				slots->active[0] = slots->preferred[0];
		}
		if (slots->active[0] == SWITCH2_NPAD_INVALID && handheld_connected)
			slots->active[0] = SWITCH2_NPAD_HANDHELD;
		if (slots->active[0] == SWITCH2_NPAD_INVALID)
			for (player = 0; player < SWITCH2_NPAD_COUNT; player++) {
				unsigned other;
				int reserved = 0;
				for (other = 1; other < SWITCH2_LOCAL_PLAYER_COUNT; other++)
					reserved |= previous[other] == player;
				if (wireless_connected[player] && !reserved) {
					slots->active[0] = player;
					break;
				}
			}
		if (!available)
			slots->active[0] = SWITCH2_NPAD_INVALID;
	}
	if (slots->active[0] != SWITCH2_NPAD_INVALID)
		slots->preferred[0] = slots->active[0];

	/* Fill the remaining local-player slots with each connected wireless
	controller exactly once.  A wireless controller currently driving player
	zero is reserved, so player zero and player one cannot cross-talk. */
	for (player = 1; player < SWITCH2_LOCAL_PLAYER_COUNT; player++)
		if (previous[player] < SWITCH2_NPAD_COUNT &&
			wireless_connected[previous[player]])
			slots->active[player] = previous[player];
		else
			slots->active[player] = SWITCH2_NPAD_INVALID;
	for (player = SWITCH2_LOCAL_PLAYER_COUNT; player <= SWITCH2_NPAD_COUNT; player++)
		slots->active[player] = SWITCH2_NPAD_INVALID;
	for (player = 1; player < SWITCH2_LOCAL_PLAYER_COUNT; player++)
		if (slots->active[player] == slots->active[0])
			slots->active[player] = SWITCH2_NPAD_INVALID;
	for (wireless = 0; wireless < SWITCH2_NPAD_COUNT; wireless++) {
		int assigned = 0;
		unsigned existing, empty = SWITCH2_LOCAL_PLAYER_COUNT;
		for (existing = 0; existing < SWITCH2_LOCAL_PLAYER_COUNT; existing++)
			if (slots->active[existing] == wireless)
				assigned = 1;
		for (existing = 1; existing < SWITCH2_LOCAL_PLAYER_COUNT; existing++)
			if (slots->active[existing] == SWITCH2_NPAD_INVALID) {
				empty = existing;
				break;
			}
		if (wireless_connected[wireless] && !assigned &&
			empty < SWITCH2_LOCAL_PLAYER_COUNT)
			slots->active[empty] = wireless;
	}
	for (player = SWITCH2_LOCAL_PLAYER_COUNT; player <= SWITCH2_NPAD_COUNT; player++)
		slots->preferred[player] = SWITCH2_NPAD_INVALID;
	for (player = 1; player < SWITCH2_LOCAL_PLAYER_COUNT; player++)
		if (slots->active[player] != SWITCH2_NPAD_INVALID)
			slots->preferred[player] = slots->active[player];
	for (; player <= SWITCH2_NPAD_COUNT; player++)
		slots->preferred[player] = SWITCH2_NPAD_INVALID;
}

uint32_t switch2_slot_npad(const struct switch2_controller_slots *slots, unsigned player)
{
	return player < SWITCH2_LOCAL_PLAYER_COUNT ? slots->active[player] : SWITCH2_NPAD_INVALID;
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

int switch2_gyro_pair_sensor(unsigned connected, unsigned mouse_tracking)
{
	unsigned available = connected & ~mouse_tracking;

	if (available & SWITCH2_JOYCON_RIGHT)
		return 1;
	return available & SWITCH2_JOYCON_LEFT ? 0 : -1;
}

void switch2_gyro_add(enum switch2_gyro_orientation orientation, int connected,
	const float rate[3], const float gravity[3], uint64_t delta_ns, float *yaw, float *pitch)
{
	const float radians_per_turn = 6.283185307f;
	const float noise_rad_per_second = 0.01f;
	const int pitch_axis = orientation == SWITCH2_GYRO_NORMAL ? 0 : 1;
	const int turn_axis = 1 - pitch_axis;
	float gravity_length, turn_rate, pitch_rate, seconds;

	if (!connected || !delta_ns || delta_ns > 100000000ULL)
		return;

	/* Player-space turn (JoyShockMapper): use gravity to combine the two
	 * non-pitch axes. A flat and an upright controller can both turn. */
	gravity_length = sqrtf(gravity[0] * gravity[0] + gravity[1] * gravity[1] + gravity[2] * gravity[2]);
	turn_rate = 0.0f;
	if (gravity_length > 0.0f) {
		float along_gravity = (rate[turn_axis] * gravity[turn_axis] + rate[2] * gravity[2]) / gravity_length;
		float turn_magnitude = sqrtf(rate[turn_axis] * rate[turn_axis] + rate[2] * rate[2]);
		turn_rate = -copysignf(fminf(fabsf(along_gravity) * 1.41421356f, turn_magnitude), along_gravity);
	}
	pitch_rate = orientation == SWITCH2_GYRO_RIGHT ? -rate[pitch_axis] : rate[pitch_axis];

	/* HID reports turns per second. Halo's facing deltas are radians. */
	turn_rate *= radians_per_turn;
	pitch_rate *= radians_per_turn;
	seconds = (float)delta_ns * 1.0e-9f;
	if (fabsf(turn_rate) >= noise_rad_per_second)
		*yaw += turn_rate * seconds;
	if (fabsf(pitch_rate) >= noise_rad_per_second)
		*pitch += pitch_rate * seconds;
}

void switch2_gyro_recenter_poll(struct switch2_gyro_recenter *button, int active, int down, uint64_t now)
{
	if (!active) {
		*button = (struct switch2_gyro_recenter){ .down = down };
		return;
	}
	if (down && !button->down) {
		button->pressed_at = now;
		button->tracking = 1;
	}
	if (!down && button->down) {
		if (button->tracking && now - button->pressed_at < 250)
			button->level_view = 1;
		button->tracking = 0;
	}
	/* Drop samples queued through the release poll as well. */
	button->discard_motion |= down || button->down;
	button->down = down;
}
