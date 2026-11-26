"""Regression tests for Switch 2 Nintendo controller prompts and 60+ FPS Drako3D performance."""

import io
import os
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "chupathingyce"))

from tools.console_build import ConsolePort
from tools.ninja_syntax import Writer


class Switch2PromptsAndPerfTests(unittest.TestCase):
    def test_engine_build_enables_game_browser_fonts_and_console_release_gates(self):
        import runpy

        mod = runpy.run_path(str(ROOT / "port/switch2/engine_build.py"))
        buf = io.StringIO()
        writer = Writer(buf)
        dummy_module = types.ModuleType("switch2_dummy")
        port = ConsolePort(ROOT / "port/switch2", dummy_module)
        sln = types.SimpleNamespace(
            port_release=True,
            console_no_debug_asserts=True,
            console_debug_tools=False,
            game_browser=True,
        )
        build_dir = Path("build/switch2")
        # Both engine_objects and platform_objects must honor sln gates.
        sig_engine = mod["engine_objects"].__code__.co_varnames[:mod["engine_objects"].__code__.co_argcount]
        self.assertIn("sln", sig_engine, "engine_objects must accept sln to pass console/release/browser defines")
        mod["engine_objects"](writer, port, build_dir, "-O2", "-Iinc", sln)
        mod["platform_objects"](writer, port, build_dir, "-O2", "-Iinc", True, sln)
        ninja_text = buf.getvalue()

        self.assertIn("-DHALO_GAME_BROWSER", ninja_text)
        self.assertIn("-DHALO_RELEASE", ninja_text)
        self.assertIn("-DHALO_CONSOLE_NO_DEBUG_ASSERTS", ninja_text)
        self.assertIn("-DHALO_CONSOLE_KEEP_ASSERTS", ninja_text)
        self.assertIn("ui_fonts.c", ninja_text)
        self.assertIn("server/src/", ninja_text)

    def test_switch2_build_uses_o2_optimization(self):
        build_py = (ROOT / "port/switch2/build.py").read_text(encoding="utf-8")
        self.assertNotIn('else "-O0"', build_py, "Switch 2 build must not fall back to -O0 on 700+ engine files")
        self.assertIn("-O2", build_py)

    def test_switch2_prompt_scheme_is_nintendo_from_boot_and_gameshare_is_switch_pro(self):
        bridge_text = (ROOT / "port/switch2/host/switch2_sdl3_bridge.c").read_text(encoding="utf-8")
        func_body = bridge_text.split("SDL_GamepadType SDL_GetGamepadType(", 1)[1].split("}", 1)[0]
        self.assertIn("SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO", func_body)

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "prompt_check.c"
            exe = Path(tmp) / "prompt_check"
            xinput_path = ROOT / "port/switch2/overrides/port/linux/src/xinput_sdl.c"
            if not xinput_path.is_file():
                xinput_path = ROOT / "port/switch/overrides/port/linux/src/xinput_sdl.c"
            if not xinput_path.is_file():
                xinput_path = ROOT / "chupathingyce/port/linux/src/xinput_sdl.c"
            xinput_lines = xinput_path.read_text(encoding="utf-8").splitlines()
            start = next(i for i, l in enumerate(xinput_lines) if "static int last_input_scheme" in l)
            end = next(i for i, l in enumerate(xinput_lines[start:], start) if l.startswith("static void mouse_poll"))
            snippet = "\n".join(xinput_lines[start:end])

            src.write_text(f"""
#include <assert.h>
#include <string.h>
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define HALO_SWITCH_CONSOLE 1
#define HALO_PROMPT_SCHEME_FUNCTIONS 1
#include "{ROOT / 'chupathingyce/port/linux/include/halo_prompt_schemes.h'}"

typedef void SDL_Gamepad;
enum {{
    SDL_GAMEPAD_TYPE_UNKNOWN = 0,
    SDL_GAMEPAD_TYPE_XBOX360 = 1,
    SDL_GAMEPAD_TYPE_PS3 = 3,
    SDL_GAMEPAD_TYPE_PS4 = 4,
    SDL_GAMEPAD_TYPE_PS5 = 5,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO = 6,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_LEFT = 7,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT = 8,
    SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_PAIR = 9,
}};
static int SDL_HasGamepad(void) {{ return 1; }}
static const char *SDL_getenv(const char *k) {{ (void)k; return NULL; }}
static int SDL_GetGamepadType(SDL_Gamepad *g) {{ (void)g; return SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO; }}
static unsigned int SDL_GetGamepadVendor(SDL_Gamepad *g) {{ (void)g; return 0x057e; }}
static unsigned int SDL_GetGamepadProduct(SDL_Gamepad *g) {{ (void)g; return 0x2009; }}
static int config_loaded_yet(void) {{ return 1; }}
static const char *config_string(const char *k) {{ (void)k; return ""; }}
static int config_boolean(const char *k) {{ (void)k; return 1; }}

{snippet}

int main(void) {{
    /* Before any input is seen on Switch 2, prompts must already be Nintendo (B=Select, A=Back), not Xbox! */
    assert(platform_input_scheme() == PROMPT_SCHEME_NINTENDO);
    assert(platform_prompt_scheme() == PROMPT_SCHEME_NINTENDO);
    return 0;
}}
""", encoding="utf-8")
            subprocess.run(["clang", "-std=c11", "-Wall", "-Werror", "-Wno-unused-function", str(src), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_docked_default_pacing_is_60hz_and_dk_success_warning_is_not_gpu_fault(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            inc = tmp_path / "inc"
            (inc / "switch2/memory").mkdir(parents=True)
            (inc / "switch/arm").mkdir(parents=True)
            (inc / "switch/arm/thread_context.h").write_text("#pragma once\n", encoding="utf-8")
            # Minimal switch.h / kaihen.h stubs to compile real nx2_platform.c and warthog_log.c on host
            (inc / "kaihen.h").write_text("#pragma once\n", encoding="utf-8")
            (inc / "drako3d.h").write_text("#pragma once\ntypedef int DkResult;\n#define DkResult_Success 0\n", encoding="utf-8")
            (inc / "deko3d.h").write_text('#pragma once\n#include "drako3d.h"\n', encoding="utf-8")
            (inc / "switch.h").write_text("""
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef int32_t s32;
typedef int64_t s64;
typedef u32 Result;
typedef u32 Handle;
#define CUR_PROCESS_HANDLE 0xFFFF8001u
#define CUR_THREAD_HANDLE  0xFFFF8000u
#define INVALID_HANDLE 0u
#define R_SUCCEEDED(r) ((r) == 0)
#define R_FAILED(r) ((r) != 0)
#define R_MODULE(r) (((r) & 0x1FFu))
#define R_DESCRIPTION(r) (((r) >> 9) & 0x1FFFu)
#define NX_NORETURN __attribute__((noreturn))
enum { InfoType_CoreMask = 0, AppletOperationMode_Handheld = 0, AppletOperationMode_Console = 1 };
enum { ApmCpuBoostMode_Normal = 0, ApmCpuBoostMode_FastLoad = 1 };
enum { ThreadActivity_Paused = 1, MemState_Type = 0xFF, MemType_MappedMemory = 6, Perm_R = 1 };
typedef struct { int dummy; } Mutex;
typedef struct { int dummy; } Event;
typedef struct { int dummy; } Service;
typedef struct { Handle handle; void *stack_mirror; void *stack_mem; } Thread;
typedef struct { int dummy; } NWindow;
typedef struct { u64 addr; u64 size; u32 type; u32 attr; u32 perm; } MemoryInfo;
typedef struct { u32 error_desc; struct { u64 x; } pc, lr, sp, far, fp; } ThreadExceptionDump;

extern int stub_operation_mode;
extern int stub_set_frame_rates_calls;
extern int stub_set_swap_interval_calls;
extern u32 stub_last_swap_interval;

static inline void mutexLock(Mutex *m) { (void)m; }
static inline void mutexUnlock(Mutex *m) { (void)m; }
static inline Result svcGetInfo(u64 *out, u32 type, Handle h, u64 id) {
    (void)type; (void)h; (void)id; *out = 0x3F; return 0;
}
static inline u64 appletGetAppletResourceUserId(void) { return 1; }
static inline Service *hidGetServiceSession(void) { static Service s; return &s; }
#define serviceDispatchIn(...) 0
static inline Result hidSetTouchScreenOutputRanges(u32 w, u32 h) { (void)w; (void)h; return 0; }
static inline Result appletSetCpuBoostMode(u32 mode) { (void)mode; return 0; }
static inline u32 appletGetOperationMode(void) { return (u32)stub_operation_mode; }
static inline Result appletGetDefaultDisplayResolutionChangeEvent(Event *e) { (void)e; return 1; }
static inline Result eventWait(Event *e, u64 t) { (void)e; (void)t; return 1; }
typedef struct { char name[8]; } SmServiceName;
#define MAKERESULT(m, d) (((m) & 0x1FFu) | (((d) & 0x1FFFu) << 9))
enum { Module_Libnx = 345, LibnxError_NotFound = 27 };
static inline void appletUnlockExit(void) {}
static inline void eventClear(Event *e) { (void)e; }
static inline void eventClose(Event *e) { (void)e; }
static inline Result nwindowReleaseVi2Layer(NWindow *w) { (void)w; return 0; }
static inline Result appletGetDefaultDisplayResolution(s32 *w, s32 *h) { *w = 1920; *h = 1080; return 0; }
static inline NWindow *nwindowGetDefault(void) { static NWindow w; return &w; }
static inline Result nwindowSetModeDimensions(NWindow *w, u32 hw, u32 hh, u32 dw, u32 dh) {
    (void)w; (void)hw; (void)hh; (void)dw; (void)dh; return 0;
}
static inline Result nwindowSetFrameRates(NWindow *w, u32 a, u32 b, bool c) {
    (void)w; (void)a; (void)b; (void)c; stub_set_frame_rates_calls++; return 0;
}
static inline Result nwindowSetSwapInterval(NWindow *w, u32 i) {
    (void)w; stub_set_swap_interval_calls++; stub_last_swap_interval = i; return 0;
}
static inline void nwindowGetDimensions(NWindow *w, u32 *ow, u32 *oh) { (void)w; *ow = 1920; *oh = 1080; }
static inline Result nwindowGetPresentInterval(NWindow *w, u16 *n, u16 *d) { (void)w; *n = 1; *d = 60; return 0; }
static inline bool envIsSyscallHinted(unsigned s) { (void)s; return false; }
static inline Result svcQueryMemory(MemoryInfo *m, u32 *p, u64 a) { (void)m; (void)p; (void)a; return 1; }
static inline Thread *threadGetSelf(void) { return NULL; }
static inline Handle threadGetCurHandle(void) { return 1; }
static inline void svcSleepThread(u64 ns) { (void)ns; }
static inline Result svcSetThreadActivity(Handle h, u32 a) { (void)h; (void)a; return 0; }
static inline Result svcUnmapMemory(void *a, void *b, u64 s) { (void)a; (void)b; (void)s; return 0; }
static inline Result svcSetThreadCoreMask(Handle h, s32 c, u64 m) { (void)h; (void)c; (void)m; return 0; }
static inline u64 svcGetSystemTick(void) { return 19200000ULL; }
""", encoding="utf-8")

            log_path = tmp_path / "warthog.log"
            harness = tmp_path / "harness.c"
            exe = tmp_path / "harness"
            warthog_log_src = (ROOT / "port/switch2/host/warthog_log.c").read_text(encoding="utf-8")
            warthog_log_patched = warthog_log_src.replace(
                '#define WARTHOG_LOG_PATH "sdmc:/switch/warthog/logs/warthog.log"',
                f'#define WARTHOG_LOG_PATH "{log_path}"'
            ).replace('mkdir("sdmc:/switch", 0777);', "").replace(
                'mkdir(WARTHOG_DIR, 0777);', ""
            ).replace('mkdir(WARTHOG_LOG_DIR, 0777);', "")
            log_hdr = (ROOT / "port/switch2/host/warthog_log.h").read_text(encoding="utf-8").replace(
                '__asm__("adrp %0, __start__\\n\\tadd %0, %0, :lo12:__start__" : "=r"(base));',
                "base = 0x10000u;"
            )
            (inc / "warthog_log.h").write_text(log_hdr, encoding="utf-8")
            patched_log_c = tmp_path / "warthog_log_test.c"
            patched_log_c.write_text(warthog_log_patched.replace('#include <warthog_log.h>', '#include <warthog_log.h>'), encoding="utf-8")

            harness.write_text("""
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "switch.h"
#include "deko3d.h"
#include "nx2_platform.h"
#include <warthog_log.h>

int stub_operation_mode = AppletOperationMode_Console; /* Docked */
int stub_set_frame_rates_calls = 0;
int stub_set_swap_interval_calls = 0;
u32 stub_last_swap_interval = 99;

void __real_hidInitializeTouchScreen(void) {}
Result __real_smGetServiceWrapper(Service *s, SmServiceName n) { (void)s; (void)n; return 0; }
struct __pthread_t;
int __real___syscall_thread_create(struct __pthread_t **t, void *(*f)(void *), void *a, void *s, size_t sz) {
    (void)t; (void)f; (void)a; (void)s; (void)sz; return 0;
}
void NX_NORETURN __real_diagAbortWithResult(Result r) { (void)r; abort(); }
void __real_abort(void) { exit(1); }
void NX_NORETURN __real_svcBreak(u32 a, uintptr_t b, uintptr_t c) { (void)a; (void)b; (void)c; abort(); }
char __executable_start[1];
int host_dk_presenting = 0;
void warthog_dk_debug_callback(void *user_data, const char *context, DkResult result, const char *message);

int main(void) {
    /* 1. Docked default must pace at 60 Hz via SwapInterval(1), NOT SetFrameRates(120Hz)! */
    nx2DisplayInit();
    nx2DisplayApply(1);
    nx2DisplayUpdate();
    assert(stub_set_frame_rates_calls == 0);
    assert(stub_set_swap_interval_calls >= 1);
    assert(stub_last_swap_interval == 1);

    /* Enabling 120 Hz mode explicitly requests SetFrameRates */
    assert(nx2DisplaySetFrameGeneration(true));
    nx2DisplayApply(1);
    assert(stub_set_frame_rates_calls >= 1);

    /* 2. DkResult_Success (0) warning must NOT emit FAULT_KIND: GPU_FAULT */
    warthog_log_open();
    warthog_dk_debug_callback(NULL, "dkQueuePresentImage", DkResult_Success, "non-fatal warning");
    warthog_log_close();
    return 0;
}
""", encoding="utf-8")
            subprocess.run([
                "clang", "-std=gnu11", "-D__SWITCH2__=1",
                "-I", str(inc), "-I", str(ROOT / "port/switch2/host"),
                str(harness),
                str(ROOT / "port/switch2/host/nx2_platform.c"),
                str(ROOT / "port/switch2/host/switch2_display.c"),
                str(patched_log_c),
                "-o", str(exe),
            ], check=True)
            subprocess.run([str(exe)], check=True)
            written = log_path.read_text(encoding="utf-8") if log_path.is_file() else ""
            self.assertNotIn("FAULT_KIND: GPU_FAULT", written)

    def test_six_core_affinity_separates_game_render_and_worker_cores(self):
        bridge_src = (ROOT / "port/switch2/host/switch2_host_bridge.c").read_text(encoding="utf-8")
        # Must not unconditionally break on the first helper core (core 1) for every worker thread.
        self.assertIn("host_thread_place_on_render_core", bridge_src)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "cores.c"
            exe = tmp_path / "cores"
            helper_body = bridge_src.split("void host_thread_place_on_render_core", 1)[1].split(
                "void host_debug_thread_backtrace", 1
            )[0]
            src.write_text(f"""
#include <assert.h>
#include <stdint.h>
typedef uint64_t u64;
typedef int32_t s32;
typedef uint32_t Handle;
#define CUR_THREAD_HANDLE 0xFFFF8000u
static u64 nx2CoreMask(void) {{ return 0x3FULL; }}
static s32 last_ideal = -1;
static u64 last_mask = 0;
static int svcSetThreadCoreMask(Handle h, s32 ideal, u64 mask) {{
    (void)h; last_ideal = ideal; last_mask = mask; return 0;
}}
void host_thread_place_on_render_core{helper_body}
int main(void) {{
    host_thread_place_on_render_core();
    assert(last_ideal == 1 && last_mask == (1ULL << 1));
    u64 seen_ideals = 0;
    for (int i = 0; i < 4; ++i) {{
        host_thread_place_on_helper_core();
        assert(last_mask == 0x3CULL);
        assert(last_ideal >= 2 && last_ideal <= 5);
        seen_ideals |= (1ULL << last_ideal);
    }}
    assert(seen_ideals == 0x3CULL);
    return 0;
}}
""", encoding="utf-8")
            subprocess.run(["clang", "-std=gnu11", "-Wall", "-Werror", str(src), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_switch2_window_chunks_batch_mmap_without_drako3d_borrowed_heap_abort(self):
        xbox_mem = (ROOT / "port/switch2/overrides/port/linux/src/xbox_memory.c").read_text(encoding="utf-8")
        host_dk = (ROOT / "port/switch/host/host_dk.c").read_text(encoding="utf-8")
        self.assertIn("SWITCH2_CONTIGUOUS_CHUNK_SIZE", xbox_mem)
        chunk_fn = host_dk.split("static void chunk_block_make(", 1)[1].split("void host_dk_window_chunk_committed", 1)[0]
        switch2_branch = chunk_fn.split("#ifdef __SWITCH2__", 1)[1].split("#else", 1)[0]
        self.assertNotIn(
            "memory_block(",
            switch2_branch,
            "Switch 2 chunk_block_make must not pass svcMapMemory-borrowed heap or alias chunks to dkMemBlockCreate",
        )
        self.assertNotIn("switch2_mman_heap_backing", switch2_branch)

    def test_switch2_menus_have_unique_widget_names_and_no_duplicate_interpolation(self):
        import xml.etree.ElementTree as ET

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "menus"
            subprocess.run(
                [sys.executable, str(ROOT / "tools/switch_menus.py"), "--out", str(out_dir), "--target", "switch2"],
                check=True,
            )
            written = sorted(out_dir.rglob("*.xml"))
            self.assertGreater(len(written), 0)
            video_xml = None
            for xml_path in written:
                tree = ET.parse(xml_path)
                seen = set()
                duplicates = []
                for elem in tree.iter("widget"):
                    name = elem.attrib.get("name")
                    if name:
                        if name in seen:
                            duplicates.append(name)
                        seen.add(name)
                self.assertEqual(
                    duplicates,
                    [],
                    f"{xml_path.name} contains duplicate widget names {duplicates}, causing engine to reject custom menus",
                )
                if xml_path.name.endswith("video_settings.xml"):
                    video_xml = seen
            self.assertIsNotNone(video_xml)
            interp_widgets = [w for w in video_xml if w.endswith("/op_interpolation")]
            self.assertEqual(len(interp_widgets), 1)

    def test_sdl_rename_path_overwrites_existing_target_when_rename_refuses_clobber(self):
        headless_src = (ROOT / "port/switch2/host/switch2_sdl_headless.c").read_text(encoding="utf-8")
        rename_fn = "bool SDL_RenamePath(" + headless_src.split("bool SDL_RenamePath(", 1)[1].split("bool SDL_RemovePath(", 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / "rename_test.c"
            exe = tmp_path / "rename_test"
            src.write_text(f"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

static char last_err[128];
static void headless_set_error(const char *msg) {{
    snprintf(last_err, sizeof(last_err), "%s", msg ? msg : "");
}}

/* Simulate Horizon OS fsdev sdmc: fsFsRenameFile, which fails with EEXIST when destination exists. */
static int horizon_rename(const char *old_path, const char *new_path) {{
    struct stat st;
    if (stat(new_path, &st) == 0) {{
        errno = EEXIST;
        return -1;
    }}
    return rename(old_path, new_path);
}}
#define rename horizon_rename

{rename_fn}

int main(int argc, char **argv) {{
    assert(argc == 3);
    const char *tmp_cfg = argv[1];
    const char *dst_cfg = argv[2];
    assert(SDL_RenamePath(tmp_cfg, dst_cfg));
    FILE *f = fopen(dst_cfg, "rb");
    assert(f != NULL);
    char buf[64] = {{0}};
    size_t n = fread(buf, 1, sizeof(buf) - 1, f);
    fclose(f);
    assert(n > 0);
    assert(strcmp(buf, "updated=true\\n") == 0);
    return 0;
}}
""", encoding="utf-8")
            subprocess.run(["clang", "-std=gnu11", "-Wall", "-Werror", str(src), "-o", str(exe)], check=True)
            old_file = tmp_path / "config.toml.new"
            new_file = tmp_path / "config.toml"
            new_file.write_text("updated=false\n", encoding="utf-8")
            old_file.write_text("updated=true\n", encoding="utf-8")
            subprocess.run([str(exe), str(old_file), str(new_file)], check=True)

    def test_warthog_log_32k_exception_stack_reuses_fd_and_flushes_startup_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            inc = tmp_path / "inc"
            (inc / "switch/arm").mkdir(parents=True)
            (inc / "switch/arm/thread_context.h").write_text("#pragma once\n", encoding="utf-8")
            (inc / "drako3d.h").write_text("#pragma once\ntypedef int DkResult;\n#define DkResult_Success 0\n", encoding="utf-8")
            (inc / "switch.h").write_text("""
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef uint32_t Result;
typedef int DkResult;
#define DkResult_Success 0
#define R_FAILED(r) ((r) != 0)
#define R_MODULE(r) ((r) & 0x1FFu)
#define R_DESCRIPTION(r) (((r) >> 9) & 0x1FFFu)
#define NX_NORETURN __attribute__((noreturn))
enum { Perm_R = 1 };
typedef struct { u64 addr; u64 size; u32 type; u32 attr; u32 perm; } MemoryInfo;
typedef struct { u32 error_desc; struct { u64 x; } pc, lr, sp, far, fp; } ThreadExceptionDump;
static inline Result svcQueryMemory(MemoryInfo *m, u32 *p, u64 a) { (void)m; (void)p; (void)a; return 1; }
static inline u64 svcGetSystemTick(void) { return 38400000ULL; }
""", encoding="utf-8")
            log_path = tmp_path / "warthog.log"
            log_hdr = (ROOT / "port/switch2/host/warthog_log.h").read_text(encoding="utf-8").replace(
                '__asm__("adrp %0, __start__\\n\\tadd %0, %0, :lo12:__start__" : "=r"(base));',
                "base = 0x8000000ULL;"
            )
            (inc / "warthog_log.h").write_text(log_hdr, encoding="utf-8")
            warthog_log_src = (ROOT / "port/switch2/host/warthog_log.c").read_text(encoding="utf-8")
            warthog_log_patched = (
                warthog_log_src
                .replace('#define WARTHOG_LOG_DIR WARTHOG_DIR "/logs"', f'#define WARTHOG_LOG_DIR "{tmp_path}"')
                .replace('mkdir("sdmc:/switch", 0777);', "")
                .replace("mkdir(WARTHOG_DIR, 0777);", "")
                .replace("mkdir(WARTHOG_LOG_DIR, 0777);", "")
                .replace(" open(WARTHOG_LOG_PATH,", " tracked_open(WARTHOG_LOG_PATH,")
                .replace("= open(WARTHOG_LOG_PATH,", "= tracked_open(WARTHOG_LOG_PATH,")
            )
            patched_c = tmp_path / "warthog_log_patched.c"
            patched_c.write_text(
                "extern int tracked_open(const char *path, int flags, ...);\n" + warthog_log_patched,
                encoding="utf-8",
            )
            harness = tmp_path / "exc_harness.c"
            exe = tmp_path / "exc_harness"
            harness.write_text(f"""
#include <assert.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include "switch.h"
#include "warthog_log.h"

extern u8 __nx_exception_stack[];
extern u64 __nx_exception_stack_size;
int host_dk_presenting = 0;
static int disallow_open = 0;

int tracked_open(const char *path, int flags, ...) {{
    if (disallow_open)
        return -1; /* On 1 KiB exception stack or contended fsdev lock, open() fails/overflows! */
    va_list ap;
    va_start(ap, flags);
    int mode = va_arg(ap, int);
    va_end(ap);
    return open(path, flags, mode);
}}

void NX_NORETURN __real_diagAbortWithResult(Result r) {{ (void)r; _exit(2); }}
void __real_abort(void) {{ _exit(3); }}
void NX_NORETURN __real_svcBreak(u32 a, uintptr_t b, uintptr_t c) {{ (void)a; (void)b; (void)c; _exit(4); }}
void __libnx_exception_handler(ThreadExceptionDump *ctx);

int main(void) {{
    /* 1. Strong exception stack >= 32 KiB must override libounce's 1 KiB weak stack */
    assert(__nx_exception_stack_size >= 0x8000ULL);
    __nx_exception_stack[0] = 0xAA;
    __nx_exception_stack[__nx_exception_stack_size - 1] = 0x55;

    assert(warthog_log_open());
    /* 2. Before presenting starts, INFO lines must be flushed immediately */
    warthog_log("INFO", "deko3d: device ready, presenting at 1920x1080");
    FILE *check = fopen("{log_path}", "rb");
    assert(check != NULL);
    char buf[512] = {{0}};
    fread(buf, 1, sizeof(buf) - 1, check);
    fclose(check);
    assert(strstr(buf, "deko3d: device ready, presenting at 1920x1080") != NULL);

    /* Once steady-state presenting starts, WARN still flushes immediately */
    warthog_log_set_presenting(true);
    warthog_log("WARN", "steady-state warning line");
    check = fopen("{log_path}", "rb");
    assert(check != NULL);
    memset(buf, 0, sizeof(buf));
    fread(buf, 1, sizeof(buf) - 1, check);
    fclose(check);
    assert(strstr(buf, "steady-state warning line") != NULL);

    /* 3. CPU exception handler must write FAULT_KIND: CPU_EXCEPTION using pre-opened fd without open() */
    disallow_open = 1;
    ThreadExceptionDump dump = {{0}};
    dump.error_desc = 0x101;
    dump.pc.x = 0x80b8e2cULL;
    dump.lr.x = 0x80b8e10ULL;
    __libnx_exception_handler(&dump);

    check = fopen("{log_path}", "rb");
    assert(check != NULL);
    memset(buf, 0, sizeof(buf));
    fread(buf, 1, sizeof(buf) - 1, check);
    fclose(check);
    assert(strstr(buf, "FAULT_KIND: CPU_EXCEPTION") != NULL);
    assert(strstr(buf, "0x00000000080b8e2c") != NULL);
    return 0;
}}
""", encoding="utf-8")
            subprocess.run(
                ["clang", "-std=gnu11", "-I", str(inc), str(harness), str(patched_c), "-o", str(exe)],
                check=True,
            )
            subprocess.run([str(exe)], check=True)

    def test_switch2_o2_codegen_aliasing_null_checks_and_pthread_stack_floor(self):
        # 1. build.py code_flags must include -fno-strict-aliasing -fno-delete-null-pointer-checks
        #    so GCC 15 at -O2 does not emit brk #0x3e8 traps or break C struct aliasing in host/mbedtls units.
        build_py = (ROOT / "port/switch2/build.py").read_text(encoding="utf-8")
        self.assertIn("-fno-strict-aliasing", build_py)
        self.assertIn("-fno-delete-null-pointer-checks", build_py)

        # 2. __wrap___syscall_thread_create must enforce >= 512 KiB stack floor when stack_addr == NULL
        nx2_src = (ROOT / "port/switch2/host/nx2_platform.c").read_text(encoding="utf-8")
        wrap_fn = nx2_src.split("int __wrap___syscall_thread_create(", 1)[1].split("static unsigned nx2CountLiveThreads", 1)[0]
        self.assertIn("0x80000", wrap_fn, "Default libounce 128 KiB pthread stack must be raised to >= 512 KiB")

    def test_per_page_memory_watch_isolates_unprotected_dynamic_writes(self):
        src_text = (ROOT / "port/switch2/host/switch2_headless_platform.c").read_text(encoding="utf-8")
        mw_section = src_text.split("#define SWITCH2_WATCH_PAGE_SIZE", 1)[1].split(
            "#ifndef HALO_SWITCH2_GRAPHICAL", 1
        )[0]
        mw_code = "#define SWITCH2_WATCH_PAGE_SIZE" + mw_section
        with tempfile.TemporaryDirectory() as tmp:
            harness = Path(tmp) / "mw_test.c"
            exe = Path(tmp) / "mw_test"
            harness.write_text(f"""
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#define PLATFORM_CONTIGUOUS_BASE 0x80000000ULL
#define PLATFORM_CONTIGUOUS_SIZE 0x20000000ULL
#define PLATFORM_CONTIGUOUS_MAXIMUM 0x20000000ULL
static unsigned char backing_sim[0x10000];
#define XBOX_ADDRESS_SPACE_BASE ((uintptr_t)backing_sim - PLATFORM_CONTIGUOUS_BASE)
{mw_code}
int main(void) {{
    void *dyn_vb_host = (void *)((uintptr_t)XBOX_ADDRESS_SPACE_BASE + PLATFORM_CONTIGUOUS_BASE + 0x1000ULL);
    unsigned long tex_addr = (unsigned long)(PLATFORM_CONTIGUOUS_BASE + 0x4000UL);
    void *tex_host = (void *)((uintptr_t)XBOX_ADDRESS_SPACE_BASE + (uintptr_t)tex_addr);

    memory_watch_initialize();
    memory_watch_protect(tex_addr, 0x2000UL);
    unsigned long serial0 = memory_watch_serial();
    unsigned long gen0 = memory_watch_generation(tex_addr, 0x2000UL);

    /* Unprotected dynamic VB/IB writes must NOT bump global serial or texture page generation */
    memory_watch_prepare_write(dyn_vb_host, 0x1000UL);
    assert(memory_watch_serial() == serial0);
    assert(memory_watch_generation(tex_addr, 0x2000UL) == gen0);

    /* Writing directly to the protected texture page bumps its generation and global serial */
    memory_watch_prepare_write(tex_host, 0x1000UL);
    unsigned long serial1 = memory_watch_serial();
    unsigned long gen1 = memory_watch_generation(tex_addr, 0x2000UL);
    assert(serial1 > serial0);
    assert(gen1 > gen0);

    /* Re-protecting and writing only to dyn_vb_host again stays isolated */
    memory_watch_protect(tex_addr, 0x2000UL);
    memory_watch_prepare_write(dyn_vb_host, 0x1000UL);
    assert(memory_watch_serial() == serial1);
    assert(memory_watch_generation(tex_addr, 0x2000UL) == gen1);

    /* Forgetting dyn_vb bumps only dyn_vb's page, NOT tex_addr */
    memory_watch_forget(dyn_vb_host, 0x1000UL);
    assert(memory_watch_generation(tex_addr, 0x2000UL) == gen1);
    assert(memory_watch_generation((unsigned long)(PLATFORM_CONTIGUOUS_BASE + 0x1000UL), 0x1000UL) > gen1);
    return 0;
}}
""", encoding="utf-8")
            subprocess.run(["clang", "-std=gnu11", "-Wall", "-Werror", str(harness), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_switch2_menus_xml_has_unique_widget_names_and_hrtf_defaults_off(self):
        import xml.etree.ElementTree as ET
        sys.path.insert(0, str(ROOT / "tools"))
        import switch_menus

        generated = switch_menus.files("switch2")
        for rel, lines in generated.items():
            xml_text = "\n".join(lines)
            root = ET.fromstring(xml_text)
            seen = set()
            for elem in root.iter("widget"):
                name = elem.attrib.get("name")
                if name:
                    self.assertNotIn(name, seen, f"Duplicate widget {name} in {rel}")
                    seen.add(name)

        port_cfg = (ROOT / "port/switch2/overrides/port/linux/src/port_config.c").read_text(encoding="utf-8")
        self.assertIn("defined(HALO_SWITCH_CONSOLE)", port_cfg)
        self.assertIn('#define DEFAULT_AUDIO_HRTF "\\"off\\""', port_cfg)

    def test_hud_and_widget_overrides_map_nintendo_buttons(self):
        for rel in ("source/interface/hud_messaging.c", "source/interface/ui_widget.c"):
            src = (ROOT / "port/switch2/overrides" / rel).read_text(encoding="utf-8")
            self.assertIn("switch2_nintendo_ui_button", src)
            self.assertIn("platform_prompt_scheme() != 3", src)
            self.assertIn("ui_overlay_button(", src)
            for token in (
                "_icon_a_button", "_icon_b_button", "_icon_x_button", "_icon_y_button",
                "_icon_black_button", "_icon_white_button",
                "_icon_left_trigger", "_icon_right_trigger",
                "_icon_start_button", "_icon_back_button",
            ):
                self.assertIn(token, src)

    def test_host_dk_disables_hw_compression_and_adds_upload_rollover(self):
        dk_src = (ROOT / "port/switch/host/host_dk.c").read_text(encoding="utf-8")
        self.assertIn("_Static_assert(DkInvalidateFlags_L2Cache == (1u << 4)", dk_src)
        self.assertIn("upload_memory_roll", dk_src)
        self.assertIn("tex.descriptors_dirty", dk_src)
        self.assertIn("dk.viewport_dirty", dk_src)
        target_fn = dk_src.split("static struct target *target_get(", 1)[1].split("static void fence_wait_said", 1)[0]
        switch2_branch = target_fn.split("#ifdef __SWITCH2__", 1)[1].split("#else", 1)[0]
        self.assertNotIn("DkImageFlags_HwCompression", switch2_branch)

    def test_dynamic_index_buffer_tracked_inline_and_post_blit_barrier(self):
        res_src = (ROOT / "port/switch2/overrides/port/linux/src/d3d8_resources.c").read_text(encoding="utf-8")
        self.assertIn("d3d8_index_buffer_contains", res_src)
        self.assertIn("index_buffer_track_add(memory, length ? length : 1);", res_src)
        self.assertIn("index_buffer_track_remove(memory);", res_src)

        d3d_dk_src = (ROOT / "port/switch/guest/d3d8_dk.c").read_text(encoding="utf-8")
        indices_fn = d3d_dk_src.split("static BOOL indices_fixed(", 1)[1].split("static void draw_write(", 1)[0]
        self.assertIn("d3d8_index_buffer_contains(indices, (size_t)count * sizeof(WORD))", indices_fn)
        draw_fn = d3d_dk_src.split("static void draw_write(", 1)[1].split("void WINAPI D3DDevice_DrawVertices(", 1)[0]
        self.assertIn("stream_flush();", draw_fn)
        self.assertIn("host_dk_idle();", draw_fn)

        dk_src = (ROOT / "port/switch/host/host_dk.c").read_text(encoding="utf-8")
        present_fn = dk_src.split("static void present(", 1)[1].split("static void commands_submit_record(", 1)[0]
        if "static void " in present_fn:
            present_fn = present_fn.split("static void ", 1)[0]
        self.assertIn("barrier(DkBarrier_Full, 0);", present_fn)

    def test_switch2_nmouse_fractional_accumulation_and_off_mode(self):
        nmouse_src = ROOT / "port/switch2/host/switch2_text_nmouse.c"
        nmouse_hdr = ROOT / "port/switch2/host/switch2_text_nmouse.h"
        with tempfile.TemporaryDirectory() as tmp:
            harness = Path(tmp) / "nmouse_test.c"
            exe = Path(tmp) / "nmouse_test"
            harness.write_text("""
#include <assert.h>
#include "switch2_text_nmouse.h"
int main(void) {
    struct switch2_nmouse_processor proc;
    struct switch2_nmouse_motion m;
    float ax = 0.0f, ay = 0.0f;
    switch2_nmouse_processor_init(&proc);
    proc.settings.sensitivity_x = 0.5f;
    proc.settings.sensitivity_y = 0.5f;
    proc.settings.invert_y = 1;
    assert(switch2_nmouse_process_accum(&proc, 1, 1, 2, 0, SWITCH2_NMOUSE_AUTO, &ax, &ay, &m) == 1);
    assert(m.xrel == 0 && m.yrel == -1);
    assert(switch2_nmouse_process_accum(&proc, 2, 1, 1, 0, SWITCH2_NMOUSE_AUTO, &ax, &ay, &m) == 1);
    assert(m.xrel == 1 && m.yrel == 0);
    assert(switch2_nmouse_process_accum(&proc, 3, 10, 10, 1, SWITCH2_NMOUSE_OFF, &ax, &ay, &m) == 0);
    assert(m.xrel == 0 && m.yrel == 0 && m.buttons == 0);
    return 0;
}
""", encoding="utf-8")
            subprocess.run(["clang", "-std=gnu11", "-Wall", "-Werror", "-I", str(nmouse_hdr.parent),
                            str(harness), str(nmouse_src), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_switch2_menus_contain_gyro_nmouse_and_refresh_options(self):
        import xml.etree.ElementTree as ET
        sys.path.insert(0, str(ROOT / "tools"))
        import switch_menus

        switch2_files = switch_menus.files("switch2")
        switch1_files = switch_menus.files("switch")
        for target_name, generated in (("switch2", switch2_files), ("switch", switch1_files)):
            for rel, lines in generated.items():
                root = ET.fromstring("\n".join(lines))
                seen = set()
                for elem in root.iter("widget"):
                    name = elem.attrib.get("name")
                    if name:
                        self.assertNotIn(name, seen, f"Duplicate widget {name} in {target_name}/{rel}")
                        seen.add(name)

        controls_xml = "\n".join(switch2_files[switch_menus.CONTROLS])
        for token in (
            "GYRO",
            "JOY-CON MOUSE",
            "input.gyro_zoom_sensitivity",
            "input.joycon_mouse",
            "input.joycon_mouse_sensitivity",
            "input.joycon_mouse_vertical_sensitivity",
            "input.joycon_mouse_zoom_sensitivity",
            "input.joycon_mouse_invert_y",
            "input.joycon_mouse_aim_assist",
        ):
            self.assertIn(token, controls_xml)

        video_xml = "\n".join(switch2_files[switch_menus.VIDEO])
        for token in ("display.refresh_rate", "display.max_fps", "display.vsync"):
            self.assertIn(token, video_xml)
        self.assertNotRegex(video_xml, r"4K\s*120|4K120")

    def test_switch2_120hz_policy_and_nmouse_prompt_preservation(self):
        nx2_src = (ROOT / "port/switch2/host/nx2_platform.c").read_text(encoding="utf-8")
        self.assertIn("nx2DisplaySetRefreshRate", nx2_src)
        dk_src = (ROOT / "port/switch/host/host_dk.c").read_text(encoding="utf-8")
        swapchain_fn = dk_src.split("static void swapchain_make(void)", 1)[1].split("static void swapchain_remake(", 1)[0]
        self.assertIn("nx2DisplayReapply();", swapchain_fn)
        sdl2_src = (ROOT / "port/switch/host/host_sdl2.c").read_text(encoding="utf-8")
        self.assertIn("nx2DisplayApply(interval);", sdl2_src)
        xinput_src = (ROOT / "port/switch2/overrides/port/linux/src/xinput_sdl.c").read_text(encoding="utf-8")
        self.assertIn("!platform_mouse_is_nmouse()", xinput_src)


if __name__ == "__main__":
    unittest.main()
