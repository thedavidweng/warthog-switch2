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
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include <switch.h>
#include <switch2/memory/heap.h>

#include <drako3d.h>
#include <uam2rt.h>

#include "warthog_log.h"
#include "headless_engine.h"

/* What port/switch2/build.py generates from UPSTREAM.json: the build's
flavor and version and the pins it was made from, so a log from a console
says exactly which build wrote it */
#include "warthog_build.h"

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

int main(int argc, char **argv)
{
	consoleInit(NULL);
	if (!warthog_log_open())
	{
		/* nothing can be logged, so the screen is the only report */
		printf("Warthog for Switch 2: cannot write sdmc:/switch/warthog/logs/warthog.log\n");
		consoleExit(NULL);
		return 1;
	}
	warthog_log("INFO", "--- launch ---");
	warthog_log("INFO", "engine symbol anchor: %zx", (size_t)warthog_engine_symbol_anchor());
	log_build();
	log_launch_context();
	log_firmware();
	log_core_mask();
	log_syscalls();
	log_memory();
	log_renderer();
	log_shader_runtime();
	const char *trigger = "sdmc:/switch/warthog/trigger_fault.txt";
	bool cpu_test = false, gpu_test = false;
	for (int i = 1; i < argc; i++)
	{
		if (!strcmp(argv[i], "--self-test-cpu-fault")) cpu_test = true;
		if (!strcmp(argv[i], "--self-test-gpu-fault")) gpu_test = true;
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
		warthog_log("INFO", "headless engine status: %d", warthog_headless_engine_run());
	warthog_log("INFO", "startup complete; returning to the homebrew menu");
	/* before the screen, which is what a player sees if the sync failed */
	warthog_log_sync();
	warthog_log_console("INFO", "Warthog for Switch 2 %s: log written to %s",
		WARTHOG_SWITCH2_VERSION, "sdmc:/switch/warthog/logs/warthog.log");
	warthog_log_close();
	consoleExit(NULL);
	return 0;
}
