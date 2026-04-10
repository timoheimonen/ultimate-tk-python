# Phase 8: Regression Suite (Kickoff)

This phase focuses on long-horizon regression locking: golden behavior/snapshot checks that guard parity-sensitive movement, combat, UI flow, and progression timing as Phase 9 release hardening proceeds.

Current baseline already implemented:

- Phase 7 balancing/parity tuning is complete for first-pass movement/camera, enemy cadence, and progression pacing slices.
- Phase 4/5/6/7 lock coverage is broad across unit, scene-flow, and scripted headless integration paths.
- Real-data parse/render smoke coverage exists and the software renderer can already produce deterministic frame digests.

## Phase 8 goals

- Define and capture canonical golden scenarios for parity-sensitive gameplay paths.
- Add deterministic regression checks for both behavior telemetry and representative render outputs.
- Build a lightweight artifact workflow for storing/updating golden references without destabilizing routine development.
- Keep Phase 7 tuned values and earlier locked invariants stable while adding broader regression breadth.

## Workstreams

1. Golden scenario catalog and acceptance envelope
   - Define scenario matrix (movement/camera, combat cadence, progression/shop flow, renderer snapshots).
   - Define per-scenario pass criteria (exact match vs tolerance-based assertions).
   - Record canonical fixture/runtime seeds and scripted inputs.

2. Behavior-golden regression expansion
   - Add high-signal scripted headless scenario checks for parity-critical counters and transitions.
   - Add aggregated runtime digest assertions for multi-step loops where appropriate.
   - Keep deterministic ordering assertions explicit for cadence/timing-sensitive paths.

3. Render-golden snapshot workflow
   - Add representative renderer golden captures (baseline rooms/events/HUD/shop overlays).
   - Define digest or pixel-compare strategy and update policy.
   - Ensure golden checks are deterministic across local runs.

4. Regression command bundling and developer ergonomics
   - Define Phase 8 command bundles for fast pre-commit and full verification modes.
   - Document when to run targeted vs full golden checks.
   - Keep runtime artifact paths and gitignore policy explicit.

5. Phase closeout and Phase 9 handoff readiness
   - Re-run full regression command matrix.
   - Confirm no regressions in locked Phase 4/5/6/7 invariants.
   - Update `python_refactor.md` and this note with completion and Phase 9 handoff context.

## Workstream 1 scenario catalog (draft)

- Movement/camera behavior-golden set:
  - `test_follow_camera_turn_in_place_firing_catches_up_faster_than_idle`
  - `test_gameplay_action_idle_camera_catchup_is_faster_than_idle`
  - `test_scripted_turn_changes_player_angle`
- Combat cadence and ordering set:
  - `test_enemy_strafe_direction_holds_across_short_reload_windows`
  - `test_enemy_strafe_switch_tick_is_staggered_between_neighbor_enemy_ids`
  - `test_scripted_multi_enemy_strafe_switches_are_staggered_during_reload`
- Progression/shop flow set:
  - `test_level_complete_scene_auto_returns_after_phase7_hold_ticks`
  - `test_run_complete_scene_auto_returns_after_phase7_hold_ticks`
  - `test_manual_progression_restart_keeps_shop_flow_stable_after_phase7_pacing`
- Real-data renderer/parser smoke set:
  - `python/tests/integration/test_real_data_render.py`
  - `python/tests/integration/test_real_data_parse.py`

## Acceptance envelope (Phase 8 draft)

- Timing/order-sensitive counters and scene transitions remain exact-match assertions.
- Camera/movement micro-feel checks keep monotonic and minimum-delta assertions (no broad tolerance widening).
- Render/parser smoke checks remain deterministic pass/fail gates in baseline matrix until dedicated golden artifact policy lands.

## Kickoff checklist

- [x] Define canonical Phase 8 golden scenario catalog.
- [ ] Implement first behavior-golden regression slice.
- [ ] Implement first render-golden regression slice.
- [ ] Publish Phase 8 command bundles and artifact policy.
- [x] Re-run full verification matrix after each closed workstream.

## Progress log

- Created Phase 8 kickoff plan and workstreams in `python/docs/notes/phase8_regression_suite.md`.
- Drafted Workstream 1 canonical scenario catalog and initial acceptance envelope from existing lock suites.
- Captured initial Phase 8 baseline verification snapshot:
  - `python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py` -> `181 passed`.
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py` -> `45 passed`.
- Next immediate action: start Workstream 2 by adding the first explicit behavior-golden aggregate assertion slice.

## Verification plan

- Unit/scene-flow suites:
  - `python/tests/unit/test_fixed_step_clock.py`
  - `python/tests/unit/test_player_control.py`
  - `python/tests/unit/test_combat.py`
  - `python/tests/unit/test_scene_flow.py`
- Integration suites:
  - `python/tests/integration/test_headless_input_script_runtime.py`
  - `python/tests/integration/test_real_data_render.py`
  - `python/tests/integration/test_real_data_parse.py`
- Phase verification command set:
  - `python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py`
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py`

## Completion criteria

- Golden behavior and render regression checks are in place for the canonical Phase 8 scenario set.
- Phase 7 tuned boundaries remain stable under expanded regression load.
- Full Phase 8 verification matrix passes.
- `python_refactor.md` and this note reflect Phase 8 completion and Phase 9 handoff scope.
