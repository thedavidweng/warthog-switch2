"""Checks for the shared renderer's Switch 2 memory boundary."""

import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MainMenuLinkTest(unittest.TestCase):
    def test_main_menu_link_and_audit(self):
        build = ROOT / "scripts/switch2/build.sh"
        subprocess.run([str(build), "configure"], cwd=ROOT, check=True, capture_output=True)
        subprocess.run([str(build), "ninja", "switch2"], cwd=ROOT, check=True, capture_output=True)
        subprocess.run([str(build), "audit"], cwd=ROOT, check=True, capture_output=True)
        out = ROOT / "build/switch2"
        self.assertTrue((out / "warthog.nro").is_file())
        self.assertTrue((out / "warthog.elf").is_file())
        linkmap = (out / "warthog.elf.map").read_text()
        for name in ("libSDL2_host.a", "libdrako3dd.a", "libuam2rt.a",
                     "d3d8_dk.o", "nv2a_vsh_dk.o", "nv2a_psh_dk.o",
                     "host_dk.c.o", "host_sdl2.c.o", "host_sdl3_events.c.o"):
            self.assertIn(name, linkmap)
        for name in ("libEGL.a", "libGLESv2.a", "libglapi.a", "libdrm_nouveau.a",
                     "/opt/devkitpro/libnx/"):
            self.assertNotIn(name, linkmap)
        result = subprocess.run(
            [str(build), "/opt/devkitpro/devkitA64/bin/aarch64-none-elf-nm",
             "--defined-only", "build/switch2/warthog.elf"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        symbols = {line.split()[-1] for line in result.stdout.splitlines() if line.split()}
        self.assertTrue({"halo_main", "D3DDevice_Present", "host_dk_submit", "host_dk_shutdown",
                         "SDL_OpenAudioDeviceStream", "sdl2_host_SDL_Init"} <= symbols)
        undef = subprocess.run(
            [str(build), "/opt/devkitpro/devkitA64/bin/aarch64-none-elf-nm",
             "-u", "build/switch2/platform/port/linux/src/sdl_platform.o"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        gl_undef = sorted({line.split()[-1] for line in undef.stdout.splitlines()
                           if line.split() and line.split()[-1].startswith("halo_gl")})
        self.assertEqual(gl_undef, [])


class RendererAddressTest(unittest.TestCase):
    def test_command_addresses_follow_platform_abi(self):
        guest = ROOT / "port/switch/guest"
        for flags, expected in (([], "4"), (["-D__SWITCH2__"], "sizeof(uintptr_t)")):
            subprocess.run(
                ["clang", "-x", "c", "-fsyntax-only", "-I", str(guest), *flags, "-"],
                input=('#include "dk_commands.h"\n'
                       f'_Static_assert(sizeof(dk_addr_t) == {expected}, "address width");\n'
                       '_Static_assert(sizeof(((struct dk_command_texture *)0)->source) == sizeof(dk_addr_t), "texture");\n'
                       '_Static_assert(sizeof(((struct dk_command_draw *)0)->index_address) == sizeof(dk_addr_t), "index");\n'
                       '_Static_assert(sizeof(((struct dk_hud_sheet *)0)->png) == sizeof(dk_addr_t), "png");\n'
                       '_Static_assert(sizeof(((struct dk_surface *)0)->data) == 4, "Xbox offset");\n'),
                text=True, check=True, capture_output=True,
            )


class SharedRendererTest(unittest.TestCase):
    def test_build_selects_shared_renderer(self):
        source = (ROOT / "port/switch2/engine_build.py").read_text()
        for name in ("d3d8_dk.c", "dk_shaders.c", "nv2a_psh_dk.c", "nv2a_vsh_dk.c",
                     "ui_overlay_dk.c", "xbox_textures_dk.c", "guest_sdl_switch.c"):
            self.assertIn(name, source)
        self.assertIn("OPENGL_ONLY", source)

    def test_switch2_presentation_and_descriptor_invalidation(self):
        source = (ROOT / "port/switch/host/host_dk.c").read_text()
        self.assertFalse((ROOT / "port/switch2/host/host_dk.c").exists())
        self.assertIn("output_height = SCREEN_FULL_HEIGHT;", source)
        self.assertIn("DkInvalidateFlags_Descriptors", source)
        self.assertIn("VI2 swapchain images cannot use hardware compression", source)

    def test_uam2_compiles_probe_shaders(self):
        probe = ROOT / "port/switch2/probe"
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            directory = Path(tmp)
            for stage in ("vert", "frag"):
                shutil.copyfile(probe / f"warthog.{stage}", directory / f"shader.{stage}")
                subprocess.run(
                    ["docker", "run", "--rm", "-v", f"{directory}:/work",
                     "warthog-switch2-toolchain:local", "uam2", "-s", stage,
                     "-o", f"/work/shader.{stage}.dksh", f"/work/shader.{stage}"],
                    check=True,
                )
                self.assertEqual((directory / f"shader.{stage}.dksh").read_bytes()[:4], b"DKSH")


class RendererBackingTest(unittest.TestCase):
    def test_backing_lookup_requires_one_committed_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "check.c"
            source.write_text(r"""
#include <assert.h>
#include <stdint.h>
#include <sys/mman.h>
#include "switch2_mman.h"
int main(void) {
    assert(switch2_mman_init());
    char *p = (char *)(uintptr_t)(xbox_address_space_base + SWITCH2_XBOX_WINDOW_LOW);
    assert(mmap(p, 4096, PROT_READ | PROT_WRITE, MAP_FIXED, -1, 0) == p);
    char *backing = switch2_mman_heap_backing((uintptr_t)p, 4096);
    assert(backing && !((uintptr_t)backing % 4096));
    assert(switch2_mman_heap_backing((uintptr_t)p + 10, 100) == backing + 10);
    assert(!switch2_mman_heap_backing((uintptr_t)p, 8192));
    assert(mmap(p + 4096, 4096, PROT_READ | PROT_WRITE, MAP_FIXED, -1, 0) == p + 4096);
    assert(!switch2_mman_heap_backing((uintptr_t)p, 8192));
    assert(!switch2_mman_heap_backing(0, 4096));
    switch2_mman_shutdown();
    assert(!switch2_mman_heap_backing((uintptr_t)p, 1));
    return 0;
}
""")
            host = ROOT / "port/switch2/host"
            executable = directory / "check"
            subprocess.run(["clang", "-I", str(host), str(host / "switch2_mman.c"),
                            str(source), "-pthread", "-o", str(executable)], check=True)
            subprocess.run([str(executable)], check=True)

class Switch2VideoSwapWithoutOpenGLTest(unittest.TestCase):
    def test_standin_gl_context_swap_does_not_call_unloaded_gl_pointers(self):
        import os
        import runpy
        import sys

        for entry in (str(ROOT), str(ROOT / "chupathingyce")):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        from tools.lp64_rewrite import read as lp64_read, rewrite as lp64_rewrite

        engine_build = runpy.run_path(str(ROOT / "port/switch2/engine_build.py"))
        sdl_include = engine_build["fetch_sdl_headers"](ROOT / "build/switch2")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            lp64 = directory / "lp64"
            game = ROOT / "chupathingyce"
            for rel_dir in ("port/linux/src", "port/linux/include", "port/include", "port/include/xdk", "source/cseries"):
                out_dir = lp64 / rel_dir
                out_dir.mkdir(parents=True, exist_ok=True)
                for src in (game / rel_dir).glob("*.h"):
                    (out_dir / src.name).write_text(lp64_rewrite(lp64_read(src)), encoding="latin-1")
            for src_path, dst_rel in (
                (ROOT / "port/switch2/overrides/port/linux/src/sdl_platform.c", "port/linux/src/sdl_platform.c"),
                (game / "port/linux/src/gl_functions.c", "port/linux/src/gl_functions.c"),
            ):
                (lp64 / dst_rel).write_text(lp64_rewrite(lp64_read(src_path)), encoding="latin-1")
            harness = directory / "harness.c"
            harness.write_text(r"""
#include <assert.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <SDL3/SDL.h>
#include "platform.h"
#include "sdl_platform.h"

static int swap_count;
static int dummy_window;

void build_identity_log(void) {}
void console_setup_start(void) {}
void console_setup_after_data(const char *root) { (void)root; }
const char *platform_data_root(void) { return "/tmp"; }
void platform_maps_folder_check(struct platform_maps_folder *maps) { memset(maps, 0, sizeof(*maps)); }
int platform_old_map_folders(char *description, unsigned int size) { (void)description; (void)size; return 0; }
int platform_old_map_folders_move(void) { return 0; }
const char *platform_folder(enum port_folder folder) { (void)folder; return "/tmp"; }
int posix_find_entry_case_insensitive(const char *d, const char *n, char *o, unsigned int s) {
    (void)d; snprintf(o, s, "%s", n); return 1;
}
int posix_make_directory(const char *p) { (void)p; return 1; }
int crash_reports_armed(void) { return 0; }
int posix_crash_pending(const char *p, char *s, unsigned int n) { (void)p; (void)s; (void)n; return 0; }
void posix_crash_discard(const char *p) { (void)p; }
void posix_crash_install(const char *p) { (void)p; }
int posix_crash_send(const char *p) { (void)p; return 0; }
void delta_legacy_start(void) {}
int config_new_defaults_pending(char *t, unsigned int s) { (void)t; (void)s; return 0; }
void config_new_defaults_answer(int a) { (void)a; }
void config_write(void) {}
const char *updater_version(void) { return "0.9.1a"; }
int updater_gamescope(void) { return 0; }
void updater_start(void) {}
void updater_poll(SDL_Window *w) { (void)w; }
int p2p_hand_off_invite(void) { return 0; }
void p2p_open_invite(const char *u) { (void)u; }
void platform_log(const char *fmt, ...) { (void)fmt; }
int config_integer(const char *k) { (void)k; return 0; }
int config_boolean(const char *k) { (void)k; return 1; }
double config_real(const char *k) { (void)k; return 0.0; }
const char *config_string(const char *k) { (void)k; return "fullscreen"; }
unsigned int config_changes(void) { return 0; }
void macos_set_swap_interval(int interval) { (void)interval; }
int macos_window_in_full_screen_space(void *w) { (void)w; return 0; }
void macos_window_toggle_full_screen_space(void *w) { (void)w; }

void SDL_SetLogOutputFunction(SDL_LogOutputFunction cb, void *u) { (void)cb; (void)u; }
void SDL_SetLogPriority(int c, SDL_LogPriority p) { (void)c; (void)p; }
bool SDL_SetHint(const char *n, const char *v) { (void)n; (void)v; return true; }
bool SDL_Init(SDL_InitFlags f) { (void)f; return true; }
bool SDL_InitSubSystem(SDL_InitFlags f) { (void)f; return true; }
void SDL_Quit(void) {}
SDL_Window *SDL_CreateWindow(const char *t, int w, int h, SDL_WindowFlags f) {
    (void)t; (void)w; (void)h; (void)f;
    return (SDL_Window *)&dummy_window;
}
int SDL_GetVersion(void) { return SDL_VERSION; }
const char *SDL_GetCurrentVideoDriver(void) { return "switch"; }
bool SDL_SyncWindow(SDL_Window *w) { (void)w; return true; }
SDL_GLContext SDL_GL_CreateContext(SDL_Window *w) {
    (void)w;
    /* Drako3D stand-in context (non-NULL handle 2, matching host_sdl2.c). */
    return (SDL_GLContext)(uintptr_t)2;
}
int SDL_strcasecmp(const char *a, const char *b) { return strcasecmp(a, b); }
bool SDL_GL_GetAttribute(SDL_GLAttr a, int *v) { (void)a; if (v) *v = 0; return true; }
bool SDL_GetClosestFullscreenDisplayMode(SDL_DisplayID d, int w, int h, float r, bool hd, SDL_DisplayMode *m) {
    (void)d; (void)w; (void)h; (void)r; (void)hd; (void)m; return false;
}
const SDL_DisplayMode *SDL_GetCurrentDisplayMode(SDL_DisplayID d) { (void)d; return NULL; }
SDL_PropertiesID SDL_GetWindowProperties(SDL_Window *w) { (void)w; return 0; }
void *SDL_GetPointerProperty(SDL_PropertiesID p, const char *n, void *d) { (void)p; (void)n; return d; }
const SDL_DisplayMode *SDL_GetWindowFullscreenMode(SDL_Window *w) { (void)w; return NULL; }
void SDL_PumpEvents(void) {}
void SDL_Delay(Uint32 ms) { (void)ms; }
bool SDL_GL_DestroyContext(SDL_GLContext c) { (void)c; return true; }
void SDL_GL_ResetAttributes(void) {}
bool SDL_GL_MakeCurrent(SDL_Window *w, SDL_GLContext c) { (void)w; (void)c; return true; }
bool SDL_GL_SetAttribute(SDL_GLAttr a, int v) { (void)a; (void)v; return true; }
bool SDL_GL_SetSwapInterval(int i) { (void)i; return true; }
bool SDL_GL_SwapWindow(SDL_Window *w) {
    assert(w == (SDL_Window *)&dummy_window);
    swap_count++;
    return true;
}
SDL_FunctionPointer SDL_GL_GetProcAddress(const char *proc) { (void)proc; return NULL; }
const char *SDL_GetError(void) { return ""; }
const char *SDL_getenv(const char *name) { return getenv(name); }
SDL_ThreadID SDL_GetCurrentThreadID(void) { return 1; }
Uint64 SDL_GetTicks(void) { return 100; }
Uint64 SDL_GetTicksNS(void) { return 100000000ULL; }
void SDL_DelayPrecise(Uint64 ns) { (void)ns; }
bool SDL_SetWindowFullscreenMode(SDL_Window *w, const SDL_DisplayMode *m) { (void)w; (void)m; return true; }
bool SDL_SetWindowFullscreen(SDL_Window *w, bool fs) { (void)w; (void)fs; return true; }
SDL_DisplayID SDL_GetDisplayForWindow(SDL_Window *w) { (void)w; return 1; }
SDL_DisplayID SDL_GetPrimaryDisplay(void) { return 1; }
const SDL_DisplayMode *SDL_GetDesktopDisplayMode(SDL_DisplayID d) { (void)d; return NULL; }
SDL_DisplayMode **SDL_GetFullscreenDisplayModes(SDL_DisplayID d, int *c) { (void)d; if (c) *c = 0; return NULL; }
void SDL_free(void *p) { free(p); }
bool SDL_SetWindowRelativeMouseMode(SDL_Window *w, bool e) { (void)w; (void)e; return true; }
bool SDL_ShowCursor(void) { return true; }
bool SDL_HideCursor(void) { return true; }
SDL_WindowFlags SDL_GetWindowFlags(SDL_Window *w) { (void)w; return 0; }
bool SDL_GetWindowSizeInPixels(SDL_Window *w, int *pw, int *ph) {
    (void)w; if (pw) *pw = 1920; if (ph) *ph = 1080; return true;
}

int main(void) {
    assert(platform_video_initialize(852, 480));
    platform_video_swap();
    assert(swap_count == 1);
    return 0;
}
""")
            exe = directory / "video_swap_check"
            subprocess.run(
                [
                    "clang", "-O0", "-g", "-std=gnu11",
                    "-ffunction-sections", "-fdata-sections",
                    *(["-Wl,-dead_strip", "-Wl,-undefined,dynamic_lookup"]
                      if sys.platform == "darwin" else ["-Wl,--gc-sections", "-Wl,--unresolved-symbols=ignore-in-object-files"]),
                    "-D__SWITCH2__", "-DHALO_LINUX_PLATFORM_LAYER", "-DHALO_64BIT",
                    "-DHALO_SWITCH_CONSOLE", "-D_FORTIFY_SOURCE=0",
                    "-fsigned-char", "-fms-extensions", "-fshort-wchar", "-fcommon",
                    "-fno-strict-aliasing", "-fwrapv", "-fno-delete-null-pointer-checks",
                    "-Wno-unused-function",
                    "-include", str(lp64 / "port/linux/include/halo_linux_prefix.h"),
                    "-I", str(lp64 / "port/linux/include"),
                    "-I", str(lp64 / "port/linux/src"),
                    "-I", str(lp64 / "source"),
                    "-I", str(lp64 / "source/cseries"),
                    "-I", str(sdl_include),
                    "-idirafter", str(lp64 / "port/include/xdk"),
                    str(lp64 / "port/linux/src/sdl_platform.c"),
                    str(lp64 / "port/linux/src/gl_functions.c"),
                    str(harness),
                    "-o", str(exe),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            for legacy in ("0", "1"):
                env = dict(os.environ, HALO_GL_LEGACY=legacy)
                run = subprocess.run([str(exe)], env=env, capture_output=True, text=True)
                self.assertEqual(run.returncode, 0, f"HALO_GL_LEGACY={legacy} failed with rc={run.returncode}")
