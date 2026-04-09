# Phase 4: Input and Player Control (Started)

This phase introduces the first gameplay control loop for the Python port.

Implemented:

- Event model expansion in `python/src/ultimatetk/core/events.py`:
  - Added action press/release events.
  - Added direct weapon-select events.
  - Added explicit action enum for movement/turning/strafe/weapon cycle.
- Headless scripted input support:
  - Added `python/src/ultimatetk/core/input_script.py` for parsing scripted events.
  - Added CLI `--input-script` and backend scheduling so controls can be replayed in headless runs.
- Terminal keyboard backend support:
  - Added `python/src/ultimatetk/core/terminal_input.py` for terminal byte decoding and action mapping.
  - Added `TerminalPlatformBackend` and CLI `--platform terminal`.
  - Added key-repeat hold logic to synthesize action release events in TTY mode.
  - Added legacy keybind translation so player1 controls from `options.cfg` are used where terminal input can represent them.
- Player control logic in `python/src/ultimatetk/systems/player_control.py`:
  - Legacy-style rotation steps (`9` degrees per tick).
  - Legacy movement behavior for forward/backward, strafe modifier, and dedicated strafe keys.
  - Wall collision checks based on floor-vs-wall level blocks.
  - Weapon slot cycling and direct slot selection.
  - Initial shoot/reload cadence based on legacy weapon loading times.
  - Simple shot tracing to wall impact points for first combat plumbing.
  - Camera follow behavior adapted from legacy `Player::move_scr`.
  - Added first-pass shop trading helpers with legacy-aligned buy/sell behavior for ammo, weapons, shield, and target system.
  - Added seeded shop sell-price generation matching legacy formulas and player-side shield/target state tracking.
  - Added shop selection/navigation helpers plus normalized buy/sell transaction event helpers for row/column-driven shop flow.
- Combat scaffolding in `python/src/ultimatetk/systems/combat.py`:
  - Deterministic enemy spawn from level enemy counts.
  - Hitscan-style shot resolution against walls and enemy hitboxes.
  - Weapon-slot damage table for first pass damage application.
  - Added weapon-specific enemy pellet volleys (shotgun/auto-shotgun spread) for more legacy-like fire behavior.
  - Added explosive near-miss splash damage for grenade-class enemy shots and low tick-damage handling for flamethrower shots.
  - Added enemy projectile entities with travel-time simulation, wall impact handling, splash falloff, and per-frame projectile updates.
  - Added first-pass crate entity spawning from level crate metadata (explicit positions or deterministic count-based placement).
  - Added destructible crate hitboxes and hit-flash effect ticks for player shots and enemy projectile collisions.
  - Added first-pass player crate collection + rewards (weapon unlock crates, bullet-pack crates, and energy restore crates).
  - Added first-pass player ammo economy for non-fist weapons: ammo-gated firing, one-round consumption per shot, and empty-weapon fallback to fist.
  - Bullet crate rewards now apply to player ammo pools with legacy-like per-type caps.
  - Added ammo snapshot helpers for runtime telemetry: current-weapon ammo (type/index, units, cap) and full per-type ammo pools/capacities.
  - Enemy hit flash and alive/dead state bookkeeping.
  - First-pass enemy behavior loop with line-of-sight aiming, 9-degree rotate steps, movement/collision, and reload-gated enemy shooting.
  - Enemy-to-player shot resolution and player damage/health tracking for bi-directional combat.
  - Enemy firing now stops once the player is dead.
- Gameplay integration in `python/src/ultimatetk/systems/gameplay_scene.py`:
  - Event handling now updates held input actions.
  - Player state is updated each simulation tick from held actions.
  - Camera follows the player and aiming direction.
  - Runtime metadata now includes player position, angle, weapon slot, reload/fire state, shots fired, cash, shield level, target-system flag, hits, enemy counters, and crate counters.
  - Runtime metadata now also includes current-weapon ammo snapshot fields plus full per-type ammo pool/capacity snapshots for HUD/shop parity scaffolding.
  - Added first-pass in-game shop mode toggled via input action, with row/column selection movement and buy/sell transaction handling wired into shop helpers.
  - Added deterministic per-level sell-price table generation hook on gameplay scene enter.
  - Runtime metadata now includes shop-active flag, shop selection row/column, and latest transaction outcome fields.
  - Enemy projectile entities are now updated each tick and rendered as world markers.
  - Crate entities are rendered from `CRATES.EFP` frames and removed from scene rendering when destroyed.
  - Touching a live crate now consumes it and applies crate-type reward effects.
  - Added player death -> game-over flow with countdown and automatic return to main menu.
  - Game-over return path now disables menu autostart to avoid immediate gameplay re-entry loops.

Visual baseline updates:

- Gameplay scene now draws a player sprite frame from `RAMBO2.EFP` based on current view angle.
- Gameplay scene also renders a translucent aim marker (`TARGET.EFP`) at player look direction.
- Gameplay scene now renders a short-lived shot impact marker at traced hit points.
- Gameplay scene now renders enemy sprites (`ENEMY*.EFP`) and supports being hit/killed by player shots.

Verification:

- Added unit tests:
  - `python/tests/unit/test_app_platform_selection.py`
  - `python/tests/unit/test_combat.py`
  - `python/tests/unit/test_events.py`
  - `python/tests/unit/test_terminal_input.py`
  - `python/tests/unit/test_input_script.py`
  - `python/tests/unit/test_headless_platform_input.py`
  - `python/tests/unit/test_player_control.py`
  - `python/tests/unit/test_scene_flow.py`
- Added integration test:
  - `python/tests/integration/test_headless_input_script_runtime.py`

Remaining work for Phase 4:

- Extend combat behavior with richer projectile/explosive parity details (special cases like mine/C4 behavior) and additional enemy behavior tuning.
- Build visual shop UI/HUD presentation parity (price panels, ownership/ammo counters, and feedback text) on top of the current interactive shop flow plumbing.
- Continue parity tuning for collision feel and camera response.
