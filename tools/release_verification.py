from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]


@dataclass(frozen=True, slots=True)
class VerificationStep:
    name: str
    command: tuple[str, ...]
    env_overrides: dict[str, str] | None = None


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
    parser.add_argument(
        "--legacy-compare-root",
        type=Path,
        default=None,
        help="Optional legacy source root for strict legacy-vs-python asset parity checks",
    )
    return parser.parse_args()


def _run_step(step: VerificationStep) -> None:
    print(f"[release-verify] {step.name}", flush=True)
    print(f"[release-verify] command: {' '.join(step.command)}", flush=True)
    env = None
    if step.env_overrides:
        env = dict(os.environ)
        env.update(step.env_overrides)
    subprocess.run(step.command, cwd=PROJECT_ROOT, check=True, env=env)


def _build_steps(args: argparse.Namespace) -> list[VerificationStep]:
    steps: list[VerificationStep] = []
    legacy_compare_root = (
        args.legacy_compare_root.expanduser().resolve() if args.legacy_compare_root else None
    )

    if not args.skip_manifest:
        manifest_command = [sys.executable, "tools/asset_manifest_report.py"]
        if legacy_compare_root is not None:
            manifest_command.extend(["--legacy-root", str(legacy_compare_root)])

        steps.append(
            VerificationStep(
                name="Regenerate asset manifest and gap report",
                command=tuple(manifest_command),
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
        integration_env = None
        if legacy_compare_root is not None:
            integration_env = {
                "ULTIMATETK_LEGACY_COMPARE_ROOT": str(legacy_compare_root),
            }

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
                env_overrides=integration_env,
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
