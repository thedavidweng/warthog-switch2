// nx2_platform: Nintendo Switch 2 (kaiHEN + libounce) platform helpers. See nx2_platform.h.
// SPDX-License-Identifier: MIT
// From NaGaa95/dolphin-nx Source/Core/Common/nx2_platform.c
// Revision 7fb685b353e19a9a5848e9bd658945d1f9cd382a
// Copyright (c) NaGaa95/dolphin-nx contributors
#if defined(__SWITCH2__)

#include "nx2_platform.h"

#include <errno.h>
#include <stdlib.h>
#include <string.h>

static u64 nx2Info(u32 type)
{
	u64 value = 0;
	return R_SUCCEEDED(svcGetInfo(&value, type, CUR_PROCESS_HANDLE, 0)) ? value : 0;
}

// ------------------------------------------------------------------------------------------------ HID
// libounce ends the program when HID refuses to activate the keyboard or the mouse, which depends on the game kaiHEN
// runs the homebrew in. Linking with -Wl,--wrap=hidInitializeKeyboard -Wl,--wrap=hidInitializeMouse (SDL calls
// them) turns a refusal into no keyboard or mouse input. ActivateKeyboard is HID's command 31, ActivateMouse 21.
static Result nx2HidActivate(u32 command)
{
	const u64 aruid = appletGetAppletResourceUserId();
	return serviceDispatchIn(hidGetServiceSession(), command, aruid, .in_send_pid = true);
}

void __wrap_hidInitializeKeyboard(void);
void __wrap_hidInitializeKeyboard(void)
{
	(void)nx2HidActivate(31);
}

void __wrap_hidInitializeMouse(void);
void __wrap_hidInitializeMouse(void)
{
	(void)nx2HidActivate(21);
}

// The touch screen reports in the output range the hosting game set (1920x1080 for a Switch 2 game), while every
// port's touch handling (SDL's included) expects the Switch's 1280x720: ask for that range before touch is activated,
// as HID requires (-Wl,--wrap=hidInitializeTouchScreen).
void __real_hidInitializeTouchScreen(void);
void __wrap_hidInitializeTouchScreen(void);
void __wrap_hidInitializeTouchScreen(void)
{
	(void)hidSetTouchScreenOutputRanges(1280, 720);
	__real_hidInitializeTouchScreen();
}

// ------------------------------------------------------------------------------------------------ CPU
u64 nx2CoreMask(void)
{
	static u64 s_mask = 0;
	if (!s_mask)
	{
		u64 mask = envIsSyscallHinted(0x29) ? nx2Info(InfoType_CoreMask) & 0xFF : 0;
		s_mask = mask ? mask : 0x3F;
	}
	return s_mask;
}

int nx2CoreCount(void)
{
	return __builtin_popcountll(nx2CoreMask());
}

int nx2CoreAt(unsigned n)
{
	const u64 mask = nx2CoreMask();
	const int count = __builtin_popcountll(mask);
	if (!count)
		return -1;
	n %= (unsigned)count;
	u64 rest = mask;
	for (unsigned i = 0; i < n; ++i)
		rest &= rest - 1;
	return __builtin_ctzll(rest);
}

Result nx2SetCpuBoost(bool on)
{
	return appletSetCpuBoostMode(on ? ApmCpuBoostMode_FastLoad : ApmCpuBoostMode_Normal);
}

// ------------------------------------------------------------------------------------------------ display
static Mutex s_displayMutex;
static bool s_frameGeneration = false;
static uint32_t s_requestedRefresh = 60;
static struct switch2_display_state s_display = {
	.internal_width = 1920, .internal_height = 1080,
	.output_width = 1920, .output_height = 1080,
	.requested_refresh = 60, .granted_refresh = 60, .interpolation = true
};
static bool s_tvEventOpen = false, s_tvRead = false;
static Event s_tvEvent;
static s32 s_tvWidth = 3840, s_tvHeight = 2160;
static u32 s_dockedWidth = 0, s_dockedHeight = 0;
static u32 s_lastWidth = 0, s_lastHeight = 0;
static bool s_presentApplied = false;
static int s_presentHz = 0, s_presentInterval = -1;

bool nx2Docked(void)
{
	return appletGetOperationMode() == AppletOperationMode_Console;
}

// The TV's resolution (AM's default display resolution), reread when AM signals a change (also when the TV's mode
// changes for 120 Hz).
static void nx2ReadTvResolution(void)
{
	if (!s_tvEventOpen && R_SUCCEEDED(appletGetDefaultDisplayResolutionChangeEvent(&s_tvEvent)))
		s_tvEventOpen = true;
	const bool changed = s_tvEventOpen && R_SUCCEEDED(eventWait(&s_tvEvent, 0));
	if (s_tvRead && !changed)
		return;
	if (changed)
		eventClear(&s_tvEvent);
	s32 width = 0, height = 0;
	if (R_SUCCEEDED(appletGetDefaultDisplayResolution(&width, &height)) && width > 0 && height > 0)
	{
		s_tvWidth = width;
		s_tvHeight = height;
	}
	s_tvRead = true;
}

// The refresh rate for the operation mode, and the docked size: the TV's resolution, at most 2160 lines, or 1440 with
// frame generation's 120 Hz output (the window asks for 120 Hz, and VI2 picks the TV's 120 Hz mode, 1440p or 1080p;
// 4K stays at 60 Hz). Call with s_displayMutex held.
static void nx2ApplyMode(void)
{
	const bool docked = nx2Docked();
	const uint32_t target_hz = s_requestedRefresh;
	nx2ReadTvResolution();
	u32 width = (u32)s_tvWidth, height = (u32)s_tvHeight;
	if (docked && target_hz > 60 && s_display.internal_height <= 1440 && (width > 2560 || height > 1440))
	{
		width = 2560;
		height = 1440;
	}
	s_display.requested_refresh = target_hz;
	switch2_display_set_output(&s_display, width, height, docked);
	s_display.requested_refresh = switch2_display_clamp_refresh(s_display.output_width, s_display.output_height, target_hz);
	width = s_display.output_width;
	height = s_display.output_height;
	if (width == s_dockedWidth && height == s_dockedHeight)
		return;
	if (R_SUCCEEDED(nwindowSetModeDimensions(nwindowGetDefault(), 1920, 1080, width, height)))
	{
		s_dockedWidth = width;
		s_dockedHeight = height;
	}
}

// Call with s_displayMutex held.
static Result nx2ApplyPacing(int swap_interval)
{
	if (swap_interval < 0)
		swap_interval = 0;
	Result rc = 0;
	NWindow* window = nwindowGetDefault();
	if (swap_interval == 0)
	{
		if (!s_presentApplied || s_presentInterval != 0)
			rc = nwindowSetSwapInterval(window, 0);
	}
	else if (s_display.requested_refresh > 60 && swap_interval == 1)
	{
		// (every call: a swap interval set elsewhere, by EGL or drako3d, withdraws the 120 Hz request)
		rc = nwindowSetFrameRates(window, 0, 0, true);
	}
	else if (!s_presentApplied || s_presentHz != (int)s_display.requested_refresh || s_presentInterval != swap_interval)
	{
		rc = nwindowSetSwapInterval(window, (u32)swap_interval);
	}
	s_presentApplied = R_SUCCEEDED(rc);
	s_presentHz = (int)s_display.requested_refresh;
	s_presentInterval = swap_interval;
	return rc;
}

void nx2DisplayInit(void)
{
	mutexLock(&s_displayMutex);
	nx2ApplyMode();
	nwindowGetDimensions(nwindowGetDefault(), &s_lastWidth, &s_lastHeight);
	mutexUnlock(&s_displayMutex);
}

bool nx2DisplaySetRefreshRate(uint32_t hz)
{
	const uint32_t target = hz > 60 ? 120 : 60;

	mutexLock(&s_displayMutex);
	if (target == s_requestedRefresh)
	{
		mutexUnlock(&s_displayMutex);
		return false;
	}
	s_requestedRefresh = target;
	nx2ApplyMode();
	const bool changed = (int)s_display.requested_refresh != s_presentHz;
	if (changed)
		s_presentApplied = false;
	mutexUnlock(&s_displayMutex);
	return changed;
}

bool nx2DisplaySetFrameGeneration(bool enabled)
{
	mutexLock(&s_displayMutex);
	if (enabled == s_frameGeneration && (!enabled || s_requestedRefresh > 60))
	{
		mutexUnlock(&s_displayMutex);
		return false;
	}
	s_frameGeneration = enabled;
	s_requestedRefresh = enabled ? 120 : 60;
	s_display.interpolation = enabled;
	nx2ApplyMode();
	const bool changed = (int)s_display.requested_refresh != s_presentHz;
	if (changed)
		s_presentApplied = false;
	mutexUnlock(&s_displayMutex);
	return changed;
}

int nx2DisplayRefreshRate(void)
{
	mutexLock(&s_displayMutex);
	int hz = 60;
	// 120 Hz is a request, which VI2 grants only where the display has a 120 Hz mode. While nx2's frame rates pace the
	// window, its present interval is 1 / the rate VI2 runs it at.
	u16 numerator = 0, denominator = 0;
	if (s_presentApplied && R_SUCCEEDED(nwindowGetPresentInterval(nwindowGetDefault(), &numerator, &denominator)))
		hz = (int)switch2_display_interval_hz(numerator, denominator);
	s_display.granted_refresh = (uint32_t)hz;
	mutexUnlock(&s_displayMutex);
	return hz;
}

void nx2DisplaySetInternalResolution(u32 height)
{
	mutexLock(&s_displayMutex);
	switch2_display_set_internal(&s_display, height);
	mutexUnlock(&s_displayMutex);
}

Result nx2DisplayApply(int swap_interval)
{
	mutexLock(&s_displayMutex);
	const Result rc = nx2ApplyPacing(swap_interval);
	mutexUnlock(&s_displayMutex);
	return rc;
}

Result nx2DisplayReapply(void)
{
	mutexLock(&s_displayMutex);
	s_presentApplied = false;
	const Result rc = nx2ApplyPacing(s_presentInterval < 0 ? 1 : s_presentInterval);
	mutexUnlock(&s_displayMutex);
	return rc;
}

bool nx2DisplayUpdate(void)
{
	mutexLock(&s_displayMutex);
	const uint32_t previousRefresh = s_display.requested_refresh;
	nx2ApplyMode();
	// Both handheld and docked at 120 Hz: swapchain creation or swap interval calls
	// withdraw the 120 Hz request, and libounce caches it so reapplying is cheap.
	if (!s_presentApplied || s_display.requested_refresh != (uint32_t)s_presentHz || s_display.requested_refresh > 60)
	{
		if (s_display.requested_refresh != previousRefresh)
			s_presentApplied = false;
		nx2ApplyPacing(s_presentInterval < 0 ? 1 : s_presentInterval);
	}
	u32 width = 0, height = 0;
	nwindowGetDimensions(nwindowGetDefault(), &width, &height);
	const bool changed = width != s_lastWidth || height != s_lastHeight;
	s_lastWidth = width;
	s_lastHeight = height;
	mutexUnlock(&s_displayMutex);
	return changed;
}

void nx2DisplaySize(u32* width, u32* height)
{
	u32 w = 1920, h = 1080;
	nwindowGetDimensions(nwindowGetDefault(), &w, &h);
	if (width)
		*width = w;
	if (height)
		*height = h;
}

// Dolphin/Mesa-specific GPU handover and JIT internals are not needed here.
// ------------------------------------------------------------------------------------------------ exit cleanup
// At exit the homebrew loader runs the next program in this same process: a thread still running would run this
// program's code under the next, and its stack mirror (mapped until a join) would keep the next program short of
// memory. Every pthread is tracked (-Wl,--wrap=__syscall_thread_create); after the C++ static destructors, running
// threads get a second to end, then are paused and their stacks unmapped. libounce releases the threads that ended.
struct __pthread_t;
int __real___syscall_thread_create(struct __pthread_t** thread, void* (*func)(void*), void* arg, void* stack_addr,
								   size_t stack_size);
int __wrap___syscall_thread_create(struct __pthread_t** thread, void* (*func)(void*), void* arg, void* stack_addr,
								   size_t stack_size);

typedef struct
{
	void* (*func)(void*);
	void* arg;
} Nx2ThreadStart;

typedef struct
{
	Thread* thread;
	void* mirror;
	void* memory;
	bool live;
} Nx2TrackedThread;

#define NX2_MAX_TRACKED_THREADS 512
static Nx2TrackedThread s_threads[NX2_MAX_TRACKED_THREADS];
static Mutex s_threadsMutex;
static bool s_releaseExitLock = false;
static bool s_exitCleanupDone = false;

// Whether mirror is still a stack mirror (svcMapMemory'd memory starting there), and its size.
static bool nx2IsStackMirror(void* mirror, u64* size)
{
	MemoryInfo info = {0};
	u32 pageInfo = 0;
	if (!envIsSyscallHinted(0x06))
		return false;
	if (R_FAILED(svcQueryMemory(&info, &pageInfo, (u64)(uintptr_t)mirror)))
		return false;
	if (size)
		*size = info.size;
	return (info.type & MemState_Type) == MemType_MappedMemory && info.addr == (u64)(uintptr_t)mirror;
}

static int nx2TrackThreadStart(Thread* self)
{
	mutexLock(&s_threadsMutex);
	int freeSlot = -1;
	for (int i = 0; i < NX2_MAX_TRACKED_THREADS; i++)
	{
		Nx2TrackedThread* entry = &s_threads[i];
		// A finished thread whose stack mirror address came back has been joined: forget it.
		if (!entry->live && entry->mirror == self->stack_mirror)
			memset(entry, 0, sizeof(*entry));
		if (freeSlot < 0 && !entry->live && !entry->mirror)
			freeSlot = i;
	}
	if (freeSlot < 0)
	{
		// Full: forget the finished threads that were joined since.
		for (int i = 0; i < NX2_MAX_TRACKED_THREADS; i++)
		{
			Nx2TrackedThread* entry = &s_threads[i];
			if (!entry->live && entry->mirror && !nx2IsStackMirror(entry->mirror, NULL))
			{
				memset(entry, 0, sizeof(*entry));
				if (freeSlot < 0)
					freeSlot = i;
			}
		}
	}
	if (freeSlot >= 0)
	{
		Nx2TrackedThread* entry = &s_threads[freeSlot];
		entry->thread = self;
		entry->mirror = self->stack_mirror;
		entry->memory = self->stack_mem;
		entry->live = true;
	}
	mutexUnlock(&s_threadsMutex);
	return freeSlot;
}

static void nx2TrackThreadFinish(int slot)
{
	if (slot < 0)
		return;
	mutexLock(&s_threadsMutex);
	s_threads[slot].live = false;
	s_threads[slot].thread = NULL;
	mutexUnlock(&s_threadsMutex);
}

static void nx2PlaceDefaultWorkerThread(void)
{
	static unsigned s_workerNext;
	const u64 mask = nx2CoreMask();
	u64 workers = mask & ~3ULL;
	if (!workers)
		workers = mask & ~1ULL;
	if (!workers)
		return;
	const unsigned count = (unsigned)__builtin_popcountll(workers);
	unsigned pick = __atomic_fetch_add(&s_workerNext, 1u, __ATOMIC_RELAXED) % count;
	u64 rest = workers;
	while (pick--)
		rest &= rest - 1;
	const int ideal = __builtin_ctzll(rest);
	(void)svcSetThreadCoreMask(CUR_THREAD_HANDLE, ideal, workers);
}

static void* nx2ThreadTrampoline(void* argument)
{
	const Nx2ThreadStart start = *(Nx2ThreadStart*)argument;
	free(argument);
	nx2PlaceDefaultWorkerThread();
	Thread* self = threadGetSelf();
	const int slot = self ? nx2TrackThreadStart(self) : -1;
	void* result = start.func(start.arg);
	nx2TrackThreadFinish(slot);
	return result;
}

int __wrap___syscall_thread_create(struct __pthread_t** thread, void* (*func)(void*), void* arg, void* stack_addr,
								   size_t stack_size)
{
	if (!stack_addr && stack_size < 0x80000)
		stack_size = 0x80000;
	Nx2ThreadStart* start = (Nx2ThreadStart*)malloc(sizeof(Nx2ThreadStart));
	if (!start)
		return ENOMEM;
	start->func = func;
	start->arg = arg;
	const int rc = __real___syscall_thread_create(thread, nx2ThreadTrampoline, start, stack_addr, stack_size);
	if (rc != 0)
		free(start);
	return rc;
}

static unsigned nx2CountLiveThreads(void)
{
	unsigned live = 0;
	mutexLock(&s_threadsMutex);
	for (int i = 0; i < NX2_MAX_TRACKED_THREADS; i++)
		live += s_threads[i].live;
	mutexUnlock(&s_threadsMutex);
	return live;
}

void nx2ExitReleaseLockLast(void)
{
	s_releaseExitLock = true;
}

static void nx2ExitCleanup(void)
{
	// (once: nx2ExitCleanupNow may already have run it)
	if (s_exitCleanupDone)
		return;
	s_exitCleanupDone = true;
	for (int waited = 0; waited < 1000 && nx2CountLiveThreads() != 0; waited += 10)
		svcSleepThread(10000000ull);

	const Handle current = threadGetCurHandle();
	mutexLock(&s_threadsMutex);
	for (int i = 0; i < NX2_MAX_TRACKED_THREADS; i++)
	{
		Nx2TrackedThread* entry = &s_threads[i];
		if (entry->live && entry->thread && entry->thread->handle != current)
		{
			// Never resumed: it must not run this program's code under the next one.
			u64 size = 0;
			// (the mirror covers the stack and libnx's TLS/reent page after it)
			if (envIsSyscallHinted(0x32) &&
				R_SUCCEEDED(svcSetThreadActivity(entry->thread->handle, ThreadActivity_Paused)) &&
				envIsSyscallHinted(0x05) && entry->mirror && nx2IsStackMirror(entry->mirror, &size))
				svcUnmapMemory(entry->mirror, entry->memory, size);
			memset(entry, 0, sizeof(*entry));
		}
		else if (!entry->live)
		{
			// Ended: libounce's _threadReleaseExited unmaps its stack and closes it after this runs (unmapping it
			// here made that fail and leaked the thread's handle).
			memset(entry, 0, sizeof(*entry));
		}
	}
	mutexUnlock(&s_threadsMutex);

	if (s_releaseExitLock)
	{
		s_releaseExitLock = false;
		appletUnlockExit();
	}
}

void nx2ExitCleanupNow(void)
{
	nx2ExitCleanup();
}

// Registered before any C++ static object is constructed, so it runs after their destructors: the last of this
// program's code before libnx's own teardown.
__attribute__((constructor(102))) static void nx2RegisterExitCleanup(void)
{
	atexit(nx2ExitCleanup);
}

// ------------------------------------------------------------------------------------------------ service lookups
// kaiHEN's SM proxy forwards every program's lookups on one shared SM session, and SM answers a lookup of a service
// nobody registered only once it is registered: such a lookup blocks that session, and every later program's
// lookups (hbmenu's included), until kaiHEN restarts. usb:hs is never answered, so it is refused here
// (-Wl,--wrap=smGetServiceWrapper).
Result __real_smGetServiceWrapper(Service* service_out, SmServiceName name);
Result __wrap_smGetServiceWrapper(Service* service_out, SmServiceName name);

Result __wrap_smGetServiceWrapper(Service* service_out, SmServiceName name)
{
	if (strncmp(name.name, "usb:hs", 6) == 0)
		return MAKERESULT(Module_Libnx, LibnxError_NotFound);
	return __real_smGetServiceWrapper(service_out, name);
}

u64 switch2PlatformCoreMask(void) { return nx2CoreMask(); }
void switch2PlatformDisplayInit(void) { nx2DisplayInit(); (void)nx2DisplayApply(1); }
int switch2PlatformRefreshRate(void) { return nx2DisplayRefreshRate(); }
Result switch2PlatformRestoreClock(void) { return nx2SetCpuBoost(false); }
// libounce now exposes VI2 layer release directly; no Mesa internals are needed.
Result switch2PlatformReleaseWindow(void)
{
	if (s_tvEventOpen) {
		eventClose(&s_tvEvent);
		s_tvEventOpen = false;
	}
	return nwindowReleaseVi2Layer(nwindowGetDefault());
}

#endif  // __SWITCH2__
