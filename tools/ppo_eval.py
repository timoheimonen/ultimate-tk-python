from __future__ import annotations

import argparse
from pathlib import Path
import sys


THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.ai.sb3_env_factory import build_sb3_env_factory
from ultimatetk.ai.training_device import detect_torch_capabilities, resolve_torch_device


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate PPO checkpoint on UltimateTKEnv")
    parser.add_argument("--model", required=True, help="Path to PPO .zip checkpoint")
    parser.add_argument("--episodes", type=int, default=5, help="Evaluation episodes")
    parser.add_argument("--seed", type=int, default=123, help="Base random seed")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda"))
    parser.add_argument("--deterministic", action="store_true", help="Use deterministic policy actions")
    parser.add_argument("--max-episode-steps", type=int, default=6000, help="Max steps per episode")
    parser.add_argument("--target-tick-rate", type=int, default=40, help="Fixed simulation tick rate")
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
    return parser.parse_args()


def _import_eval_dependencies() -> object:
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
    if args.episodes < 1:
        raise ValueError("--episodes must be >= 1")

    PPO = _import_eval_dependencies()
    caps = detect_torch_capabilities()
    device = resolve_torch_device(args.device, capabilities=caps)

    env = build_sb3_env_factory(
        project_root=PROJECT_ROOT,
        max_episode_steps=max(1, int(args.max_episode_steps)),
        target_tick_rate=max(1, int(args.target_tick_rate)),
        enforce_asset_manifest=not args.disable_asset_manifest_check,
        render_enabled=bool(args.render_scenes),
    )()

    model_path = Path(args.model).expanduser().resolve()
    model = PPO.load(str(model_path), env=env, device=device, print_system_info=False)

    episode_rewards: list[float] = []
    episode_lengths: list[int] = []
    completion_count = 0

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
    print(
        "aggregate episodes=%d mean_reward=%.3f mean_steps=%.1f completion_rate=%.3f device=%s"
        % (
            len(episode_rewards),
            mean_reward,
            mean_steps,
            completion_rate,
            device,
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
