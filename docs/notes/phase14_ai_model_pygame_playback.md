# Phase 14: Saved AI Model Playback in Pygame (Plan)

This phase adds a visible playback path so trained PPO policies can be watched in the pygame runtime at normal capped FPS.

## Goals

- Load a saved PPO model and run it in-game with pygame presentation enabled.
- Keep playback at normal fixed-speed limits (default 40 FPS), not uncapped training throughput mode.
- Preserve phase-13 training stack and avoid destabilizing the main runtime entrypoint.

## Constraints

- Keep default game runtime path (`python -m ultimatetk`) unchanged for this slice.
- Keep optional dependency behavior explicit and error messages actionable.
- Use existing Gym observation/action semantics so playback matches training behavior.

## Architecture decisions

- Implement playback first as dedicated tool: `tools/ppo_play_pygame.py`.
- Reuse `TrainingRuntimeDriver` with `render_enabled=True` for scene update + frame generation.
- Reuse SB3 action mapping helper (`MultiDiscrete` vector -> env action dict) and `ActionCodec` for event conversion.
- Keep pygame event handling active for quit, with optional manual input mixing for debug runs.

## Workstreams

### Workstream 1: Playback tool

- [x] Add `tools/ppo_play_pygame.py` CLI.
- [x] Load PPO model and resolve torch device (`auto|cpu|mps|cuda`).
- [x] Drive gameplay using policy predictions and AI action decoding.
- [x] Present rendered frames via pygame backend at target FPS cap.

### Workstream 2: Shared action mapping

- [x] Extract reusable SB3 vector->env action helper in `src/ultimatetk/ai/sb3_action_wrapper.py`.
- [x] Keep wrapper behavior equivalent by routing through shared helper.

### Workstream 3: Tests and docs

- [x] Extend PPO tools CLI help smoke tests for playback tool.
- [ ] Add targeted unit coverage for playback loop stop-reason behavior.
- [x] Update README usage examples after full validation run.
- [x] Update `python_refactor.md` once phase14 validation is complete.

## Validation matrix (planned)

- `python3 -m pytest tests/unit/test_ppo_tools_cli.py tests/unit/test_sb3_action_wrapper.py tests/unit/test_training_device.py`
- Manual playback smoke:
  - `python3 tools/ppo_play_pygame.py --model runs/ai/ppo/<run>/final_model.zip --target-fps 40 --window-scale 3 --device auto`
- Safety bundle:
  - `python3 tools/release_verification.py --skip-integration`

## Validation snapshot

- `python3 -m pytest tests/unit/test_ppo_tools_cli.py tests/unit/test_sb3_action_wrapper.py tests/unit/test_training_device.py` -> `11 passed`.
- `python3 tools/ppo_play_pygame.py --model runs/ai/ppo/phase13_smoke_fast_auto/final_model.zip --max-seconds 1 --target-fps 40 --window-scale 2 --device auto --deterministic` -> playback smoke passed (`reason=max_seconds`, `steps=38`, `effective_fps=34.5`, `device=cpu`).
- `python3 tools/release_verification.py --skip-integration` -> release unit matrix passed (`183 passed`).
