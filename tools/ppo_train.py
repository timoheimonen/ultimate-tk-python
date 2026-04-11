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


DEFAULT_TOTAL_TIMESTEPS = 5_000_000
DEFAULT_N_ENVS = 1
DEFAULT_MAX_EPISODE_STEPS = 6000
DEFAULT_TARGET_TICK_RATE = 40
DEFAULT_CHECKPOINT_FREQ = 1_000_000
DEFAULT_EVAL_FREQ = 25_000
DEFAULT_EVAL_EPISODES = 5
DEFAULT_SEED = 123
DEFAULT_DEVICE = "auto"
DEFAULT_N_STEPS = 4096
DEFAULT_BATCH_SIZE = 512
DEFAULT_LEARNING_RATE = 0.00005
DEFAULT_LEARNING_RATE_START = 0.0003
DEFAULT_DECAY_RATIO = 0.5
DEFAULT_ENT_COEF = 0.01
DEFAULT_ENT_COEF_START = 0.05
DEFAULT_GAMMA = 0.99
DEFAULT_GAE_LAMBDA = 0.95
DEFAULT_CLIP_RANGE = 0.2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train PPO policy on UltimateTK Gymnasium env")
    parser.add_argument("--run-name", default="", help="Run directory name under runs/ai/ppo")
    parser.add_argument("--runs-root", default="", help="Override runs root directory")
    parser.add_argument("--total-timesteps", type=int, default=DEFAULT_TOTAL_TIMESTEPS, help="Training timesteps")
    parser.add_argument("--n-envs", type=int, default=DEFAULT_N_ENVS, help="Number of parallel envs")
    parser.add_argument("--max-episode-steps", type=int, default=DEFAULT_MAX_EPISODE_STEPS, help="Max steps per episode")
    parser.add_argument("--target-tick-rate", type=int, default=DEFAULT_TARGET_TICK_RATE, help="Fixed simulation tick rate")
    parser.add_argument("--checkpoint-freq", type=int, default=DEFAULT_CHECKPOINT_FREQ, help="Checkpoint frequency")
    parser.add_argument("--eval-freq", type=int, default=DEFAULT_EVAL_FREQ, help="Evaluation frequency")
    parser.add_argument("--eval-episodes", type=int, default=DEFAULT_EVAL_EPISODES, help="Evaluation episodes per run")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Base random seed")
    parser.add_argument("--device", default=DEFAULT_DEVICE, choices=("auto", "cpu", "mps", "cuda"))
    parser.add_argument("--resume-from", default="", help="Path to .zip checkpoint to resume from")
    parser.add_argument("--n-steps", type=int, default=DEFAULT_N_STEPS, help="PPO rollout steps")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="PPO batch size")
    parser.add_argument(
        "--learning-rate",
        type=float,
        default=DEFAULT_LEARNING_RATE,
        help="Target/min PPO learning rate after linear decay",
    )
    parser.add_argument(
        "--learning-rate-start",
        type=float,
        default=DEFAULT_LEARNING_RATE_START,
        help="Starting PPO learning rate before linear decay",
    )
    parser.add_argument(
        "--learning-rate-decay-steps",
        type=int,
        default=None,
        help="Override linear LR decay duration in timesteps (default: 80%% of total timesteps)",
    )
    parser.add_argument(
        "--decay-ratio",
        type=float,
        default=DEFAULT_DECAY_RATIO,
        help="Default decay fraction of total timesteps when explicit decay steps are not set",
    )
    parser.add_argument(
        "--ent-coef",
        type=float,
        default=DEFAULT_ENT_COEF,
        help="Target/min entropy coefficient after linear decay",
    )
    parser.add_argument(
        "--ent-coef-start",
        type=float,
        default=DEFAULT_ENT_COEF_START,
        help="Starting entropy coefficient before linear decay",
    )
    parser.add_argument(
        "--ent-coef-decay-steps",
        type=int,
        default=None,
        help="Override entropy decay duration in timesteps (default: 80%% of total timesteps)",
    )
    parser.add_argument("--gamma", type=float, default=DEFAULT_GAMMA, help="Discount factor")
    parser.add_argument("--gae-lambda", type=float, default=DEFAULT_GAE_LAMBDA, help="GAE lambda")
    parser.add_argument("--clip-range", type=float, default=DEFAULT_CLIP_RANGE, help="PPO clipping range")
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


def _import_training_dependencies() -> tuple[object, object, object, object, object, object]:
    try:
        from stable_baselines3 import PPO
        from stable_baselines3.common.callbacks import BaseCallback, CallbackList, CheckpointCallback, EvalCallback
        from stable_baselines3.common.vec_env import DummyVecEnv, VecMonitor
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "stable-baselines3 dependencies are missing. Install with conda, for example: "
            "conda install -n ultimatetk -c conda-forge pytorch stable-baselines3",
        ) from exc

    try:
        import tensorboard  # noqa: F401
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "tensorboard is required for PPO training logs. Install with conda, for example: "
            "conda install -n ultimatetk -c conda-forge tensorboard",
        ) from exc

    return PPO, BaseCallback, CallbackList, CheckpointCallback, EvalCallback, (DummyVecEnv, VecMonitor)


def _default_run_name() -> str:
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"ppo_{timestamp}"


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


def _linear_decay_value(*, start: float, end: float, decay_steps: int, step: int) -> float:
    elapsed = max(0, int(step))
    if elapsed >= int(decay_steps):
        return float(end)
    ratio = float(elapsed) / float(decay_steps)
    return float(start + (end - start) * ratio)


def _build_linear_lr_schedule(*, lr_start: float, lr_end: float, decay_steps: int, total_timesteps: int):
    if lr_start <= 0.0 or lr_end <= 0.0:
        raise ValueError("learning rates must be > 0")
    if decay_steps < 1:
        raise ValueError("--learning-rate-decay-steps must be >= 1")
    if total_timesteps < 1:
        raise ValueError("--total-timesteps must be >= 1")

    effective_decay_steps = min(int(decay_steps), int(total_timesteps))

    def _schedule(progress_remaining: float) -> float:
        elapsed = (1.0 - float(progress_remaining)) * float(total_timesteps)
        return _linear_decay_value(
            start=float(lr_start),
            end=float(lr_end),
            decay_steps=effective_decay_steps,
            step=int(elapsed),
        )

    return _schedule


def _build_entropy_decay_callback(*, base_callback_cls: type, ent_start: float, ent_end: float, decay_steps: int):
    class EntCoefDecayCallback(base_callback_cls):
        def _on_step(self) -> bool:  # type: ignore[override]
            self.model.ent_coef = _linear_decay_value(
                start=float(ent_start),
                end=float(ent_end),
                decay_steps=int(decay_steps),
                step=int(self.model.num_timesteps),
            )
            return True

    return EntCoefDecayCallback()


def main() -> int:
    args = parse_args()

    if args.total_timesteps < 1:
        raise ValueError("--total-timesteps must be >= 1")
    if args.n_envs < 1:
        raise ValueError("--n-envs must be >= 1")
    if args.eval_episodes < 1:
        raise ValueError("--eval-episodes must be >= 1")
    if args.learning_rate <= 0.0:
        raise ValueError("--learning-rate must be > 0")
    if args.learning_rate_start <= 0.0:
        raise ValueError("--learning-rate-start must be > 0")
    if args.learning_rate_start < args.learning_rate:
        raise ValueError("--learning-rate-start must be >= --learning-rate")
    if args.decay_ratio <= 0.0 or args.decay_ratio > 1.0:
        raise ValueError("--decay-ratio must be in (0, 1]")
    if args.learning_rate_decay_steps is not None and args.learning_rate_decay_steps < 1:
        raise ValueError("--learning-rate-decay-steps must be >= 1")
    if args.ent_coef <= 0.0:
        raise ValueError("--ent-coef must be > 0")
    if args.ent_coef_start <= 0.0:
        raise ValueError("--ent-coef-start must be > 0")
    if args.ent_coef_start < args.ent_coef:
        raise ValueError("--ent-coef-start must be >= --ent-coef")
    if args.ent_coef_decay_steps is not None and args.ent_coef_decay_steps < 1:
        raise ValueError("--ent-coef-decay-steps must be >= 1")
    if args.gae_lambda <= 0.0 or args.gae_lambda > 1.0:
        raise ValueError("--gae-lambda must be in (0, 1]")
    if args.clip_range <= 0.0 or args.clip_range > 1.0:
        raise ValueError("--clip-range must be in (0, 1]")

    PPO, BaseCallback, CallbackList, CheckpointCallback, EvalCallback, vec_env_types = _import_training_dependencies()
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
    default_decay_steps = max(1, int(float(args.total_timesteps) * float(args.decay_ratio)))
    effective_lr_decay_steps = (
        int(args.learning_rate_decay_steps)
        if args.learning_rate_decay_steps is not None
        else default_decay_steps
    )
    effective_ent_decay_steps = (
        int(args.ent_coef_decay_steps)
        if args.ent_coef_decay_steps is not None
        else default_decay_steps
    )
    effective_lr_decay_steps = min(int(effective_lr_decay_steps), int(args.total_timesteps))

    learning_rate_schedule = _build_linear_lr_schedule(
        lr_start=float(args.learning_rate_start),
        lr_end=float(args.learning_rate),
        decay_steps=effective_lr_decay_steps,
        total_timesteps=int(args.total_timesteps),
    )
    effective_ent_decay_steps = min(int(effective_ent_decay_steps), int(args.total_timesteps))

    if resume_path:
        model = PPO.load(
            str(Path(resume_path).expanduser().resolve()),
            env=train_env,
            device=device,
            print_system_info=False,
        )
        model.learning_rate = learning_rate_schedule
        model.lr_schedule = learning_rate_schedule
        model.ent_coef = _linear_decay_value(
            start=float(args.ent_coef_start),
            end=float(args.ent_coef),
            decay_steps=effective_ent_decay_steps,
            step=int(model.num_timesteps),
        )
        reset_num_timesteps = False
    else:
        model = PPO(
            "MultiInputPolicy",
            train_env,
            verbose=1,
            seed=args.seed,
            device=device,
            tensorboard_log=str(tensorboard_dir),
            n_steps=max(1, int(args.n_steps)),
            batch_size=max(1, int(args.batch_size)),
            learning_rate=learning_rate_schedule,
            ent_coef=float(args.ent_coef_start),
            gamma=float(args.gamma),
            gae_lambda=float(args.gae_lambda),
            clip_range=float(args.clip_range),
        )
        reset_num_timesteps = True

    callback_items: list[object] = []
    callback_items.append(
        _build_entropy_decay_callback(
            base_callback_cls=BaseCallback,
            ent_start=float(args.ent_coef_start),
            ent_end=float(args.ent_coef),
            decay_steps=effective_ent_decay_steps,
        ),
    )
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
        "learning_rate_start": float(args.learning_rate_start),
        "learning_rate_decay_steps": int(effective_lr_decay_steps),
        "ent_coef": float(args.ent_coef),
        "ent_coef_start": float(args.ent_coef_start),
        "ent_coef_decay_steps": int(effective_ent_decay_steps),
        "decay_ratio": float(args.decay_ratio),
        "gamma": float(args.gamma),
        "gae_lambda": float(args.gae_lambda),
        "clip_range": float(args.clip_range),
        "resume_from": resume_path,
        "render_training_scenes": bool(args.render_training_scenes),
    }
    _write_run_config(run_dir / "run_config.json", config_payload)

    print(f"TensorBoard logdir: {tensorboard_dir}")
    print(
        "To view live training metrics, run: "
        f"tensorboard --logdir '{tensorboard_dir}' --host 127.0.0.1 --port 6006",
    )
    print("Then open: http://127.0.0.1:6006/")

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
