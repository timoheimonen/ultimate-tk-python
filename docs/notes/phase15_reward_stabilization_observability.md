# Phase 15: Reward Stabilization + Observability (Plan)

This phase hardens reward-learning stability and makes reward dynamics easier to inspect during training.

## Goals

- Keep reward defaults in one canonical current-state document.
- Add optional per-step reward-component observability for debugging and tuning.
- Define repeatable A/B validation protocol for reward changes.

## Scope

- In scope: reward shaping telemetry, test coverage for telemetry consistency, documentation cleanup and evaluation protocol.
- Out of scope: changing core gameplay mechanics, changing observation/action contracts, large PPO architecture changes.

## Workstreams

### Workstream 1: Canonical reward documentation

- [x] Rewrite `docs/notes/ai_gym_reward_improvements.md` to authoritative current-state format.
- [x] Mark old reward-value narratives as superseded historical context.

### Workstream 2: Reward breakdown telemetry

- [x] Add optional reward breakdown payload to env step info (for example `info["reward_breakdown"]`).
- [x] Ensure payload is stable and machine-readable for analysis scripts.

### Workstream 3: Tests

- [x] Add unit coverage for reward-breakdown accounting consistency.
- [x] Verify reward sum equals emitted scalar reward across representative scenarios.

### Workstream 4: Evaluation protocol

- [x] Add short PPO A/B protocol (baseline vs new reward config) with fixed seeds.
- [x] Record minimum report fields (episode reward mean, episode length mean, terminal reason distribution).

## PPO A/B protocol (fixed-seed smoke)

Use matched hyperparameters and seeds, changing only reward configuration under test.

1) Train run A and run B with same arguments except reward variant source.

```bash
python3 tools/ppo_train.py --run-name phase15_a --total-timesteps 2048 --n-envs 1 --seed 123 --eval-freq 0 --checkpoint-freq 0 --device auto
python3 tools/ppo_train.py --run-name phase15_b --total-timesteps 2048 --n-envs 1 --seed 123 --eval-freq 0 --checkpoint-freq 0 --device auto
```

2) Evaluate both models with fixed episode count/seed and export summaries.

```bash
python3 tools/ppo_eval.py --model runs/ai/ppo/phase15_a/final_model.zip --episodes 5 --seed 321 --deterministic --device auto --summary-json-out runs/ai/ppo/phase15_a/eval_summary.json
python3 tools/ppo_eval.py --model runs/ai/ppo/phase15_b/final_model.zip --episodes 5 --seed 321 --deterministic --device auto --summary-json-out runs/ai/ppo/phase15_b/eval_summary.json
```

3) Compare required fields from both summary files:

- `mean_reward`
- `mean_steps`
- `reason_counts` (terminal reason distribution)
- `completion_rate`

## Validation matrix (planned)

- `pytest tests/unit/test_gym_reward.py`
- `pytest tests/unit/test_gym_env.py`
- `python3 tools/gym_random_policy_smoke.py --episodes 3 --max-steps 500`
- Short PPO A/B smoke runs with identical seeds and matched hyperparameters

## Exit criteria

- Current reward defaults and behavior documented without contradictions.
- Reward telemetry available for tuning/debug sessions.
- Tests verify telemetry accounting and no regressions in reward mechanics.
- A/B result snapshot captured in tracker notes.

## Validation snapshot

- `pytest tests/unit/test_gym_reward.py tests/unit/test_gym_env.py` -> `24 passed`.
- `python3 tools/gym_random_policy_smoke.py --episodes 3 --max-steps 500` -> passed (3 episodes).
