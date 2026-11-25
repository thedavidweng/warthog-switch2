/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include <stdint.h>

enum switch2_gyro_orientation {
	SWITCH2_GYRO_NORMAL,
	SWITCH2_GYRO_LEFT,
	SWITCH2_GYRO_RIGHT
};

/* libnx uses 0..3 for wireless npads and 32 for the handheld npad.  Keeping
the values here makes slot selection testable without including libnx. */
#define SWITCH2_NPAD_NO1 0u
#define SWITCH2_NPAD_COUNT 4u
#define SWITCH2_NPAD_HANDHELD 32u
#define SWITCH2_NPAD_INVALID UINT32_MAX
#define SWITCH2_LOCAL_PLAYER_COUNT 4u

struct switch2_controller_slots {
	uint32_t preferred[SWITCH2_NPAD_COUNT + 1];
	uint32_t active[SWITCH2_NPAD_COUNT + 1];
};

void switch2_slots_init(struct switch2_controller_slots *slots);
void switch2_slots_update(struct switch2_controller_slots *slots,
	int handheld_connected, const int wireless_connected[SWITCH2_NPAD_COUNT]);
uint32_t switch2_slot_npad(const struct switch2_controller_slots *slots, unsigned player);
int switch2_slot_connected(const struct switch2_controller_slots *slots, unsigned player);

enum switch2_gyro_mode {
	SWITCH2_GYRO_OFF,
	SWITCH2_GYRO_ALWAYS,
	SWITCH2_GYRO_ZOOM_ONLY
};

struct switch2_gyro_settings {
	enum switch2_gyro_mode mode;
	float sensitivity_horizontal;
	float sensitivity_vertical;
	int invert_horizontal;
	int invert_vertical;
};

void switch2_gyro_apply(const struct switch2_gyro_settings *settings, int zoomed,
	float yaw, float pitch, float *out_yaw, float *out_pitch);
uint16_t switch2_rumble_level(uint32_t level);

void switch2_gyro_add(enum switch2_gyro_orientation orientation, int connected,
	float x, float y, uint64_t delta_ns, float *yaw, float *pitch);
