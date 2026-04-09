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

2. Entity lifecycle and state-transition hygiene
   - Verify dead-state gating across all enemy attack/damage paths (including in-flight projectile and delayed splash outcomes).
   - Validate removal timing for spent projectiles/explosives so runtime counters and rendered state stay in sync.
   - Validate hit-flash and death state transitions for enemies/crates against expected single-trigger behavior.

3. Crate interaction and reward consistency
   - Verify destruction-versus-collection exclusivity for crate outcomes.
   - Validate crate reward application and combat-side crate counters in mixed combat/pickup scenarios.

4. Combat economy and telemetry consistency
   - Verify ammo consumption/refund rules across normal fire, trigger-only follow-ups, and empty-weapon fallback paths.
   - Verify runtime telemetry invariants (shots/hits/damage/explosive counts) for monotonic and state-consistent updates.

5. Regression expansion and lock criteria
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
