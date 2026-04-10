from __future__ import annotations

import argparse
from pathlib import Path
from time import perf_counter, sleep
import sys


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.ai.action_codec import ActionCodec
from ultimatetk.ai.observation import blank_observation, extract_observation
from ultimatetk.ai.runtime_driver import TrainingRuntimeDriver
from ultimatetk.ai.sb3_action_wrapper import sb3_vector_to_env_action
from ultimatetk.ai.training_device import detect_torch_capabilities, resolve_torch_device
from ultimatetk.core.events import EventType
from ultimatetk.core.platform_pygame import PygamePlatformBackend
from ultimatetk.core.state import AppMode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play PPO model with pygame visualization")
    parser.add_argument("--model", required=True, help="Path to PPO .zip model")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda"))
    parser.add_argument("--target-fps", type=int, default=40, help="Playback FPS limit")
    parser.add_argument("--window-scale", type=int, default=3, help="Pygame window scale")
    parser.add_argument("--level-index", type=int, default=0, help="Start level index")
    parser.add_argument("--seed", type=int, default=123, help="Reserved for future deterministic hooks")
    parser.add_argument("--max-steps", type=int, default=0, help="Optional step cap (0 disables)")
    parser.add_argument("--max-seconds", type=float, default=0.0, help="Optional wall-clock cap (0 disables)")
    parser.add_argument("--deterministic", action="store_true", help="Use deterministic policy actions")
    parser.add_argument(
        "--allow-manual-input",
        action="store_true",
        help="Allow manual gameplay key inputs alongside AI (ESC quit is always enabled)",
    )
    parser.add_argument(
        "--disable-asset-manifest-check",
        action="store_true",
        help="Disable game_data asset manifest enforcement",
    )
    return parser.parse_args()


def _import_playback_dependencies() -> object:
    try:
        from stable_baselines3 import PPO
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "stable-baselines3 dependencies are missing. Install with conda, for example: "
            "conda install -n ultimatetk -c conda-forge pytorch stable-baselines3",
        ) from exc
    return PPO


def main() -> int:
    args = parse_args()
    if args.target_fps < 1:
        raise ValueError("--target-fps must be >= 1")
    if args.window_scale < 1:
        raise ValueError("--window-scale must be >= 1")
    if args.max_steps < 0:
        raise ValueError("--max-steps must be >= 0")
    if args.max_seconds < 0:
        raise ValueError("--max-seconds must be >= 0")

    del args.seed

    PPO = _import_playback_dependencies()
    caps = detect_torch_capabilities()
    device = resolve_torch_device(args.device, capabilities=caps)

    model_path = Path(args.model).expanduser().resolve()
    model = PPO.load(str(model_path), device=device, print_system_info=False)

    driver = TrainingRuntimeDriver.create(
        level_index=max(0, int(args.level_index)),
        target_tick_rate=max(1, int(args.target_fps)),
        enforce_asset_manifest=not args.disable_asset_manifest_check,
        project_root=PROJECT_ROOT,
        render_enabled=True,
    )
    action_codec = ActionCodec()
    action_codec.reset()

    platform = PygamePlatformBackend(window_scale=args.window_scale)
    platform.startup(driver.context)

    driver.scene_manager.render(0.0)
    driver.context.runtime.render_frame += 1
    platform.present(driver.context, driver.scene_manager.current_scene_name, 0.0)

    target_dt = 1.0 / float(max(1, int(args.target_fps)))
    max_steps = int(args.max_steps)
    max_seconds = float(args.max_seconds)
    steps = 0
    stop_reason = "quit"
    wall_start = perf_counter()

    try:
        while driver.context.runtime.running:
            frame_start = perf_counter()
            polled = tuple(platform.poll_events())
            if any(event.type == EventType.QUIT for event in polled):
                stop_reason = "quit"
                break

            runtime = driver.context.runtime
            view = driver.gameplay_view()
            if view is None:
                observation = blank_observation(runtime)
            else:
                observation = extract_observation(view, runtime)

            action_vector, _ = model.predict(observation, deterministic=bool(args.deterministic))
            ai_action = sb3_vector_to_env_action(action_vector)
            ai_events = action_codec.decode(ai_action)

            if args.allow_manual_input:
                manual_events = tuple(event for event in polled if event.type != EventType.QUIT)
                step_events = tuple(manual_events) + tuple(ai_events)
            else:
                step_events = tuple(ai_events)

            driver.step(step_events)
            platform.present(driver.context, driver.scene_manager.current_scene_name, 0.0)
            steps += 1

            runtime = driver.context.runtime
            if runtime.player_dead:
                stop_reason = "death"
                break
            if runtime.mode == AppMode.RUN_COMPLETE or runtime.progression_event == "run_complete":
                stop_reason = "run_complete"
                break
            if max_steps > 0 and steps >= max_steps:
                stop_reason = "max_steps"
                break
            if max_seconds > 0.0 and (perf_counter() - wall_start) >= max_seconds:
                stop_reason = "max_seconds"
                break

            frame_elapsed = perf_counter() - frame_start
            wait_seconds = target_dt - frame_elapsed
            if wait_seconds > 0.0:
                sleep(wait_seconds)
    finally:
        platform.shutdown(driver.context)
        driver.close()

    total_wall_seconds = perf_counter() - wall_start
    achieved_fps = float(steps) / total_wall_seconds if total_wall_seconds > 0 else 0.0
    print(
        "Playback finished reason=%s steps=%d wall_seconds=%.2f effective_fps=%.1f device=%s"
        % (
            stop_reason,
            steps,
            total_wall_seconds,
            achieved_fps,
            device,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
