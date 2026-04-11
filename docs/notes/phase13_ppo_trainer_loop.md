# Phase 13: PPO Trainer + Checkpoint/Eval Loop (Plan)

This phase builds a practical PPO training pipeline on top of the Phase 12 Gymnasium env.

## Goals

- Provide a runnable PPO trainer CLI for local experimentation.
- Save periodic checkpoints during training.
- Run periodic evaluation and keep best-model artifacts.
- Support resume-from-checkpoint workflows.
- Support Apple Silicon (`mps`) and CUDA (`cuda`) device selection with safe fallback.

## Constraints

- Keep default runtime and release verification dependency-safe for non-AI users.
- Preserve existing Gym env contract from Phase 12.
- Install new training modules via conda in current env (`ultimatetk`) when needed.

## Architecture decisions

- Use Stable-Baselines3 PPO with `MultiInputPolicy` for dict observations (`rays`, `state`).
- Add a Gym action wrapper to expose PPO-friendly `MultiDiscrete` action vectors while preserving internal env action schema.
- Device selection token is explicit: `auto|cpu|mps|cuda`.
- `auto` preference order: `cuda -> cpu` (MPS remains explicit opt-in via `--device mps`).

## Workstreams

### Workstream 1: Training adapters and device selection

- [x] Add SB3 action wrapper translating `MultiDiscrete(11)` into env action dict.
- [x] Add env-factory helper for trainer/eval scripts.
- [x] Add torch device capability detection and resolution helper.

### Workstream 2: PPO trainer CLI

- [x] Add `tools/ppo_train.py` entrypoint.
- [x] Add checkpoint callback wiring.
- [x] Add eval callback wiring with best-model save path.
- [x] Add resume-from-checkpoint support.
- [x] Write run config/artifact metadata per run directory.

### Workstream 3: Standalone evaluation CLI

- [x] Add `tools/ppo_eval.py` for checkpoint/final-model evaluation.
- [x] Report per-episode and aggregate metrics.

### Workstream 4: Tests

- [x] Add unit tests for SB3 action wrapper mapping/shape contract.
- [x] Add unit tests for device resolver behavior.
- [x] Add optional dependency-safe script import/argument smoke tests.

### Workstream 5: Docs and tracking

- [x] Update `README.md` with trainer/eval usage and device guidance.
- [x] Update optional training extras in `pyproject.toml`.
- [x] Update `python_refactor.md` progress log after validation run.

## Validation matrix (planned)

- `python3 -m pytest tests/unit/test_sb3_action_wrapper.py tests/unit/test_training_device.py`
- `python3 -m pytest tests/unit/test_gym_env.py tests/integration/test_gym_env_progression.py tests/integration/test_gym_env_shop_progression.py`
- Trainer smoke (short):
  - `python3 tools/ppo_train.py --total-timesteps 512 --n-envs 1 --eval-freq 256 --checkpoint-freq 256 --device cpu`
- Eval smoke:
  - `python3 tools/ppo_eval.py --model <checkpoint-or-final.zip> --episodes 1 --device cpu`
- Safety bundle:
  - `python3 tools/release_verification.py`

## Progress log

- Added training adapter modules:
  - `src/ultimatetk/ai/sb3_action_wrapper.py`
  - `src/ultimatetk/ai/sb3_env_factory.py`
  - `src/ultimatetk/ai/training_device.py`
- Added PPO tooling:
  - `tools/ppo_train.py`
  - `tools/ppo_eval.py`
- Added throughput optimizations:
  - training/eval env path now skips scene rendering by default (opt-in flags keep rendering available for debugging)
  - training callbacks can be disabled (`--eval-freq 0`, `--checkpoint-freq 0`) for maximum step throughput
  - `auto` device resolution now prefers `cpu` on non-CUDA hosts to avoid low-throughput MPS default behavior
  - PPO trainer now requires tensorboard and always enables tensorboard logging at training start, printing browser launch instructions
- Added tests:
  - `tests/unit/test_sb3_action_wrapper.py`
  - `tests/unit/test_training_device.py`
  - `tests/unit/test_ppo_tools_cli.py`
- Updated packaging/docs/tracking:
  - `pyproject.toml`
  - `README.md`
  - `python_refactor.md`
- Added configurable weapon-mode training scenarios:
  - `tools/ppo_train.py` now exposes `--weapon-mode` with snake_case weapon slots plus `normal_mode`
  - `TrainingRuntimeDriver` now applies non-`normal_mode` overrides (selected-weapon lock, true infinite player ammo, crate suppression)
  - env-factory/gym wiring propagates weapon mode from trainer to runtime (`src/ultimatetk/ai/sb3_env_factory.py`, `src/ultimatetk/ai/gym_env.py`)
- Added evaluation weapon-mode parity:
  - `tools/ppo_eval.py` now exposes `--weapon-mode` with the same choices as training
  - eval env wiring now forwards weapon mode to runtime so checkpoint evaluation can mirror training scenario constraints exactly
- Installed extra training dependency in active conda env:
  - `conda install -y -n ultimatetk -c conda-forge tensorboard`

## Validation snapshot

- `python3 -m pytest tests/unit/test_sb3_action_wrapper.py tests/unit/test_training_device.py` -> `8 passed`.
- `python3 -m pytest tests/unit/test_training_device.py tests/unit/test_sb3_action_wrapper.py tests/unit/test_ppo_tools_cli.py` -> `10 passed`.
- `python3 -m pytest tests/unit/test_gym_env.py tests/integration/test_gym_env_progression.py tests/integration/test_gym_env_shop_progression.py` -> `6 passed`.
- `python3 -m pytest tests/unit/test_gym_env.py tests/unit/test_ppo_tools_cli.py` -> `8 passed`.
- `python3 tools/ppo_train.py --total-timesteps 512 --n-envs 1 --eval-freq 0 --checkpoint-freq 0 --device auto --run-name phase13_smoke_fast_auto` -> smoke run passed on uncapped path (`fps` reported as `1211`, final model artifact created).
- `python3 tools/ppo_eval.py --model runs/ai/ppo/phase13_smoke_fast_auto/final_model.zip --episodes 1 --deterministic --device auto` -> eval smoke passed.
- `python3 tools/release_verification.py --skip-integration` -> unit verification bundle passed (`183 passed`).
