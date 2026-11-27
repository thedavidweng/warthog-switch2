/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "switch2_splitscreen.h"

#include <string.h>

static struct switch2_present_route present_route;
static int present_route_set;
static unsigned active_viewports = 1;
static struct switch2_splitscreen_stats stats;

static unsigned clamp_players(unsigned players)
{
	return players < 1 ? 1 : players > SWITCH2_SPLITSCREEN_MAX_PLAYERS ?
		SWITCH2_SPLITSCREEN_MAX_PLAYERS : players;
}

static uint32_t end_coordinate(uint32_t start, uint32_t size, uint32_t limit)
{
	uint64_t end = (uint64_t)start + size;
	return end > limit ? limit : (uint32_t)end;
}

unsigned switch2_splitscreen_layout(unsigned players, uint32_t width, uint32_t height,
	enum switch2_split_orientation orientation, struct switch2_split_rect viewports[4])
{
	uint32_t half_width = width / 2, half_height = height / 2;
	players = clamp_players(players);
	memset(viewports, 0, sizeof(struct switch2_split_rect) * 4);
	if (players == 1) {
		viewports[0] = (struct switch2_split_rect){ 0, 0, width, height };
	} else if (players == 2 && orientation == SWITCH2_SPLIT_VERTICAL) {
		viewports[0] = (struct switch2_split_rect){ 0, 0, half_width, height };
		viewports[1] = (struct switch2_split_rect){ half_width, 0, width - half_width, height };
	} else if (players == 2) {
		viewports[0] = (struct switch2_split_rect){ 0, 0, width, half_height };
		viewports[1] = (struct switch2_split_rect){ 0, half_height, width, height - half_height };
	} else if (players == 3) {
		viewports[0] = (struct switch2_split_rect){ 0, 0, half_width, half_height };
		viewports[1] = (struct switch2_split_rect){ half_width, 0, width - half_width, half_height };
		viewports[2] = (struct switch2_split_rect){ 0, half_height, width, height - half_height };
	} else {
		viewports[0] = (struct switch2_split_rect){ 0, 0, half_width, half_height };
		viewports[1] = (struct switch2_split_rect){ half_width, 0, width - half_width, half_height };
		viewports[2] = (struct switch2_split_rect){ 0, half_height, half_width, height - half_height };
		viewports[3] = (struct switch2_split_rect){ half_width, half_height, width - half_width, height - half_height };
	}
	return players;
}

struct switch2_split_rect switch2_splitscreen_clamp(struct switch2_split_rect rectangle,
	uint32_t width, uint32_t height)
{
	uint32_t right = end_coordinate(rectangle.x, rectangle.width, width);
	uint32_t bottom = end_coordinate(rectangle.y, rectangle.height, height);
	if (rectangle.x > width) rectangle.x = width;
	if (rectangle.y > height) rectangle.y = height;
	rectangle.width = right > rectangle.x ? right - rectangle.x : 0;
	rectangle.height = bottom > rectangle.y ? bottom - rectangle.y : 0;
	return rectangle;
}

struct switch2_split_rect switch2_splitscreen_confine(struct switch2_split_rect rectangle,
	struct switch2_split_rect viewport)
{
	uint32_t right = end_coordinate(rectangle.x, rectangle.width, UINT32_MAX);
	uint32_t bottom = end_coordinate(rectangle.y, rectangle.height, UINT32_MAX);
	uint32_t viewport_right = end_coordinate(viewport.x, viewport.width, UINT32_MAX);
	uint32_t viewport_bottom = end_coordinate(viewport.y, viewport.height, UINT32_MAX);
	if (rectangle.x < viewport.x) rectangle.x = viewport.x;
	if (rectangle.y < viewport.y) rectangle.y = viewport.y;
	if (right > viewport_right) right = viewport_right;
	if (bottom > viewport_bottom) bottom = viewport_bottom;
	rectangle.width = right > rectangle.x ? right - rectangle.x : 0;
	rectangle.height = bottom > rectangle.y ? bottom - rectangle.y : 0;
	return rectangle;
}

void switch2_splitscreen_present_route(struct switch2_present_route *route,
	uint32_t width, uint32_t height)
{
	route->surface = SWITCH2_OUTPUT_PRIMARY;
	route->destination = (struct switch2_split_rect){ 0, 0, width, height };
}

void switch2_splitscreen_set_present_route(const struct switch2_present_route *route)
{
	present_route = *route;
	present_route_set = 1;
}

void switch2_splitscreen_get_present_route(struct switch2_present_route *route,
	uint32_t width, uint32_t height)
{
	if (!present_route_set)
		switch2_splitscreen_present_route(route, width, height);
	else
		*route = present_route;
}

void switch2_splitscreen_set_active_viewports(unsigned count)
{
	active_viewports = clamp_players(count);
}

unsigned switch2_splitscreen_active_viewports(void)
{
	return active_viewports;
}

void switch2_splitscreen_record_frame(unsigned count, uint64_t frame_ns)
{
	count = clamp_players(count);
	active_viewports = count;
	stats.active_viewports = count;
	stats.frames++;
	stats.total_ns += frame_ns;
	stats.last_ns = frame_ns;
	if (frame_ns > stats.maximum_ns)
		stats.maximum_ns = frame_ns;
}

void switch2_splitscreen_get_stats(struct switch2_splitscreen_stats *out)
{
	*out = stats;
}

/* Upstream pause-menu behaviour is match-scoped: LEAVE GAME leaves the
whole local match, including every split-screen player. */
int switch2_splitscreen_pause_leave_match(unsigned active)
{
	(void)active;
	return 1;
}
