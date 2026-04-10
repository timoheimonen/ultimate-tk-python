# Phase 12: Gymnasium AI Training Interface (Implementation)

This phase adds a Gymnasium-compatible training interface on top of the existing headless gameplay runtime.

Implementation is in progress and initial end-to-end scaffolding is now landed.

## Goals

- Provide a deterministic `gymnasium.Env` wrapper for training agents against the game simulation.
- Start episodes directly in headless gameplay at level 1 (skip boot/menu flows for training mode).
- Allow progression through subsequent levels during one training episode.
- End training episode when run completion is reached, with explicit completion signaling.
- Use vector observations with 360-degree radial sensing split into 32 sectors.

## Locked requirements from planning

- Action interface uses combined controls (`MultiBinary`/`MultiDiscrete`) and includes strafing.
- Shop is enabled in training mode so the agent can buy/sell items needed for later levels.
- Environment starts headless directly in gameplay, level 1.
- Environment progresses to further levels as normal gameplay progression allows.
- At final run completion, environment indicates game completion and stops the episode.
- Player death is a terminal condition and episode is resettable immediately (`terminal_reason=death`).

## Architecture decisions (locked)

- The Gymnasium env owns the loop and does not call `GameApplication.run()`.
- Each `step()` advances exactly one fixed simulation tick (`dt = 1 / target_tick_rate`).
- Training reset path bypasses boot/menu and enters gameplay scene directly.
- Episode-complete detection is tied to run-complete scene entry (`AppMode.RUN_COMPLETE` + progression event).
- Shop interactions are part of the training policy interface and must remain available during episodes.

## Required code change inventory (authoritative)

This section lists every planned code touch required to deliver the Phase 12 requirements.

### New files

- `src/ultimatetk/ai/__init__.py`
  - Export env entry points for training consumers.
- `src/ultimatetk/ai/gym_env.py`
  - Implement `UltimateTKEnv(gymnasium.Env)`.
  - Own `reset/step/close`, action/observation spaces, reward + termination + info.
  - Start episodes at level 1 gameplay in headless mode.
- `src/ultimatetk/ai/runtime_driver.py`
  - Add small single-tick runtime driver around `GameContext` + `SceneManager`.
  - Build training context/session and run scene `handle_events -> update -> render` tick pipeline.
- `src/ultimatetk/ai/action_codec.py`
  - Define `spaces.Dict` action schema using `MultiBinary` + `Discrete`.
  - Convert action tensors into `AppEvent` press/release/select events using hold-state diffing.
  - Include explicit shop-toggle control in trigger actions.
- `src/ultimatetk/ai/observation.py`
  - Implement 32-sector radial sensor extraction.
  - Build fixed-shape normalized observation dict (`rays`, `state`).
- `src/ultimatetk/ai/reward.py`
  - Implement reward calculation from runtime/stat deltas.
  - Emit termination reason helpers (`death`, `game_completed`, `time_limit`).
- `tests/unit/test_gym_env.py`
  - Env contract tests (`reset`, `step`, spaces, termination/truncation flags).
- `tests/unit/test_gym_action_codec.py`
  - Press/release diffing and action translation tests.
- `tests/unit/test_gym_observation.py`
  - Observation shape/normalization/channel-mapping tests.
- `tests/integration/test_gym_env_progression.py`
  - End-to-end headless progression coverage from level 1 through run completion.
- `tools/gym_random_policy_smoke.py`
  - Minimal random-action smoke runner for local sanity checks.

### Modified files

- `src/ultimatetk/systems/gameplay_scene.py`
  - Added read-only snapshot/accessor (`GameplayStateView`) for AI observation extraction.
- `src/ultimatetk/core/scenes.py`
  - Added `current_scene` accessor used by training driver.
- `pyproject.toml`
  - Add optional dependency group for AI stack (`gymnasium`, `numpy`) without changing default install requirements.
- `README.md`
  - Add Gymnasium env usage section (install extras, reset/step example, completion signaling contract).
- `python_refactor.md`
  - Track Phase 12 implementation progress by workstream.

Default runtime flows (`headless`, `terminal`, `pygame`) remain unchanged.

## Non-goals (initial interface)

- No pixel-observation policy input in v1 (vector-only first pass).
- No pygame dependency for training path.
- No multiplayer/deathmatch training mode.

## Workstream 1: Environment scaffold and registration

- [x] Add AI package namespace (for example `src/ultimatetk/ai/`).
- [x] Add `UltimateTKEnv` implementing Gymnasium API (`reset`, `step`, `close`, `observation_space`, `action_space`).
- [x] Add optional dependency group for AI stack (for example `gymnasium`, `numpy`) while keeping default runtime dependency-free.
- [x] Add a tiny random-policy smoke script for local validation.

Acceptance checks:

- [x] Env can be imported and instantiated without pygame.
- [x] `reset(seed=...)` wiring applies deterministic seed initialization.

## Workstream 2: Training runtime mode (headless, gameplay-first)

- [x] Add training-mode runtime entry path that bypasses boot/menu and enters gameplay scene immediately.
- [x] Force level index to 0 on episode reset unless explicitly configured otherwise.
- [x] Keep progression enabled so level completion transitions continue to next level.
- [x] Keep shop interactions enabled in training mode (open, navigate, buy, sell) with normal game economy rules.

Acceptance checks:

- [x] Episode starts in gameplay scene on level 1.
- [x] Shop can be opened and used during training episodes.
- [x] Shop purchases/sales affect player state and carry through subsequent levels in the same run.
- [x] Level-complete transitions advance to next level in training episodes.

## Workstream 3: Action interface (`MultiBinary` + `Discrete`)

- [x] Define `spaces.Dict` action layout with hold and trigger groups.
- [x] Include strafing controls (`strafe_left`, `strafe_right`) in hold actions.
- [x] Support optional direct weapon-slot selection as a discrete branch.
- [x] Translate action state into press/release events by diffing previous hold state.

Proposed v1 action structure:

- `hold: MultiBinary(8)` -> `move_forward`, `move_backward`, `turn_left`, `turn_right`, `strafe_left`, `strafe_right`, `shoot`, `strafe_modifier`
- `trigger: MultiBinary(2)` -> `next_weapon`, `toggle_shop`
- `weapon_select: Discrete(13)` -> `0=no-op`, `1..12 => slots 0..11`

Acceptance checks:

- [x] Hold actions generate stable press/release event streams.
- [x] Combined behaviors (move + strafe + shoot) execute in same step.
- [x] Shop toggle and in-shop controls are reachable from policy actions.

## Workstream 4: Observation interface (32-sector radial vector)

- [x] Implement 360-degree radial sensing from player center with 32 sectors (11.25 degrees each).
- [x] For each sector, publish nearest normalized distance per object channel.
- [x] Include dynamic threat channels for incoming enemy projectiles (distance and urgency/time-to-impact features).
- [x] Add global player/state features (health, shield, ammo, weapon, enemies alive, etc.).

Proposed v1 observation structure:

- `rays: float32[32, C]` channels (initial target):
  - `wall`
  - `enemy`
  - `enemy_projectile`
  - `crate_weapon`
  - `crate_ammo`
  - `crate_energy`
  - `mine`
  - `c4`
- `state: float32[N]` (initial target):
  - player health/shield normalized
  - current weapon slot normalized
  - current ammo + ammo pools normalized
  - reload/load ticks normalized
  - enemies alive ratio
  - closest projectile distance normalized
  - closest projectile time-to-impact normalized

Acceptance checks:

- [x] Observation shape is fixed and batch-friendly.
- [x] Observation values are normalized/clamped and finite.

## Workstream 5: Rewards, termination, and completion signaling

- [x] Define reward components from runtime deltas (kills, hits, pickups, damage, death, step cost).
- [x] Return `terminated=True` for terminal outcomes:
  - player death
  - run complete (game completed)
- [x] Return `truncated=True` when max-step/time cap is reached.
- [x] Include explicit completion indicator in `info`, for example:
  - `info["game_completed"] = True` on run completion
  - `info["terminal_reason"]` in `{ "death", "game_completed", "time_limit" }`
  - `info["level_index"]` current level at terminal step

Acceptance checks:

- [x] Final run completion ends episode and flags `game_completed=True`.
- [x] Player death ends episode with `terminal_reason="death"` and allows immediate `reset()`.
- [x] Training loop can stop cleanly when game completion is reported.

## Workstream 6: Determinism, tests, and docs

- [x] Add unit tests for env reset/step contracts and spaces.
- [x] Add deterministic replay checks under fixed seed.
- [x] Add progression-path integration test covering level1 -> ... -> run completion episode ending.
- [x] Add integration coverage for shop usage impact across level progression (buy in earlier level, verify carry-over into later level).
- [x] Update README and tracker with AI interface usage and constraints.

Acceptance checks:

- [x] Focused AI env test matrix is green.
- [x] Existing release verification remains green without AI optional deps installed.

## Verification matrix (planned)

- Focused env contract tests:
  - `python3 -m pytest tests/unit/test_gym_env.py`
- Action codec + observation slices:
  - `python3 -m pytest tests/unit/test_gym_action_codec.py tests/unit/test_gym_observation.py`
- Progression completion integration:
  - `python3 -m pytest tests/integration/test_gym_env_progression.py`
- Shop-progression integration:
  - `python3 -m pytest tests/integration/test_gym_env_shop_progression.py`
- Full release safety:
  - `python3 tools/release_verification.py`

## Commit slicing plan

- [x] Commit A (`feat`): add env scaffold + optional AI extras + import-safe wiring.
- [x] Commit B (`feat`): add headless gameplay-first training mode with progression continuity.
- [x] Commit C (`feat`): implement action translation (`MultiBinary`/`MultiDiscrete`) with strafing.
- [x] Commit D (`feat`): implement radial observation extractor and global state vector.
- [x] Commit E (`feat`): add reward/termination/completion signaling.
- [x] Commit F (`test`): add env unit/integration coverage (including shop-progression behavior).
- [x] Commit G (`docs`): update README + tracker + phase note closeout state.

Applied via:

- `5cd20fb` (`feat: add phase-12 gymnasium training scaffold`)
- `1cc8225` (`test: lock deterministic gym replay behavior`)

## Completion criteria

- [x] Gymnasium env runs headless and deterministic under fixed seed.
- [x] Episodes start directly at level 1 gameplay with shop enabled.
- [x] Level progression continues across levels within the same episode.
- [x] Shop/economy interactions are available and persist through level progression in the same run.
- [x] Run completion signals game completion and terminates training episode.
- [x] Documentation and tracker reflect final Phase 12 status.

## Progress log

- Implemented initial Gymnasium stack under `src/ultimatetk/ai/`:
  - `gym_env.py`, `runtime_driver.py`, `action_codec.py`, `observation.py`, `reward.py`, `__init__.py`.
- Added gameplay AI snapshot accessor (`GameplayStateView`) in `src/ultimatetk/systems/gameplay_scene.py` and scene-manager current-scene accessor in `src/ultimatetk/core/scenes.py`.
- Added training smoke utility at `tools/gym_random_policy_smoke.py`.
- Added optional extras in `pyproject.toml`: `ai = ["gymnasium>=0.29", "numpy>=1.26"]`.
- Added AI-focused tests:
  - `tests/unit/test_gym_action_codec.py`
  - `tests/unit/test_gym_observation.py`
  - `tests/unit/test_gym_env.py`
  - `tests/integration/test_gym_env_progression.py`
  - `tests/integration/test_gym_env_shop_progression.py`
- Verification snapshot:
  - `python3 -m pytest tests/unit/test_scene_flow.py tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py tests/unit/test_gym_action_codec.py tests/unit/test_gym_observation.py tests/unit/test_gym_env.py` -> `61 passed, 8 skipped`.
  - `conda install -y -n ultimatetk -c conda-forge numpy gymnasium` installed optional AI deps in the active conda env.
  - `python3 -m pytest tests/unit/test_gym_action_codec.py tests/unit/test_gym_observation.py tests/unit/test_gym_env.py tests/integration/test_gym_env_progression.py tests/integration/test_gym_env_shop_progression.py` -> `10 passed`.
  - `python3 tools/gym_random_policy_smoke.py --episodes 1 --max-steps 200` -> smoke run passed (`truncated=True`, `terminal_reason=time_limit`).
  - `python3 -m pytest tests/unit/test_gym_env.py` -> `4 passed` (includes fixed-seed deterministic replay check).
  - Reward shaping follow-up: standardized negative-shaping config names to `*_cost`, added engagement-gated strafing reward (enemy-visible plus shooting/hit/projectile-threat context), added anti-stuck small-area cost tracking, and tightened idle anti-vibration thresholds (`idle_distance_epsilon=3.0`, `idle_ticks_threshold=45`) with updated reward unit coverage (`python3 -m pytest tests/unit/test_gym_reward.py` -> `9 passed`).

## Phase 12 closeout

- Phase 12 initial Gymnasium interface goals are complete.
- Default runtime/release flows remain dependency-safe for non-AI environments.
- Optional AI dependency path is validated in the `ultimatetk` conda environment.
  - `python3 tools/release_verification.py` -> unit `183 passed`, integration `47 passed, 1 skipped`.
