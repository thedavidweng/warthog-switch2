/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once

#include <stdint.h>

#define SWITCH2_SPLITSCREEN_MAX_PLAYERS 4u

struct switch2_split_rect {
	uint32_t x, y, width, height;
};

enum switch2_split_orientation {
	SWITCH2_SPLIT_HORIZONTAL,
	SWITCH2_SPLIT_VERTICAL
};

enum switch2_output_surface {
	SWITCH2_OUTPUT_PRIMARY = 0,
	SWITCH2_OUTPUT_SECONDARY = 1
};

struct switch2_present_route {
	enum switch2_output_surface surface;
	struct switch2_split_rect destination;
};

struct switch2_splitscreen_stats {
	uint32_t active_viewports;
	uint64_t frames;
	uint64_t total_ns;
	uint64_t last_ns;
	uint64_t maximum_ns;
};

unsigned switch2_splitscreen_layout(unsigned players, uint32_t width, uint32_t height,
	enum switch2_split_orientation orientation, struct switch2_split_rect viewports[4]);
struct switch2_split_rect switch2_splitscreen_clamp(struct switch2_split_rect rectangle,
	uint32_t width, uint32_t height);
struct switch2_split_rect switch2_splitscreen_confine(struct switch2_split_rect rectangle,
	struct switch2_split_rect viewport);
void switch2_splitscreen_present_route(struct switch2_present_route *route,
	uint32_t width, uint32_t height);
void switch2_splitscreen_set_present_route(const struct switch2_present_route *route);
void switch2_splitscreen_get_present_route(struct switch2_present_route *route,
	uint32_t width, uint32_t height);
void switch2_splitscreen_set_active_viewports(unsigned count);
unsigned switch2_splitscreen_active_viewports(void);
void switch2_splitscreen_record_frame(unsigned active_viewports, uint64_t frame_ns);
void switch2_splitscreen_get_stats(struct switch2_splitscreen_stats *stats);
int switch2_splitscreen_pause_leave_match(unsigned active_viewports);
