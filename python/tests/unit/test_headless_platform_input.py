from __future__ import annotations

import logging
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.context import GameContext
from ultimatetk.core.events import AppEvent, InputAction
from ultimatetk.core.paths import GamePaths
from ultimatetk.core.platform import HeadlessPlatformBackend


class HeadlessPlatformInputTests(unittest.TestCase):
    def test_poll_events_uses_script_schedule(self) -> None:
        backend = HeadlessPlatformBackend(
            input_schedule={
                1: (AppEvent.action_pressed(InputAction.MOVE_FORWARD),),
                3: (AppEvent.action_released(InputAction.MOVE_FORWARD),),
            },
        )

        context = GameContext(
            config=RuntimeConfig(),
            paths=GamePaths(
                python_root=PROJECT_ROOT,
                game_data_root=PROJECT_ROOT / "game_data",
                runs_root=PROJECT_ROOT / "runs",
            ),
            logger=logging.getLogger("ultimatetk.test.headless"),
        )

        backend.startup(context)
        self.assertEqual(tuple(backend.poll_events()), ())

        frame_1_events = tuple(backend.poll_events())
        self.assertEqual(len(frame_1_events), 1)
        self.assertEqual(frame_1_events[0].action, InputAction.MOVE_FORWARD)

        self.assertEqual(tuple(backend.poll_events()), ())

        frame_3_events = tuple(backend.poll_events())
        self.assertEqual(len(frame_3_events), 1)
        self.assertEqual(frame_3_events[0].action, InputAction.MOVE_FORWARD)

    def test_poll_events_without_script_returns_empty(self) -> None:
        backend = HeadlessPlatformBackend()
        context = GameContext(
            config=RuntimeConfig(),
            paths=GamePaths(
                python_root=PROJECT_ROOT,
                game_data_root=PROJECT_ROOT / "game_data",
                runs_root=PROJECT_ROOT / "runs",
            ),
            logger=logging.getLogger("ultimatetk.test.headless"),
        )

        backend.startup(context)
        self.assertEqual(tuple(backend.poll_events()), ())
        self.assertEqual(tuple(backend.poll_events()), ())


if __name__ == "__main__":
    unittest.main()
