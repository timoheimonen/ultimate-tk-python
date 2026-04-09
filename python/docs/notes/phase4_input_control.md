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
  - Refined collision probe checks (triple-point edge probes) for less edge-graze clipping and improved corner stability.
  - Retuned axis collision resolution so diagonal moves re-evaluate probes per-axis (using current orthogonal position), reducing corner stickiness and improving wall-slide behavior when one axis is blocked.
  - Weapon slot cycling and direct slot selection.
  - Initial shoot/reload cadence based on legacy weapon loading times.
  - Simple shot tracing to wall impact points for first combat plumbing.
  - Camera follow behavior adapted from legacy `Player::move_scr`.
  - Camera response smoothing tuned with look-ahead dead-zones and minimum step catch-up so small look-offset deltas no longer stall.
  - Camera large-gap vertical catch-up now snaps at viewport half-height parity (matching horizontal threshold style) to reduce delayed re-centering after abrupt Y-offset jumps.
  - Camera dead-zone handling now treats idle shooting/firing as action-active (tighter dead-zones than fully idle) so turn/aim response while stationary is less sluggish.
  - Retuned movement/camera response from side-by-side feel capture checks (turn-in-place firing, backward motion, and strafe-turn blends) by adding movement-intent-aware look-ahead and blend-aware dead-zone/catch-up handling.
  - Retuned map-bound camera clamp/release behavior to avoid sticky edge drift: when re-entering open space from clamped bounds, edge-release dead-zone logic now allows immediate inward camera movement.
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
  - Added first-pass player explosive entities for mine/C4 weapons (deploy from player shots, mine arming delay/contact trigger, fuse expiry, and radial detonation damage against enemies/crates/player).
  - Added wall-aware mine/C4 blast gating with lateral ray fan checks so explosive damage is blocked by map walls.
  - Added partial-cover blast weighting (center-ray biased) so mine/C4 damage scales by unobstructed ray coverage instead of binary blocked/unblocked behavior.
  - Refined corner/corridor obstruction behavior by tracing rays from the blast origin with distance-scaled lateral spread and extra side-only leakage damping when center rays are blocked.
  - Tightened explosive ray tracing for corner-edge cases by using finer ray-step sampling and endpoint floor checks, reducing tile-edge grazing leakage.
  - Enemy grenade/projectile splash damage now uses the same wall-aware blast coverage model, including partial versus fully blocked obstruction behavior.
  - Tightened enemy line-of-sight corner-edge handling by using finer LOS trace sampling, preventing wall-graze peek shots.
  - Tightened enemy direct-shot trace sampling to reduce wall-graze pellet leakage in hitscan/non-projectile enemy fire.
  - Tightened player shot trace sampling to reduce wall-graze leakage when resolving hitscan shots against enemies/crates.
  - Tightened enemy projectile sub-step sampling to reduce corner-graze wall leakage in travel-time projectile hits.
  - Tuned enemy firing cadence bookkeeping to follow legacy attack-window behavior: `shoot_count` now advances while enemies stay aligned with a visible target (not only on fire events) and resets when LOS/alignment is lost, improving projectile/explosive burst spread cadence parity.
  - Added post-shot explosive pressure parity: after long-range explosive shots, enemies now keep a short forward-pressure window during reload (legacy-style `walk_cnt` behavior) instead of immediately defaulting to strafe-only repositioning.
  - Added lost-sight chase parity: enemies now start a distance-scaled short chase window after breaking LOS from a previously seen target, preserving last known attack heading before returning to patrol.
  - Added legacy-style front-arc vision gating for enemy detection: enemy LOS now also requires the player to be inside a 180-degree forward vision cone, reducing rear-hemisphere instant aggro.
  - Added legacy-style vision-distance gating for enemy detection: enemy LOS now also respects the original short sight range (~160 px), reducing long-corridor instant aggro from far targets.
  - Retuned enemy LOS ray progression to legacy 5-pixel stepping cadence (with existing endpoint floor checks and vision gating), reducing over-eager wall-graze peek fire from dense modern trace sampling.
  - Added legacy-style patrol idle/burst cadence for no-LOS enemies: patrol now idles until low-probability start rolls, then moves in finite bursts (matching old `walk_cnt` behavior) instead of continuously roaming.
  - Added patrol turn-lock parity while idle: random patrol retarget rolls now apply only once enemies finish rotating to their current target heading, preventing mid-rotation retarget churn.
  - Added additional enemy combat tuning while tracking player: in-range strafe repositioning during reload windows and point-blank explosive self-blast safety gating.
  - Retuned enemy strafe edge behavior so blocked primary strafe lanes now retry the opposite strafe direction in the same tick, reducing reload-phase side-wall stalls.
  - Retuned enemy strafe cadence around reload and sight reacquisition by decoupling strafe-side choice from shoot-counter parity and adding per-enemy reload-phase stagger, reducing synchronized side-switch jitter in multi-enemy rooms.
  - Added scripted runtime parity checks for mine/C4 timing boundaries: mine arm-transition trigger timing and C4 remote-trigger detonation timing now validated at `N-1`, `N`, and `N+1` frame windows.
  - Added scripted runtime multi-contact explosive micro-cases in tight lanes: simultaneous enemy-edge mine contact, chained mine detonations across sequential placements, and nearest-contact mine trigger ordering.
  - Added richer explosive parity for enemy projectiles: blast impacts now apply wall-aware splash damage against nearby crates (not only direct crate collisions).
  - Added crate-aware enemy cover/impact handling: enemy LOS checks now treat live crates as blockers, and non-projectile enemy hitscan traces impact/damage crates instead of piercing through them.
  - Refined mine parity with configurable proximity trigger radius and wall-aware line-of-sight gating for trigger checks.
  - Retuned mine proximity-trigger contact geometry so trigger checks use nearest enemy collision-bounds points (not only enemy centers), improving edge-contact trigger parity.
  - Added crate-aware mine proximity trigger gating so live crates can block enemy contact-trigger LOS checks (matching wall obstruction behavior).
  - Added C4 activator follow-up behavior in gameplay flow: firing the C4 slot while a C4 charge is already active now remote-triggers existing charges instead of placing another charge.
  - Retuned C4 activator economy flow so remote-trigger follow-up shots refund the consumed C4 ammo unit when reusing already-placed charges (no extra ammo burn for trigger-only shots).
  - Retuned enemy explosive splash-to-player edge handling with collision-bounds fallback: if player-center splash miss occurs but the collision box edge is inside blast radius, apply scaled edge-contact splash damage instead of full center miss.
  - Retuned enemy explosive splash cover handling so live crates can now attenuate/block splash rays when they sit between blast impacts and the player during enemy missed-shot and projectile wall/expiry splash cases.
  - Retuned player mine/C4 blast obstruction micro-cases so live crates can attenuate/block splash ray coverage against nearby enemies/player in tight corridor lanes while preserving direct crate damage resolution for the target crate itself.
  - Retuned mine contact-trigger corner behavior so very-near partially covered enemies can still trigger armed mines (coverage- and distance-gated), while farther partial corner contacts remain blocked.
  - Retuned shop/HUD visual treatment with state-aware shop cell styling (owned/full/no-cash tinting + corner state markers), active-row emphasis and state-colored selection status text, plus color-tuned HUD health/ammo/reload readouts.
  - Refined blast obstruction edge-cases with extra narrow-lane damping when only a highly dominant side ray path is open.
  - Added kind-specific player explosive falloff tuning (C4 versus mine) for closer legacy-like detonation feel.
  - Added additional scripted-obstruction parity hooks for mine/C4 micro-cases (diagonal graze and one-tile choke variants).
  - Added first-pass crate entity spawning from level crate metadata (explicit positions or deterministic count-based placement).
  - Added destructible crate hitboxes and hit-flash effect ticks for player shots and enemy projectile collisions.
  - Added first-pass player crate collection + rewards (weapon unlock crates, bullet-pack crates, and energy restore crates).
  - Added shield-aware health capacity parity for player energy flow: shield levels now raise effective max health (`+10` per level), energy crates heal up to that effective cap, and shield sell-down clamps current health to the new cap.
  - Added first-pass player ammo economy for non-fist weapons: ammo-gated firing, one-round consumption per shot, and empty-weapon fallback to fist.
  - Bullet crate rewards now apply to player ammo pools with legacy-like per-type caps.
  - Added ammo snapshot helpers for runtime telemetry: current-weapon ammo (type/index, units, cap) and full per-type ammo pools/capacities.
  - Enemy hit flash and alive/dead state bookkeeping.
  - First-pass enemy behavior loop with line-of-sight aiming, 9-degree rotate steps, movement/collision, and reload-gated enemy shooting.
  - Enemy-to-player shot resolution and player damage/health tracking for bi-directional combat.
  - Enemy firing now stops once the player is dead.
  - Enemy projectile damage/hit telemetry now also gates on player-alive state, so in-flight projectiles no longer add post-death damage/hit totals.
- Gameplay integration in `python/src/ultimatetk/systems/gameplay_scene.py`:
  - Event handling now updates held input actions.
  - Player state is updated each simulation tick from held actions.
  - Camera follows the player and aiming direction.
  - Runtime metadata now includes player position, angle, weapon slot, reload/fire state, shots fired, cash, shield level, target-system flag, hits, enemy counters, and crate counters.
  - Runtime metadata now also includes current-weapon ammo snapshot fields plus full per-type ammo pool/capacity snapshots for HUD/shop parity scaffolding.
  - Added first-pass in-game shop mode toggled via input action, with row/column selection movement and buy/sell transaction handling wired into shop helpers.
  - Added deterministic per-level sell-price table generation hook on gameplay scene enter.
  - Runtime metadata now includes shop-active flag, shop selection row/column, and latest transaction outcome fields including blocked-reason text.
  - Added first-pass visual shop overlay panel (selection grid, per-cell short labels + owned/stock counters, selected-item legacy names, buy/sell info, and transaction feedback text with blocked reason) rendered on top of gameplay while shop mode is active.
  - Added first-pass gameplay HUD overlay (weapon/ammo/health status bars, cash/shield/target text, and shop-open control hint) while shop mode is closed.
  - HUD health readout now renders current/effective-capacity values so shield-based health capacity changes are visible during gameplay.
  - Shop overlay cell rendering now includes icon-like pixel glyphs with per-weapon/per-ammo identity (distinct silhouettes for each weapon slot and ammo type) plus highlighted selected-state icon color.
  - Completed shop icon/detail fidelity pass for dense shop grids: refined remaining weapon/ammo silhouettes and enforced fixed-width 2-character label/counter alignment (including zero-padded numeric counters).
  - HUD layout/styling updated with multi-meter bars (health/ammo/reload), denser status readout, and explicit active mine/C4 counters.
  - HUD explosive status polish now includes armed-vs-active mine counts and hot-vs-active C4 counts, with dedicated readiness meters for mine arming and near-fuse C4 state.
  - HUD hint/readout polish now color-codes explosive readiness segments (mine and C4 status values) for faster glance parsing while preserving compact legacy-style text layout.
  - Added explicit HUD warning-transition parity checks for low-HP, low-ammo, unarmed-mine, and hot-C4 state changes by asserting meter/text color transitions at threshold boundaries.
  - HUD/runtime telemetry now exposes active player explosive state (active count plus mine/C4 split and detonation counter).
  - HUD/runtime telemetry now also exposes mine armed-count and C4 hot-count snapshots for explosive readiness visibility.
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
  - Added enemy corner-graze LOS coverage so enemies stop firing through wall-edge peeks.
  - Added enemy shotgun corner-graze coverage so wall-edge obstruction reduces leaked pellet hits.
  - Added player shot corner-graze coverage so wall-edge obstruction blocks leaked hitscan enemy hits.
  - Added enemy projectile corner-graze coverage so wall-edge obstruction blocks leaked travel-time projectile hits.
  - Added enemy shoot-counter cadence coverage for LOS/alignment attack windows and reload-phase accumulation before explosive projectile fire.
  - Added lost-sight chase-window coverage for previously seen versus never-seen enemy LOS states.
  - Added enemy front-vision-arc coverage so rear-hemisphere targets do not trigger direct fire while patrol heading is unchanged.
  - Added enemy vision-distance coverage so far targets beyond the legacy sight range do not trigger direct fire while heading/LOS remain clear.
  - Added enemy LOS trace-step coverage so enemy vision checks use legacy 5-pixel progression cadence.
  - Added enemy patrol idle/burst cadence coverage so no-LOS enemies stay idle without start rolls and begin finite movement bursts on start rolls.
  - Added patrol turn-lock coverage so idle retarget rolls wait for heading alignment and preserve in-progress turns.
  - Added mine proximity-trigger LOS coverage plus enemy projectile wall-impact crate-splash coverage.
- Added integration test:
  - `python/tests/integration/test_headless_input_script_runtime.py`
  - Added scripted shield shop + energy-crate flow coverage, including buy-heal-to-shield-cap and sell-back clamp-to-base-cap assertions.
  - Added scripted enemy explosive post-shot pressure coverage by comparing pressured versus near-disabled pressure-trigger runs.
  - Added scripted enemy lost-sight chase coverage for prior-contact versus no-prior-contact LOS break behavior.
  - Added scripted enemy front-vision-arc coverage for rear-target non-detection.
  - Added scripted enemy vision-distance coverage for far-target non-detection.
  - Added scripted enemy LOS trace-step coverage by recording runtime LOS calls and verifying legacy step usage.
  - Added scripted enemy patrol idle-vs-burst coverage by forcing patrol rolls to idle-only and burst-start variants.
  - Added scripted patrol turn-lock coverage by forcing retarget/start rolls during an in-progress idle turn and verifying target heading stability.
  - Added scripted mine/C4 runtime telemetry integration coverage (pre-seeded loadout + `--input-script` weapon/shoot sequence).
  - Added scripted C4 corner-obstruction scenario asserting open-lane crate destruction versus blocked-corner survival.
  - Added scripted C4 side-wall leakage scenario asserting damped partial crate damage for side-only obstruction and zero damage for fully blocked lanes.
  - Added scripted C4 micro-obstruction scenarios for diagonal-corner damping and one-tile choke blocking behavior.
  - Added scripted mine corridor obstruction scenario (enemy-triggered mine detonation with open-lane versus blocked-lane crate/enemy outcomes).
  - Added scripted mine micro-obstruction scenarios for diagonal and one-tile choke variants.
  - Added scripted enemy grenade obstruction scenario asserting partial-damage lane behavior versus fully blocked lane behavior.
  - Added scripted enemy LOS corner-graze scenario asserting open-lane enemy fire versus blocked wall-edge no-fire behavior.
  - Added scripted enemy direct-shot corner-graze scenario asserting open-lane hits versus blocked wall-graze no-fire behavior under legacy LOS cadence.
  - Added scripted player-shot corner-graze scenario asserting open-lane hits/kills versus blocked wall-graze no-hit behavior.
  - Added scripted enemy projectile corner-graze scenario asserting open-lane hits versus blocked wall-graze no-hit behavior.
  - Added scripted blocked-lane enemy strafe fallback scenario asserting same-tick opposite-lane retry when primary strafe movement is blocked.
  - Added scripted projectile-expiry crate-cover scenario asserting reduced expiry splash damage with live crate cover versus open-lane expiry damage.
  - Added scripted multi-enemy strafe cadence scenario asserting staggered reload-side switch timing across nearby enemies (no synchronized switch tick).
  - Added scripted mine/C4 boundary-window timing assertions covering mine arm-trigger and C4 remote-trigger transitions at `N-1`, `N`, and `N+1` frames.
  - Added scripted mine multi-contact micro-cases for simultaneous edge contacts, chained detonations across two mine placements, and nearest-contact trigger ordering.
  - Added enemy grenade splash obstruction unit coverage for partial and fully blocked wall configurations.
  - Added enemy crate-cover LOS and enemy-hitscan-into-crate unit coverage.
  - Added mine proximity-trigger crate-obstruction unit coverage.
  - Added mine proximity-trigger edge-contact coverage for enemy collision-bounds trigger checks.
  - Added projectile splash edge-contact coverage for player collision-bounds fallback handling.
  - Added enemy explosive crate-cover splash unit coverage for direct near-miss and projectile wall-impact cases.
  - Added enemy strafe blocked-lane opposite-retry unit coverage and projectile-expiry splash crate-cover unit coverage.
  - Added enemy strafe cadence unit coverage for shoot-counter-independent side stability and per-enemy staggered switch timing.
  - Added mine multi-contact nearest-order unit coverage so mine trigger checks prioritize nearest valid enemy contact when multiple contacts overlap.
  - Added player C4/mine tight-corridor crate-cover splash unit coverage.
  - Added mine trigger partial-corner near-versus-far unit coverage.
  - Added camera action-active idle dead-zone unit coverage (shoot-hold/fire-animation versus fully idle behavior).
  - Added camera feel-capture unit coverage for turn-in-place firing catch-up cadence, backward-motion look-ahead damping, and strafe-turn blend dead-zone tightening.
  - Added camera edge-release unit coverage for right/bottom map-bound clamp exit behavior (no sticky dead-zone hold when target re-enters open space).
  - Added scene-flow coverage for shop cell state classification and state-driven color mapping.
  - Added scene-flow coverage for full shop icon bitmap catalog/distinctness and fixed-width 2-character shop cell label/counter alignment.
  - Added scene-flow HUD warning-transition coverage asserting color-state transitions for low HP, low ammo, unarmed-vs-armed mines, and cool-vs-hot C4 indicators.
  - Added C4 remote-trigger ammo-conservation scene-flow coverage.
  - Added enemy-projectile dead-player guard unit coverage so in-flight projectiles no longer count/player-damage after death.
  - Added scene-flow coverage for C4 remote-trigger behavior and new explosive readiness runtime counters.

Finalized and locked (do not retune further unless a regression appears):

- Mine proximity trigger nearest-collision-bounds contact math plus HUD explosive-readiness hint color-coding.
- Movement/camera/combat micro-parity bundle: diagonal per-axis collision wall-slide behavior, vertical half-screen camera snap threshold, and scaled player-edge splash fallback.
- C4 remote-trigger ammo conservation (refund on trigger-only follow-up) plus dead-player projectile hit/damage telemetry gating.

Remaining work for Phase 4:

- None. Phase 4 input/control parity checklist is complete.

Next phase planning:

- See `python/docs/notes/phase5_combat_entities.md` for active combat/entity closeout workstreams.
