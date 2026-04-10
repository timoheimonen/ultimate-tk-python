from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.events import EventType, InputAction
from ultimatetk.core.terminal_input import (
    TOKEN_ARROW_DOWN,
    TOKEN_ARROW_LEFT,
    TOKEN_ARROW_RIGHT,
    TOKEN_ARROW_UP,
    TOKEN_TAB,
    TerminalInputMapper,
    TerminalKeyDecoder,
    build_token_to_action_from_legacy_keys,
)
from ultimatetk.formats.options_cfg import KeysConfig


class TerminalKeyDecoderTests(unittest.TestCase):
    def test_decodes_ascii_and_arrows(self) -> None:
        decoder = TerminalKeyDecoder()
        tokens = decoder.feed(b"w\x1b[A\x1b[D")
        self.assertEqual(tokens, ("w", "ARROW_UP", "ARROW_LEFT"))

    def test_decodes_tab_and_ctrl_c(self) -> None:
        decoder = TerminalKeyDecoder()
        tokens = decoder.feed(b"\t\x03")
        self.assertEqual(tokens, ("TAB", "CTRL_C"))

    def test_flush_pending_escape(self) -> None:
        decoder = TerminalKeyDecoder()
        self.assertEqual(decoder.feed(b"\x1b"), ())
        self.assertEqual(decoder.flush_pending_escape(), ("ESC",))


class TerminalInputMapperTests(unittest.TestCase):
    def test_press_and_auto_release(self) -> None:
        mapper = TerminalInputMapper(hold_frames=2)

        frame0 = mapper.events_for_tokens(("w",), frame=0)
        self.assertEqual(frame0[0].type, EventType.ACTION_PRESSED)
        self.assertEqual(frame0[0].action, InputAction.MOVE_FORWARD)

        frame1 = mapper.events_for_tokens((), frame=1)
        self.assertEqual(frame1, ())

        frame2 = mapper.events_for_tokens((), frame=2)
        self.assertEqual(len(frame2), 1)
        self.assertEqual(frame2[0].type, EventType.ACTION_RELEASED)
        self.assertEqual(frame2[0].action, InputAction.MOVE_FORWARD)

    def test_repeat_extends_hold_window(self) -> None:
        mapper = TerminalInputMapper(hold_frames=2)
        mapper.events_for_tokens(("w",), frame=0)
        repeated = mapper.events_for_tokens(("w",), frame=1)
        self.assertEqual(repeated, ())

        self.assertEqual(mapper.events_for_tokens((), frame=2), ())
        released = mapper.events_for_tokens((), frame=3)
        self.assertEqual(len(released), 1)
        self.assertEqual(released[0].type, EventType.ACTION_RELEASED)

    def test_weapon_select_and_quit_tokens(self) -> None:
        mapper = TerminalInputMapper()
        events = mapper.events_for_tokens(("3", "ESC"), frame=0)
        self.assertEqual(events[0].type, EventType.WEAPON_SELECT)
        self.assertEqual(events[0].weapon_slot, 3)
        self.assertEqual(events[1].type, EventType.QUIT)

    def test_shop_toggle_token_maps_to_action(self) -> None:
        mapper = TerminalInputMapper()
        events = mapper.events_for_tokens(("r",), frame=0)
        self.assertEqual(events[0].type, EventType.ACTION_PRESSED)
        self.assertEqual(events[0].action, InputAction.TOGGLE_SHOP)


class TerminalLegacyBindingTests(unittest.TestCase):
    def test_build_bindings_from_legacy_keys_with_fallback(self) -> None:
        keys = KeysConfig(
            k_left=96,
            k_right=97,
            k_up=94,
            k_down=99,
            k_shoot=90,
            k_shift=54,
            k_strafe=92,
            k_lstrafe=51,
            k_rstrafe=52,
        )

        token_map, unsupported = build_token_to_action_from_legacy_keys(keys)

        self.assertEqual(token_map[TOKEN_ARROW_LEFT], InputAction.TURN_LEFT)
        self.assertEqual(token_map[TOKEN_ARROW_RIGHT], InputAction.TURN_RIGHT)
        self.assertEqual(token_map[TOKEN_ARROW_UP], InputAction.MOVE_FORWARD)
        self.assertEqual(token_map[TOKEN_ARROW_DOWN], InputAction.MOVE_BACKWARD)
        self.assertEqual(token_map[","], InputAction.STRAFE_LEFT)
        self.assertEqual(token_map["."], InputAction.STRAFE_RIGHT)
        self.assertEqual(token_map[" "], InputAction.SHOOT)
        self.assertEqual(token_map[TOKEN_TAB], InputAction.NEXT_WEAPON)
        self.assertEqual(token_map["z"], InputAction.STRAFE_MODIFIER)
        self.assertEqual(unsupported, (54, 90, 92))

    def test_build_bindings_from_letters_adds_uppercase_alias(self) -> None:
        keys = KeysConfig(
            k_left=30,
            k_right=32,
            k_up=17,
            k_down=31,
            k_shoot=57,
            k_shift=15,
            k_strafe=44,
            k_lstrafe=16,
            k_rstrafe=18,
        )

        token_map, unsupported = build_token_to_action_from_legacy_keys(keys)

        self.assertEqual(unsupported, ())
        self.assertEqual(token_map["a"], InputAction.TURN_LEFT)
        self.assertEqual(token_map["A"], InputAction.TURN_LEFT)
        self.assertEqual(token_map["q"], InputAction.STRAFE_LEFT)
        self.assertEqual(token_map["Q"], InputAction.STRAFE_LEFT)
        self.assertEqual(token_map["e"], InputAction.STRAFE_RIGHT)
        self.assertEqual(token_map["E"], InputAction.STRAFE_RIGHT)


if __name__ == "__main__":
    unittest.main()
