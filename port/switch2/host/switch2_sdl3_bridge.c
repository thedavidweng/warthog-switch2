/*
GUEST_SDL.C

The SDL3 functions the platform layer calls (sdl_platform.c, xinput_sdl.c,
dsound_sdl.c), for the guest. SDL itself runs in the host; objects it
returns (windows, contexts, gamepads, audio streams) are 64-bit pointers
there, so the guest only ever sees small integer handles that the host maps
back (host_sdl.c). Events are written by SDL straight into the guest's
buffer: SDL_Event has the same 128-byte layout in both ABIs for every event
type that carries no pointer, which covers all the platform layer reads.
*/

/* before SDL: musl's alloca.h must come first */
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <strings.h>
#include <pthread.h>
#include <SDL3/SDL.h>
#include "nx2_platform.h"
#include "nx2_gameshare.h"
#include "switch2_gameshare.h"
#include "switch2_input.h"
#include "switch2_text_nmouse.h"

int host_sdl_init(unsigned int flags);
int host_sdl_set_hint(const char *name, const char *value);
void host_sdl_get_error(char *buffer, unsigned int size);
long long host_sdl_ticks(void);
long long host_sdl_thread_id(void);
unsigned int host_sdl_create_window(const char *title, int width, int height, long long flags);
void host_sdl_window_size_in_pixels(unsigned int window, int *width, int *height);
int host_sdl_set_relative_mouse(unsigned int window, int enabled);
int host_sdl_gl_set_attribute(int attribute, int value);
unsigned int host_sdl_gl_create_context(unsigned int window);
int host_sdl_gl_make_current(unsigned int window, unsigned int context);
int host_sdl_gl_set_swap_interval(int interval);
int host_sdl_gl_swap_window(unsigned int window);
int host_sdl_poll_event(void *event);
int host_sdl_set_clipboard_text(const char *text);
void host_sdl_get_clipboard_text(char *buffer, unsigned int size);
/* the keyboard's keys by name (the controls' bindings, xinput_sdl.c) */
void host_sdl_scancode_name(int scancode, char *buffer, unsigned int size);
int host_sdl_scancode_from_name(const char *name);
int host_sdl_show_toast(const char *message, int duration, int gravity, int x, int y);
int host_sdl_show_simple_message_box(unsigned int flags, const char *title, const char *message);
int host_sdl_show_message_box(unsigned int flags, const char *title, const char *message, int count,
	const unsigned int *button_flags, const int *button_ids, const uintptr_t *button_texts);
int host_sdl_open_url(const char *url);
int host_sdl_get_gamepads(unsigned int *ids, int capacity);
unsigned int host_sdl_open_gamepad(unsigned int id);
unsigned int host_sdl_gamepad_from_id(unsigned int id);
int host_sdl_gamepad_axis(unsigned int gamepad, int axis);
int host_sdl_gamepad_button(unsigned int gamepad, int button);
int host_sdl_gamepad_type(unsigned int gamepad);
const char *host_sdl_gamepad_name(unsigned int gamepad);
int host_sdl_rumble_gamepad(unsigned int gamepad, unsigned int low, unsigned int high, unsigned int milliseconds);
/* callback: void (*)(void *userdata, unsigned int stream, int additional, int total),
called on the audio thread */
unsigned int host_sdl_open_audio_stream(unsigned int device, const void *spec, uintptr_t callback, uintptr_t userdata);
int host_sdl_put_audio_stream_data(unsigned int stream, const void *data, int length);
int host_sdl_resume_audio_stream_device(unsigned int stream);
void host_sdl_quit(void);
void host_sdl_close_gamepad(unsigned int gamepad);

static bool relative_mouse;
static pthread_mutex_t event_lock = PTHREAD_MUTEX_INITIALIZER;
static SDL_Event event_queue[32];
static unsigned event_read, event_count;

static AppletHookCookie lifecycle_cookie;
static bool lifecycle_hooked, lifecycle_exit, lifecycle_quit_sent;
static struct switch2_controller_slots controller_slots;
static Nx2GameShareInput gameshare_input;
static bool gameshare_guest_connected;

#define SWITCH2_GAMESHARE_GAMEPAD_ID 0x47530001u

static void gameshare_poll(void)
{
	bool connected;
	SDL_Event event;
	unsigned int ids[16];
	int count = host_sdl_get_gamepads(ids, 16);
	int wireless[SWITCH2_NPAD_COUNT] = { 0, 0, 0, 0 };

	for (int i = 0; i < count && i < (int)SWITCH2_NPAD_COUNT; i++)
		wireless[i] = 1;
	switch2_slots_update(&controller_slots, 0, wireless);
	switch2_gameshare_update();
	connected = switch2_gameshare_active();
	if (connected)
		(void)switch2_gameshare_guest_input(&gameshare_input);
	if (connected == gameshare_guest_connected)
		return;
	gameshare_guest_connected = connected;
	event.type = connected ? SDL_EVENT_GAMEPAD_ADDED : SDL_EVENT_GAMEPAD_REMOVED;
	event.gdevice.which = SWITCH2_GAMESHARE_GAMEPAD_ID;
	SDL_PushEvent(&event);
}

static void lifecycle_hook(AppletHookType type, void *unused)
{
	(void)unused;
	if (type == AppletHookType_OnExitRequest)
		lifecycle_exit = true;
}

void switch2_lifecycle_start(void)
{
	if (!lifecycle_hooked) {
		appletHook(&lifecycle_cookie, lifecycle_hook, NULL);
		lifecycle_hooked = true;
	}
}

void switch2_lifecycle_stop(void)
{
	if (lifecycle_hooked) {
		appletUnhook(&lifecycle_cookie);
		lifecycle_hooked = false;
	}
}

bool SDL_Init(SDL_InitFlags flags)
{
	bool ok = host_sdl_init(flags) != 0;
	if (ok) {
		switch2_slots_init(&controller_slots);
		switch2_text_nmouse_start();
	}
	return ok;
}

bool SDL_StartTextInput(SDL_Window *window)
{
	(void)window;
	return switch2_swkbd_prompt(0) != 0;
}

bool SDL_StartTextInputWithProperties(SDL_Window *window, SDL_PropertiesID props)
{
	SDL_TextInputType type;
	(void)window;
	type = (SDL_TextInputType)SDL_GetNumberProperty(props,
		SDL_PROP_TEXTINPUT_TYPE_NUMBER, SDL_TEXTINPUT_TYPE_TEXT);
	return switch2_swkbd_prompt(type == SDL_TEXTINPUT_TYPE_TEXT_PASSWORD_HIDDEN ||
		type == SDL_TEXTINPUT_TYPE_TEXT_PASSWORD_VISIBLE) != 0;
}

bool SDL_StopTextInput(SDL_Window *window)
{
	(void)window;
	return true;
}

bool SDL_TextInputActive(SDL_Window *window)
{
	(void)window;
	return false;
}



const char *SDL_GetScancodeName(SDL_Scancode scancode)
{
	static __thread char buffer[64];

	host_sdl_scancode_name((int)scancode, buffer, sizeof(buffer));
	return buffer;
}

SDL_Scancode SDL_GetScancodeFromName(const char *name)
{
	return (SDL_Scancode)host_sdl_scancode_from_name(name);
}


SDL_ThreadID SDL_GetCurrentThreadID(void)
{
	return (SDL_ThreadID)host_sdl_thread_id();
}


/* ---------- the clipboard (internet play's invite links, sdl_platform.c) */

bool SDL_SetClipboardText(const char *text)
{
	return host_sdl_set_clipboard_text(text) != 0;
}

char *SDL_GetClipboardText(void)
{
	char buffer[1024];

	host_sdl_get_clipboard_text(buffer, sizeof(buffer));
	return strdup(buffer);
}

bool SDL_ShowAndroidToast(const char *message, int duration, int gravity, int xoffset, int yoffset)
{
	return host_sdl_show_toast(message, duration, gravity, xoffset, yoffset) != 0;
}

/* ---------- a message for the player (sdl_platform.c): the host's own window */

bool SDL_ShowSimpleMessageBox(SDL_MessageBoxFlags flags, const char *title, const char *message, SDL_Window *window)
{
	(void)window;
	return host_sdl_show_simple_message_box((unsigned int)flags, title, message) != 0;
}

bool SDL_ShowMessageBox(const SDL_MessageBoxData *data, int *answer)
{
	unsigned int flags[8];
	uintptr_t texts[8];
	int ids[8];
	int index, chosen;

	if (!data || data->numbuttons < 0 || data->numbuttons > 8)
		return false;
	for (index = 0; index < data->numbuttons; index++)
	{
		flags[index] = (unsigned int)data->buttons[index].flags;
		ids[index] = data->buttons[index].buttonID;
		texts[index] = (uintptr_t)data->buttons[index].text;
	}
	chosen = host_sdl_show_message_box((unsigned int)data->flags, data->title, data->message, data->numbuttons,
		flags, ids, texts);
	if (answer)
		*answer = chosen;
	return chosen != -1;
}

/* ---------- the web browser (the game list's profile) */

bool SDL_OpenURL(const char *url)
{
	return host_sdl_open_url(url) != 0;
}


void SDL_Delay(Uint32 milliseconds)
{
	struct timespec duration;

	duration.tv_sec = milliseconds / 1000;
	duration.tv_nsec = (long)(milliseconds % 1000) * 1000000L;
	nanosleep(&duration, NULL);
}

/* ---------- video */

SDL_Window *SDL_CreateWindow(const char *title, int width, int height, SDL_WindowFlags flags)
{
	return (SDL_Window *)(uintptr_t)host_sdl_create_window(title, width, height, (long long)flags);
}

bool SDL_GetWindowSizeInPixels(SDL_Window *window, int *width, int *height)
{
	int w = 0, h = 0;

	host_sdl_window_size_in_pixels((unsigned int)(uintptr_t)window, &w, &h);
	if (width)
		*width = w;
	if (height)
		*height = h;
	return true;
}

bool SDL_SetWindowRelativeMouseMode(SDL_Window *window, bool enabled)
{
	bool ok = host_sdl_set_relative_mouse((unsigned int)(uintptr_t)window, enabled) != 0;
	if (ok) relative_mouse = enabled;
	return ok;
}

bool SDL_GL_SetAttribute(SDL_GLAttr attribute, int value)
{
	return host_sdl_gl_set_attribute((int)attribute, value) != 0;
}

SDL_GLContext SDL_GL_CreateContext(SDL_Window *window)
{
	return (SDL_GLContext)(uintptr_t)host_sdl_gl_create_context((unsigned int)(uintptr_t)window);
}

bool SDL_GL_MakeCurrent(SDL_Window *window, SDL_GLContext context)
{
	return host_sdl_gl_make_current((unsigned int)(uintptr_t)window, (unsigned int)(uintptr_t)context) != 0;
}

bool SDL_GL_SetSwapInterval(int interval)
{
	return host_sdl_gl_set_swap_interval(interval) != 0;
}

bool SDL_GL_SwapWindow(SDL_Window *window)
{
	return host_sdl_gl_swap_window((unsigned int)(uintptr_t)window) != 0;
}


/* ---------- events */

bool SDL_PollEvent(SDL_Event *event)
{
	SDL_Event scratch;
	switch2_text_nmouse_poll();
	gameshare_poll();
	if (!appletMainLoop() && !lifecycle_quit_sent)
		lifecycle_exit = true;
	if (lifecycle_exit && !lifecycle_quit_sent) {
		SDL_Event quit = { .type = SDL_EVENT_QUIT };
		if (SDL_PushEvent(&quit)) {
			lifecycle_exit = false;
			lifecycle_quit_sent = true;
		}
	}
	if (nx2DisplayUpdate()) {
		u32 width, height;
		nx2DisplaySize(&width, &height);
		(void)nx2DisplayReapply();
		(void)nx2DisplayRefreshRate();
		SDL_Event resized = { .type = SDL_EVENT_WINDOW_RESIZED };
		resized.window.windowID = 1;
		resized.window.data1 = width;
		resized.window.data2 = height;
		SDL_PushEvent(&resized);
		resized.type = SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED;
		SDL_PushEvent(&resized);
	}
	pthread_mutex_lock(&event_lock);
	if (event_count)
	{
		if (event) *event = event_queue[event_read];
		event_read = (event_read + 1) % 32;
		event_count--;
		pthread_mutex_unlock(&event_lock);
		return true;
	}
	pthread_mutex_unlock(&event_lock);
	return host_sdl_poll_event(event ? event : &scratch) != 0;
}

/* (the dedicated server's, which has no window and never runs on Android:
SDL_PollEvent pumps the host's events itself) */
void SDL_PumpEvents(void)
{
}

int SDL_PeepEvents(SDL_Event *events, int count, SDL_EventAction action, Uint32 first, Uint32 last)
{
	(void)events;
	(void)count;
	(void)action;
	(void)first;
	(void)last;
	return 0;
}

/* ---------- gamepads */

bool SDL_HasGamepad(void)
{
	unsigned int ids[16];

	return host_sdl_get_gamepads(ids, 16) > 0 || gameshare_guest_connected;
}

SDL_JoystickID *SDL_GetGamepads(int *count)
{
	unsigned int ids[16];
	int found = host_sdl_get_gamepads(ids, 16);
	SDL_JoystickID *result = malloc((found + (gameshare_guest_connected ? 1 : 0) + 1) *
		sizeof(SDL_JoystickID));
	int index;

	if (!result)
		return NULL;
	for (index = 0; index < found; index++)
		result[index] = ids[index];
	if (gameshare_guest_connected)
		result[found++] = SWITCH2_GAMESHARE_GAMEPAD_ID;
	result[found] = 0;
	if (count)
		*count = found;
	return result;
}

SDL_Gamepad *SDL_OpenGamepad(SDL_JoystickID id)
{
	if (id == SWITCH2_GAMESHARE_GAMEPAD_ID)
		return gameshare_guest_connected ? (SDL_Gamepad *)(uintptr_t)id : NULL;
	return (SDL_Gamepad *)(uintptr_t)host_sdl_open_gamepad(id);
}

SDL_Gamepad *SDL_GetGamepadFromID(SDL_JoystickID id)
{
	if (id == SWITCH2_GAMESHARE_GAMEPAD_ID)
		return gameshare_guest_connected ? (SDL_Gamepad *)(uintptr_t)id : NULL;
	return (SDL_Gamepad *)(uintptr_t)host_sdl_gamepad_from_id(id);
}

Sint16 SDL_GetGamepadAxis(SDL_Gamepad *gamepad, SDL_GamepadAxis axis)
{
	if ((uintptr_t)gamepad == SWITCH2_GAMESHARE_GAMEPAD_ID) {
		switch (axis) {
			case SDL_GAMEPAD_AXIS_LEFTX: return (Sint16)gameshare_input.stick[0];
			case SDL_GAMEPAD_AXIS_LEFTY: return (Sint16)-gameshare_input.stick[1];
			case SDL_GAMEPAD_AXIS_RIGHTX: return (Sint16)gameshare_input.stick[2];
			case SDL_GAMEPAD_AXIS_RIGHTY: return (Sint16)-gameshare_input.stick[3];
			case SDL_GAMEPAD_AXIS_LEFT_TRIGGER:
				return (gameshare_input.buttons & HidNpadButton_ZL) ? INT16_MAX : 0;
			case SDL_GAMEPAD_AXIS_RIGHT_TRIGGER:
				return (gameshare_input.buttons & HidNpadButton_ZR) ? INT16_MAX : 0;
			default: return 0;
		}
	}
	return (Sint16)host_sdl_gamepad_axis((unsigned int)(uintptr_t)gamepad, (int)axis);
}

bool SDL_GetGamepadButton(SDL_Gamepad *gamepad, SDL_GamepadButton button)
{
	if ((uintptr_t)gamepad == SWITCH2_GAMESHARE_GAMEPAD_ID) {
		static const uint64_t buttons[] = {
			[SDL_GAMEPAD_BUTTON_SOUTH] = HidNpadButton_B,
			[SDL_GAMEPAD_BUTTON_EAST] = HidNpadButton_A,
			[SDL_GAMEPAD_BUTTON_WEST] = HidNpadButton_Y,
			[SDL_GAMEPAD_BUTTON_NORTH] = HidNpadButton_X,
			[SDL_GAMEPAD_BUTTON_BACK] = HidNpadButton_Minus,
			[SDL_GAMEPAD_BUTTON_START] = HidNpadButton_Plus,
			[SDL_GAMEPAD_BUTTON_LEFT_SHOULDER] = HidNpadButton_L,
			[SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER] = HidNpadButton_R,
			[SDL_GAMEPAD_BUTTON_DPAD_UP] = HidNpadButton_Up,
			[SDL_GAMEPAD_BUTTON_DPAD_DOWN] = HidNpadButton_Down,
			[SDL_GAMEPAD_BUTTON_DPAD_LEFT] = HidNpadButton_Left,
			[SDL_GAMEPAD_BUTTON_DPAD_RIGHT] = HidNpadButton_Right,
		};
		return button >= 0 && button < (int)(sizeof(buttons) / sizeof(buttons[0])) &&
			(gameshare_input.buttons & buttons[button]) != 0;
	}
	return host_sdl_gamepad_button((unsigned int)(uintptr_t)gamepad, (int)button) != 0;
}

SDL_GamepadType SDL_GetGamepadType(SDL_Gamepad *gamepad)
{
	if ((uintptr_t)gamepad == SWITCH2_GAMESHARE_GAMEPAD_ID)
		return SDL_GAMEPAD_TYPE_STANDARD;
	return (SDL_GamepadType)host_sdl_gamepad_type((unsigned int)(uintptr_t)gamepad);
}

bool SDL_RumbleGamepad(SDL_Gamepad *gamepad, Uint16 low, Uint16 high, Uint32 milliseconds)
{
	if ((uintptr_t)gamepad == SWITCH2_GAMESHARE_GAMEPAD_ID) {
		(void)milliseconds;
		nx2GameShareSetGuestRumble(switch2_rumble_level(low) / 65535.0f,
			switch2_rumble_level(high) / 65535.0f);
		return true;
	}
	return host_sdl_rumble_gamepad((unsigned int)(uintptr_t)gamepad, low, high, milliseconds) != 0;
}

/* ---------- audio */

/* the 32-bit build plays on the system's output alone: it lists no
outputs to choose (Audio Setup's Output Device shows only the default), so
every audio.device name falls to the default and its stream, opened once,
is never closed (dsound_sdl.c) */
SDL_AudioDeviceID *SDL_GetAudioPlaybackDevices(int *count)
{
	SDL_AudioDeviceID *result = malloc(sizeof(SDL_AudioDeviceID));

	if (result)
		result[0] = 0;
	if (count)
		*count = 0;
	return result;
}

const char *SDL_GetAudioDeviceName(SDL_AudioDeviceID device)
{
	(void)device;
	return NULL;
}

/* (no names, as above: audio.hrtf = "auto" cannot tell headphones here, and
leaves the rendering off; "on" turns it on) */
SDL_AudioDeviceID SDL_GetAudioStreamDevice(SDL_AudioStream *stream)
{
	(void)stream;
	return 0;
}

void SDL_DestroyAudioStream(SDL_AudioStream *stream)
{
	(void)stream;
}

SDL_AudioStream *SDL_OpenAudioDeviceStream(SDL_AudioDeviceID device, const SDL_AudioSpec *spec,
	SDL_AudioStreamCallback callback, void *userdata)
{
	return (SDL_AudioStream *)(uintptr_t)host_sdl_open_audio_stream(device, spec, (uintptr_t)callback,
		(uintptr_t)userdata);
}

bool SDL_PutAudioStreamData(SDL_AudioStream *stream, const void *data, int length)
{
	return host_sdl_put_audio_stream_data((unsigned int)(uintptr_t)stream, data, length) != 0;
}

bool SDL_ResumeAudioStreamDevice(SDL_AudioStream *stream)
{
	return host_sdl_resume_audio_stream_device((unsigned int)(uintptr_t)stream) != 0;
}

bool SDL_InitSubSystem(SDL_InitFlags flags) { return host_sdl_init(flags) != 0; }
void SDL_Quit(void)
{
	unsigned int ids[16];
	int count = host_sdl_get_gamepads(ids, 16);
	for (int i = 0; i < count; i++)
		host_sdl_rumble_gamepad(ids[i], switch2_rumble_level(0), switch2_rumble_level(0), 0);
	nx2GameShareSetGuestRumble(0.0f, 0.0f);
	gameshare_guest_connected = false;
	host_sdl_quit();
}
int SDL_strcasecmp(const char *a, const char *b) { return strcasecmp(a, b); }
Uint64 SDL_GetTicksNS(void)
{
	struct timespec t;
	clock_gettime(CLOCK_MONOTONIC, &t);
	return (Uint64)t.tv_sec * 1000000000ULL + (Uint64)t.tv_nsec;
}
void SDL_DelayPrecise(Uint64 ns)
{
	struct timespec t = { (time_t)(ns / 1000000000ULL), (long)(ns % 1000000000ULL) };
	nanosleep(&t, NULL);
}
int SDL_SetAtomicInt(SDL_AtomicInt *a, int v) { return __atomic_exchange_n(&a->value, v, __ATOMIC_SEQ_CST); }
int SDL_GetAtomicInt(SDL_AtomicInt *a) { return __atomic_load_n(&a->value, __ATOMIC_SEQ_CST); }

SDL_DisplayID SDL_GetPrimaryDisplay(void) { return 1; }
SDL_DisplayID SDL_GetDisplayForWindow(SDL_Window *window) { (void)window; return 1; }
const SDL_DisplayMode *SDL_GetDesktopDisplayMode(SDL_DisplayID id)
{
	static SDL_DisplayMode mode;
	int rate = switch2PlatformRefreshRate();
	u32 width, height;
	nx2DisplaySize(&width, &height);
	(void)id;
	mode.displayID = 1;
	mode.format = SDL_PIXELFORMAT_XRGB8888;
	mode.w = width; mode.h = height;
	mode.pixel_density = 1.0f;
	mode.refresh_rate = rate > 0 ? (float)rate : 60.0f;
	return &mode;
}
const SDL_DisplayMode *SDL_GetCurrentDisplayMode(SDL_DisplayID id) { return SDL_GetDesktopDisplayMode(id); }
bool SDL_GetClosestFullscreenDisplayMode(SDL_DisplayID id, int w, int h, float rate, bool density, SDL_DisplayMode *closest)
{
	(void)w; (void)h; (void)rate; (void)density;
	*closest = *SDL_GetDesktopDisplayMode(id);
	return true;
}
SDL_DisplayMode **SDL_GetFullscreenDisplayModes(SDL_DisplayID id, int *count)
{
	SDL_DisplayMode **modes = malloc(2 * sizeof(*modes));
	if (!modes) return NULL;
	modes[0] = (SDL_DisplayMode *)SDL_GetDesktopDisplayMode(id); modes[1] = NULL;
	if (count) *count = 1;
	return modes;
}
bool SDL_GetDisplayUsableBounds(SDL_DisplayID id, SDL_Rect *rect)
{
	const SDL_DisplayMode *mode = SDL_GetDesktopDisplayMode(id);
	*rect = (SDL_Rect){ 0, 0, mode->w, mode->h };
	return true;
}
bool SDL_SetWindowFullscreenMode(SDL_Window *w, const SDL_DisplayMode *m) { (void)w; (void)m; return true; }
bool SDL_SetWindowFullscreen(SDL_Window *w, bool f) { (void)w; (void)f; return true; }
bool SDL_SetWindowSize(SDL_Window *window, int w, int h) { (void)window; (void)w; (void)h; return true; }
SDL_WindowFlags SDL_GetWindowFlags(SDL_Window *w) { (void)w; return SDL_WINDOW_FULLSCREEN | SDL_WINDOW_OPENGL; }
bool SDL_GetWindowSize(SDL_Window *w, int *x, int *y) { return SDL_GetWindowSizeInPixels(w, x, y); }
SDL_WindowID SDL_GetWindowID(SDL_Window *w) { (void)w; return 1; }
SDL_Window *SDL_GetKeyboardFocus(void) { return (SDL_Window *)(uintptr_t)1; }
void SDL_GL_ResetAttributes(void) {}
bool SDL_GL_GetAttribute(SDL_GLAttr a, int *value)
{
	*value = a == SDL_GL_DEPTH_SIZE ? 24 :
		(a == SDL_GL_RED_SIZE || a == SDL_GL_GREEN_SIZE || a == SDL_GL_BLUE_SIZE ||
		 a == SDL_GL_ALPHA_SIZE || a == SDL_GL_STENCIL_SIZE) ? 8 : 0;
	return true;
}
bool SDL_ShowCursor(void) { return true; }
bool SDL_HideCursor(void) { return true; }
bool SDL_SetWindowMouseGrab(SDL_Window *w, bool grab) { (void)w; (void)grab; return true; }
void SDL_WarpMouseInWindow(SDL_Window *w, float x, float y) { (void)w; (void)x; (void)y; }
bool SDL_GetWindowRelativeMouseMode(SDL_Window *w) { (void)w; return relative_mouse; }
bool SDL_PushEvent(SDL_Event *event)
{
	bool ok;
	pthread_mutex_lock(&event_lock);
	ok = event_count < 32;
	if (ok) { event_queue[(event_read + event_count) % 32] = *event; event_count++; }
	pthread_mutex_unlock(&event_lock);
	return ok;
}
const char *SDL_GetGamepadName(SDL_Gamepad *pad)
{
	if ((uintptr_t)pad == SWITCH2_GAMESHARE_GAMEPAD_ID)
		return "GameShare guest";
	return host_sdl_gamepad_name((unsigned int)(uintptr_t)pad);
}
char *SDL_GetGamepadMapping(SDL_Gamepad *pad) { (void)pad; return NULL; }
void SDL_CloseGamepad(SDL_Gamepad *pad)
{
	if ((uintptr_t)pad != SWITCH2_GAMESHARE_GAMEPAD_ID)
		host_sdl_close_gamepad((unsigned int)(uintptr_t)pad);
}
SDL_Keycode SDL_GetKeyFromScancode(SDL_Scancode s, SDL_Keymod m, bool key_event)
{
	(void)m; (void)key_event;
	if (s >= SDL_SCANCODE_A && s <= SDL_SCANCODE_Z) return SDLK_A + (s - SDL_SCANCODE_A);
	if (s >= SDL_SCANCODE_1 && s <= SDL_SCANCODE_9) return SDLK_1 + (s - SDL_SCANCODE_1);
	if (s == SDL_SCANCODE_0) return SDLK_0;
	switch (s) {
	case SDL_SCANCODE_RETURN: return SDLK_RETURN;
	case SDL_SCANCODE_ESCAPE: return SDLK_ESCAPE;
	case SDL_SCANCODE_SPACE: return SDLK_SPACE;
	case SDL_SCANCODE_TAB: return SDLK_TAB;
	case SDL_SCANCODE_BACKSPACE: return SDLK_BACKSPACE;
	default: return SDL_SCANCODE_TO_KEYCODE(s);
	}
}
SDL_JoystickID SDL_AttachVirtualJoystick(const SDL_VirtualJoystickDesc *d) { (void)d; return 0; }
bool SDL_DetachVirtualJoystick(SDL_JoystickID id) { (void)id; return false; }
SDL_Joystick *SDL_GetJoystickFromID(SDL_JoystickID id) { (void)id; return NULL; }
bool SDL_SetJoystickVirtualButton(SDL_Joystick *j, int b, bool d) { (void)j; (void)b; (void)d; return false; }
bool SDL_SetJoystickVirtualAxis(SDL_Joystick *j, int a, Sint16 v) { (void)j; (void)a; (void)v; return false; }
void SDL_UpdateJoysticks(void) {}
SDL_Renderer *SDL_CreateRenderer(SDL_Window *w, const char *n) { (void)w; (void)n; return NULL; }
bool SDL_SetRenderVSync(SDL_Renderer *r, int v) { (void)r; (void)v; return false; }
bool SDL_SetRenderDrawColor(SDL_Renderer *r, Uint8 a, Uint8 b, Uint8 c, Uint8 d) { (void)r; (void)a; (void)b; (void)c; (void)d; return false; }
bool SDL_RenderClear(SDL_Renderer *r) { (void)r; return false; }
bool SDL_SetRenderScale(SDL_Renderer *r, float x, float y) { (void)r; (void)x; (void)y; return false; }
bool SDL_RenderDebugText(SDL_Renderer *r, float x, float y, const char *s) { (void)r; (void)x; (void)y; (void)s; return false; }
bool SDL_RenderFillRect(SDL_Renderer *r, const SDL_FRect *rect) { (void)r; (void)rect; return false; }
bool SDL_RenderPresent(SDL_Renderer *r) { (void)r; return false; }
void SDL_DestroyRenderer(SDL_Renderer *r) { (void)r; }
void SDL_ShowOpenFileDialog(SDL_DialogFileCallback cb, void *u, SDL_Window *w, const SDL_DialogFileFilter *f, int n, const char *p, bool many)
{
	(void)w; (void)f; (void)n; (void)p; (void)many;
	if (cb) cb(u, NULL, -1);
}
