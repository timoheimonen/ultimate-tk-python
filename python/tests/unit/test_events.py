from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.events import AppEvent, EventType, InputAction


class EventModelTests(unittest.TestCase):
    def test_action_pressed_constructor(self) -> None:
        event = AppEvent.action_pressed(InputAction.MOVE_FORWARD)
        self.assertEqual(event.type, EventType.ACTION_PRESSED)
        self.assertEqual(event.action, InputAction.MOVE_FORWARD)
        self.assertIsNone(event.weapon_slot)

    def test_action_released_constructor(self) -> None:
        event = AppEvent.action_released(InputAction.TURN_LEFT)
        self.assertEqual(event.type, EventType.ACTION_RELEASED)
        self.assertEqual(event.action, InputAction.TURN_LEFT)
        self.assertIsNone(event.weapon_slot)

    def test_weapon_select_constructor(self) -> None:
        event = AppEvent.weapon_select(4)
        self.assertEqual(event.type, EventType.WEAPON_SELECT)
        self.assertEqual(event.weapon_slot, 4)
        self.assertIsNone(event.action)


if __name__ == "__main__":
    unittest.main()
