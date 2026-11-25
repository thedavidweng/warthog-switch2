"""Host checks for the Switch 2 GameShare adapter and guest display."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "port/switch2/host"


class GameShareTest(unittest.TestCase):
    def test_mit_provenance_and_notice(self):
        for name in ("nx2_gameshare.h", "nx2_gameshare.c"):
            text = (HOST / name).read_text()
            self.assertIn("SPDX-License-Identifier: MIT", text)
            self.assertIn("Cemu-nx", text)
            self.assertIn("NaGaa95/dolphin-nx", text)
            self.assertIn("7fb685b353e19a9a5848e9bd658945d1f9cd382a", text)
        self.assertIn("nx2_gameshare", (ROOT / "README.md").read_text())
        self.assertIn("nx2_gameshare.{c,h}", (ROOT / "tools/switch_package.py").read_text())

    def test_availability_cancel_and_teardown_order(self):
        text = (HOST / "switch2_gameshare.c").read_text()
        self.assertIn("AppletType_Application", text)
        self.assertIn("stplInitialize", text)
        self.assertIn("Nx2GameShare_Cancelled", text)
        self.assertLess(text.index("host_dk_gameshare_close"),
                        text.index("nx2GameShareEnd"))
        bridge = (HOST / "switch2_host_bridge.c").read_text()
        self.assertLess(bridge.index("switch2_gameshare_shutdown()"),
                        bridge.index("host_dk_shutdown()"))

    def test_separate_view_routes_both_outputs(self):
        text = (ROOT / "port/switch/host/host_dk.c").read_text()
        self.assertIn("nx2GameShareSeparateActive", text)
        self.assertIn("dk.guest_swapchain", text)
        self.assertIn("dkQueuePresentImage(dk.queue, dk.guest_swapchain", text)
        self.assertIn("DkImageFlags_UsageRender | DkImageFlags_UsagePresent | DkImageFlags_Usage2DEngine", text)
        split = (HOST / "switch2_splitscreen.h").read_text()
        self.assertRegex(split, r"SWITCH2_OUTPUT_PRIMARY\s*=\s*0")
        self.assertRegex(split, r"SWITCH2_OUTPUT_SECONDARY\s*=\s*1")

    def test_guest_is_player_one_and_campaign_is_two_players(self):
        text = (HOST / "switch2_gameshare.c").read_text()
        self.assertIn("switch2_gameshare_campaign_players(unsigned players)", text)
        self.assertRegex(text, r"return players == 2")
        input_text = (HOST / "switch2_input.c").read_text()
        self.assertIn("player = 1", input_text)
        self.assertIn("player zero and player one cannot cross-talk", input_text)

    def test_sdl_bridge_wires_gameshare_guest(self):
        text = (HOST / "switch2_sdl3_bridge.c").read_text()
        for symbol in ("switch2_gameshare_update", "SDL_EVENT_GAMEPAD_ADDED",
                       "SDL_EVENT_GAMEPAD_REMOVED", "SWITCH2_GAMESHARE_GAMEPAD_ID",
                       "switch2_gameshare_guest_input", "nx2GameShareSetGuestRumble"):
            self.assertIn(symbol, text)
        self.assertIn("switch2_gameshare_guest_audio",
                      (ROOT / "port/switch/host/host_sdl2.c").read_text())

    def test_normal_split_screen_remains_four_players(self):
        text = (HOST / "switch2_input.h").read_text()
        self.assertIn("SWITCH2_LOCAL_PLAYER_COUNT 4u", text)
        split = (HOST / "switch2_splitscreen.c").read_text()
        self.assertIn("SWITCH2_SPLITSCREEN_MAX_PLAYERS", split)
