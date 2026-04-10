from __future__ import annotations

import argparse
from typing import Sequence

from ultimatetk.core.app import GameApplication
from ultimatetk.core.config import RuntimeConfig
from ultimatetk.core.logging_setup import configure_logging


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ultimate TK Python refactor")
    parser.add_argument("--target-fps", type=int, default=40, help="Simulation tick rate")
    parser.add_argument(
        "--max-frame-time",
        type=float,
        default=0.25,
        help="Maximum clamped frame delta in seconds",
    )
    parser.add_argument(
        "--max-updates-per-frame",
        type=int,
        default=8,
        help="Maximum simulation updates to process per render frame",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=None,
        help="Optional runtime cap for the current process",
    )
    parser.add_argument(
        "--autostart-gameplay",
        action="store_true",
        help="Transition from menu scaffold to gameplay scaffold automatically",
    )
    parser.add_argument(
        "--status-print-interval",
        type=int,
        default=0,
        help="Log runtime status every N render frames (0 disables)",
    )
    parser.add_argument(
        "--platform",
        choices=("headless", "terminal"),
        default="headless",
        help="Runtime platform backend",
    )
    parser.add_argument(
        "--terminal-hold-frames",
        type=int,
        default=2,
        help="Frames to keep terminal actions active without repeat",
    )
    parser.add_argument(
        "--input-script",
        default=None,
        help=(
            "Headless input script entries as '<frame>:<event>' separated by ';', "
            "for example '5:+MOVE_FORWARD;20:-MOVE_FORWARD;25:+TURN_LEFT'"
        ),
    )
    session_group = parser.add_mutually_exclusive_group()
    session_group.add_argument(
        "--load-session",
        action="store_true",
        help="Load persisted session profile from runs/profiles/session.json",
    )
    session_group.add_argument(
        "--new-session",
        action="store_true",
        help="Start fresh session and overwrite persisted session profile",
    )
    parser.add_argument(
        "--no-save-session",
        action="store_true",
        help="Disable automatic session profile save on shutdown",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    configure_logging(args.log_level)

    config = RuntimeConfig(
        target_tick_rate=args.target_fps,
        max_frame_time_seconds=args.max_frame_time,
        max_updates_per_frame=args.max_updates_per_frame,
        max_seconds=args.max_seconds,
        autostart_gameplay=args.autostart_gameplay,
        status_print_interval=args.status_print_interval,
        platform=args.platform,
        terminal_hold_frames=args.terminal_hold_frames,
        input_script=args.input_script,
        session_load_on_start=args.load_session,
        session_new_on_start=args.new_session,
        session_auto_save=not args.no_save_session,
    )
    app = GameApplication.create(config)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
