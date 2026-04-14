from __future__ import annotations

import argparse
import math
from pathlib import Path
from time import perf_counter, sleep
import sys

import numpy as np


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.ai.action_codec import ActionCodec
from ultimatetk.ai.observation import (
    CHANNEL_C4,
    CHANNEL_CRATE_AMMO,
    CHANNEL_CRATE_ENERGY,
    CHANNEL_CRATE_WEAPON,
    CHANNEL_ENEMY,
    CHANNEL_MINE,
    CHANNEL_PROJECTILE,
    CHANNEL_WALL,
    RAY_CHANNEL_COUNT,
    RAY_SECTOR_COUNT,
    blank_observation,
    extract_observation,
)
from ultimatetk.ai.runtime_driver import WEAPON_MODE_NORMAL, TrainingRuntimeDriver
from ultimatetk.ai.sb3_action_wrapper import sb3_vector_to_env_action
from ultimatetk.ai.training_device import detect_torch_capabilities, resolve_torch_device
from ultimatetk.core.events import EventType
from ultimatetk.core.platform_pygame import PygamePlatformBackend
from ultimatetk.core.state import AppMode


WEAPON_MODE_CHOICES: tuple[str, ...] = (
    WEAPON_MODE_NORMAL,
    "fist",
    "pistola",
    "shotgun",
    "uzi",
    "auto_rifle",
    "grenade_launcher",
    "auto_grenadier",
    "heavy_launcher",
    "auto_shotgun",
    "c4_activator",
    "flame_thrower",
    "mine_dropper",
)

_RAY_CHANNEL_LEGEND: tuple[tuple[str, int, tuple[int, int, int]], ...] = (
    ("wall", CHANNEL_WALL, (255, 255, 255)),
    ("enemy", CHANNEL_ENEMY, (255, 70, 70)),
    ("proj", CHANNEL_PROJECTILE, (255, 170, 60)),
    ("crateW", CHANNEL_CRATE_WEAPON, (80, 170, 255)),
    ("crateA", CHANNEL_CRATE_AMMO, (100, 220, 120)),
    ("crateE", CHANNEL_CRATE_ENERGY, (220, 110, 255)),
    ("mine", CHANNEL_MINE, (255, 215, 70)),
    ("c4", CHANNEL_C4, (255, 120, 200)),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play PPO model with pygame visualization")
    parser.add_argument("--model", required=True, help="Path to PPO .zip model")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda"))
    parser.add_argument("--target-fps", type=int, default=40, help="Playback FPS limit")
    parser.add_argument("--window-scale", type=int, default=3, help="Pygame window scale")
    parser.add_argument(
        "--ray-debug-panel",
        action="store_true",
        help="Show right-side 360-degree ray debug panel",
    )
    parser.add_argument(
        "--ray-debug-width",
        type=int,
        default=320,
        help="Ray debug panel width in pixels",
    )
    parser.add_argument(
        "--ray-debug-scale",
        type=int,
        default=1,
        help="Ray debug panel UI scale",
    )
    parser.add_argument("--level-index", type=int, default=0, help="Start level index")
    parser.add_argument("--seed", type=int, default=123, help="Reserved for future deterministic hooks")
    parser.add_argument(
        "--weapon-mode",
        default=WEAPON_MODE_NORMAL,
        choices=WEAPON_MODE_CHOICES,
        help=(
            "Playback weapon mode. normal_mode keeps current gameplay behavior; "
            "other modes force selected weapon with infinite ammo and disable crates"
        ),
    )
    parser.add_argument("--max-steps", type=int, default=0, help="Optional step cap (0 disables)")
    parser.add_argument("--max-seconds", type=float, default=0.0, help="Optional wall-clock cap (0 disables)")
    parser.add_argument(
        "--deterministic",
        dest="deterministic",
        action="store_true",
        default=True,
        help="Use deterministic policy actions (default)",
    )
    parser.add_argument(
        "--stochastic",
        dest="deterministic",
        action="store_false",
        help="Use stochastic policy sampling instead of deterministic actions",
    )
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


def _build_ray_debug_draw_fn(
    latest_observation_ref: dict[str, dict[str, np.ndarray] | None],
    ui_scale: int,
) -> object:
    def draw_ray_panel(pygame_module: object, window: object, panel_rect: object) -> None:
        observation = latest_observation_ref.get("value")
        if not isinstance(observation, dict):
            return

        rays = observation.get("rays")
        if rays is None:
            return

        matrix = np.asarray(rays, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != RAY_SECTOR_COUNT or matrix.shape[1] < RAY_CHANNEL_COUNT:
            return

        panel_x = int(panel_rect.x)
        panel_y = int(panel_rect.y)
        panel_w = int(panel_rect.width)
        panel_h = int(panel_rect.height)
        margin = 12 * ui_scale
        legend_h = 22 * ui_scale
        radius = max(10, min(panel_w - (2 * margin), panel_h - (2 * margin) - (legend_h * 3)) // 2)
        center_x = panel_x + (panel_w // 2)
        center_y = panel_y + margin + radius

        pygame_module.draw.circle(window, (50, 55, 70), (center_x, center_y), radius, width=max(1, ui_scale))
        pygame_module.draw.circle(window, (30, 34, 44), (center_x, center_y), max(2, radius // 2), width=1)

        sector_angle = 360.0 / float(RAY_SECTOR_COUNT)
        for sector in range(RAY_SECTOR_COUNT):
            angle = math.radians((sector * sector_angle) + (sector_angle * 0.5))
            dir_x = math.sin(angle)
            dir_y = -math.cos(angle)
            spoke_color = (42, 48, 62) if (sector % 4 != 0) else (62, 70, 90)
            spoke_x = center_x + int(dir_x * radius)
            spoke_y = center_y + int(dir_y * radius)
            pygame_module.draw.line(window, spoke_color, (center_x, center_y), (spoke_x, spoke_y), width=1)

        for label, channel, color in _RAY_CHANNEL_LEGEND:
            del label
            for sector in range(RAY_SECTOR_COUNT):
                value = float(matrix[sector, channel])
                value = 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)
                angle = math.radians((sector * sector_angle) + (sector_angle * 0.5))
                dir_x = math.sin(angle)
                dir_y = -math.cos(angle)
                point_r = int(value * radius)
                px = center_x + int(dir_x * point_r)
                py = center_y + int(dir_y * point_r)
                pygame_module.draw.circle(window, color, (px, py), max(1, ui_scale))

        pygame_module.draw.circle(window, (255, 255, 255), (center_x, center_y), max(2, ui_scale + 1))
        pygame_module.draw.line(
            window,
            (255, 255, 255),
            (center_x, center_y),
            (center_x, center_y - radius),
            width=max(1, ui_scale),
        )

        font = pygame_module.font.Font(None, max(14, 14 * ui_scale))
        legend_x = panel_x + margin
        legend_y = center_y + radius + (8 * ui_scale)
        for idx, (label, _channel, color) in enumerate(_RAY_CHANNEL_LEGEND):
            row = idx // 2
            col = idx % 2
            x = legend_x + col * max(100, panel_w // 2 - margin)
            y = legend_y + row * legend_h
            pygame_module.draw.rect(window, color, (x, y + 3, 10 * ui_scale, 10 * ui_scale))
            text_surface = font.render(label, True, (220, 220, 230))
            window.blit(text_surface, (x + (14 * ui_scale), y))

    return draw_ray_panel


def main() -> int:
    args = parse_args()
    if args.target_fps < 1:
        raise ValueError("--target-fps must be >= 1")
    if args.window_scale < 1:
        raise ValueError("--window-scale must be >= 1")
    if args.ray_debug_width < 1:
        raise ValueError("--ray-debug-width must be >= 1")
    if args.ray_debug_scale < 1:
        raise ValueError("--ray-debug-scale must be >= 1")
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
        weapon_mode=str(args.weapon_mode),
    )
    action_codec = ActionCodec()
    action_codec.reset()

    latest_observation_ref: dict[str, dict[str, np.ndarray] | None] = {"value": None}
    debug_draw_fn = None
    panel_width = 0
    if args.ray_debug_panel:
        panel_width = int(args.ray_debug_width)
        debug_draw_fn = _build_ray_debug_draw_fn(latest_observation_ref, int(args.ray_debug_scale))

    platform = PygamePlatformBackend(
        window_scale=args.window_scale,
        debug_panel_width_px=panel_width,
        debug_draw_fn=debug_draw_fn,
    )
    platform.startup(driver.context)

    runtime = driver.context.runtime
    view = driver.gameplay_view()
    if view is None:
        latest_observation_ref["value"] = blank_observation(runtime)
    else:
        latest_observation_ref["value"] = extract_observation(view, runtime)

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
            latest_observation_ref["value"] = observation

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
