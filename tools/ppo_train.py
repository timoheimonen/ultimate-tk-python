from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
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
    parser = argparse.ArgumentParser(description="Train PPO policy on UltimateTK Gymnasium env")
    parser.add_argument("--run-name", default="", help="Run directory name under runs/ai/ppo")
    parser.add_argument("--runs-root", default="", help="Override runs root directory")
    parser.add_argument("--total-timesteps", type=int, default=200_000, help="Training timesteps")
    parser.add_argument("--n-envs", type=int, default=1, help="Number of parallel envs")
    parser.add_argument("--max-episode-steps", type=int, default=6000, help="Max steps per episode")
    parser.add_argument("--target-tick-rate", type=int, default=40, help="Fixed simulation tick rate")
    parser.add_argument("--checkpoint-freq", type=int, default=50_000, help="Checkpoint frequency")
    parser.add_argument("--eval-freq", type=int, default=25_000, help="Evaluation frequency")
    parser.add_argument("--eval-episodes", type=int, default=5, help="Evaluation episodes per run")
    parser.add_argument("--seed", type=int, default=123, help="Base random seed")
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "mps", "cuda"))
    parser.add_argument("--resume-from", default="", help="Path to .zip checkpoint to resume from")
    parser.add_argument("--n-steps", type=int, default=1024, help="PPO rollout steps")
    parser.add_argument("--batch-size", type=int, default=256, help="PPO batch size")
    parser.add_argument("--learning-rate", type=float, default=3e-4, help="PPO learning rate")
    parser.add_argument("--gamma", type=float, default=0.99, help="Discount factor")
    parser.add_argument(
        "--disable-asset-manifest-check",
        action="store_true",
        help="Disable game_data asset manifest enforcement",
    )
    parser.add_argument(
        "--render-training-scenes",
        action="store_true",
        help="Render scene frames during training (off by default for max throughput)",
    )
    return parser.parse_args()


def _import_training_dependencies() -> tuple[object, object, object, object, object]:
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback, EvalCallback
        from stable_baselines3.common.vec_env import DummyVecEnv, VecMonitor
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "stable-baselines3 dependencies are missing. Install with conda, for example: "
            "conda install -n ultimatetk -c conda-forge pytorch stable-baselines3",
        ) from exc
    return PPO, CallbackList, CheckpointCallback, EvalCallback, (DummyVecEnv, VecMonitor)


def _default_run_name() -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"ppo_{timestamp}"


def _tensorboard_available() -> bool:
    try:
        import tensorboard  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


def _build_run_dir(args: argparse.Namespace) -> Path:
    if args.runs_root:
        runs_root = Path(args.runs_root).expanduser().resolve()
    else:
        runs_root = (PROJECT_ROOT / "runs" / "ai" / "ppo").resolve()
    runs_root.mkdir(parents=True, exist_ok=True)

    run_name = args.run_name.strip() or _default_run_name()
    run_dir = runs_root / run_name
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _write_run_config(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()

    if args.total_timesteps < 1:
        raise ValueError("--total-timesteps must be >= 1")
    if args.n_envs < 1:
        raise ValueError("--n-envs must be >= 1")
    if args.eval_episodes < 1:
        raise ValueError("--eval-episodes must be >= 1")

    PPO, CallbackList, CheckpointCallback, EvalCallback, vec_env_types = _import_training_dependencies()
    DummyVecEnv, VecMonitor = vec_env_types

    caps = detect_torch_capabilities()
    device = resolve_torch_device(args.device, capabilities=caps)

    run_dir = _build_run_dir(args)
    checkpoints_dir = run_dir / "checkpoints"
    eval_dir = run_dir / "eval"
    best_dir = run_dir / "best_model"
    tensorboard_dir = run_dir / "tensorboard"
    checkpoint_save_freq = max(0, int(args.checkpoint_freq))
    eval_freq = max(0, int(args.eval_freq))

    if checkpoint_save_freq > 0:
        checkpoints_dir.mkdir(parents=True, exist_ok=True)
    if eval_freq > 0:
        eval_dir.mkdir(parents=True, exist_ok=True)
        best_dir.mkdir(parents=True, exist_ok=True)
    tensorboard_enabled = _tensorboard_available()
    if tensorboard_enabled:
        tensorboard_dir.mkdir(parents=True, exist_ok=True)

    env_factory = build_sb3_env_factory(
        project_root=PROJECT_ROOT,
        max_episode_steps=max(1, int(args.max_episode_steps)),
        target_tick_rate=max(1, int(args.target_tick_rate)),
        enforce_asset_manifest=not args.disable_asset_manifest_check,
        render_enabled=bool(args.render_training_scenes),
    )
    train_env = DummyVecEnv([env_factory for _ in range(args.n_envs)])
    train_env = VecMonitor(train_env)
    train_env.seed(args.seed)

    eval_env = None
    if eval_freq > 0:
        eval_env = DummyVecEnv([env_factory])
        eval_env = VecMonitor(eval_env)
        eval_env.seed(args.seed + 10_000)

    resume_path = args.resume_from.strip()
    if resume_path:
        model = PPO.load(
            str(Path(resume_path).expanduser().resolve()),
            env=train_env,
            device=device,
            print_system_info=False,
        )
        reset_num_timesteps = False
    else:
        model = PPO(
            "MultiInputPolicy",
            train_env,
            verbose=1,
            seed=args.seed,
            device=device,
            tensorboard_log=str(tensorboard_dir) if tensorboard_enabled else None,
            n_steps=max(1, int(args.n_steps)),
            batch_size=max(1, int(args.batch_size)),
            learning_rate=float(args.learning_rate),
            gamma=float(args.gamma),
        )
        reset_num_timesteps = True

    callback_items: list[object] = []
    if checkpoint_save_freq > 0:
        callback_items.append(
            CheckpointCallback(
                save_freq=max(1, checkpoint_save_freq // args.n_envs),
                save_path=str(checkpoints_dir),
                name_prefix="ppo_model",
            ),
        )
    if eval_freq > 0:
        assert eval_env is not None
        callback_items.append(
            EvalCallback(
                eval_env,
                best_model_save_path=str(best_dir),
                log_path=str(eval_dir),
                eval_freq=max(1, eval_freq // args.n_envs),
                n_eval_episodes=int(args.eval_episodes),
                deterministic=True,
                render=False,
            ),
        )
    callback = CallbackList(callback_items) if callback_items else None

    config_payload: dict[str, object] = {
        "run_dir": str(run_dir),
        "device_requested": args.device,
        "device_resolved": device,
        "torch_capabilities": {
            "torch_installed": caps.torch_installed,
            "cuda_available": caps.cuda_available,
            "mps_available": caps.mps_available,
        },
        "total_timesteps": int(args.total_timesteps),
        "n_envs": int(args.n_envs),
        "max_episode_steps": int(args.max_episode_steps),
        "target_tick_rate": int(args.target_tick_rate),
        "checkpoint_freq": int(args.checkpoint_freq),
        "eval_freq": int(args.eval_freq),
        "eval_episodes": int(args.eval_episodes),
        "seed": int(args.seed),
        "n_steps": int(args.n_steps),
        "batch_size": int(args.batch_size),
        "learning_rate": float(args.learning_rate),
        "gamma": float(args.gamma),
        "resume_from": resume_path,
        "render_training_scenes": bool(args.render_training_scenes),
    }
    _write_run_config(run_dir / "run_config.json", config_payload)

    if not tensorboard_enabled:
        print("tensorboard is not installed; tensorboard logging is disabled")

    try:
        model.learn(
            total_timesteps=int(args.total_timesteps),
            callback=callback,
            reset_num_timesteps=reset_num_timesteps,
            progress_bar=False,
        )
        final_model_path = run_dir / "final_model"
        model.save(str(final_model_path))
    finally:
        train_env.close()
        if eval_env is not None:
            eval_env.close()

    print(f"Training complete. Artifacts: {run_dir}")
    if checkpoint_save_freq > 0:
        print(f"- checkpoints: {checkpoints_dir}")
    if eval_freq > 0:
        print(f"- best model dir: {best_dir}")
    print(f"- final model: {run_dir / 'final_model.zip'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
