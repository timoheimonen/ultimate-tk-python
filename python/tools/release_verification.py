from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


THIS_FILE = Path(__file__).resolve()
PYTHON_ROOT = THIS_FILE.parents[1]


@dataclass(frozen=True, slots=True)
class VerificationStep:
    name: str
    command: tuple[str, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run release verification command bundle")
    parser.add_argument(
        "--skip-manifest",
        action="store_true",
        help="Skip asset manifest regeneration step",
    )
    parser.add_argument(
        "--skip-unit",
        action="store_true",
        help="Skip unit verification matrix",
    )
    parser.add_argument(
        "--skip-integration",
        action="store_true",
        help="Skip integration verification matrix",
    )
    return parser.parse_args()


def _run_step(step: VerificationStep) -> None:
    print(f"[release-verify] {step.name}", flush=True)
    print(f"[release-verify] command: {' '.join(step.command)}", flush=True)
    subprocess.run(step.command, cwd=PYTHON_ROOT, check=True)


def _build_steps(args: argparse.Namespace) -> list[VerificationStep]:
    steps: list[VerificationStep] = []

    if not args.skip_manifest:
        steps.append(
            VerificationStep(
                name="Regenerate asset manifest and gap report",
                command=(sys.executable, "tools/asset_manifest_report.py"),
            ),
        )

    if not args.skip_unit:
        steps.append(
            VerificationStep(
                name="Run phase unit verification matrix",
                command=(
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/unit/test_fixed_step_clock.py",
                    "tests/unit/test_player_control.py",
                    "tests/unit/test_combat.py",
                    "tests/unit/test_scene_flow.py",
                ),
            ),
        )

    if not args.skip_integration:
        steps.append(
            VerificationStep(
                name="Run phase integration verification matrix",
                command=(
                    sys.executable,
                    "-m",
                    "pytest",
                    "tests/integration/test_headless_input_script_runtime.py",
                    "tests/integration/test_real_data_render.py",
                    "tests/integration/test_real_data_parse.py",
                ),
            ),
        )

    if not steps:
        raise ValueError("no steps selected; remove skip flags or select at least one step")

    return steps


def main() -> int:
    args = parse_args()
    steps = _build_steps(args)

    for step in steps:
        _run_step(step)

    print("[release-verify] all selected steps passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
