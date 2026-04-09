from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.events import EventType, InputAction
from ultimatetk.core.input_script import parse_input_script


class InputScriptTests(unittest.TestCase):
    def test_parse_empty_script(self) -> None:
        self.assertEqual(parse_input_script(None), {})
        self.assertEqual(parse_input_script(""), {})

    def test_parse_press_release_and_weapon_select(self) -> None:
        schedule = parse_input_script(
            "5:+MOVE_FORWARD;8:-MOVE_FORWARD;12:WEAPON=3",
        )

        self.assertEqual(schedule[5][0].type, EventType.ACTION_PRESSED)
        self.assertEqual(schedule[5][0].action, InputAction.MOVE_FORWARD)

        self.assertEqual(schedule[8][0].type, EventType.ACTION_RELEASED)
        self.assertEqual(schedule[8][0].action, InputAction.MOVE_FORWARD)

        self.assertEqual(schedule[12][0].type, EventType.WEAPON_SELECT)
        self.assertEqual(schedule[12][0].weapon_slot, 3)

    def test_parse_alias_names(self) -> None:
        schedule = parse_input_script("1:+up;2:+left;3:+strafe;4:+next;5:+shop")
        self.assertEqual(schedule[1][0].action, InputAction.MOVE_FORWARD)
        self.assertEqual(schedule[2][0].action, InputAction.TURN_LEFT)
        self.assertEqual(schedule[3][0].action, InputAction.STRAFE_MODIFIER)
        self.assertEqual(schedule[4][0].action, InputAction.NEXT_WEAPON)
        self.assertEqual(schedule[5][0].action, InputAction.TOGGLE_SHOP)

    def test_parse_quit_token(self) -> None:
        schedule = parse_input_script("10:quit")
        self.assertEqual(schedule[10][0].type, EventType.QUIT)

    def test_invalid_entry_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_input_script("10+MOVE_FORWARD")
        with self.assertRaises(ValueError):
            parse_input_script("-1:+MOVE_FORWARD")
        with self.assertRaises(ValueError):
            parse_input_script("1:+NOPE")
        with self.assertRaises(ValueError):
            parse_input_script("1:WEAPON=-2")


if __name__ == "__main__":
    unittest.main()
