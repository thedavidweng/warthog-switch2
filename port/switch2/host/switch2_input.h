/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once
#include <stdint.h>

enum switch2_gyro_orientation {
	SWITCH2_GYRO_NORMAL,
	SWITCH2_GYRO_LEFT,
	SWITCH2_GYRO_RIGHT
};

enum switch2_joycon_side {
	SWITCH2_JOYCON_LEFT = 1u << 0,
	SWITCH2_JOYCON_RIGHT = 1u << 1
};

int switch2_gyro_pair_sensor(unsigned connected, unsigned mouse_tracking);

/* libnx uses 0..3 for wireless npads and 32 for the handheld npad.  Keeping
the values here makes slot selection testable without including libnx. */
#define SWITCH2_NPAD_NO1 0u
#define SWITCH2_NPAD_COUNT 4u
#define SWITCH2_NPAD_HANDHELD 32u
#define SWITCH2_NPAD_INVALID UINT32_MAX
#define SWITCH2_LOCAL_PLAYER_COUNT 4u

struct switch2_controller_slots {
	uint32_t preferred_primary;
	uint32_t active[SWITCH2_LOCAL_PLAYER_COUNT];
};

void switch2_slots_init(struct switch2_controller_slots *slots);
void switch2_slots_update(struct switch2_controller_slots *slots,
	int handheld_connected, const int wireless_connected[SWITCH2_NPAD_COUNT]);
uint32_t switch2_slot_npad(const struct switch2_controller_slots *slots, unsigned player);
int switch2_slot_connected(const struct switch2_controller_slots *slots, unsigned player);

uint16_t switch2_rumble_level(uint32_t level);

void switch2_gyro_add(enum switch2_gyro_orientation orientation, int connected,
	const float rate[3], const float gravity[3], uint64_t delta_ns, float *yaw, float *pitch);

struct switch2_gyro_recenter {
	uint64_t pressed_at;
	int down;
	int tracking;
	int discard_motion;
	int level_view;
};

void switch2_gyro_recenter_poll(struct switch2_gyro_recenter *button, int active, int down, uint64_t now);
