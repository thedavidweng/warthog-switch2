/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "switch2_text_nmouse.h"

#include <string.h>

static uint32_t nmouse_suppression[4];

#if defined(__SWITCH2__)
#include <SDL3/SDL.h>
#include <switch.h>
#include <switch/applets/swkbd.h>
#include <switch2/services/nmouse.h>

static struct switch2_nmouse_processor nmouse_processor;
static HidNmouseHandle nmouse_handle;
static int nmouse_ready;
static int keyboard_ready;
static int mouse_ready;
static char text_input_buffers[32][1024];
static unsigned text_input_buffer;

static void push_key(uint16_t scancode, int down)
{
	SDL_Event event;
	memset(&event, 0, sizeof(event));
	event.type = down ? SDL_EVENT_KEY_DOWN : SDL_EVENT_KEY_UP;
	event.key.scancode = (SDL_Scancode)scancode;
	event.key.key = SDL_GetKeyFromScancode(event.key.scancode, 0, down);
	event.key.down = down;
	SDL_PushEvent(&event);
}

static void push_mouse_motion(int xrel, int yrel)
{
	SDL_Event event;
	memset(&event, 0, sizeof(event));
	event.type = SDL_EVENT_MOUSE_MOTION;
	event.motion.xrel = (float)xrel;
	event.motion.yrel = (float)yrel;
	SDL_PushEvent(&event);
}

static void push_mouse_button(uint8_t button, int down)
{
	SDL_Event event;
	memset(&event, 0, sizeof(event));
	event.type = down ? SDL_EVENT_MOUSE_BUTTON_DOWN : SDL_EVENT_MOUSE_BUTTON_UP;
	event.button.button = button;
	event.button.down = down;
	SDL_PushEvent(&event);
}

static SwkbdTextCheckResult switch2_swkbd_text_check(char *text, size_t size)
{
	switch2_utf8_truncate(text, size);
	return SwkbdTextCheckResult_OK;
}

static int show_swkbd(int password)
{
	SwkbdConfig config;
	char text[1024];
	Result rc;

	memset(text, 0, sizeof(text));
	rc = swkbdCreate(&config, 0);
	if (R_FAILED(rc))
		return 0;
	if (password)
		swkbdConfigMakePresetPassword(&config);
	else
		swkbdConfigMakePresetDefault(&config);
	swkbdConfigSetStringLenMax(&config, sizeof(text) - 1);
	swkbdConfigSetTextCheckCallback(&config, switch2_swkbd_text_check);
	rc = swkbdShow(&config, text, sizeof(text));
	swkbdClose(&config);
	if (R_FAILED(rc))
		return 1;
	switch2_utf8_truncate(text, sizeof(text) - 1);
	if (text[0]) {
		SDL_Event event;
		char *buffer = text_input_buffers[text_input_buffer++ % 32];
		memset(&event, 0, sizeof(event));
		event.type = SDL_EVENT_TEXT_INPUT;
		strncpy(buffer, text, sizeof(text_input_buffers[0]) - 1);
		buffer[sizeof(text_input_buffers[0]) - 1] = 0;
		event.text.text = buffer;
		SDL_PushEvent(&event);
	}
	push_key(SDL_SCANCODE_RETURN, 1);
	push_key(SDL_SCANCODE_RETURN, 0);
	return 1;
}

void switch2_text_nmouse_start(void)
{
	hidInitializeKeyboard();
	hidInitializeMouse();
	keyboard_ready = mouse_ready = 1;
	switch2_nmouse_processor_init(&nmouse_processor);
	if (R_SUCCEEDED(hidInitializeNmouse(NULL, 0, 1920, 1080,
			HidNmousePointerType_Default))) {
		hidSetMergedNmouseSourceTypes(HidNmouseType_JoyLeft |
			HidNmouseType_JoyRight | HidNmouseType_StandardMouse);
		nmouse_ready = R_SUCCEEDED(hidGetMergedNmouseHandle(&nmouse_handle));
	}
}

void switch2_text_nmouse_stop(void)
{
	struct switch2_nmouse_motion motion;
	if (nmouse_ready) {
		switch2_nmouse_disconnect(&nmouse_processor, &motion);
		if (motion.button_released & HidMouseButton_Left)
			push_mouse_button(SDL_BUTTON_LEFT, 0);
		if (motion.button_released & HidMouseButton_Right)
			push_mouse_button(SDL_BUTTON_RIGHT, 0);
		hidFinalizeNmouse();
		nmouse_ready = 0;
		memset(nmouse_suppression, 0, sizeof(nmouse_suppression));
	}
	keyboard_ready = mouse_ready = 0;
}

void switch2_text_nmouse_poll(void)
{
	HidKeyboardState keys[17];
	HidMouseState mice[17];
	HidNmouseStateWithDelta nmouse[16];
	size_t count;
	struct switch2_nmouse_motion motion;
	unsigned i, key;
	static uint64_t previous_keys;
	static uint64_t previous_mouse;

	if (keyboard_ready) {
		count = hidGetKeyboardStates(keys, 17);
		for (i = 0; i < count; ++i) {
			if (keys[i].sampling_number <= previous_keys)
				continue;
			previous_keys = keys[i].sampling_number;
			for (key = 0; key < 256; ++key) {
				int old = i ? hidKeyboardStateGetKey(&keys[i - 1], key) : 0;
				int now = hidKeyboardStateGetKey(&keys[i], key);
				if (old != now)
					push_key((uint16_t)key, now);
			}
		}
	}
	if (mouse_ready) {
		count = hidGetMouseStates(mice, 17);
		for (i = 0; i < count; ++i) {
			if (mice[i].sampling_number <= previous_mouse)
				continue;
			previous_mouse = mice[i].sampling_number;
			push_mouse_motion(mice[i].delta_x, mice[i].delta_y);
			if (i && ((mice[i].buttons ^ mice[i - 1].buttons) &
					HidMouseButton_Left))
				push_mouse_button(SDL_BUTTON_LEFT,
					!!(mice[i].buttons & HidMouseButton_Left));
			if (i && ((mice[i].buttons ^ mice[i - 1].buttons) &
					HidMouseButton_Right))
				push_mouse_button(SDL_BUTTON_RIGHT,
					!!(mice[i].buttons & HidMouseButton_Right));
		}
	}
	if (nmouse_ready) {
		{
			size_t total = 0;
			count = hidGetNmouseStatesWithDelta(nmouse_handle, nmouse, 16, &total);
			if (count > total)
				count = total;
		}
		for (i = count; i > 0; --i) {
			if (!switch2_nmouse_process(&nmouse_processor,
					nmouse[i - 1].sampling_number,
					nmouse[i - 1].delta_x, nmouse[i - 1].delta_y,
					nmouse[i - 1].buttons, &motion))
				continue;
			nmouse_suppression[0] =
				(motion.buttons & HidMouseButton_Left ? 3u : 0u) |
				(motion.buttons & HidMouseButton_Right ? 12u : 0u);
			if (motion.xrel || motion.yrel)
				push_mouse_motion(motion.xrel, motion.yrel);
			if (motion.button_pressed & HidMouseButton_Left)
				push_mouse_button(SDL_BUTTON_LEFT, 1);
			if (motion.button_released & HidMouseButton_Left)
				push_mouse_button(SDL_BUTTON_LEFT, 0);
			if (motion.button_pressed & HidMouseButton_Right)
				push_mouse_button(SDL_BUTTON_RIGHT, 1);
			if (motion.button_released & HidMouseButton_Right)
				push_mouse_button(SDL_BUTTON_RIGHT, 0);
		}
	}
}

int switch2_swkbd_prompt(int password)
{
	return show_swkbd(password);
}

#endif

void switch2_nmouse_processor_init(struct switch2_nmouse_processor *p)
{
	memset(p, 0, sizeof(*p));
	p->settings.sensitivity_x = 1.0f;
	p->settings.sensitivity_y = 1.0f;
}

int switch2_nmouse_process(struct switch2_nmouse_processor *p,
	uint64_t sample, int dx, int dy, uint32_t buttons,
	struct switch2_nmouse_motion *out)
{
	if (p->have_sampling && sample <= p->last_sampling)
		return 0;
	p->have_sampling = 1;
	p->last_sampling = sample;
	out->xrel = (int)(dx * p->settings.sensitivity_x *
		(p->settings.invert_x ? -1.0f : 1.0f));
	out->yrel = (int)(dy * p->settings.sensitivity_y *
		(p->settings.invert_y ? -1.0f : 1.0f));
	out->buttons = buttons;
	out->button_pressed = buttons & ~p->buttons;
	out->button_released = p->buttons & ~buttons;
	p->buttons = buttons;
	return 1;
}

void switch2_nmouse_disconnect(struct switch2_nmouse_processor *p,
	struct switch2_nmouse_motion *out)
{
	out->xrel = out->yrel = 0;
	out->buttons = 0;
	out->button_pressed = 0;
	out->button_released = p->buttons;
	p->buttons = 0;
	p->have_sampling = 0;
	memset(nmouse_suppression, 0, sizeof(nmouse_suppression));
}

size_t switch2_utf8_truncate(char *text, size_t max_bytes)
{
	size_t n = 0;
	if (!text)
		return 0;
	while (text[n] && n < max_bytes) {
		unsigned char c = (unsigned char)text[n];
		size_t width = c < 0x80 ? 1 : c < 0xE0 ? 2 : c < 0xF0 ? 3 : 4;
		size_t i;
		if (c >= 0xF5 || n + width > max_bytes)
			break;
		for (i = 1; i < width; ++i)
			if (((unsigned char)text[n + i] & 0xC0) != 0x80)
				goto invalid;
		n += width;
	}
	text[n] = 0;
	return n;
invalid:
	text[0] = 0;
	return 0;
}

uint32_t switch2_nmouse_suppression_mask(const uint32_t *active,
	unsigned count, unsigned player)
{
	return active && player < count ? active[player] : 0;
}

int switch2_nmouse_suppresses_gamepad_button(unsigned player, int button)
{
	uint32_t mask = player < 4 ? nmouse_suppression[player] : 0;
	return ((button == 9 || button == 10) && (mask & 3)) ||
		((button == 11 || button == 12) && (mask & 12));
}
