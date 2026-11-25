/* SPDX-License-Identifier: GPL-3.0-or-later */
#pragma once

#include <stddef.h>
#include <stdint.h>
#include "nx2_gameshare.h"

#if defined(__SWITCH2__)
int switch2_gameshare_available(char *error, size_t error_size);
Nx2GameShareResult switch2_gameshare_begin(char *error, size_t error_size);
void switch2_gameshare_update(void);
void switch2_gameshare_shutdown(void);
int switch2_gameshare_active(void);
int switch2_gameshare_guest_input(Nx2GameShareInput *input);
void switch2_gameshare_guest_audio(const int16_t *frames, uint32_t frame_count,
	uint32_t sample_rate);
int switch2_gameshare_campaign_players(unsigned players);
#else
static inline int switch2_gameshare_available(char *error, size_t size)
{
	(void)error; (void)size; return 0;
}
#endif
