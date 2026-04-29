# AI-Gym Reward System

**Status:** ACTIVE (April 2026 face-engagement redesign)  
**Date:** April 2026

## Current State (Authoritative)

The reward model is split into three tiers: **progression**, **engagement**, and **anti-passivity**.

### Engagement rewards (dense, per-tick)

`face_enemy_reward` and `aim_center_reward` fire when **any** visible enemy occupies a front sector (0/1/31). `alignment` is based on the nearest visible enemy's sector, regardless of front/center status. All four values are computed in a single `_enemy_target_signal()` call.

| Parameter | Default | Trigger |
|---|---:|---|
| `face_enemy_reward` | `0.004` | Enemy in front sector (0, 1, or 31) — one tick |
| `aim_center_reward` | `0.002` | Enemy in exact center (sector 0) — one tick, additive |
| `alignment_improvement_reward` | `0.015` | Player turns *toward* nearest enemy (delta scored, not farmable) |
| `valid_shot_reward` | `0.025` | Shot fired while enemy is in front sector |

### Exploration rewards

| Parameter | Default | Trigger |
|---|---:|---|
| `tile_discovery_reward` | `0.03` | Tile not visited this episode |
| `frontier_tile_reward` | `0.04` | Tile further from spawn than any previous (Chebyshev radius) |

### Progression rewards

| Parameter | Default | Trigger |
|---|---:|---|
| `step_cost` | `0.0015` | Every tick (light time pressure) |
| `kill_reward` | `6.0` | Per enemy killed |
| `hit_reward` | `0.4` | Per projectile hit on enemy |
| `damage_dealt_reward` | `0.04` | Per point of damage dealt |
| `crate_reward` | `0.12` | Per crate collected |
| `damage_cost` | `0.05` | Per point of damage taken |
| `death_cost` | `15.0` | Terminal failure |
| `level_complete_reward_base` | `10.0` | Level completion |
| `level_complete_reward_per_enemy` | `1.0` | Scaled by enemy headcount |
| `run_complete_reward` | `30.0` | Full-run victory |

### Anti-passivity penalties

| Parameter | Default | Trigger |
|---|---:|---|
| `inactivity_ticks_threshold` | `60` | Grace before inactivity penalty |
| `inactivity_cost` | `0.015` | No new tile AND no combat progress (hits/kills/damage/valid-shot) |
| `enemy_los_penalty_ticks` | `80` | Grace while enemy visible in front |
| `enemy_los_penalty_cost` | `0.008` | Enemy in front but no hits for too long |
| `stuck_ticks_threshold` | `20` | Movement < 2px per tick |
| `stuck_cost` | `0.02` | Penalty per tick beyond stuck threshold |

### Shooting discipline

| Parameter | Default | Trigger |
|---|---:|---|
| `stationary_shoot_no_hit_grace_ticks` | `5` | Grace for stationary shooting |
| `stationary_shoot_no_hit_cost` | `0.015` | Stationary shooting without hits |
| `shoot_no_target_grace_ticks` | `5` | Grace for blind shooting |
| `shoot_no_target_cost` | `0.02` | Shooting with no front-sector enemy |

### How "front" is determined

`_enemy_target_signal()` inspects ray channel 1 (enemy) across all 32 sectors. Returns `(front, centered, alignment, any_visible)`:
- `front` / `centered`: true if **any** visible enemy is in sector 0, 1, or 31 (front) / sector 0 (centered). Not limited to nearest.
- `alignment`: 1.0 - (circular_sector_offset / 16) of the **nearest** visible enemy, clamped ≥ 0.
- `any_visible`: false when no enemy is visible at all; used to reset the alignment baseline so re-sightings are not rewarded.

### Inactivity / exploration reset conditions

`_inactivity_ticks` resets to 0 when ANY of these occur:
- New tile discovered
- Hit, kill, or damage dealt (combat progress)
- Valid shot (shot fired + enemy in front sector)

This replaces the old idle penalty, which only suppressed while shooting — the new version also resets on exploration, so moving into new territory is explicitly encouraged.

### What was removed

| Old parameter | Replacement |
|---|---:|
| `look_at_enemy_reward` | `face_enemy_reward` + `aim_center_reward` (front-only, not 360°) |
| `strafing_reward` | Removed; replaced by valid-shot and face engagement signals |
| `idle_cost` / `idle_ticks_threshold` | `inactivity_cost` / `inactivity_ticks_threshold` (resets on exploration too) |
| `bad_shoot_cost` | Covered by `shoot_no_target_cost` + `stationary_shoot_no_hit_cost` |
| `visible_no_hit_cost` | `enemy_los_penalty_cost` (front-only, shorter grace) |

### Gym environment

- `info["reward_breakdown"]` exposes all breakdown keys.
- `info["inactivity_ticks"]` replaced the old `stationary_ticks`.

## Validation

- `pytest tests/unit/test_gym_reward.py` → `43 passed`
- `pytest tests/unit/test_gym_env.py tests/unit/test_gym_reward.py` → `54 passed`
- `python3 tools/gym_random_policy_smoke.py --episodes 3 --max-steps 500` → passed
