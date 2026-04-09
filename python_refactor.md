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
4. Input and player control
   - Movement, collision, aiming/rotation, weapon switching
5. Combat and entities
   - Bullets, enemies, crates, effects, damage/death flow
6. UI and progression
   - Main menu, options, episode/level flow, shop, HUD
7. Balancing and parity pass
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
- Retuned mine proximity trigger contact math to use nearest enemy collision-bounds points (instead of center-only distance/LOS), improving tight edge-contact trigger parity; HUD hint/readout now color-codes mine/C4 readiness values for quicker in-combat parsing.
- Retuned movement/camera/combat micro-parity: diagonal collision now resolves per-axis with current orthogonal probes for cleaner wall-slide behavior, camera vertical large-gap snap now uses viewport half-height parity, and explosive splash adds scaled player-collision-edge fallback when center-only splash misses.
- Headless runtime now supports scripted input event replay via `--input-script` for Phase 4 validation loops.
- Added terminal keyboard backend selection (`--platform terminal`) with action mapping and synthetic key-release handling.
- Terminal backend now translates player1 `options.cfg` scan-code keybinds into terminal actions where possible.
- Unit tests cover clock/scene flow plus EFP/FNT/LEV/palette/options format parsing.
- Rendering and phase-4 control unit tests were added under `python/tests/`.
- Asset repository adapter and migration/probe tooling added under `python/src/ultimatetk/assets/` and `python/tools/`.
- Added `python/tools/render_probe.py` to output a baseline rendered frame as PPM.
- Planning document created.
- Combat/entity/progression systems are still in progress (advanced projectile edge cases, visual HUD/shop parity, and broader UI/progression flow).
