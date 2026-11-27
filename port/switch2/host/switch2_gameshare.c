/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "switch2_gameshare.h"

#if defined(__SWITCH2__)
#include <stdio.h>
#include <string.h>
#include <switch.h>
#include <switch2/services/stpl.h>
#include "switch2_perf.h"
#include "warthog_log.h"

/* host_dk owns the GPU and therefore owns opening the second swapchain. */
int host_dk_gameshare_open(void *window, int width, int height);
void host_dk_gameshare_close(void);

static bool renderer_screen_open(void *window, int width, int height, void *user)
{
	(void)user;
	return host_dk_gameshare_open(window, width, height);
}

static void renderer_screen_close(void *user)
{
	(void)user;
	host_dk_gameshare_close();
}

static const Nx2GameShareScreen screen = {
	renderer_screen_open, renderer_screen_close, NULL
};

int switch2_gameshare_available(char *error, size_t error_size)
{
	Result rc;
	if (error && error_size) error[0] = 0;
	if (appletGetAppletType() != AppletType_Application) {
		if (error && error_size)
			snprintf(error, error_size,
				"GameShare requires AppletType_Application title takeover");
		return 0;
	}
	/* This is a capability probe only.  The service is immediately released;
	   the helper opens it again for the actual host session. */
	rc = stplInitialize();
	if (R_FAILED(rc)) {
		if (error && error_size)
			snprintf(error, error_size,
				"GameShare is unavailable from this host title (stpl:u %#x)",
				(unsigned)rc);
		return 0;
	}
	stplExit();
	return 1;
}

Nx2GameShareResult switch2_gameshare_begin(char *error, size_t error_size)
{
	if (!switch2_gameshare_available(error, error_size)) {
		warthog_log("WARN", "GameShare refused: %s", error ? error : "unavailable");
		return Nx2GameShare_Failed;
	}
	Nx2GameShareResult result = nx2GameShareBegin(&screen, error, error_size);
	if (result == Nx2GameShare_Cancelled)
		warthog_log("INFO", "GameShare matchmaking cancelled; local match restored");
	else if (result == Nx2GameShare_Failed)
		warthog_log("WARN", "GameShare start failed: %s", error ? error : "unknown");
	else
		warthog_log("INFO", "GameShare session started (%s view)",
			nx2GameShareSeparateActive() ? "separate" : "mirror");
	return result;
}

void switch2_gameshare_update(void)
{
	static uint64_t disconnected;
	if (!nx2GameShareActive()) return;
	nx2GameShareUpdate();
	if (!nx2GameShareGuestConnected() && !disconnected) {
		disconnected = 1;
		warthog_log("INFO", "GameShare guest disconnected; returning to host display");
		host_dk_gameshare_close();
	}
	if (nx2GameShareGuestConnected()) disconnected = 0;
}

void switch2_gameshare_shutdown(void)
{
	if (nx2GameShareActive())
		nx2GameShareEnd();
	else
		host_dk_gameshare_close();
}

int switch2_gameshare_active(void) { return nx2GameShareActive(); }

int switch2_gameshare_guest_input(Nx2GameShareInput *input)
{
	return nx2GameShareGetGuestInput(input) ? 1 : 0;
}

void switch2_gameshare_guest_audio(const int16_t *frames, uint32_t frame_count,
	uint32_t sample_rate)
{
	nx2GameShareWriteGuestAudioRate(frames, frame_count, sample_rate);
}

int switch2_gameshare_campaign_players(unsigned players)
{
	return players == 2;
}
#endif
