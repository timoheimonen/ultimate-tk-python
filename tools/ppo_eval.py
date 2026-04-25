from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.ai.sb3_env_factory import build_sb3_env_factory
from ultimatetk.ai.runtime_driver import WEAPON_MODE_NORMAL, WEAPON_MODE_TO_SLOT
from ultimatetk.ai.training_device import detect_torch_capabilities, resolve_torch_device


DEFAULT_EVAL_EPISODES = 5
DEFAULT_SEED = 123
DEFAULT_DEVICE = "auto"
DEFAULT_DETERMINISTIC = True
DEFAULT_MAX_EPISODE_STEPS = 6000
DEFAULT_TARGET_TICK_RATE = 40
WEAPON_MODE_CHOICES: tuple[str, ...] = (WEAPON_MODE_NORMAL, *WEAPON_MODE_TO_SLOT.keys())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate PPO checkpoint on UltimateTKEnv")
    parser.add_argument("--model", required=True, help="Path to PPO .zip checkpoint")
    parser.add_argument("--episodes", type=int, default=DEFAULT_EVAL_EPISODES, help="Evaluation episodes")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Base random seed")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=("auto", "cpu", "mps", "cuda"))
    parser.add_argument(
        "--deterministic",
        dest="deterministic",
        action="store_true",
        default=DEFAULT_DETERMINISTIC,
        help="Use deterministic policy actions (default)",
    )
    parser.add_argument(
        "--stochastic",
        dest="deterministic",
        action="store_false",
        help="Use stochastic policy sampling instead of deterministic actions",
    )
    parser.add_argument(
        "--max-episode-steps",
        type=int,
        default=DEFAULT_MAX_EPISODE_STEPS,
        help="Max steps per episode",
    )
    parser.add_argument(
        "--target-tick-rate",
        type=int,
        default=DEFAULT_TARGET_TICK_RATE,
        help="Fixed simulation tick rate",
    )
    parser.add_argument(
        "--disable-asset-manifest-check",
        action="store_true",
        help="Disable game_data asset manifest enforcement",
    )
    parser.add_argument(
        "--render-scenes",
        action="store_true",
        help="Render scene frames during evaluation (off by default for max throughput)",
    )
    parser.add_argument(
        "--weapon-mode",
        default=WEAPON_MODE_NORMAL,
        choices=WEAPON_MODE_CHOICES,
        help=(
            "Evaluation weapon mode. normal_mode keeps current gameplay behavior; "
            "other modes force selected weapon with infinite ammo and disable crates"
        ),
    )
    parser.add_argument(
        "--summary-json-out",
        default="",
        help="Optional path for writing aggregate evaluation summary JSON",
    )
    return parser.parse_args()


def _import_eval_dependencies() -> tuple[object, object]:
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.vec_env import DummyVecEnv, VecNormalize
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "stable-baselines3 dependencies are missing. Install with conda, for example: "
            "conda install -n ultimatetk -c conda-forge pytorch stable-baselines3",
        ) from exc
    return PPO, (DummyVecEnv, VecNormalize)


def main() -> int:
    args = parse_args()
    if args.episodes < 1:
        raise ValueError("--episodes must be >= 1")

    PPO, _vec_env_types = _import_eval_dependencies()
    caps = detect_torch_capabilities()
    device = resolve_torch_device(args.device, capabilities=caps)

    env = build_sb3_env_factory(
        project_root=PROJECT_ROOT,
        max_episode_steps=max(1, int(args.max_episode_steps)),
        target_tick_rate=max(1, int(args.target_tick_rate)),
        enforce_asset_manifest=not args.disable_asset_manifest_check,
        render_enabled=bool(args.render_scenes),
        weapon_mode=str(args.weapon_mode),
        frame_skip=1,
    )()

    model_path = Path(args.model).expanduser().resolve()
    model = PPO.load(str(model_path), env=env, device=device, print_system_info=False)

    episode_rewards: list[float] = []
    episode_lengths: list[int] = []
    completion_count = 0
    reason_counts: dict[str, int] = {}

    try:
        for episode in range(args.episodes):
            observation, info = env.reset(seed=args.seed + episode)
            del info
            reward_total = 0.0
            step_count = 0
            terminated = False
            truncated = False
            terminal_reason = ""
            game_completed = False

            while not terminated and not truncated:
                action, _ = model.predict(observation, deterministic=bool(args.deterministic))
                observation, reward, terminated, truncated, info = env.step(action)
                reward_total += float(reward)
                step_count += 1
                terminal_reason = str(info.get("terminal_reason", ""))
                game_completed = bool(info.get("game_completed", False))

            if game_completed:
                completion_count += 1

            reason_key = terminal_reason or "unknown"
            reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1

            episode_rewards.append(reward_total)
            episode_lengths.append(step_count)
            print(
                "episode=%d steps=%d reward=%.3f terminated=%s truncated=%s reason=%s completed=%s"
                % (
                    episode,
                    step_count,
                    reward_total,
                    terminated,
                    truncated,
                    terminal_reason,
                    game_completed,
                ),
            )
    finally:
        env.close()

    mean_reward = sum(episode_rewards) / float(len(episode_rewards))
    mean_steps = sum(episode_lengths) / float(len(episode_lengths))
    completion_rate = completion_count / float(len(episode_rewards))
    sorted_reasons = sorted(reason_counts.items(), key=lambda item: item[0])
    reason_distribution = ",".join(f"{key}:{value}" for key, value in sorted_reasons)
    print(
        "aggregate episodes=%d mean_reward=%.3f mean_steps=%.1f completion_rate=%.3f reasons=%s device=%s weapon_mode=%s"
        % (
            len(episode_rewards),
            mean_reward,
            mean_steps,
            completion_rate,
            reason_distribution,
            device,
            str(args.weapon_mode),
        ),
    )

    if args.summary_json_out.strip():
        summary_path = Path(args.summary_json_out).expanduser().resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_payload = {
            "episodes": len(episode_rewards),
            "mean_reward": mean_reward,
            "mean_steps": mean_steps,
            "completion_rate": completion_rate,
            "reason_counts": {key: int(value) for key, value in sorted_reasons},
            "device": str(device),
            "weapon_mode": str(args.weapon_mode),
            "deterministic": bool(args.deterministic),
            "model": str(model_path),
        }
        summary_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
