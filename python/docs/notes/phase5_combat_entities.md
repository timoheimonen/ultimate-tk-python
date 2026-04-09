# Phase 5: Combat and Entities (Plan)

This phase closes remaining combat/entity parity and hardens deterministic behavior before wider UI/progression work.

Current baseline already implemented:

- Deterministic enemy spawn and behavior loop with LOS/vision gating, patrol cadence, strafe tuning, and reload-gated attacks.
- Hitscan + projectile combat paths for player/enemies, including wall/crate obstruction and splash falloff handling.
- Player mine/C4 deploy/arm/trigger/detonation flow with runtime telemetry and scripted timing/contact parity coverage.
- Destructible crates, pickup rewards, health/death flow, and gameplay runtime counters for core combat outcomes.

## Phase 5 goals

- Lock advanced projectile/explosive edge-case parity so ordering and damage outcomes stay deterministic across corner/corridor micro-cases.
- Lock entity lifecycle transitions (alive/dead, hit-flash, detonation/removal, reward/counter accounting) so no duplicate or late-state side effects occur.
- Lock combat economy/telemetry consistency so ammo usage/refunds, hit/damage counts, and active-entity snapshots remain coherent frame-to-frame.
- Expand regression coverage for combat/entity scenarios so parity-sensitive behavior remains stable as later phases iterate.

## Workstreams

1. Projectile and explosive resolution hardening (completed)
   - Audit direct-hit versus splash precedence across enemy projectile wall-impact/expiry and player explosive detonation paths.
   - Verify crate/player/enemy resolution ordering for simultaneous-contact frames.
   - Validate deterministic ordering where multiple valid contacts exist in the same tick.

2. Entity lifecycle and state-transition hygiene (completed)
   - Verify dead-state gating across all enemy attack/damage paths (including in-flight projectile and delayed splash outcomes).
   - Validate removal timing for spent projectiles/explosives so runtime counters and rendered state stay in sync.
   - Validate hit-flash and death state transitions for enemies/crates against expected single-trigger behavior.

3. Crate interaction and reward consistency (completed)
   - Verify destruction-versus-collection exclusivity for crate outcomes.
   - Validate crate reward application and combat-side crate counters in mixed combat/pickup scenarios.

4. Combat economy and telemetry consistency (completed)
   - Verify ammo consumption/refund rules across normal fire, trigger-only follow-ups, and empty-weapon fallback paths.
   - Verify runtime telemetry invariants (shots/hits/damage/explosive counts) for monotonic and state-consistent updates.

5. Regression expansion and lock criteria (in progress)
   - Add unit micro-cases for any uncovered combat/entity ordering boundaries.
   - Add scripted headless (`--input-script`) runtime scenarios for parity-sensitive transitions.
   - Keep Phase 4 finalized bundles locked unless a regression is proven.

## Progress log

- Completed Workstream 1 by hardening projectile/explosive simultaneous-contact ordering in `python/src/ultimatetk/systems/combat.py`:
  - Player-explosive detonation now uses a pre-detonation alive-crate cover snapshot so crate cover attenuation is evaluated from a stable same-tick geometry baseline (even when crates are destroyed by the same blast).
  - Enemy/projectile and crate splash resolution now evaluates crate targets in deterministic nearest-first order (distance, then id).
  - Enemy projectile direct-crate-impact splash against player now includes secondary crate cover attenuation (excluding the impact crate itself), aligning crate-impact splash behavior with wall-impact/expiry cover handling.
- Added Workstream 1 regression coverage in `python/tests/unit/test_combat.py`:
  - `test_grenade_projectile_crate_impact_splash_respects_secondary_crate_cover_for_player`
  - `test_player_c4_destroyed_cover_crate_still_reduces_same_blast_player_damage`
  - `test_enemy_projectile_splash_evaluates_crates_nearest_first`
- Verification run after Workstream 1 changes:
  - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Started Workstream 2 by hardening dead-state gating and delayed-path cleanup in enemy attack/projectile flows:
  - `resolve_enemy_shot_against_player` and `resolve_enemy_attack_against_player` now return no-hit/no-damage for dead enemies (and skip dead-player attack resolution), preventing late-state attack side effects when called from delayed or direct paths.
  - `update_enemy_projectiles` now clears in-flight projectiles immediately when the player is already dead, preventing post-death delayed splash side effects and keeping active-projectile state in sync.
  - `update_enemy_projectiles` now supports optional owner-liveness gating (`enemies=`) and drops projectiles whose known owner enemy is dead, while preserving standalone scripted projectile micro-cases with unknown owners.
  - Gameplay update loop now passes current enemies into projectile updates so owner-liveness gating applies during normal runtime.
- Added Workstream 2 regression coverage in `python/tests/unit/test_combat.py`:
  - `test_enemy_projectile_dead_player_path_does_not_damage_crates`
  - `test_enemy_projectile_discarded_when_owner_enemy_is_dead`
  - `test_dead_enemy_attack_resolution_is_gated`
- Extended Workstream 2 transition hygiene coverage:
  - Added dead-entity non-retrigger assertions for direct hit paths so dead enemy/crate states are ignored by subsequent shot traces without reapplying hit-flash/death transitions.
  - Added dead-entity non-retrigger assertions for player C4 detonation paths so dead enemy/crate states are ignored by later blast resolution.
  - Added gameplay scene-flow coverage verifying active projectile/explosive buffers are cleared in the same tick that game-over activates, and runtime active counters immediately reflect zero.
  - Gameplay update loop now short-circuits into game-over activation at tick start when player is already dead, preventing post-death simulation side effects in that frame (including pending explosive detonation/hit counter drift) before runtime publication.
- Verification run after this Workstream 2 start chunk:
  - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py`
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
  - `python3 -m pytest tests/unit/test_player_control.py`
- Closed Workstream 2 after completing all three lifecycle goals:
  - dead-state gating is now explicit across direct and delayed enemy attack/projectile paths,
  - spent/invalid combat entities are removed before they can leak post-death side effects into runtime counters,
  - enemy/crate hit-flash and death transitions are covered by non-retrigger regression cases for both direct shot and C4 splash paths.
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Started Workstream 3 crate interaction/reward consistency coverage:
  - Added scene-flow mixed-outcome cases to validate destruction-versus-collection exclusivity at gameplay ordering boundaries:
    - same-crate same-tick collect-versus-destroy precedence,
    - full-health energy crate not collected and then destroyed in the same tick,
    - mixed two-crate tick where one crate is collected and a second crate is destroyed with counters/rewards staying coherent.
  - Added combat-level exclusivity/reward guards for destroyed crates and post-collection non-destruction checks.
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Closed Workstream 3 after validating crate outcome exclusivity and mixed-scenario counter coherence:
  - Added scripted headless runtime coverage (`test_scripted_mixed_crate_collect_and_destroy_updates_runtime_consistently`) where one crate is collected while another is destroyed in the same runtime window, verifying reward/counter consistency end-to-end.
  - Confirmed single-crate exclusivity in both directions across unit+scene-flow paths (collect-precedes-destroy on eligible pickup crates, and full-health energy crates remain destroyable without accidental collection).
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Started Workstream 4 combat economy + telemetry consistency by extending scene-flow runtime coverage in `python/tests/unit/test_scene_flow.py`:
  - Added empty-weapon fallback runtime assertions (`test_gameplay_empty_weapon_fallback_keeps_runtime_shot_and_ammo_state_consistent`) to verify no accidental shot/ammo counter drift when no-ammo shoot input falls back to fist.
  - Extended C4 trigger-only follow-up economy checks (`test_gameplay_c4_remote_trigger_does_not_consume_extra_c4_ammo`) with runtime ammo snapshot and shot-counter assertions so trigger-only refunds stay telemetry-coherent.
  - Added monotonic telemetry/state-consistency coverage (`test_gameplay_runtime_combat_telemetry_totals_are_monotonic_and_active_counts_match_state`) to lock non-decreasing combat totals and runtime active-entity snapshot coherence against internal projectile/explosive buffers.
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Closed Workstream 4 by extending scripted headless runtime economy/telemetry coverage in `python/tests/integration/test_headless_input_script_runtime.py`:
  - Added empty-weapon fallback scripted coverage (`test_scripted_empty_weapon_fallback_keeps_runtime_ammo_and_shot_telemetry_stable`) to verify runtime weapon/ammo snapshots and shot counters remain consistent when shoot input falls back to fist due to empty ammo.
  - Extended C4 remote-trigger boundary coverage (`test_scripted_c4_remote_trigger_uses_n_minus_1_n_n_plus_1_timing`) with runtime ammo snapshot assertions so trigger-only refund flow is validated end-to-end (two shots, one retained C4 ammo unit).
  - Added explicit active-explosive telemetry invariant assertion in scripted mine+C4 runtime coverage (`test_scripted_mine_and_c4_update_explosive_runtime`) to ensure `player_explosives_active == player_mines_active + player_c4_active`.
  - Workstream 4 goals are now covered across unit + scene-flow + scripted integration paths: normal fire consumption, trigger-only refund follow-up behavior, empty-weapon fallback consistency, and monotonic/state-consistent combat telemetry snapshots.
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Started Workstream 5 regression expansion by adding explicit lock tests for Phase 4/5 projectile-lifecycle invariants:
  - Added unit micro-case `test_enemy_projectile_with_unknown_owner_is_not_discarded_by_owner_gating` in `python/tests/unit/test_combat.py` so owner-liveness filtering keeps standalone scripted projectiles when owner ids are unknown (discard only known-dead owners).
  - Added scripted headless runtime scenario `test_scripted_dead_player_projectile_telemetry_gates_hits_and_damage` in `python/tests/integration/test_headless_input_script_runtime.py` to lock dead-player projectile telemetry gating end-to-end (no post-death hit/damage accumulation, projectile buffer cleared, crate side effects suppressed, game-over active).
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Continued Workstream 5 with additional owner-liveness boundary lock coverage:
  - Added unit micro-case `test_enemy_projectile_owner_gating_drops_only_known_dead_owners` in `python/tests/unit/test_combat.py` to assert mixed-owner behavior in the same update pass (known-dead owner projectiles are discarded while unknown-owner projectiles still resolve normally).
  - Added scripted headless runtime scenario `test_scripted_unknown_owner_projectile_is_preserved_by_owner_gating` in `python/tests/integration/test_headless_input_script_runtime.py` to lock the gameplay-loop path where `update_enemy_projectiles(..., enemies=...)` must preserve unknown-owner projectiles and publish corresponding hit/damage telemetry.
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Continued Workstream 5 with dead-player cleanup precedence lock coverage:
  - Added unit micro-case `test_enemy_projectile_dead_player_gating_precedes_owner_and_crate_resolution` in `python/tests/unit/test_combat.py` to ensure dead-player short-circuit cleanup wins over owner-gating and crate-resolution branches in mixed projectile sets.
  - Added scripted headless runtime scenario `test_scripted_dead_player_clears_projectile_and_explosive_buffers_same_tick` in `python/tests/integration/test_headless_input_script_runtime.py` to lock same-tick gameplay cleanup invariants (projectile/explosive buffers zeroed, no post-death detonation/hit/damage telemetry drift, game-over active).
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Continued Workstream 5 with in-update death ordering hardening in `python/src/ultimatetk/systems/combat.py`:
  - `update_enemy_projectiles` now short-circuits immediately when a projectile hit kills the player, clearing any remaining in-flight projectiles before follow-up entries can apply late crate/player side effects in the same update pass.
  - Added unit lock coverage `test_enemy_projectile_player_death_stops_followup_projectile_crate_side_effects` in `python/tests/unit/test_combat.py`.
  - Added scripted headless runtime lock coverage `test_scripted_player_death_halts_followup_projectile_crate_side_effects` in `python/tests/integration/test_headless_input_script_runtime.py`.
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`
- Continued Workstream 5 by locking pre-lethal ordering preservation for the same in-update boundary:
  - Added unit lock coverage `test_enemy_projectile_prelethal_crate_side_effects_are_preserved_before_death_short_circuit` in `python/tests/unit/test_combat.py`.
  - Extended scripted runtime lock coverage with `test_scripted_prelethal_projectile_side_effects_remain_before_death_short_circuit` in `python/tests/integration/test_headless_input_script_runtime.py`.
  - These tests ensure the death short-circuit blocks only post-death follow-up side effects, while preserving deterministic side effects from projectiles resolved before the lethal hit in the same pass.
  - Verified with the full phase command set:
    - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
    - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`

## Verification plan

- Unit suites:
  - `python/tests/unit/test_combat.py`
  - `python/tests/unit/test_scene_flow.py`
  - `python/tests/unit/test_player_control.py` (for shared movement/camera/combat coupling boundaries)
- Integration suite:
  - `python/tests/integration/test_headless_input_script_runtime.py`
- Phase verification command set:
  - `python3 -m pytest tests/unit/test_combat.py tests/unit/test_scene_flow.py tests/unit/test_player_control.py`
  - `python3 -m pytest tests/integration/test_headless_input_script_runtime.py`

## Completion criteria

- Remaining Phase 5 workstreams are closed with passing unit/integration coverage.
- No regressions in locked Phase 4 invariants:
  - mine nearest-collision-bounds trigger math + HUD explosive-readiness hint coloring,
  - movement/camera/combat micro-parity bundle,
  - C4 trigger-only ammo refund + dead-player projectile telemetry gating.
- `python_refactor.md` and this note are updated to reflect closure and handoff to Phase 6.
