/* SPDX-License-Identifier: GPL-3.0-or-later */
#include <SDL2/SDL.h>
#include <switch.h>
#include <switch2/services/nmouse.h>
#include <stdio.h>
#include <sys/stat.h>
#include "nx2_platform.h"

int __wrap_SDL_VideoInit(const char *driver_name) { (void)driver_name; return -1; }
void __wrap_SDL_VideoQuit(void) {}

static void audio_callback(void *data, Uint8 *stream, int length)
{
	SDL_AtomicAdd((SDL_atomic_t *)data, 1);
	SDL_memset(stream, 0, length);
}

int main(void)
{
	mkdir("sdmc:/switch", 0777);
	mkdir("sdmc:/switch/warthog", 0777);
	mkdir("sdmc:/switch/warthog/logs", 0777);
	FILE *log = fopen("sdmc:/switch/warthog/logs/sdl_probe.log", "w");
	if (!log) {
		switch2PlatformRestoreClock();
		return 1;
	}
	setvbuf(log, NULL, _IOLBF, 0);
	fprintf(log, "firmware=0x%x\napplet_type=%d\ncore_mask=0x%llx\n",
		hosversionGet(), appletGetAppletType(), (unsigned long long)switch2PlatformCoreMask());
	switch2PlatformDisplayInit();
	fprintf(log, "display.mode=%s\ndisplay.refresh_hz=%d\n",
		appletGetOperationMode() == AppletOperationMode_Console ? "docked" : "handheld",
		switch2PlatformRefreshRate());

	int init = SDL_Init(SDL_INIT_AUDIO | SDL_INIT_JOYSTICK | SDL_INIT_GAMECONTROLLER | SDL_INIT_EVENTS);
	fprintf(log, "sdl.init=%d\n", init);
	if (init == 0) {
		hidInitializeKeyboard();
		hidInitializeMouse();
		fprintf(log, "hid.keyboard_mouse=activation_attempted\n");
		int count = SDL_NumJoysticks();
		fprintf(log, "controller.count=%d\n", count);
		for (int i = 0; i < count; ++i) {
			int supported = SDL_IsGameController(i);
			fprintf(log, "controller.%d.supported=%d\n", i, supported);
			if (supported) {
				SDL_GameController *controller = SDL_GameControllerOpen(i);
				fprintf(log, "controller.%d.open=%d\n", i, controller != NULL);
				if (controller) SDL_GameControllerClose(controller);
			}
		}
		SDL_AudioSpec desired = {0}, obtained = {0};
		SDL_atomic_t callbacks = {0};
		desired.freq = 48000;
		desired.format = AUDIO_S16SYS;
		desired.channels = 2;
		desired.samples = 1024;
		desired.callback = audio_callback;
		desired.userdata = &callbacks;
		SDL_AudioDeviceID audio = SDL_OpenAudioDevice(NULL, 0, &desired, &obtained, 0);
		fprintf(log, "audio.open=%u\naudio.error=%s\n", audio, audio ? "" : SDL_GetError());
		if (audio) SDL_PauseAudioDevice(audio, 0);
		for (int i = 0; i < 30 && appletMainLoop(); ++i) {
			SDL_Event event;
			while (SDL_PollEvent(&event))
				fprintf(log, "sdl.event=%u\n", event.type);
			fprintf(log, "display.mode.current=%s\n",
				appletGetOperationMode() == AppletOperationMode_Console ? "docked" : "handheld");
			SDL_Delay(100);
		}
		if (audio) SDL_CloseAudioDevice(audio);
		fprintf(log, "audio.callbacks=%d\n", SDL_AtomicGet(&callbacks));
		SDL_Quit();
	} else fprintf(log, "sdl.error=%s\n", SDL_GetError());

	Result rc = hidInitializeNmouse(NULL, 0, 1920, 1080, HidNmousePointerType_Default);
	fprintf(log, "nmouse.initialize=0x%x\n", rc);
	if (R_SUCCEEDED(rc)) {
		HidNmouseHandle handles[18];
		s32 count = 0;
		rc = hidGetAllNmouseHandles(handles, 18, &count);
		fprintf(log, "nmouse.handles.result=0x%x\nnmouse.handles.count=%d\n", rc, count);
		fprintf(log, "nmouse.finalize=0x%x\n", hidFinalizeNmouse());
	}
	fprintf(log, "swkbd=provided_by_libounce_not_opened\n");
	fprintf(log, "display.release=0x%x\n", switch2PlatformReleaseWindow());
	fprintf(log, "clock.normal=0x%x\n", switch2PlatformRestoreClock());
	fclose(log);
	return init == 0 ? 0 : 1;
}
