# Gymnasium Vector-Observation Plan

## Goal
Build a Gymnasium-compatible environment for the Python port using vector observations (not pixels), while keeping existing runtime backends (`headless`, `terminal`, later `pygame`) independent from core simulation logic.

## Scope
- In scope:
  - `gymnasium.Env` wrapper for single-agent training
  - Deterministic `reset(seed=...)` and fixed-step `step(action)`
  - 64-ray 360-degree vector observation with entity-specific channels
  - Reward/termination/truncation API suitable for RL training
  - Compatibility with Gymnasium vectorized execution (`SyncVectorEnv`, `AsyncVectorEnv`)
- Out of scope (initially):
  - Pixel observations
  - Multi-agent or networked training modes
  - Rendering requirements for Gym operation

## Design Principles
- Keep simulation platform-agnostic; Gym should not depend on window/input backends.
- Keep observation/action mapping deterministic and testable.
- Reuse existing gameplay and event systems instead of adding parallel logic.
- Maintain backward compatibility with current CLI runtime workflows.

## Architecture

### 1) Engine Session API
Create an engine/session layer that can run without CLI loop ownership.

Proposed interface:
- `reset(seed: int | None) -> tuple[ObsType, dict]`
- `step(action: ActionType) -> tuple[ObsType, float, bool, bool, dict]`
- `close() -> None`

Responsibilities:
- Instantiate and own `GameContext`, scene manager, and fixed-step progression for Gym stepping.
- Apply translated RL action input each step as existing `AppEvent`s.
- Expose authoritative state snapshot used by observation and reward builders.

### 2) Action Translation Layer
Define a canonical RL action format and map it into existing input events.

Recommended initial action space:
- `buttons`: `MultiBinary(K)` for held actions
  - `MOVE_FORWARD`, `MOVE_BACKWARD`, `TURN_LEFT`, `TURN_RIGHT`, `STRAFE_MODIFIER`, `STRAFE_LEFT`, `STRAFE_RIGHT`, `SHOOT`, `NEXT_WEAPON`, `TOGGLE_SHOP`
- `weapon_slot`: `Discrete(N+1)`
  - `0` = no direct select, `1..N` = select slot

Translation behavior:
- Maintain held-button edge transitions (press/release events).
- Emit direct weapon select event when non-zero slot is chosen.

### 3) Vector Observation Builder (Core Requirement)
Observation uses 64 angular slots around player (360 degrees total).

Ray constants:
- `NUM_RAYS = 64`
- `ANGLE_STEP = 360.0 / NUM_RAYS` (5.625 degrees)
- `MAX_RAY_RANGE = 200.0` (configurable)

Per-ray channels (in fixed order):
1. `wall_dist`
2. `free_dist`
3. `enemy_dist`
4. `crate_dist`
5. `pickup_dist`
6. `projectile_dist`
7. `enemy_present`
8. `crate_present`
9. `pickup_present`
10. `projectile_present`
11. `mine_dist`
12. `mine_present`

Per-ray encoding:
- Distance channels normalized to `[0, 1]` using `min(distance, MAX_RAY_RANGE) / MAX_RAY_RANGE`.
- If not found: distance = `1.0`, presence mask = `0.0`.
- If found: distance normalized value, presence mask = `1.0`.

Ray feature count:
- `64 * 12 = 768`

Scalar context (append after ray features, normalized):
- `health_norm`, `shield_norm`
- `weapon_slot_norm`
- `reload_norm`
- `ammo_current_norm`
- `cash_norm`
- `target_system_enabled`
- `mines_active_norm`, `c4_active_norm`
- `shop_active`
- `enemies_alive_norm`, `crates_alive_norm`
- `episode_progress_norm`

Final observation:
- `np.ndarray(shape=(640 + S,), dtype=np.float32)`
- Flat vector for broad algorithm compatibility

Entity semantics:
- `crate_dist`: destructible crates only.
- `pickup_dist`: collectible pickups only (separate from crates).
- `projectile_dist`: hostile projectile threats.

### 4) Reward and Episode Logic
Implement reward as a configurable module separate from scene logic.

Initial reward terms (suggested defaults):
- `+R_kill` for enemy kill
- `+R_crate_collect` for crate reward collection
- `+R_cash_delta` scaled by cash gain
- `-R_damage_taken` proportional to player damage
- `-R_death` on death
- optional small step penalty for efficiency

Episode status:
- `terminated = True` when terminal gameplay condition reached (death or level completion when implemented)
- `truncated = True` when max episode steps/time limit reached

### 5) Gymnasium Wrapper
Create wrapper module (proposed path):
- `python/src/ultimatetk/rl/gym_env.py`

Expose:
- `class UltimateTKGymEnv(gymnasium.Env)`
- declared `action_space` and `observation_space`
- `metadata = {"render_modes": []}` for vector-only v1

Vectorized execution:
- Ensure env creation function is side-effect free and picklable.
- Validate compatibility with:
  - `gymnasium.vector.SyncVectorEnv`
  - `gymnasium.vector.AsyncVectorEnv`

## Determinism Plan
- Route all stochastic systems through seeded RNG boundaries.
- Ensure `reset(seed=X)` reproduces:
  - enemy/shop/randomized setup
  - deterministic step sequence under identical action traces
- Add deterministic rollout tests comparing key runtime counters and sampled observation slices.

## Implementation Phases

### Phase A: Session extraction
- Add reusable simulation session API decoupled from CLI loop.
- Keep current app/scene behavior unchanged for existing modes.

### Phase B: Action adapter
- Add RL action schema and event translation with held-action edge tracking.

### Phase C: Observation pipeline
- Implement 64-ray scanner + scalar context builder.
- Add normalization constants and stable feature ordering.

### Phase D: Reward + done/truncate
- Implement configurable reward function and termination policy.

### Phase E: Gym wrapper
- Implement `gymnasium.Env` class and spaces.
- Add vectorized environment smoke validation.

### Phase F: Documentation and examples
- Add usage docs and a minimal training/evaluation script.

## Testing Strategy
- Unit tests:
  - Action translation edge behavior (press/release consistency)
  - Ray casting correctness in controlled maps
  - Observation shape, dtype, bounds, ordering
  - Reward component correctness on scripted transitions
- Integration tests:
  - `reset(seed)` determinism and reproducibility over fixed action scripts
  - Gym API compliance (`reset`, `step`, `close`)
  - Vectorized env startup and stepping

## Risks and Mitigations
- Risk: behavior drift between CLI runtime and Gym session loop
  - Mitigation: single shared simulation stepping path
- Risk: ray scans become CPU hotspot in vectorized training
  - Mitigation: cache-friendly scans, configurable ray count/range, profiling
- Risk: hidden nondeterminism in existing systems
  - Mitigation: RNG audit and deterministic integration tests

## Definition of Done (Gym v1)
- Gym env runs fully headless with vector observations only.
- Observation includes 64-slot 360-degree channels for wall/enemy/crate/pickup/projectile/free-space.
- Deterministic `reset(seed)` and stable step semantics are verified by tests.
- Compatible with Gymnasium vectorized wrappers.
- Existing non-Gym runtime modes remain functional.
