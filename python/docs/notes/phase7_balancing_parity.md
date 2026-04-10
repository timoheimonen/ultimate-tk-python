# Phase 7: Balancing and Parity Pass (Kickoff)

This phase shifts focus from feature-complete flow to gameplay-feel parity: timing, pacing, and tuning across movement, camera, combat, and progression.

Current baseline already implemented:

- Phase 6 scene flow and progression loop are complete (menu -> gameplay -> level_complete/run_complete -> menu) with deterministic transitions.
- Session/profile continuity hooks are in place for startup load/new-session and shutdown autosave behavior.
- Phase 5 combat and entity invariants are locked with broad unit + scripted integration coverage.
- Runtime telemetry already exposes key combat/progression counters for deterministic verification.

## Phase 7 goals

- Tune core gameplay feel to legacy parity targets (timing and responsiveness) while preserving deterministic simulation behavior.
- Tune camera behavior and movement intent transitions for stable readability in combat and traversal.
- Tune enemy pacing and combat cadence (sight/reaction/fire/reload/strafe/effect timing) for practical parity in mixed encounters.
- Tune progression/economy pacing around level transitions, shop windows, and run continuity without regressing locked invariants.
- Expand lock coverage around tuned values so future refactors do not drift balancing outcomes.

## Workstreams

1. Baseline capture and parity target definition
   - Define canonical parity scenarios (movement, camera, enemy encounter, shop/progression loops).
   - Capture baseline runtime telemetry snapshots from scripted headless scenarios.
   - Define acceptable tolerance windows for timing-sensitive behaviors.

2. Movement and camera balancing pass
   - Tune movement/collision/camera parameters that influence feel (dead-zones, catch-up, look-ahead, turn blending).
   - Validate no regressions in locked Phase 4 movement/camera micro-parity boundaries.
   - Add/adjust tests to lock the finalized tuning envelope.

3. Combat and enemy cadence balancing pass
   - Tune enemy reaction, LOS cadence, attack/reload windows, strafe pressure, and projectile/explosive pacing.
   - Validate player weapon cadence/economy feel remains coherent with encounter pacing.
   - Keep dead-state/projectile ordering and splash-cover lock invariants intact.

4. Progression and economy pacing pass
   - Tune level-to-level progression tempo (level_complete/run_complete hold/confirm timing).
   - Review shop/economy pacing interactions against expected run flow.
   - Verify persisted-session continuity does not skew pacing assumptions across restarts.

5. Regression lock expansion and phase closeout
   - Add targeted unit + scripted integration lock cases for all finalized balancing decisions.
   - Re-run full lock suites spanning movement/combat/scene-flow/progression paths.
   - Update `python_refactor.md` and this note with final outcomes and handoff context for Phase 8.

## Workstream 1 baseline scenario set

- Movement/camera intent transitions:
  - `test_scripted_turn_changes_player_angle`
  - `test_scripted_enemy_strafe_blocked_lane_retries_opposite_direction`
  - `test_scripted_multi_enemy_strafe_switches_are_staggered_during_reload`
  - Key runtime fields: `player_angle_degrees`, per-enemy movement angle cadence, scene-stable camera behavior from `test_player_control.py`.
- Combat cadence and damage pacing:
  - `test_scripted_shoot_increments_shot_counter`
  - `test_scripted_enemy_explosive_long_range_shot_applies_forward_pressure`
  - `test_scripted_enemy_los_corner_graze_open_vs_blocked`
  - Key runtime fields: `player_shots_fired_total`, `enemy_shots_fired_total`, `enemy_hits_total`, `enemy_damage_to_player_total`.
- Economy/progression pacing:
  - `test_scripted_shop_open_and_buy_attempt_sets_shop_runtime`
  - `test_scripted_shield_buy_plus_energy_crate_reaches_shield_cap`
  - `test_scripted_manual_progression_loop_reaches_run_complete_and_returns_to_menu`
  - Key runtime fields: `shop_last_*`, `player_health`, `player_cash`, `progression_*`.
- Explosive/contact timing boundaries:
  - `test_scripted_mine_arm_transition_uses_n_minus_1_n_n_plus_1_timing`
  - `test_scripted_c4_remote_trigger_uses_n_minus_1_n_n_plus_1_timing`
  - Key runtime fields: `player_explosive_detonations_total`, `player_mines_armed`, `player_c4_hot`, `player_explosives_active`.

## Initial tolerance windows (Phase 7 draft)

- Deterministic counters and scene/progression transitions remain exact-match assertions (no tolerance).
- Tick-boundary cadence checks use strict `N-1/N/N+1` ordering where already locked; newly added cadence checks may allow `+/-1` tick only when queue/confirm timing is involved.
- Position/pressure movement checks keep directional assertions plus minimum displacement deltas (default floor: `>= 2.0` world units unless scenario requires stricter bounds).
- Damage pacing checks preserve relational expectations (`blocked == 0`, `partial < open`) and only allow float epsilon for arithmetic comparison (`<= 1e-6`).

## First tuning slice target (movement/camera)

- Candidate parameters in `python/src/ultimatetk/systems/player_control.py`:
  - `CAMERA_LOOK_AHEAD_DISTANCE`
  - `CAMERA_WALK_LOOK_BOOST`
  - `CAMERA_DEAD_ZONE_X`, `CAMERA_DEAD_ZONE_Y`
  - `CAMERA_IDLE_DEAD_ZONE_*`, `CAMERA_ACTION_DEAD_ZONE_*`
  - `CAMERA_CATCHUP_DIVISOR`, `CAMERA_MAX_STEP`
- Guardrails:
  - Preserve locked edge-release and strafe-turn dead-zone behavior.
  - Keep movement collision feel and shot-trace coupling unchanged unless a parity gap is proven.
- Validation focus for this slice:
  - `python/tests/unit/test_player_control.py`
  - `python/tests/unit/test_scene_flow.py -k camera`
  - `python/tests/integration/test_headless_input_script_runtime.py -k "turn_changes_player_angle or enemy_strafe_blocked_lane_retries_opposite_direction"`

## Progress log

- Created Phase 7 kickoff plan and workstream structure in `python/docs/notes/phase7_balancing_parity.md`.
- Defined Workstream 1 canonical scenario set and initial tolerance windows using existing scripted runtime and unit lock coverage.
- Ran first baseline verification snapshot for Phase 7 command set:
  - `python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py` -> `175 passed`.
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py` -> `44 passed`.
- Identified first parameter slice for Workstream 2 (movement/camera constants and focused guard suites).
- Next immediate action: apply first movement/camera tuning delta and lock any new boundary assertions.

## Kickoff checklist

- [x] Define canonical Phase 7 parity scenarios and acceptance tolerances.
- [x] Capture baseline telemetry from scripted runtime scenarios.
- [ ] Complete first tuning slice for movement/camera with lock updates.
- [ ] Complete first tuning slice for combat/enemy cadence with lock updates.
- [ ] Re-run phase verification command set after each closed workstream.

## Verification plan

- Unit suites:
  - `python/tests/unit/test_fixed_step_clock.py`
  - `python/tests/unit/test_player_control.py`
  - `python/tests/unit/test_combat.py`
  - `python/tests/unit/test_scene_flow.py`
- Integration suites:
  - `python/tests/integration/test_headless_input_script_runtime.py`
  - `python/tests/integration/test_real_data_render.py`
- Phase verification command set:
  - `python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py`
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py`

## Completion criteria

- Phase 7 workstreams are closed with documented tuning decisions and passing verification suites.
- Final movement/camera/combat/progression pacing values are locked by targeted regression coverage.
- Locked Phase 4/5/6 invariants remain passing after balancing changes.
- `python_refactor.md` and this note reflect Phase 7 completion status and Phase 8 handoff context.
