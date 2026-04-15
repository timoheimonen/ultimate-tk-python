# Python Refactor Plan (No Multiplayer)

## Objective
Port The Ultimate TK from DOS C/C++ to Python while preserving gameplay feel and data compatibility, with multiplayer/IPX removed from scope and all runtime data packaged in root-native runtime folders.

## Scope
- In scope:
  - Single-player gameplay loop
  - Existing level/content formats (`.LEV`, `.EFP`, `.FNT`, `palette.tab`, `options.cfg`)
  - Menus, options, shop, combat, enemies, effects, rendering
  - Self-contained Python runtime and assets under root-local runtime paths (`src/`, `game_data/`, `runs/`)
- Out of scope:
  - IPX networking, lobby/join flow, chat, server/client sync
  - Any code under legacy network transport modules

## Project Folder Layout
The project now uses a root-native layout:

```text
game_data/            # runtime assets bundled for Python version
  efps/               # migrated image assets
  fnts/               # migrated font assets
  levs/               # migrated level/episode assets
  music/              # migrated module music assets
  wavs/               # migrated sound effects
  palette.tab         # migrated lighting/palette tables
  options.cfg         # migrated/default runtime options (or generated on first run)
src/
  ultimatetk/
    core/         # bootstrap, timing, constants, shared utilities
    formats/      # binary format readers/writers (.lev, .efp, .fnt, cfg, palette)
    assets/       # asset registry and runtime resource management
    world/        # map state, level state, spatial helpers
    entities/     # player, enemy, bullet, crate, effect models/behavior
    systems/      # game loop systems: input, movement, combat, progression
    rendering/    # software-style render pipeline and lighting compositing
    ui/           # menu flow, HUD, shop, option screens
    audio/        # music/sfx playback facade and mixer behavior
    debug/        # profiling hooks, frame metrics, capture tools
tests/
  unit/           # isolated parser and logic tests
  integration/    # subsystem interaction tests
  regression/     # golden checks for behavior/visual parity
tools/            # one-off converters, inspectors, validation scripts
docs/
  notes/          # implementation notes and parity findings
runs/
  screenshots/    # captured outputs for visual comparison
  profiles/       # perf traces and timing reports
```

## Legacy-to-Python Mapping
- `SRC/GAME.CPP` -> `core/`, `systems/`, `ui/` (startup, menu, loop orchestration)
- `SRC/CLASSES.CPP` + `SRC/CLASSES.H` -> `entities/` + `world/` + `systems/`
- `SRC/DRAW.CPP` -> `rendering/`
- `SRC/WRITE.CPP` -> `rendering/` + font support in `formats/`
- `SRC/MISCFUNC.CPP` -> `core/` + `systems/` utility flows
- `SRC/OPTIONS.CPP` -> `ui/` + `core/config`
- `SRC/SHOP.H` -> `ui/shop` + economy logic in `systems/`
- `SRC/EFP/EFP.CPP` -> `formats/efp`
- `SRC/CLASSES.CPP:Level::load` -> `formats/lev`
- `SRC/GAME.CPP:load_tables` -> `formats/palette_tab`

## Multiplayer Removal Plan
- Exclude all runtime behavior tied to:
  - `SRC/IPX/IPX.CPP`, `SRC/IPX/IPX.H`
  - `SRC/IPXDEFS.CPP`, `SRC/IPXDEFS.H`
  - `SRC/INT/INT.ASM`, `SRC/INT/INT.H`
- Remove/dead-end network branches in logic port:
  - packet send/receive paths
  - server/client state updates
  - network-specific menu entries and join flow

## Asset Packaging Requirement
- Final Python game must not depend on `EFPS/`, `FNTS/`, `LEVS/`, `MUSIC/`, `WAVS/`, or other data from repository root.
- All required runtime data must exist under `game_data/`.
- End state: original legacy file structure is not needed anymore for the Python build.
- Asset path resolution in Python code must be relative to repository root runtime paths.
- Keep a migration checklist/manifest so required files are verifiable before release.

## Milestones
1. Architecture and runtime skeleton
   - Define app entrypoint, fixed tick model, global state boundaries
2. Binary format parity
   - Load `.EFP`, `.FNT`, `.LEV`, `palette.tab`, `options.cfg` into Python structures
3. Rendering baseline
   - Tile/sprite drawing, transparency rules, palette/shadow/light table usage
4. Input and player control (completed)
   - Movement, collision, aiming/rotation, weapon switching
5. Combat and entities (completed)
   - Bullets, enemies, crates, effects, damage/death flow
6. UI and progression (completed)
   - Main menu, options, episode/level flow, shop, HUD
7. Balancing and parity pass (completed)
   - Timing adjustments, camera behavior, spawn and effect cadence
8. Regression suite (completed)
   - Golden snapshots and behavior checks from known scenarios
9. Data colocation and release hardening (completed)
   - Migrate all required runtime assets into `game_data/`
   - Ensure all graphical and sound assets are readable/migrated from original legacy files into `game_data/`
   - Verify the game launches and runs without reading root-level legacy data paths
10. Root flatten and legacy cleanup (completed)
    - Make legacy-root compare checks optional (off by default)
    - Move Python project layout from `python/` to repository root
    - Remove original root-level legacy game-data directories after flatten verification
11. Optional pygame runtime frontend (completed)
    - Add `--platform pygame` backend with lazy import and dependency-safe default runtime path
    - Keep internal rendering at `320x200` with integer window scaling (`--window-scale`)
    - Ensure menu/progression/gameplay scenes publish visible frames and stable input/quit behavior
12. Gymnasium AI training interface (completed)
    - Add headless `gymnasium.Env` wrapper under `src/ultimatetk/ai/`
    - Start directly in level-1 gameplay, keep shop actions enabled, and preserve progression carry-over
    - Expose 32-sector radial vector observations, multi-action controls (including strafing), and terminal signaling (`death`, `game_completed`, `time_limit`)
13. PPO trainer + checkpoint/eval loop (in progress)
    - Add SB3 PPO tooling over the Gymnasium env with checkpoint and periodic evaluation callbacks
    - Support resume-from-checkpoint workflows and run artifact directories under `runs/ai/ppo/`
    - Support `cpu`/`mps`/`cuda` device selection for Apple Silicon and CUDA hosts
14. Saved AI model pygame playback (in progress)
    - Add dedicated playback tool that runs trained PPO checkpoints with visible pygame output
    - Keep playback at normal FPS cap for visual inspection of policy behavior
    - Reuse phase-12/13 observation/action semantics for parity with training

## Validation Strategy
- Data parity:
  - Parse real repository assets and verify dimensions/counts and key fields
- Logic parity:
  - Recreate controlled scenarios (movement speed, fire rate, enemy reaction)
- Visual parity:
  - Compare frame captures on known rooms/events
- Timing parity:
  - Keep fixed-step target equivalent to original 40 FPS behavior
- Isolation parity:
  - Validate startup/gameplay works when only root-local runtime data paths are available

## Risks and Watch Items
- Palette/shadow/light math must match legacy table behavior
- Collision and movement feel are sensitive to small integer/float differences
- Legacy random/event cadence can drift if update order changes
- Signed byte vs unsigned byte handling in asset decoding

## Definition of Done (Single-Player)
- Player can launch, choose episode, play through levels, fight enemies, use shop, and complete progression without network code.
- All runtime content required by Python build exists in root-local runtime folders (`src/`, `game_data/`, `runs/`).
- Python build runs correctly without reading root-level DOS asset directories.
- Gameplay and visuals are close enough to legacy behavior for practical parity.

## Current Status
- Folder scaffold created.
- Self-contained asset destination scaffold created at `python/game_data/`.
- Section 1 implementation started and completed with a runnable runtime skeleton (`python/src/ultimatetk/core/`).
- Fixed-step clock (40 FPS target) and scene/state boundaries are in place.
- Section 2 implementation completed for binary format parsing in `python/src/ultimatetk/formats/`.
- Section 3 rendering baseline implemented in `python/src/ultimatetk/rendering/` and integrated into `GameplayScene`.
- Tile rendering, transparent/translucent sprite paths, and palette shadow/light table application are now active.
- Section 4 implementation started in `python/src/ultimatetk/systems/player_control.py` and `GameplayScene`.
- Legacy-style movement/rotation, wall collision checks, camera follow, and weapon slot switching are now scaffolded.
- Added initial shoot/reload cadence and wall-hit shot tracing hooks for early combat plumbing.
- Added first-pass enemy spawning, hit resolution, and enemy kill bookkeeping in gameplay simulation.
- Added first-pass enemy behavior loop with line-of-sight aiming, rotation, movement, and reload-gated enemy shooting.
- Combat loop is now bi-directional: enemies can damage the player, and runtime telemetry tracks player health plus enemy shot/hit totals.
- Added weapon-specific enemy pellet volleys for shotgun-style enemies and gated enemy fire once the player is dead.
- Added explosive near-miss splash damage for grenade-class enemy attacks and low tick-damage behavior for flamethrower attacks.
- Added enemy projectile entities with travel-time updates, wall/splash resolution, and active projectile tracking in gameplay runtime telemetry.
- Added player death/game-over flow in gameplay runtime state with countdown-based return to main menu.
- Added first-pass destructible crate entities (level-driven spawn, shot/projectile hit handling, and crate runtime telemetry).
- Added first-pass crate pickup/reward flow (player overlap collection, weapon unlock crates, bullet-pack crates, and energy restore crates).
- Added first-pass player ammo economy parity hooks (weapon ammo gating/consumption, bullet-crate ammo grants with per-type capacity caps, and empty-weapon fallback to fist).
- Runtime telemetry now exposes ammo telemetry snapshots for HUD/shop parity work (current-weapon ammo type/units/cap plus full per-type ammo pools and capacities).
- Added first-pass shop trading parity for ammo/weapons/shield/target, seeded sell-price generation, in-scene shop flow plumbing (toggle, row/column selection, buy/sell transaction events, runtime shop telemetry including blocked reasons), rendered overlays for shop + gameplay HUD (legacy item naming labels, counters, transaction feedback, first-pass weapon/ammo/health/cash/shield/target HUD, and active explosive counters), and first-pass player mine/C4 deploy-arming-detonation combat hooks with wall-aware blast-ray gating, partial-cover ray-weighted falloff, corner/corridor obstruction tuning, finer ray-trace sampling for tile-edge grazing control, plus scripted mine/C4 runtime telemetry and obstruction integration coverage (including mine corridor trigger/detonation obstruction scenarios, C4 side-wall leakage assertions, and scripted enemy grenade partial-vs-blocked obstruction checks); enemy grenade/projectile splash obstruction now follows the same wall-aware partial/full blocking model.
- Tightened enemy line-of-sight corner-edge behavior by sampling LOS rays at finer steps, preventing wall-graze peek shots and adding dedicated unit plus scripted integration coverage.
- Tightened enemy direct-shot tracing for corner-edge wall grazes, reducing leaked pellet hits and adding dedicated shotgun unit plus scripted direct-shot corner-graze integration coverage.
- Tightened player shot tracing for corner-edge wall grazes, reducing leaked hitscan enemy hits and adding dedicated player-shot corner-graze unit plus scripted integration coverage.
- Tightened enemy projectile sub-step tracing for corner-edge wall grazes, reducing leaked travel-time projectile hits and adding dedicated unit plus scripted projectile corner-graze integration coverage.
- Continued Phase 4 parity tuning with enemy in-range strafe behavior, point-blank explosive safety gating, grenade splash-to-crate propagation, mine proximity trigger LOS gating, extra narrow-lane explosive-ray damping, kind-specific mine/C4 falloff tuning, camera smoothing dead-zones/min-step catch-up, refined collision probes, visual shop/HUD polish including per-weapon/per-ammo shop glyph silhouettes plus expanded HUD status bars/readouts, and additional scripted mine/C4 obstruction micro-case coverage (diagonal and one-tile choke variants).
- Added shield-aware player health-capacity parity hooks: shield level now raises effective health cap (`+10` per level), energy-crate healing respects the shield-adjusted cap, shield sell-down clamps current health to the new cap, and HUD health text now shows current/capacity values.
- Tuned enemy firing cadence parity bookkeeping so `shoot_count` advances through aligned LOS attack windows (not only at fire instants) and resets on attack-window breaks, improving projectile/explosive spread cadence behavior.
- Added scripted headless shield shop + energy-crate integration coverage for buy-heal and sell-clamp flow.
- Added legacy-style enemy post-shot explosive forward-pressure tuning so long-range explosive shots temporarily bias reload movement toward forward push (walk-count style) before falling back to normal strafing/patrol flow.
- Added legacy-style enemy lost-sight chase-window tuning so enemies keep moving along last known attack heading for a distance-scaled window after LOS breaks, with new unit/integration coverage for prior-contact versus no-prior-contact behavior.
- Added legacy-style enemy front-arc vision gating so LOS detection also requires the player to be inside a 180-degree forward cone, with new unit/integration coverage for rear-hemisphere non-detection.
- Added legacy-style enemy vision-distance gating so LOS detection also requires targets to be within the short original sight radius (~160 px), with new unit/integration coverage for far-target non-detection.
- Added legacy-style enemy patrol idle/burst cadence so no-LOS patrol movement starts only on low-probability rolls and runs in finite bursts (old `walk_cnt` style), with unit/integration coverage for idle versus burst-start paths.
- Added patrol turn-lock parity so idle random retarget rolls wait until current heading rotation completes, with new unit/integration coverage for in-progress-turn target stability.
- Retuned enemy LOS sampling cadence to legacy 5-pixel progression for vision checks (while preserving modern corner-graze endpoint checks and vision gating), with new unit/integration coverage for step usage and updated blocked corner direct-shot expectations.
- Added crate-aware enemy cover/impact parity so live crates now block enemy LOS checks and absorb non-projectile enemy hitscan shots instead of letting traces pass through.
- Added crate-aware mine proximity trigger parity so live crates can also block mine contact-trigger LOS checks (not just walls).
- Added C4 activator follow-up parity in gameplay flow: firing C4 while a charge is already active now remote-triggers existing C4 charges instead of deploying another.
- HUD/runtime explosive-readiness telemetry expanded with mine armed-count and C4 hot-count, and HUD overlay now renders dedicated readiness bars plus armed/hot status readouts.
- FINALIZED (locked): mine proximity trigger contact math now uses nearest enemy collision-bounds points (instead of center-only distance/LOS), and HUD hint/readout color-codes mine/C4 readiness values for quicker in-combat parsing.
- FINALIZED (locked): movement/camera/combat micro-parity bundle includes per-axis diagonal collision wall-slide behavior, viewport half-height vertical camera snap for large gaps, and scaled player-collision-edge splash fallback when center-only splash misses.
- FINALIZED (locked): C4 activator trigger economy refunds the consumed C4 ammo unit on trigger-only follow-up shots when reusing existing charges, and enemy projectile hit/damage telemetry now gates on player-alive state to avoid post-death accumulation.
- Continued remaining Phase-4 tuning with enemy strafe-direction hold windows to reduce reload-phase zig-zag jitter, mine proximity checks anchored to explosive blast-center offsets, state-aware shop cell tinting for owned/full/unaffordable entries, and idle camera dead-zone stabilization; added unit coverage for strafe hold cadence, blast-center mine triggering, and idle-versus-walking camera response.
- Continued remaining Phase-4 combat parity by adding crate-aware explosive splash cover handling for enemy missed-shot grenade splash and enemy projectile wall/expiry splash against player, with new unit coverage for direct and projectile crate-cover reduction cases.
- Continued remaining Phase-4 mine/C4 obstruction micro-case tuning by adding crate-aware splash ray attenuation/blocking for player explosive damage against enemies/player in tight corridor lanes while preserving crate-target damage resolution, with dedicated C4/mine corridor cover unit coverage.
- Continued remaining Phase-4 mine trigger tuning for tight corner lanes by allowing very-near partial-cover contact triggers (ray-coverage gated with distance ratio) while keeping farther partial-contact cases blocked; added dedicated near-versus-far corner trigger unit coverage.
- Continued remaining Phase-4 HUD/shop fidelity polish with state-driven shop cell visuals (owned/full/no-cash marker tinting, active-row emphasis, and state-colored selection status text) plus HUD readout color tuning for health/ammo/reload glance readability; added scene-flow coverage for shop cell state/visual color mapping.
- Continued remaining Phase-4 combat edge-case parity by adding blocked-lane strafe fallback (retry opposite strafe direction when the primary side is obstructed) and projectile-expiry splash crate-cover attenuation checks, with dedicated unit coverage plus scripted headless runtime coverage for blocked-lane retry ordering and projectile-expiry crate-cover interactions.
- Continued remaining Phase-4 movement/camera feel tuning by making camera dead-zone behavior action-aware while idle (shoot-hold/fire-animation keeps tighter dead-zones than fully idle), with dedicated unit coverage.
- Continued remaining Phase-4 enemy combat cadence tuning for multi-enemy rooms by decoupling strafe-side selection from shoot-counter parity and adding per-enemy reload-phase strafe staggering, with new unit and scripted headless runtime coverage to verify non-synchronized side-switch timing around reload/reacquisition windows.
- Continued remaining Phase-4 explosive timing/contact parity by adding scripted `N-1`/`N`/`N+1` runtime boundary checks for mine arm-trigger and C4 remote-trigger transitions, plus scripted tight-lane multi-contact mine micro-cases (simultaneous edge contacts, chained detonations across sequential placements, and nearest-contact ordering) with supporting unit coverage.
- Completed remaining Phase-4 shop fidelity pass with refined per-weapon/per-ammo shop cell silhouettes and fixed-width 2-character label/counter alignment in dense 16x16 grid cells (including zero-padded numeric counters), with new scene-flow coverage for icon distinctness and text-slot alignment.
- Completed remaining Phase-4 HUD warning-transition coverage by asserting low-HP/low-ammo and mine/C4 readiness color-state changes (including unarmed-vs-armed mine and cool-vs-hot C4 transitions) in scene-flow tests.
- Completed remaining Phase-4 movement/camera feel pass by tuning movement-intent-aware camera look-ahead and strafe-turn blend dead-zone/catch-up behavior from side-by-side capture scenarios (turn-in-place firing, backward movement, and strafe-turn blends), plus map-bound edge-release handling to prevent sticky clamp drift when re-entering open space; added dedicated player-control unit coverage for these transitions.
- Headless runtime now supports scripted input event replay via `--input-script` for Phase 4 validation loops.
- Added terminal keyboard backend selection (`--platform terminal`) with action mapping and synthetic key-release handling.
- Terminal backend now translates player1 `options.cfg` scan-code keybinds into terminal actions where possible.
- Unit tests cover clock/scene flow plus EFP/FNT/LEV/palette/options format parsing.
- Rendering and phase-4 control unit tests were added under `python/tests/`.
- Asset repository adapter and migration/probe tooling added under `python/src/ultimatetk/assets/` and `python/tools/`.
- Added `python/tools/render_probe.py` to output a baseline rendered frame as PPM.
- Planning document created.
- Phase 4 input/control parity checklist is complete and locked in `python/docs/notes/phase4_input_control.md`.
- Phase 5 combat/entities planning note created at `python/docs/notes/phase5_combat_entities.md` and is now the active implementation guide.
- Started and completed Phase 5 Workstream 1 (projectile/explosive resolution hardening): stabilized same-tick crate-cover geometry for explosive attenuation, added deterministic nearest-first contact ordering for crate splash evaluation, and aligned direct-crate-impact projectile splash-to-player attenuation with secondary crate cover behavior; added targeted combat regression coverage and re-ran unit/integration verification suites.
- Started Phase 5 Workstream 2 (entity lifecycle/state-transition hygiene) with dead-state gating hardening: dead-enemy attack paths now short-circuit to no-hit/no-damage, enemy projectiles are now culled immediately when player is already dead, and gameplay projectile updates now optionally gate delayed projectile resolution by known owner-enemy liveness; added combat regressions for dead-player crate-side-effect suppression, dead-owner projectile discard, and dead-enemy attack resolution.
- Continued Phase 5 Workstream 2 with state-transition hygiene assertions: added dead-entity non-retrigger coverage for shot and C4 blast paths (no duplicate hit-flash/death transitions) and scene-flow coverage that game-over activation clears active projectile/explosive buffers in the same tick with runtime active counters immediately synchronized to zero.
- Continued Phase 5 Workstream 2 lifecycle gating in gameplay flow: if player is already dead at update start, the scene now enters game-over before simulation steps run, preventing post-death same-tick projectile/explosive side effects and counter drift.
- Completed Phase 5 Workstream 2 (entity lifecycle/state-transition hygiene): closed dead-state gating, removal timing, and hit-flash/death non-retrigger coverage goals with passing unit and scripted integration verification.
- Started Phase 5 Workstream 3 (crate interaction and reward consistency) with mixed combat/pickup exclusivity coverage: added scene-flow same-tick collect-vs-destroy precedence checks, full-health energy-crate non-collection then destruction checks, mixed dual-crate collect+destroy counter consistency checks, and combat-level guards for destroyed-crate reward suppression/post-collection non-destruction behavior.
- Completed Phase 5 Workstream 3 (crate interaction and reward consistency): validated destruction-versus-collection exclusivity and reward/counter coherence with unit, scene-flow, and scripted headless mixed collect+destroy runtime coverage.
- Completed Phase 5 Workstream 4 (combat economy and telemetry consistency): validated normal-fire ammo consumption and empty-weapon fallback runtime stability, locked C4 trigger-only refund telemetry consistency across scene-flow + scripted integration paths, and added monotonic/state-consistent combat telemetry invariants (including active-explosive decomposition consistency).
- Started Phase 5 Workstream 5 (regression expansion and lock criteria): added unit coverage for unknown-owner projectile retention under owner-liveness gating and scripted headless dead-player projectile telemetry gating coverage to lock post-death hit/damage suppression and same-tick projectile cleanup invariants.
- Continued Phase 5 Workstream 5 with mixed-owner gating lock coverage: added unit and scripted integration tests that ensure owner-liveness filtering drops only projectiles from known-dead owners while preserving unknown-owner projectiles in gameplay runtime updates with coherent hit/damage telemetry publication.
- Continued Phase 5 Workstream 5 with dead-player cleanup precedence lock coverage: added unit and scripted integration tests confirming dead-player gating clears mixed projectile/explosive buffers before owner/crate resolution branches and prevents post-death detonation/hit/damage telemetry drift.
- Continued Phase 5 Workstream 5 with in-update death ordering hardening: `update_enemy_projectiles` now halts on lethal player hits and clears remaining in-flight projectiles in the same pass; added unit + scripted integration lock tests to prevent follow-up projectile crate side effects after player death.
- Continued Phase 5 Workstream 5 with pre-lethal ordering lock coverage: added unit + scripted integration tests confirming deterministic side effects resolved before a lethal projectile are preserved, while only post-death follow-up effects are suppressed by the short-circuit.
- Completed Phase 5 Workstream 5 (regression expansion and lock criteria): finished final lock sweep for mine trigger ordering, HUD readiness tint transitions, movement/camera micro-parity boundaries, and C4/dead-player projectile telemetry gating; verified with full phase unit + integration command set.
- Completed Phase 5 handoff closeout: all Workstreams 1-5 are now closed and documented in `python/docs/notes/phase5_combat_entities.md`.
- Phase 6 kickoff note/checklist created at `python/docs/notes/phase6_ui_progression.md` and is now the active implementation guide for UI/progression flow.
- Completed Phase 6 Workstream 1 (interactive main-menu transition wiring): replaced the menu scaffold with explicit start/quit entries, added deterministic non-autostart menu navigation/confirm handling while preserving autostart flow, and expanded scene-flow plus scripted headless coverage for manual start and menu-selected quit behavior.
- Completed initial Phase 6 Workstream 2 (session progression state machine): manual-flow level completion now advances `session.level_index` deterministically (`enemies_alive == 0` trigger), missing-next-level completion falls back to main menu with index reset, and death path remains non-advancing retry via game-over -> menu; added scene-flow and scripted headless progression coverage.
- Completed Phase 6 Workstream 3 (inter-level and run-outcome UI states): progression now routes through explicit `level_complete` and `run_complete` scenes with deterministic hold/confirm timing, runtime progression metadata publication (`progression_*` fields), and expanded unit/scripted integration coverage for level-complete and content-end fallback paths.
- Completed Phase 6 Workstream 4 (persistence and profile continuity hooks): added minimal persisted session profile storage under `python/runs/profiles/session.json` (`player_name`, `episode_index`, `level_index`, schema version), wired explicit startup load/new-session entry points plus shutdown auto-save controls, and added dedicated unit coverage for profile store, app wiring, and CLI flag parsing.
- Completed Phase 6 Workstream 5 (regression expansion and lock criteria): added full manual menu->gameplay->progression->menu loop coverage in unit and scripted headless integration suites, ensured persisted profile artifacts are gitignored, and re-verified Phase 5 combat/entity lock suites remained stable.
- Phase 6 goals are now complete; next focus moves to Phase 7 balancing/parity pass.
- Phase 7 kickoff plan created at `python/docs/notes/phase7_balancing_parity.md` with baseline-capture, balancing, and lock-expansion workstreams.
- Started Phase 7 Workstream 1 (baseline capture/targets): defined canonical movement/combat/economy/progression parity scenarios plus initial tolerance windows in `python/docs/notes/phase7_balancing_parity.md`, and captured first baseline verification snapshot (`175` unit tests + `44` integration tests passing).
- Prepared first Phase 7 Workstream 2 movement/camera tuning slice by enumerating candidate camera parameters and focused guard suites in `python/docs/notes/phase7_balancing_parity.md`.
- Completed first Phase 7 Workstream 2 movement/camera tuning slice: turn-in-place shooting camera catch-up now uses explicit action-idle catch-up tuning (`CAMERA_ACTION_IDLE_CATCHUP_BONUS = 2`), with strengthened unit lock assertion and passing focused + full phase verification suites.
- Completed first Phase 7 Workstream 3 combat/enemy cadence tuning slice: increased enemy reload-phase strafe hold cadence (`ENEMY_STRAFE_DIRECTION_HOLD_TICKS = 5`) to reduce zig-zag jitter, added explicit unit lock coverage for the tuned hold window, and re-verified focused + full phase suites.
- Completed first Phase 7 Workstream 4 progression/economy pacing slice: reduced level/run progression hold timing (`LevelCompleteScene: 20 ticks`, `RunCompleteScene: 30 ticks`), added explicit scene-flow lock tests for tuned hold windows, and re-verified focused + full phase suites.
- Started Phase 7 Workstream 5 lock expansion: added progression confirm-timing lock assertions (confirm immediately zeroes `progression_ticks_remaining` before transition update) and re-verified focused progression paths plus full phase suites.
- Continued Phase 7 Workstream 5 lock expansion with enemy strafe cadence boundaries: added explicit unit + scripted integration assertions for first-switch index and neighbor stagger delta in tuned reload-phase strafe behavior, then re-verified focused + full phase suites.
- Continued Phase 7 Workstream 5 lock expansion with runtime-level camera catch-up coverage: added scene-flow assertions that action-idle camera updates keep the tuned minimum catch-up lead over idle (`>= 2` pixels) and re-verified focused + full phase suites.
- Continued Phase 7 Workstream 5 lock expansion with progression auto-return timing coverage: added scene-flow assertions that `level_complete` and `run_complete` auto-return only on the final tuned hold tick, with updated full phase verification (`180` unit tests + `44` integration tests passing).
- Continued Phase 7 Workstream 5 lock expansion with post-progression shop/economy stability coverage: added scene-flow assertions that shop open/buy/close and blocked-purchase cash invariants remain stable after manual progression-loop restart, with updated full phase verification (`181` unit tests + `44` integration tests passing).
- Completed Phase 7 closeout: all five workstreams are now closed and documented in `python/docs/notes/phase7_balancing_parity.md`; next focus moves to Phase 8 regression-suite expansion and golden-check handoff prep.
- Phase 8 kickoff note/checklist created at `python/docs/notes/phase8_regression_suite.md` and is now the active implementation guide for regression-suite expansion.
- Started Phase 8 Workstream 1 (golden scenario catalog): drafted canonical behavior/render scenario sets plus acceptance envelope in `python/docs/notes/phase8_regression_suite.md`, and captured baseline verification snapshot (`181` unit tests + `45` integration tests passing).
- Completed Phase 8 Workstream 2 slice 1 (behavior-golden): added deterministic runtime behavior digest assertions for scripted manual progression-loop endpoint coverage in `python/tests/integration/test_headless_input_script_runtime.py`, with Phase 8 verification matrix re-confirmed passing (`181` unit tests + `45` integration tests).
- Completed Phase 8 Workstream 3 slice 1 (render-golden): added deterministic real-data render camera/digest golden locks in `python/tests/integration/test_real_data_render.py`, with Phase 8 verification matrix re-confirmed passing (`181` unit tests + `45` integration tests).
- Completed Phase 8 Workstream 4: published fast/full regression command bundles and Phase 8 golden artifact policy in `python/docs/notes/phase8_regression_suite.md`.
- Completed Phase 8 closeout: all five workstreams are now closed and documented in `python/docs/notes/phase8_regression_suite.md`; next focus moves to Phase 9 data-colocation/release-hardening work.
- Phase 9 kickoff note/checklist created at `python/docs/notes/phase9_data_release_hardening.md` and is now the active implementation guide for final release hardening.
- Started Phase 9 Workstream 1 (asset inventory and colocation manifest hardening): added `python/tools/asset_manifest_report.py`, generated `python/game_data/asset_manifest.json` plus `python/game_data/asset_manifest_gap_list.md`, and added integration locks for manifest-required missing-asset checks plus graphical/sound parity against original legacy source directories (`python3 -m pytest tests/integration/test_real_data_parse.py` -> `3 passed`; full integration matrix -> `47 passed`).
- Completed first Phase 9 Workstream 2/3 isolation slices: startup now enforces `asset_manifest.json` required-asset validation and in-root path checks, repository resolution now blocks symlink/path escapes outside expected asset directories, and new negative-path integration coverage locks fail-fast behavior when manifest-required assets are missing (`python3 -m pytest tests/unit/test_fixed_step_clock.py tests/unit/test_player_control.py tests/unit/test_combat.py tests/unit/test_scene_flow.py` -> `181 passed`; `python3 -m pytest tests/integration/test_headless_input_script_runtime.py tests/integration/test_real_data_render.py tests/integration/test_real_data_parse.py` -> `48 passed`).
- Completed first Phase 9 Workstream 4 release-workflow/docs slice: documented release verification command bundles and runtime artifact expectations in phase notes, hardened `python/.gitignore` for runtime screenshot/profile artifacts while preserving tracked `.gitkeep` placeholders, and re-ran full phase verification matrix (`181` phase unit tests + `48` phase integration tests passing).
- Completed Phase 9 closeout: all five workstreams are closed, final hardened-path verification matrix is passing (`181` phase unit tests + `48` phase integration tests), and release-readiness handoff documentation is finalized in `python/docs/notes/phase9_data_release_hardening.md`.
- Added post-Phase-9 release runbook automation: `python/tools/release_verification.py` now runs the manifest + unit + integration release bundle from one command, and `python/docs/release_verification.md` documents usage plus artifact hygiene (`python3 python/tools/release_verification.py` and `python3 python/tools/release_verification.py --skip-integration` validated successfully).
- Added Phase 10 execution checklist plan at `python/docs/notes/phase10_root_flatten_cleanup.md` for optional legacy-compare mode, root flattening, and legacy data cleanup sequencing.
- Started Phase 10 Workstream 2 conflict-prep move: archived original DOS-era payload (`SRC`, `BAK`, root asset directories, binaries/docs/config files) under `ARCHIVE/` to remove root-level naming collisions ahead of flattening, with unit matrix verification (`181 passed`).
- Completed Phase 10 Workstream 1 (optional legacy-compare mode): manifest generation and release verification now run in default python-only mode without legacy root directories, while strict parity checks remain available via explicit legacy-root flags/environment (`python3 python/tools/release_verification.py --skip-integration` passed; strict mode `python3 python/tools/release_verification.py --legacy-compare-root ARCHIVE --skip-unit` passed).
- Completed Phase 10 Workstream 3 (root flatten): moved project runtime/docs/tooling from `python/` to repository root (`src/`, `tests/`, `tools/`, `docs/`, `game_data/`, `runs/`, `pyproject.toml`, root `.gitignore`), removed the wrapper directory, and verified root-layout execution (`python3 tools/release_verification.py` -> `181 passed`, plus integration matrix `47 passed, 1 skipped` default mode).
- Continued Phase 10 Workstream 4 cleanup: root legacy asset/source trees remain archived under `ARCHIVE/` and strict parity mode remains available via `python3 tools/release_verification.py --legacy-compare-root ARCHIVE --skip-unit` (`48 passed`).
- Historical references above that use `python/...` paths reflect pre-flatten commit history and are kept for traceability.
- Completed Phase 10 closeout: root-native project layout is finalized, legacy payload is archived under `ARCHIVE/`, default release verification is legacy-independent, strict legacy parity checks remain opt-in, and `docs/notes/phase10_root_flatten_cleanup.md` now records full completion.
- Started and completed Phase 11 Workstream 1 (optional pygame runtime selection/lazy import guardrails): added `--platform pygame` wiring with default headless unchanged, added lazy pygame import in a dedicated backend (`src/ultimatetk/core/platform_pygame.py`) with clear missing-dependency install hint, and verified with focused platform/CLI/pygame unit tests (`10 passed`) plus headless and pygame-startup smoke checks.
- Completed Phase 11 Workstream 2 (frame handoff for visual backend presentation): runtime state now publishes latest gameplay indexed frame payload and palette bytes (`last_render_pixels`, `last_render_palette`) alongside existing digest/size telemetry, with scene-flow assertions and focused verification (`python3 -m pytest tests/unit/test_scene_flow.py tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py` -> `48 passed`).
- Completed Phase 11 Workstream 3 (pygame backend implementation): replaced the initial backend stub with startup/poll/present/shutdown flow, added keyboard/action parity mapping and direct weapon-slot handling, and added mocked-pygame unit coverage for event mapping plus frame presentation (`python3 -m pytest tests/unit/test_scene_flow.py tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py` -> `48 passed`).
- Completed Phase 11 Workstream 4 (scaling policy and CLI controls): added `--window-scale` CLI support with positive-integer validation, wired `pygame_window_scale` through runtime config into backend selection, added non-positive scale guard in app creation, and extended CLI/platform unit coverage (`python3 -m pytest tests/unit/test_scene_flow.py tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py` -> `52 passed`).
- Completed Phase 11 Workstream 5 (packaging/tests/docs): added optional `pygame` dependency extra in `pyproject.toml`, updated `README.md` with pygame launch/install guidance and scale examples, and re-verified non-pygame release flow with `python3 tools/release_verification.py` (`181` unit passed, integration `47 passed, 1 skipped`).
- Completed Phase 11 closeout validation: expanded pygame backend unit coverage for default/custom window sizing, quit-event mapping, and duplicate-keydown suppression, then re-ran focused phase-11 unit matrix (`python3 -m pytest tests/unit/test_scene_flow.py tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py` -> `56 passed`) and marked phase checklist completion in `docs/notes/phase11_pygame_runtime_frontend.md`.
- Completed post-closeout live pygame smoke verification after installing local dependency: `PYTHONPATH=src python3 -m ultimatetk --platform pygame --autostart-gameplay --window-scale 2 --max-seconds 1` successfully exercised boot -> menu -> gameplay -> clean shutdown.
- Added post-closeout pygame control discoverability follow-up: expanded pygame weapon-selection input mappings with numpad (`KP0..KP9`, `KP-`, `KP+`) and `F1..F12`, added mouse-wheel and `PageUp/PageDown` cycling support, and extended focused unit verification (`python3 -m pytest tests/unit/test_scene_flow.py tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py` -> `59 passed`).
- Added post-closeout Phase 11 UI-visibility follow-up: implemented software-rendered main-menu and progression scene overlays so pygame no longer shows black screens in those states, added scene-flow render payload coverage, and re-verified (`python3 -m pytest tests/unit/test_scene_flow.py tests/unit/test_app_platform_selection.py tests/unit/test_cli_session_args.py tests/unit/test_pygame_platform.py` -> `61 passed`; `python3 tools/release_verification.py` -> `183` unit passed, integration `47 passed, 1 skipped`).
- Started Phase 12 planning for Gymnasium AI training interface: added `docs/notes/phase12_gymnasium_ai_training_interface.md` with locked decisions (headless gameplay-first reset at level 1, shop enabled for learning economy-dependent progression, `MultiBinary`/`MultiDiscrete` actions with strafing, 32-sector radial observation plan, explicit death-reset handling, and explicit run-complete `game_completed` termination signaling).
- Started Phase 12 implementation (initial scaffold): added `src/ultimatetk/ai/` Gymnasium stack (`gym_env.py`, `runtime_driver.py`, `action_codec.py`, `observation.py`, `reward.py`), added gameplay AI snapshot accessor (`GameplayStateView`) and scene-manager `current_scene` accessor, added optional `ai` extras in `pyproject.toml`, added Gym/random-policy smoke tool and AI-focused unit/integration tests, and re-verified non-AI release bundle stability (`python3 tools/release_verification.py` -> unit `183 passed`, integration `47 passed, 1 skipped`; AI tests currently skip in local env without `gymnasium`/`numpy`).
- Continued Phase 12 validation after installing optional AI dependencies via conda (`conda install -y -n ultimatetk -c conda-forge numpy gymnasium`): AI-focused unit/integration matrix now passes (`10 passed`), random-policy smoke run passes, and fixed-seed deterministic replay coverage was added to `tests/unit/test_gym_env.py` (`4 passed`).
- Completed Phase 12 closeout: Gymnasium interface goals are complete (headless gameplay-first reset, shop-enabled policy controls, multi-level progression carry-over, run-complete termination signaling, and deterministic replay coverage), with passing AI matrix (`11 passed`) and unchanged release verification (`183` unit passed, integration `47 passed, 1 skipped`).
- Started Phase 13 PPO tooling slice: added SB3 action-space adapter (`src/ultimatetk/ai/sb3_action_wrapper.py`), torch device resolver (`src/ultimatetk/ai/training_device.py`), SB3 env factory (`src/ultimatetk/ai/sb3_env_factory.py`), trainer/eval CLIs (`tools/ppo_train.py`, `tools/ppo_eval.py`), phase note (`docs/notes/phase13_ppo_trainer_loop.md`), and unit coverage for action wrapping/device resolution (`tests/unit/test_sb3_action_wrapper.py`, `tests/unit/test_training_device.py`); README and optional deps were updated for conda-first training setup.
- Continued Phase 13 validation + tooling bring-up: installed trainer deps via conda in `ultimatetk` (`conda install -y -n ultimatetk -c conda-forge pytorch stable-baselines3`), added CLI help smoke tests (`tests/unit/test_ppo_tools_cli.py`), validated targeted unit/integration suites (`8 passed` + `6 passed`), and completed short MPS-backed train/eval smoke runs (`tools/ppo_train.py` + `tools/ppo_eval.py`) with checkpoint/best/final artifacts under `runs/ai/ppo/phase13_smoke2/`.
- Continued Phase 13 throughput optimization and logging setup: installed `tensorboard` via conda (`conda install -y -n ultimatetk -c conda-forge tensorboard`), switched training env runtime to skip scene rendering by default, added opt-in render flags to train/eval tools, allowed disabling eval/checkpoint callbacks (`--eval-freq 0 --checkpoint-freq 0`) for uncapped throughput runs, and tuned auto-device selection to prefer CPU on non-CUDA hosts; re-validated unit/regression bundles (`10 passed`, `6 passed`, release unit matrix `183 passed`) and recorded uncapped training smoke throughput (`fps 1211`, `runs/ai/ppo/phase13_smoke_fast_auto/`).
- Continued Phase 13 tensorboard visibility hardening: `tools/ppo_train.py` now requires tensorboard, always writes tensorboard logs, and prints explicit browser launch instructions (`tensorboard --logdir ... --host 127.0.0.1 --port 6006`) when training starts; validated with short smoke run producing `events.out.tfevents...` under `runs/ai/ppo/phase13_tb_check/tensorboard/`.
- Started Phase 14 pygame playback slice: added plan note (`docs/notes/phase14_ai_model_pygame_playback.md`), introduced shared SB3 action conversion helper (`sb3_vector_to_env_action`) in `src/ultimatetk/ai/sb3_action_wrapper.py`, and added `tools/ppo_play_pygame.py` to run saved PPO models through `TrainingRuntimeDriver` with pygame presentation at capped FPS (default 40) plus optional manual-input mixing for debug sessions; validated with updated PPO tool tests (`11 passed`), short live playback smoke (`reason=max_seconds`, `steps=38`), and release unit verification (`183 passed`).
- Removed in-repo `ARCHIVE/` payload snapshot from version control to reduce repository footprint; strict legacy comparison and legacy-data migration remain available via explicit external legacy root paths (`--legacy-compare-root /path/to/original/legacy-root`, `--legacy-root /path/to/original/legacy-root`).
- Updated PPO trainer defaults for long-form stable training runs: `--total-timesteps` now defaults to `5_000_000`, rollout/batch defaults to `n_steps=2048` and `batch_size=128`, LR schedule defaults to `3e-4 -> 5e-5`, entropy schedule defaults to `0.05 -> 0.01`, and explicit `--gae-lambda`/`--clip-range` flags were added with defaults `0.95` / `0.2`.
- Started enemy-AI follow-up tuning for early-level combat readability: fixed short-range dead-zone stalls in engage distance selection, added blocked-forward strafe fallback, added conservative last-seen investigate state and neighbor-separation steering to reduce static clumping, documented the rollout in `docs/notes/enemy_ai_improvement_plan.md`, and locked behavior with expanded combat unit coverage (`python3 -m pytest tests/unit/test_combat.py` -> `101 passed`).
- Completed Phase 1 DRY test-harness cleanup for scripted headless integration scenarios: consolidated app bootstrap/gameplay-entry/combat-state extraction/tile mutation helpers in `tests/integration/test_headless_input_script_runtime.py`, removed repeated inline setup blocks across scenario helpers and menu/progression tests, and re-verified the full file (`pytest tests/integration/test_headless_input_script_runtime.py -q` -> `43 passed`).
- Tuned Gym reward shaping to reduce local-optimum jitter: standardized config naming to sign-consistent `*_cost` fields, lowered/conditioned strafing reward to engagement-only contexts, added anti-stuck area penalty tracking, and increased idle movement epsilon with lower idle tick threshold to punish corner vibration sooner (`pytest tests/unit/test_gym_reward.py` -> `9 passed`).
- Completed DRY refactoring pass on `src/ultimatetk/systems/combat.py` (longest non-test source): extracted shared helpers (`_table_lookup`, `_point_in_rect`, `_projectile_overlaps_rect`, `_closest_point_on_rect`, `_reset_enemy_engagement`, `_apply_damage`, `_advance_flash_ticks`, `_alive_count`, `_projectile_splash_resolution`, `_angle_to_radians`), collapsed 11 identical tuple-accessor functions into one-liner wrappers, deduplicated 5 AABB collision functions, consolidated entity damage/flash/count logic, consolidated projectile impact branches, named inline magic numbers as constants, and consolidated the crate-type expansion loop; verified with full test suite (`336 passed, 1 skipped`).
- Updated PPO trainer defaults: `n_steps=4096`, `batch_size=512`, `decay_ratio=0.8` for longer stable rollouts.
- Completed DRY refactoring pass on `src/ultimatetk/systems/gameplay_scene.py` (2nd longest non-test source, 2230→2129 lines): extracted state-reset helpers (`_reset_input_flags`, `_reset_entity_holders`, `_reset_stat_counters`, `_sell_seed`) replacing 6-way duplicated input-flag blocks and 2-way duplicated counter/asset blocks; extracted `_publish_zeroed_runtime_state` and `_publish_zeroed_shop_last_fields` eliminating the largest copy-paste block (~50 lines duplicated between `on_enter` and `_publish_player_runtime_state`); extracted `_count_player_explosives` for deduplicated mine/C4 counting; replaced icon if-chains with tuple lookups (`_WEAPON_ICON_KINDS`, `_AMMO_ICON_KINDS`); added `_clamp01` helper replacing 6 repeated ratio-clamp expressions; and unified 7 shop-cell dispatch methods via a `_ShopCellInfo` descriptor with a single `_shop_cell_info` method; verified with full test suite (`336 passed, 1 skipped`).
- Started phased DRY refactor for `src/ultimatetk/systems/player_control.py` with safe helper extraction: added internal tuple lookup helpers plus shared index validators and migrated repeated wrapper/accessor guards to those helpers; phase tracking note added at `docs/notes/player_control_dry_refactor.md`.
- Continued phased DRY refactor for `src/ultimatetk/systems/player_control.py` with shop transaction dedupe: extracted shared transaction event construction plus buy/sell row resolvers (`weapon`/`ammo`/`shield`/`target`) so validation, success/units/category mapping, and block-reason handling are centralized while preserving current behavior.
- Continued phased DRY refactor for `src/ultimatetk/systems/player_control.py` with movement/camera dedupe: extracted axis-specific collision probing into one helper and unified duplicated camera-axis follow logic through a shared path while preserving constants and motion feel.
- Completed phased DRY refactor for `src/ultimatetk/systems/player_control.py`: finished helper-based dedupe across table/index access, shop transaction resolution, and movement/camera axis paths, then re-verified targeted unit/integration suites plus full regression (`336 passed, 1 skipped`).
- Added PPO weapon-mode training scenarios: `tools/ppo_train.py` now accepts `--weapon-mode` (`normal_mode` plus weapon-specific snake_case slots), runtime driver applies selected-weapon lock with true infinite player ammo and crate suppression for non-`normal_mode` runs, and gym/CLI coverage now locks the new behavior (`tests/unit/test_gym_env.py`, `tests/unit/test_ppo_tools_cli.py`).
- Added PPO evaluation parity for scenario modes: `tools/ppo_eval.py` now accepts `--weapon-mode` (same snake_case choices as training) and forwards it through env factory/runtime so eval can match training conditions exactly; CLI smoke coverage now asserts flag visibility.
- Extended PPO training robustness and environment diversity controls: tuned default Gym reward shaping values in `src/ultimatetk/ai/reward.py` (higher death/damage/stuck penalties, reduced passive visibility reward, adjusted completion rewards) and added optional per-episode randomized start-level sampling for training via `--randomize-level-on-reset` + `--level-index-pool` (`tools/ppo_train.py`, `src/ultimatetk/ai/gym_env.py`, `src/ultimatetk/ai/sb3_env_factory.py`), with new unit coverage for randomized/reset-override behavior in `tests/unit/test_gym_env.py`; README PPO docs were updated to match current defaults and new flags.
- Completed AI-gym reward system improvements: implemented five systematic reward shaping enhancements to fix learning dynamics issues (local optima traps like "hiding in shop" and slow learning): (1) Level-Complete Reward Scaling scales by enemy count (base 8.0 + enemies × 0.8) to incentivize progression relative to difficulty; (2) Look-At-Enemy Reward Increase raised from 0.0015 to 0.010 (6.7×) to strengthen engagement incentive; (3) Strafing-Reward Improvement raised from 0.0008 to 0.008 (10×) and removed ammo condition to encourage active combat maneuvering; (4) Shooting Without Target Penalty applies -0.04 after 5-tick grace period to discourage blind spray; (5) Tile-Based Exploration Reward grants +0.001 bonus per new visited tile to reward map exploration and reduce stuck/idle penalties. All improvements track state properly with grace periods, and comprehensive English documentation/tests confirm expected behavior (`tests/unit/test_gym_reward.py` -> `12 passed`; smoke run `episodes=3` passes).
- Started Phase 15 reward stabilization + observability planning: rewrote `docs/notes/ai_gym_reward_improvements.md` into contradiction-free current-state canonical format (active defaults, active logic, validation snapshot, superseded historical note) and added phase plan `docs/notes/phase15_reward_stabilization_observability.md` for reward breakdown telemetry, accounting tests, and PPO A/B evaluation protocol.
- Continued Phase 15 implementation: added component-wise reward telemetry to Gym step info (`info["reward_breakdown"]`) by extending `RewardStep` in `src/ultimatetk/ai/reward.py` and wiring through `src/ultimatetk/ai/gym_env.py`; added accounting-consistency coverage in `tests/unit/test_gym_reward.py` and `tests/unit/test_gym_env.py`; updated Phase 15 and reward notes to reflect telemetry landing.
- Rebalanced Gym reward defaults for training stability and fixed stuck-counter reset behavior in `src/ultimatetk/ai/reward.py`: reduced dense penalty saturation (especially stuck/visible-no-hit), increased death penalty relative to combat rewards, enabled non-zero shooting-discipline penalties by default, and reset stuck/stationary-shoot counters when conditions clear; extended reward unit coverage with stuck-reset regression tests and active-default checks (`pytest tests/unit/test_gym_reward.py` -> `15 passed`), and re-ran smoke episodes (`python3 tools/gym_random_policy_smoke.py --episodes 3 --max-steps 500`).
