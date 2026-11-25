/*
WARTHOG FOR SWITCH 2: THE STARTUP PROGRAM

What ticket #3 asks for: the smallest Warthog that launches under kaiHEN,
appears in hbmenu with its name, icon, author and version, writes a log under
sdmc:/switch/warthog/logs and returns to hbmenu cleanly. It draws nothing and
plays nothing; what it does is record what the console granted the process,
which is the evidence the later tickets are decided on.

Everything it reports is a read-only question. The syscalls kaiHEN does not
grant are asked about with envIsSyscallHinted and never called: under kaiHEN
an ungranted one terminates the process instead of returning an error, so the
answer to "is 0x77 hinted" has to be obtained without invoking 0x77.

The exception and graphics diagnostic records also go to host/warthog_log.c.
No Drako3D device or swapchain is created by this startup program yet.

SPDX-License-Identifier: GPL-3.0-or-later
*/

#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include <switch.h>
#include <switch2/memory/heap.h>

#include <drako3d.h>
#include <uam2rt.h>

#include "warthog_log.h"
#include "headless_engine.h"
#include "switch2_net.h"
#include "switch2_gamedata.h"
#include "switch2_mman.h"
#include "nx2_platform.h"
#include "switch2_lifecycle.h"
#include "switch2_update.h"
#include "switch2_gameshare.h"

extern int halo_main(void);
void host_dk_shutdown(void);
void host_debug_shutdown(void);
void host_sdl_quit(void);
void platform_xbox_memory_reset_for_shutdown(void);
void xbox_heap_reset_for_shutdown(void);
void switch2_lifecycle_start(void);
void switch2_lifecycle_stop(void);
void switch2_lifecycle_cleanup(void);
const char *host_https_roots(void);
int switch2_seed_certificates(const char *root, const char *bundle);

/* What port/switch2/build.py generates from UPSTREAM.json: the build's
flavor and version and the pins it was made from, so a log from a console
says exactly which build wrote it */
#include "warthog_build.h"

typedef int (*https_body_fn)(void *, const void *, size_t, long long);
int host_https_get(const char *, int, https_body_fn, void *, char *, size_t, char *, size_t);

struct update_download { uint8_t *data; size_t size; };

static int update_body(void *ctx, const void *data, size_t size, long long total)
{
	(void)total;
	struct update_download *download = ctx;
	if (size > 128 * 1024 * 1024 - download->size) return 0;
	uint8_t *next = realloc(download->data, download->size + size);
	if (!next) return 0;
	download->data = next;
	memcpy(next + download->size, data, size);
	download->size += size;
	return 1;
}

static int update_http(void *ctx, const char *url, int follow, uint8_t **body,
                       size_t *size, char *location, size_t location_size)
{
	char error[256];
	struct update_download download = {0};
	if (!*(const bool *)ctx) return -1;
	int status = host_https_get(url, follow, update_body, &download, location,
	                            location_size, error, sizeof(error));
	*body = download.data;
	*size = download.size;
	return status;
}

extern const u8 __start__[];

__attribute__((noinline)) void warthog_deliberate_test_fault(void)
{
	__asm__ volatile("brk #0");
}

/* The syscalls the original Switch port used and kaiHEN does not grant
(AGENTS.md, "Platform constraints"). Listed so the log records the answer
for each: a hinted one may be used, an unhinted one may not. */
static const struct
{
	unsigned number;
	const char *name;
} watched_syscalls[] = {
	{ 0x4B, "svcCreateCodeMemory" },
	{ 0x4C, "svcControlCodeMemory" },
	{ 0x73, "svcSetProcessMemoryPermission" },
	{ 0x74, "svcMapProcessMemory" },
	{ 0x75, "svcUnmapProcessMemory" },
	{ 0x77, "svcMapProcessCodeMemory" },
	{ 0x78, "svcUnmapProcessCodeMemory" },
};

static const char *applet_type_name(AppletType type)
{
	switch (type)
	{
		case AppletType_Application: return "Application";
		case AppletType_SystemApplet: return "SystemApplet";
		case AppletType_LibraryApplet: return "LibraryApplet";
		case AppletType_OverlayApplet: return "OverlayApplet";
		case AppletType_SystemApplication: return "SystemApplication";
		case AppletType_Default: return "Default";
		case AppletType_None: return "None";
	}
	return "unknown";
}

static void log_build(void)
{
	warthog_log("INFO", "Warthog for Switch 2 %s (%s build)", WARTHOG_SWITCH2_VERSION, WARTHOG_SWITCH2_FLAVOR);
	warthog_log("INFO", "pins: warthog-switch %s", WARTHOG_SWITCH2_WARTHOG_SWITCH_COMMIT);
	warthog_log("INFO", "pins: chupathingyce %s", WARTHOG_SWITCH2_CHUPATHINGYCE_COMMIT);
	warthog_log("INFO", "pins: drako3d %s %s", WARTHOG_SWITCH2_DRAKO3D_VERSION, WARTHOG_SWITCH2_DRAKO3D_COMMIT);
	warthog_log("INFO", "pins: uam2 %s %s", WARTHOG_SWITCH2_UAM2_VERSION, WARTHOG_SWITCH2_UAM2_COMMIT);
	warthog_log("INFO", "MODULE_BASE: %p", (void *)warthog_module_base());
}

static void log_launch_context(void)
{
	AppletType type = appletGetAppletType();

	warthog_log("INFO", "launch context: AppletType %d (%s)", (int)type, applet_type_name(type));
	warthog_log("INFO", "launch context: OperationMode %d", (int)appletGetOperationMode());

	/* hbmenu runs the next NRO in the same process, so this is where the
	previous program's resources would show up as still held. libounce has no
	svcGetProcessHandle; envGetOwnProcessHandle is the handle it already
	holds. */
	Handle handle = envGetOwnProcessHandle();

	warthog_log("INFO", "process handle: %s (%#x)", handle != 0 ? "granted" : "not granted", handle);
}

static void log_firmware(void)
{
	SetSysFirmwareVersion firmware = { 0 };

	if (R_FAILED(setsysInitialize()))
	{
		warthog_log("WARN", "firmware: setsys is unavailable");
		return;
	}
	Result result = setsysGetFirmwareVersion(&firmware);

	if (R_SUCCEEDED(result))
	{
		warthog_log("INFO", "firmware: %s (version %u.%u.%u, platform %s)",
			firmware.display_version, firmware.major, firmware.minor, firmware.micro, firmware.platform);
	}
	else
	{
		warthog_log("WARN", "firmware: setsysGetFirmwareVersion failed (%#x)", result);
	}
	setsysExit();
}

static void log_core_mask(void)
{
	u64 mask = 0;
	Result result = svcGetInfo(&mask, InfoType_CoreMask, CUR_PROCESS_HANDLE, 0);

	if (R_FAILED(result))
	{
		warthog_log("WARN", "core mask: svcGetInfo failed (%#x)", result);
		return;
	}
	warthog_log("INFO", "core mask: %#llx (the cores this title may run on)", (unsigned long long)mask);
}

static void log_syscalls(void)
{
	size_t index;

	for (index = 0; index < sizeof(watched_syscalls) / sizeof(*watched_syscalls); index++)
	{
		/* asked, never invoked: an unhinted syscall terminates the process
		under kaiHEN rather than returning an error */
		warthog_log("INFO", "syscall %#04x %s: %s", watched_syscalls[index].number, watched_syscalls[index].name,
			envIsSyscallHinted(watched_syscalls[index].number) ? "hinted" : "not hinted");
	}
}

static void log_memory(void)
{
	warthog_log("INFO", "heap: %llu KiB total, %llu KiB free",
		(unsigned long long)(heapGetTotalSize() / 1024), (unsigned long long)(heapGetFreeSize() / 1024));
}

/* Drako3D's provenance, without a GPU device: this takes the
address of dkDeviceCreate. `--gc-sections` (libounce's switch.specs) keeps
the archive member that defines a symbol the program references, which is
what puts libdrako3d.a in warthog.elf.map for tools/switch2_audit.py. */
static void log_renderer(void)
{
	warthog_log("INFO", "renderer: Drako3D, dkDeviceCreate at %p (no device created yet)",
		(void *)(uintptr_t)&dkDeviceCreate);
}

/* The shader compiler's runtime: proving it initialises here means a later failure is the
shader, not the runtime */
static void log_shader_runtime(void)
{
	if (uam2rt_init())
	{
		warthog_log("INFO", "uam2rt: initialised");
		uam2rt_exit();
		warthog_log("INFO", "uam2rt: shut down");
	}
	else
	{
		warthog_log("ERROR", "uam2rt: uam2rt_init failed");
	}
}

extern uintptr_t warthog_engine_symbol_anchor(void);

static void wait_for_menu_return(u64 buttons, const char *prompt)
{
	printf("%s\n", prompt);
	consoleUpdate(NULL);
	PadState pad;
	padConfigureInput(1, HidNpadStyleSet_NpadStandard);
	padInitializeDefault(&pad);
	while (appletMainLoop())
	{
		padUpdate(&pad);
		if (padGetButtonsDown(&pad) & buttons)
			break;
		consoleUpdate(NULL);
	}
}

static void extraction_progress(void *ctx, int index, int count, const char *path, uint64_t done, uint64_t total)
{
	static int previous;
	static int previous_percent = -1;
	int percent = total ? (int)(done * 100 / total) : 100;
	(void)ctx;
	if (previous != index || previous_percent != percent)
	{
		printf("\rExtracting %d/%d: %s %d%%          ", index, count, path, percent);
		consoleUpdate(NULL);
		previous_percent = percent;
	}
	if (previous != index || done == total)
	{
		warthog_log("INFO", "Extracting %d/%d: %s %llu/%llu bytes", index, count, path,
			(unsigned long long)done, (unsigned long long)total);
		previous = index;
	}
}

int main(int argc, char **argv)
{
	if (!switch2_update_finish_pending(WARTHOG_SWITCH2_CARD_DIR))
	{
		switch2PlatformRestoreClock();
		return 1;
	}
	consoleInit(NULL);
	if (!warthog_log_open())
	{
		/* nothing can be logged, so the screen is the only report */
		printf("Warthog for Switch 2: cannot write sdmc:/switch/warthog/logs/warthog.log\n");
		consoleExit(NULL);
		switch2PlatformRestoreClock();
		return 1;
	}
	warthog_log("INFO", "--- launch ---");
	const char *data_root = getenv("HALO_DATA_ROOT");
	if (!data_root || !*data_root) data_root = "sdmc:/switch/warthog";
	if (!switch2_net_cleanup_stale_map_parts(data_root))
		warthog_log("WARN", "maps: cannot clean stale download parts");
	if (!switch2_seed_certificates(data_root, host_https_roots()))
		warthog_log("WARN", "game list: cannot prepare certificate bundle");
	warthog_log("INFO", "engine symbol anchor: %zx", (size_t)warthog_engine_symbol_anchor());
	log_build();
	log_launch_context();
	log_firmware();
	log_core_mask();
	log_syscalls();
	log_memory();
	log_renderer();
	AppletType type = appletGetAppletType();
	bool restricted = type == AppletType_LibraryApplet || type == AppletType_SystemApplet ||
		type == AppletType_OverlayApplet;
	u64 available = heapGetTotalSize();
	warthog_log("INFO", "memory budget: %llu bytes of heap", (unsigned long long)available);
	if (switch2_lifecycle_refuse_launch(restricted, available))
	{
		warthog_log_console("ERROR", "Restricted applet mode or insufficient memory. Launch Warthog using title takeover "
			"(full-memory Application mode) under kaiHEN.");
		wait_for_menu_return(HidNpadButton_Plus | HidNpadButton_B,
			"Press + or B to return to the homebrew menu.");
		switch2PlatformRestoreClock();
		nx2ExitCleanupNow();
		warthog_log_close();
		consoleExit(NULL);
		return 1;
	}
	SocketInitConfig sockets = *socketGetDefaultInitConfig();
	sockets.num_bsd_sessions = 8;
	sockets.sb_efficiency = 8;
	sockets.tcp_tx_buf_max_size = 0x80000;
	sockets.tcp_rx_buf_max_size = 0x80000;
	bool sockets_ready = R_SUCCEEDED(socketInitialize(&sockets));
	if (!sockets_ready)
		warthog_log("WARN", "sockets: initialization failed; networking is unavailable");
	if (HALO_BUILD_NUMBER > 0) {
		char update_error[256];
		int result = switch2_update_check(WARTHOG_SWITCH2_CARD_DIR, WARTHOG_SWITCH2_FLAVOR, HALO_BUILD_NUMBER,
		                                  update_http, &sockets_ready, update_error, sizeof(update_error));
		if (result < 0) warthog_log("WARN", "update: %s", update_error);
		else if (result > 0) warthog_log("INFO", "update installed; restart to use it");
	}
	log_shader_runtime();
	const char *trigger = "sdmc:/switch/warthog/trigger_fault.txt";
	bool cpu_test = false, gpu_test = false, headless_check = false, gameshare = false;
	for (int i = 1; i < argc; i++)
	{
		if (!strcmp(argv[i], "--self-test-cpu-fault")) cpu_test = true;
		if (!strcmp(argv[i], "--self-test-gpu-fault")) gpu_test = true;
		if (!strcmp(argv[i], "--headless-check")) headless_check = true;
		if (!strcmp(argv[i], "--gameshare")) gameshare = true;
	}
	if (access(trigger, F_OK) == 0)
	{
		if (unlink(trigger) == 0) cpu_test = true;
		else warthog_log("ERROR", "cannot remove fault trigger; skipping it");
	}
	if (cpu_test)
	{
		warthog_log_sync();
		warthog_deliberate_test_fault();
	}
	if (gpu_test)
		warthog_dk_debug_callback(NULL, "self-test", DkResult_Fail, "deliberate GPU diagnostic");
	if (!cpu_test && !gpu_test)
	{
		char message[512];
		int status = switch2_gamedata_prepare("sdmc:/switch/warthog", "sdmc:/switch/ChupaThingyCE",
			0, extraction_progress, NULL, message, sizeof(message));
		warthog_log_console(status == SWITCH2_GAMEDATA_OK ? "INFO" : "ERROR", "%s", message);
		consoleUpdate(NULL);
		if (status == SWITCH2_GAMEDATA_OK)
		{
			char path[1024];
			const char *root = getenv("HALO_DATA_ROOT");
			if (!root || !*root) root = "sdmc:/switch/warthog";
			int length = snprintf(path, sizeof(path), "%s/maps/ui.map", root);
			if (!headless_check && length > 0 && (size_t)length < sizeof(path) && access(path, R_OK) == 0)
			{
				warthog_log("INFO", "maps/ui.map ready; releasing console and entering Halo main menu via Drako3D");
				warthog_log_sync();
				consoleExit(NULL);
				switch2PlatformDisplayInit();
				switch2_lifecycle_start();
				atexit(switch2_lifecycle_cleanup);
				if (gameshare) {
					char gameshare_error[256];
					switch2_gameshare_begin(gameshare_error, sizeof(gameshare_error));
				}
				halo_main();
				switch2_lifecycle_cleanup();
				platform_xbox_memory_reset_for_shutdown();
				xbox_heap_reset_for_shutdown();
				switch2_mman_shutdown();
				if (sockets_ready) socketExit();
				warthog_log_close();
				return 0;
			}
			warthog_log("INFO", "headless engine status: %d", warthog_headless_engine_run());
		}
		else
		{
			wait_for_menu_return(HidNpadButton_Plus,
				"Press + to return to the homebrew menu.");
		}
	}
	warthog_log("INFO", "startup complete; returning to the homebrew menu");
	/* before the screen, which is what a player sees if the sync failed */
	warthog_log_sync();
	warthog_log_console("INFO", "Warthog for Switch 2 %s: log written to %s",
		WARTHOG_SWITCH2_VERSION, "sdmc:/switch/warthog/logs/warthog.log");
	if (sockets_ready) socketExit();
	warthog_log_close();
	consoleExit(NULL);
	nx2ExitCleanupNow();
	switch2PlatformRestoreClock();
	return 0;
}
