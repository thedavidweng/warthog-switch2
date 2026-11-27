/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once

#include <stddef.h>
#include <stdint.h>

#define SWITCH2_NMOUSE_DEVICE_ID 0x4E4D5332u

enum switch2_nmouse_mode {
	SWITCH2_NMOUSE_OFF = 0,
	SWITCH2_NMOUSE_AUTO = 1,
	SWITCH2_NMOUSE_RIGHT = 2,
	SWITCH2_NMOUSE_LEFT = 3,
	SWITCH2_NMOUSE_BOTH = 4
};

struct switch2_nmouse_settings {
	float sensitivity_x;
	float sensitivity_y;
	int invert_x;
	int invert_y;
};

struct switch2_nmouse_motion {
	int xrel;
	int yrel;
	uint32_t buttons;
	uint32_t button_pressed;
	uint32_t button_released;
};

struct switch2_nmouse_processor {
	uint64_t last_sampling;
	int have_sampling;
	uint32_t buttons;
	struct switch2_nmouse_settings settings;
};

void switch2_nmouse_processor_init(struct switch2_nmouse_processor *processor);
int switch2_nmouse_process(struct switch2_nmouse_processor *processor,
	uint64_t sampling_number, int delta_x, int delta_y, uint32_t buttons,
	struct switch2_nmouse_motion *motion);
int switch2_nmouse_process_accum(struct switch2_nmouse_processor *processor,
	uint64_t sampling_number, int delta_x, int delta_y, uint32_t buttons,
	int mode, float *accum_x, float *accum_y,
	struct switch2_nmouse_motion *motion);
void switch2_nmouse_disconnect(struct switch2_nmouse_processor *processor,
	struct switch2_nmouse_motion *motion);
void switch2_text_nmouse_configure(int mode, float sensitivity_x, float sensitivity_y, int invert_y);

/* Truncate at most max_bytes UTF-8 bytes, always leaving a valid string. */
size_t switch2_utf8_truncate(char *text, size_t max_bytes);
void switch2_text_nmouse_start(void);
void switch2_text_nmouse_stop(void);
void switch2_text_nmouse_poll(void);
unsigned switch2_nmouse_tracking_joycons(unsigned npad);
int switch2_swkbd_prompt(int password);

/* One mask per logical player; bits are L/ZL/R/ZR in that order. */
uint32_t switch2_nmouse_suppression_mask(const uint32_t *active_buttons,
	unsigned player_count, unsigned player);
int switch2_nmouse_suppresses_gamepad_button(unsigned player, int button);
