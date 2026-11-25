#include "platform.h"
#include "sdl_platform.h"
#include "port_config.h"
#include <stdlib.h>
#include <string.h>
#define HALO_VERSION "dev"
static int stop_requested;
BOOL platform_sdl_initialize(void)
{
	return TRUE;
}

/* no disc image to offer: a server is given its maps */
BOOL platform_offer_game_data(char *destination, unsigned long size)
{
	(void)destination;
	(void)size;
	return FALSE;
}

/* as sdl_platform.c's (display.interpolation, on unless set off): the game's
main loop then runs unthrottled by the Xbox's 60 Hz display, which with no
display to wait for would spin; the director paces it (dedicated.c) */
int halo_interpolation_enabled(void)
{
	static int enabled;
	static unsigned long read_at = (unsigned long)-1;

	if (read_at != config_changes())
	{
		read_at = config_changes();
		enabled = config_boolean("display.interpolation");
	}
	return enabled;
}

/* ---------- no window */

BOOL platform_screen_mode(long *width, long *height)
{
	(void)width;
	(void)height;
	return FALSE;
}

/* (Video Setup's lists: a server has no display) */
int platform_display_resolutions(long *widths, long *heights, int maximum)
{
	(void)widths;
	(void)heights;
	(void)maximum;
	return 0;
}

int platform_window_sizes(long *widths, long *heights, int maximum)
{
	(void)widths;
	(void)heights;
	(void)maximum;
	return 0;
}

BOOL platform_video_initialize(unsigned long width, unsigned long height)
{
	(void)width;
	(void)height;
	return FALSE;
}

void platform_display_apply(void)
{
}

void platform_video_drawable_size(int *width, int *height)
{
	*width = 640;
	*height = 480;
}

void platform_video_window_size(int *width, int *height)
{
	*width = 640;
	*height = 480;
}

void platform_video_swap(void)
{
}

void platform_mouse_capture(BOOL capture)
{
	(void)capture;
}

/* ---------- no player at the machine */

BOOL platform_next_keystroke(struct platform_keystroke *keystroke)
{
	(void)keystroke;
	return FALSE;
}

int platform_clipboard_get(char *text, int size)
{
	if (size > 0)
		text[0] = 0;
	return 0;
}

void platform_clipboard_set(const char *text)
{
	(void)text;
}

/* (no invite to ask about: port/linux/game/invite_prompt.c) */
int platform_take_clipboard_invite(char *text, int size)
{
	if (size > 0)
		text[0] = 0;
	return 0;
}

void platform_show_message(const char *title, const char *message)
{
	platform_log("%s: %s", title, message);
}

void platform_open_url(const char *url)
{
	(void)url;
}

void platform_request_quit(void)
{
	stop_requested = 1;
}

/* (the server plays no movies: bink_playback.c) */
int platform_movie_skip_pressed(void)
{
	return 0;
}

void platform_scoreboard_scroll(int open, long *notches, long *pages)
{
	(void)open;
	if (notches)
		*notches = 0;
	if (pages)
		*pages = 0;
}

void platform_menus_set_active(BOOL active)
{
	(void)active;
}

void platform_binding_capture_begin(void)
{
}

int platform_binding_capture_poll(int *input)
{
	(void)input;
	return 3;
}

void platform_ui_pointer_set_active(BOOL active)
{
	(void)active;
}

BOOL platform_ui_pointer_read(struct platform_ui_pointer *pointer)
{
	memset(pointer, 0, sizeof(*pointer));
	return FALSE;
}

void platform_input_read(struct platform_input_state *state, BOOL consume_motion)
{
	(void)consume_motion;
	memset(state, 0, sizeof(*state));
}

/* ---------- events */

/* every frame (server_input.c's XInputGetState): stops as asked */
void platform_pump_events(void)
{
	(void)stop_requested;
}

/* ---------- the version (updater.c's, which the server leaves out: it
updates as its deployment does, server/README.md) */

void updater_start(void)
{
}

const char *updater_version(void)
{
	return HALO_VERSION;
}


/*
SERVER_INPUT.C

The dedicated server's controllers (server/README.md), in place of
xinput_sdl.c: no player sits at the machine. As the game's dedicated mode
has under SDL's dummy drivers, the first port holds a controller that never
moves (its state all zeros), and the debug keyboard is there but never types;
no other port has one. Reading the first controller, every frame, is also
when the platform layer pumps its events (server_platform.c), as
xinput_sdl.c does.
*/

#include "platform.h"
#include "sdl_platform.h"

#include <stdio.h>
#include <string.h>

#define PORT_COUNT 4

XPP_DEVICE_TYPE XDEVICE_TYPE_GAMEPAD_TABLE;
XPP_DEVICE_TYPE XDEVICE_TYPE_MEMORY_UNIT_TABLE;
XPP_DEVICE_TYPE XDEVICE_TYPE_DEBUG_KEYBOARD_TABLE;

struct controller
{
	BOOL open;
};

static struct controller controllers[PORT_COUNT];
static struct controller keyboard_device;
static DWORD reported_gamepads;
static BOOL reported_keyboard;

/* ---------- the keyboard and mouse's (none) */

int halo_linux_mouse_look(short gamepad_index, float *yaw, float *pitch)
{
	(void)gamepad_index;
	*yaw = 0.0f;
	*pitch = 0.0f;
	return FALSE;
}

int halo_linux_mouse_aiming(short gamepad_index)
{
	(void)gamepad_index;
	return FALSE;
}

/* the debug camera's mouse and keyboard (director.c): none */
int halo_linux_debug_camera_input(short gamepad_index, int free_camera, int *up, int *down, int *switch_key,
	float *wheel)
{
	(void)gamepad_index;
	(void)free_camera;
	*up = FALSE;
	*down = FALSE;
	*switch_key = FALSE;
	*wheel = 0.0f;
	return FALSE;
}

int platform_input_scheme(void)
{
	return 0;
}

int platform_prompt_scheme(void)
{
	return 0;
}

void platform_text_typing(int typing)
{
	(void)typing;
}

void platform_chat_typing(int typing)
{
	(void)typing;
}

int platform_chat_escape(void)
{
	return 0;
}

void platform_text_field(int typing)
{
	(void)typing;
}

/* (no gamepad of a player's: the menus' screens never open here) */
int platform_gamepad_count(void)
{
	return 0;
}

int platform_gamepad_describe(int index, char *name, size_t size)
{
	(void)index;
	if (size)
		name[0] = 0;
	return -1;
}

int halo_input_from_name(const char *name)
{
	(void)name;
	return -1;
}

void halo_input_name(int input, char *name, size_t size)
{
	(void)input;
	if (size)
		name[0] = 0;
}

void halo_input_shown_name(const char *binding, char *shown, size_t size)
{
	if (size)
		snprintf(shown, size, "%s", binding);
}

unsigned long halo_keyboard_actions(short controller_index)
{
	(void)controller_index;
	return 0;
}

int halo_keyboard_prompts(void)
{
	return 0;
}

int halo_keyboard_action_shown(int action, char *shown, unsigned long size)
{
	(void)action;
	if (size)
		shown[0] = 0;
	return 0;
}

void test_input_hold_action(int hold)
{
	(void)hold;
}

void test_input_hold_melee(int hold)
{
	(void)hold;
}

void test_input_hold_fire(int hold)
{
	(void)hold;
}

/* ---------- XAPI */

VOID WINAPI XInitDevices(DWORD preallocation_type_count, PXDEVICE_PREALLOC_TYPE preallocation_types)
{
	(void)preallocation_type_count;
	(void)preallocation_types;
	platform_sdl_initialize();
}

BOOL WINAPI XGetDeviceChanges(PXPP_DEVICE_TYPE device_type, PDWORD insertions, PDWORD removals)
{
	*insertions = 0;
	*removals = 0;
	if (device_type == XDEVICE_TYPE_GAMEPAD)
	{
		*insertions = XDEVICE_PORT0_MASK & ~reported_gamepads;
		reported_gamepads = XDEVICE_PORT0_MASK;
	}
	else if (device_type == XDEVICE_TYPE_DEBUG_KEYBOARD && !reported_keyboard)
	{
		*insertions = 1;
		reported_keyboard = TRUE;
	}
	return *insertions || *removals;
}

HANDLE WINAPI XInputOpen(PXPP_DEVICE_TYPE device_type, DWORD port, DWORD slot,
	PXINPUT_POLLING_PARAMETERS polling_parameters)
{
	(void)slot;
	(void)polling_parameters;
	if (device_type == XDEVICE_TYPE_GAMEPAD && port < PORT_COUNT)
	{
		controllers[port].open = TRUE;
		return (HANDLE)&controllers[port];
	}
	if (device_type == XDEVICE_TYPE_DEBUG_KEYBOARD && port == 0)
	{
		keyboard_device.open = TRUE;
		return (HANDLE)&keyboard_device;
	}
	SetLastError(ERROR_DEVICE_NOT_CONNECTED);
	return NULL;
}

VOID WINAPI XInputClose(HANDLE device)
{
	struct controller *controller = (struct controller *)device;

	if (controller)
		controller->open = FALSE;
}

DWORD WINAPI XInputGetState(HANDLE device, PXINPUT_STATE state)
{
	memset(state, 0, sizeof(*state));
	if (device != (HANDLE)&controllers[0] || !controllers[0].open)
	{
		int port;

		for (port = 1; port < PORT_COUNT; port++)
		{
			if (device == (HANDLE)&controllers[port] && controllers[port].open)
				return ERROR_SUCCESS;
		}
		return ERROR_DEVICE_NOT_CONNECTED;
	}
	platform_pump_events();
	return ERROR_SUCCESS;
}

DWORD WINAPI XInputSetState(HANDLE device, PXINPUT_FEEDBACK feedback)
{
	(void)device;
	if (!feedback)
		return ERROR_INVALID_PARAMETER;
	feedback->Header.dwStatus = ERROR_SUCCESS;
	return ERROR_SUCCESS;
}

DWORD WINAPI XInputDebugInitKeyboardQueue(PXINPUT_DEBUG_KEYQUEUE_PARAMETERS parameters)
{
	(void)parameters;
	return ERROR_SUCCESS;
}

DWORD WINAPI XInputDebugGetKeystroke(PXINPUT_DEBUG_KEYSTROKE keystroke)
{
	memset(keystroke, 0, sizeof(*keystroke));
	return ERROR_HANDLE_EOF;
}

/*
GAME_CONSOLE_GAPS.C

Game functions the Switch's build calls but the game builds to nothing on a
console. The game takes it that no console has the game list
(HALO_GAME_BROWSER: halo_console_features.h, "which no console build has"),
and the Switch does: so units built for the game list (profile_names.c,
lobby_screen.c, server_commands.c, network_server_manager.c, probe.c) call
what a console leaves out (Delta's device identity, the Guide's party and
friends, Steam, MCC maps). Each answers here as the game would with that
part away. They go when upstream gates its callers as it gates these.
*/

#include <stdio.h>
#include <string.h>

/* ---------- Delta's device identity (port/linux/src/identity.c, out under
HALO_CONSOLE_NO_DELTA_IDENTITY) */

#define IDENTITY_ID_SIZE 16

/* (no verified players: no name passes for one's handle) */
int identity_impersonates(const char *name, const char *handle, int cut)
{
	(void)name;
	(void)handle;
	(void)cut;
	return 0;
}

/* (no verified mark to tell names apart by: the name as it is, which the
caller then shows as it is) */
int identity_unverified_name(const unsigned short *name, int length, unsigned short *out, int size)
{
	int index;

	for (index = 0; index < length && index < size && name[index]; index++)
		out[index] = name[index];
	return index;
}

static int hex_digit(char c)
{
	return c >= '0' && c <= '9' ? c - '0' : c >= 'a' && c <= 'f' ? c - 'a' + 10 : c >= 'A' && c <= 'F' ? c - 'A' + 10 :
		-1;
}

/* a profile's account file's line, read as the game reads it: 0 a guest
("guest"), 2 that account (32 hex digits, into account), 1 the copy's own
account for the owner, a guest for any other */
int identity_account_choice(const char *line, int owner, unsigned char *account)
{
	char text[80];
	const char *at = line ? line : "";
	int length, index;

	if ((unsigned char)at[0] == 0xEF && (unsigned char)at[1] == 0xBB && (unsigned char)at[2] == 0xBF)
		at += 3;
	while (*at == ' ' || *at == '\t')
		at++;
	snprintf(text, sizeof(text), "%s", at);
	length = (int)strlen(text);
	while (length && (text[length - 1] == ' ' || text[length - 1] == '\t' || text[length - 1] == '\r' ||
		text[length - 1] == '\n'))
	{
		length--;
	}
	text[length] = 0;
	if (!strcmp(text, "guest"))
		return 0;
	if (length == 2 * IDENTITY_ID_SIZE)
	{
		for (index = 0; index < IDENTITY_ID_SIZE; index++)
		{
			int high = hex_digit(text[2 * index]), low = hex_digit(text[2 * index + 1]);

			if (high < 0 || low < 0)
				break;
			account[index] = (unsigned char)(high << 4 | low);
		}
		if (index == IDENTITY_ID_SIZE)
			return 2;
	}
	return owner ? 1 : 0;
}

/* ---------- the Guide's party and friends (port/linux/src/browser.c, out
under HALO_CONSOLE_NO_GUIDE) */

struct social_party;
struct social_state;

/* (never a party: the serial never moves, so the caller's stays as it was) */
void browser_party_get(struct social_party *party, int *serial)
{
	(void)party;
	(void)serial;
}

int browser_social_get(struct social_state *state, int *serial)
{
	(void)state;
	(void)serial;
	return 0; /* BROWSER_SOCIAL_NONE */
}

/* ---------- Steam (port/linux/src/steam_bridge_pipe.c, out with HALO_MCC 0) */

int steam_link_progress(const char *id_text, unsigned long long *done, unsigned long long *total, char *error,
	int error_size)
{
	(void)id_text;
	if (done)
		*done = 0;
	if (total)
		*total = 0;
	if (error && error_size > 0)
		snprintf(error, (size_t)error_size, "%s", "no Steam on this console");
	return 5; /* STEAM_BRIDGE_ITEM_FAILED */
}

/* ---------- MCC maps (port/linux/game/mcc_workshop.c, out with HALO_MCC 0) */

struct mcc_workshop_item;

/* (no MCC maps, so no map has a Workshop item or a title of one) */
int mcc_workshop_listing(char const name[128], struct mcc_workshop_item *item)
{
	(void)name;
	(void)item;
	return 0;
}

int mcc_workshop_map_title(char const *level, const void *catalog_name, char const *item_title, char *title,
	unsigned size)
{
	(void)level;
	(void)catalog_name;
	(void)item_title;
	(void)title;
	(void)size;
	return 0;
}

#include <stdint.h>
extern void physical_memory_allocate(void), cache_files_initialize(void), cache_file_header_verify(void);
extern void scenario_tags_load(void), main_loop(void), real_math_initialize(void);
uintptr_t warthog_engine_symbol_anchor(void) { return (uintptr_t)&physical_memory_allocate ^ (uintptr_t)&cache_files_initialize ^ (uintptr_t)&cache_file_header_verify ^ (uintptr_t)&scenario_tags_load ^ (uintptr_t)&main_loop ^ (uintptr_t)&real_math_initialize ^ (uintptr_t)&xbox_address_space_base; }

static volatile unsigned int mw_serial = 1;
void memory_watch_initialize(void) {}
void memory_watch_protect(unsigned long address, unsigned long size) { (void)address; (void)size; }
unsigned long memory_watch_generation(unsigned long address, unsigned long size) { (void)address; (void)size; return mw_serial; }
unsigned long memory_watch_serial(void) { return mw_serial; }
void memory_watch_prepare_write(void *address, unsigned long size) { (void)address; (void)size; ++mw_serial; }
void memory_watch_forget(void *address, unsigned long size) { (void)address; (void)size; ++mw_serial; }

unsigned char halo_screen_fast_warp(void) { return 0; }
unsigned char halo_screen_fast_blur(void) { return 0; }
void halo_screen_warp_blend(unsigned char on) { (void)on; }
void halo_switch_renderer_idle(void) {}
void d3d8_gl_map_loading(const char *name) { (void)name; }
float d3d8_gl_map_progress(void) { return 0; }
int d3d8_gl_map_waiting(void) { return 0; }
void dk_hud_prepare(const long *assets, long count) { (void)assets; (void)count; }
void dk_hud_forget(void) {}
int halo_linux_gyro_look(short index, float *yaw, float *pitch) { (void)index; *yaw = *pitch = 0; return 0; }
int halo_linux_gyro_zoom_only(void) { return 0; }
int updater_install_status(char *line, int size) { if (size > 0 && line) line[0] = 0; return 0; }
int updater_ready(char *latest, int size) { if (size > 0 && latest) latest[0] = 0; return 0; }
const char *updater_install_amount(char *text, int size) { if (size > 0) text[0] = 0; return text; }
int updater_install_begin(void) { return 0; }

unsigned short mcc_network_inventory_entry_size(void) { return 0; }
void mcc_network_handle_inventories(const void *entries, short count) { (void)entries; (void)count; }
unsigned short mcc_network_campaign_entry_size(void) { return 0; }
void mcc_network_handle_campaign(const void *entries, short count) { (void)entries; (void)count; }
unsigned short mcc_object_names_entry_size(void) { return 0; }
void mcc_object_names_receive(const void *entries, short count, long time) { (void)entries; (void)count; (void)time; }
void mcc_game_speed_receive(const void *entries, short count) { (void)entries; (void)count; }
