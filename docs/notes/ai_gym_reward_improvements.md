# AI-Gym Reward System Improvements

**Status:** COMPLETED (with April 2026 follow-up rebalance)  
**Date:** April 2026  
**Author:** Analysis & Implementation

## Current State (Authoritative)

This section is source of truth for active default reward shaping in `src/ultimatetk/ai/reward.py`.

### Active default parameters

| Parameter | Current default | Notes |
|---|---:|---|
| `step_cost` | `0.001` | Small per-step pressure to act with purpose |
| `kill_reward` | `5.0` | Sparse high-value combat success signal |
| `hit_reward` | `0.5` | Intermediate combat progress signal |
| `crate_reward` | `0.15` | Pickup incentive |
| `damage_cost` | `0.04` | Damage-taking discouragement |
| `death_cost` | `12.0` | Strong terminal failure penalty |
| `level_complete_reward_base` | `8.0` | Completion base bonus |
| `level_complete_reward_per_enemy` | `0.8` | Difficulty scaling by enemy count |
| `run_complete_reward` | `40.0` | Full-run completion reward |
| `look_at_enemy_reward` | `0.003` | Light engagement shaping |
| `strafing_reward` | `0.003` | Light defensive movement shaping |
| `idle_ticks_threshold` | `120` | Idle grace before penalty |
| `idle_cost` | `0.2` | Anti-idle penalty |
| `stationary_shoot_no_hit_grace_ticks` | `4` | Grace before stationary no-hit penalty |
| `stationary_shoot_no_hit_cost` | `0.01` | Discourages stationary blind fire |
| `stuck_ticks_threshold` | `20` | Trapped-area grace before penalty |
| `stuck_cost` | `0.02` | Mild anti-stuck penalty |
| `bad_shoot_ticks_threshold` | `20` | Grace for sustained bad shooting |
| `bad_shoot_cost` | `0.02` | Discourages low-value shooting patterns |
| `shoot_no_target_grace_ticks` | `5` | Grace for no-target shooting |
| `shoot_no_target_cost` | `0.015` | Discourages shooting with no visible target |
| `tile_discovery_reward` | `0.001` | Exploration bonus for newly visited tiles |
| `visible_no_hit_ticks_threshold` | `100` | Grace before visible-no-hit penalty |
| `visible_no_hit_cost` | `0.004` | Discourages passive enemy visibility farming |

### Active reward-logic behavior

- `level_complete` uses scaled reward: `base + enemies_total * per_enemy`.
- `stuck` counter resets when player is not trapped (real movement or shooting), not only on progression/death transitions.
- `stationary_shoot_no_hit` counter resets when stationary-shoot conditions stop being true.
- `shoot_no_target` and `stationary_shoot_no_hit` penalties are active by default (non-zero costs).
- Exploration bonus (`tile_discovery_reward`) applies once per newly visited tile.
- Gym step info now exposes `reward_breakdown` with component-wise reward contributions per step.

## Why Follow-up Rebalance Was Needed

Post-implementation smoke validation showed dense penalties still dominated total return, especially trapped-area behavior. Follow-up rebalance reduced penalty saturation, increased terminal failure cost relative to combat gains, and improved counter-reset behavior to stabilize policy learning.

## Validation Snapshot

- `pytest tests/unit/test_gym_reward.py` -> `15 passed`
- `python3 tools/gym_random_policy_smoke.py --episodes 3 --max-steps 500` -> passed (3 episodes)

## Historical Notes (Superseded)

Original v1 tuning notes in earlier revisions of this document (including values such as `look_at_enemy_reward=0.010`, `strafing_reward=0.008`, `shoot_no_target_cost=0.04`) are historical context only and are not current defaults.

## Next Iteration

Phase 15 tracks reward stabilization and observability follow-up work:

- `docs/notes/phase15_reward_stabilization_observability.md`
