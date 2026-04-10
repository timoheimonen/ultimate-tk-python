from __future__ import annotations

import sys
from pathlib import Path
import unittest

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    np = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.events import AppEvent, InputAction

if np is not None:
    from ultimatetk.ai.action_codec import ActionCodec


@unittest.skipIf(np is None, "numpy optional dependency is not installed")
class GymActionCodecTests(unittest.TestCase):
    def test_generates_press_and_release_events_for_hold_actions(self) -> None:
        codec = ActionCodec()

        pressed = codec.decode(
            {
                "hold": np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.int8),
                "trigger": np.array([0], dtype=np.int8),
                "weapon_select": 0,
            },
        )
        self.assertEqual(pressed, (AppEvent.action_pressed(InputAction.MOVE_FORWARD),))

        held = codec.decode(
            {
                "hold": np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.int8),
                "trigger": np.array([0], dtype=np.int8),
                "weapon_select": 0,
            },
        )
        self.assertEqual(held, ())

        released = codec.decode(
            {
                "hold": np.array([0, 0, 0, 0, 0, 0, 0, 0], dtype=np.int8),
                "trigger": np.array([0], dtype=np.int8),
                "weapon_select": 0,
            },
        )
        self.assertEqual(released, (AppEvent.action_released(InputAction.MOVE_FORWARD),))

    def test_emits_trigger_and_weapon_select_events(self) -> None:
        codec = ActionCodec()
        events = codec.decode(
            {
                "hold": np.zeros((8,), dtype=np.int8),
                "trigger": np.array([1], dtype=np.int8),
                "weapon_select": 3,
            },
        )

        self.assertIn(AppEvent.action_pressed(InputAction.NEXT_WEAPON), events)
        self.assertIn(AppEvent.weapon_select(2), events)

    def test_reset_clears_hold_diff_state(self) -> None:
        codec = ActionCodec()
        codec.decode(
            {
                "hold": np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.int8),
                "trigger": np.array([0], dtype=np.int8),
                "weapon_select": 0,
            },
        )

        codec.reset()
        events = codec.decode(
            {
                "hold": np.array([1, 0, 0, 0, 0, 0, 0, 0], dtype=np.int8),
                "trigger": np.array([0], dtype=np.int8),
                "weapon_select": 0,
            },
        )
        self.assertEqual(events, (AppEvent.action_pressed(InputAction.MOVE_FORWARD),))


if __name__ == "__main__":
    unittest.main()
