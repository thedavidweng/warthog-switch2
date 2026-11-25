// nx2_platform: Nintendo Switch 2 (kaiHEN + libounce) platform helpers shared by the NX ports.
// SPDX-License-Identifier: MIT
// From NaGaa95/dolphin-nx Source/Core/Common/nx2_platform.h
// Revision 7fb685b353e19a9a5848e9bd658945d1f9cd382a
#pragma once
#include <switch.h>
#include <stdbool.h>

u64 nx2CoreMask(void);
int nx2CoreCount(void);
int nx2CoreAt(unsigned n);
Result nx2SetCpuBoost(bool on);
void nx2DisplayInit(void);
bool nx2DisplaySetFrameGeneration(bool enabled);
int nx2DisplayRefreshRate(void);
Result nx2DisplayApply(int swap_interval);
Result nx2DisplayReapply(void);
bool nx2DisplayUpdate(void);
void nx2DisplaySize(u32* width, u32* height);
bool nx2Docked(void);
void nx2ExitReleaseLockLast(void);
void nx2ExitCleanupNow(void);

u64 switch2PlatformCoreMask(void);
void switch2PlatformDisplayInit(void);
int switch2PlatformRefreshRate(void);
Result switch2PlatformRestoreClock(void);
Result switch2PlatformReleaseWindow(void);
