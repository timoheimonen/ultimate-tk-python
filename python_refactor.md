# Python Refactor Plan (No Multiplayer)

## Objective
Port The Ultimate TK from DOS C/C++ to Python while preserving gameplay feel and data compatibility, with multiplayer/IPX removed from scope and all runtime data packaged inside `python/`.

## Scope
- In scope:
  - Single-player gameplay loop
  - Existing level/content formats (`.LEV`, `.EFP`, `.FNT`, `palette.tab`, `options.cfg`)
  - Menus, options, shop, combat, enemies, effects, rendering
  - Self-contained Python runtime and assets under `python/` only
- Out of scope:
  - IPX networking, lobby/join flow, chat, server/client sync
  - Any code under legacy network transport modules

## Python Folder Layout
The following structure has been created under `python/`:

```text
python/
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
- All required runtime data must exist under `python/game_data/`.
- End state: original legacy file structure is not needed anymore for the Python build.
- Asset path resolution in Python code must be relative to `python/`.
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
7. Balancing and parity pass (active)
   - Timing adjustments, camera behavior, spawn and effect cadence
8. Regression suite
   - Golden snapshots and behavior checks from known scenarios
9. Data colocation and release hardening
   - Migrate all required runtime assets into `python/game_data/`
   - Verify the game launches and runs without reading root-level legacy data paths

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
  - Validate startup/gameplay works when only `python/` data paths are available

## Risks and Watch Items
- Palette/shadow/light math must match legacy table behavior
- Collision and movement feel are sensitive to small integer/float differences
- Legacy random/event cadence can drift if update order changes
- Signed byte vs unsigned byte handling in asset decoding

## Definition of Done (Single-Player)
- Player can launch, choose episode, play through levels, fight enemies, use shop, and complete progression without network code.
- All runtime content required by Python build exists inside `python/`.
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
