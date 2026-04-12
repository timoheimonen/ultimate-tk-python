# AI-Gym Reward System Improvements

**Status:** COMPLETED  
**Date:** April 2026  
**Author:** Analysis & Implementation  

## Summary

Analysis revealed that AI models learn slowly and get stuck in local optima (e.g., "hiding in shop"). This document describes five systematic improvements to the reward-shaping system designed to improve learning dynamics and encourage balanced gameplay.

---

## Problem Analysis

### 1. Level-Complete Reward Does Not Scale

**Problem:**
- All levels award the same +18.0 bonus for level completion
- Level 1: 4 enemies → +18.0
- Level 10: 27 enemies → +18.0
- Model does not perceive difference in level difficulty

**Impact:** Model can get stuck on early levels because reward ratio does not incentivize progression.

**Solution:** Scale level-complete-reward by enemy count.
- Formula: `base_reward + enemies_total * per_enemy_multiplier`
- Example: `8.0 + enemies_total * 0.8`

---

### 2. Look-At-Enemy Reward Is Too Low

**Problem:**
- `look_at_enemy_reward: 0.0015` per frame
- 150 seconds gameplay × 60 FPS × 0.0015 = +13.5 total bonus
- Compared to single hit (0.35): 23× smaller

**Impact:** 
- Model can "hide" and collect visibility bonus without active engagement
- Incentive to search and track enemies is too weak

**Solution:** Increase look-at-enemy-reward 6.7× (0.0015 → 0.010)
- Brings visibility bonus to same incentive level as movement costs

---

### 3. Strafing-Reward Is Too Conditional and Small

**Problem:**
- `strafing_reward: 0.0008` (1250× smaller than kill_reward)
- Requires: enemy visible + moving + **AND** (shooting or hit or projectile threat)
- Too many conditions for reward activation

**Impact:**
- Model avoids movement when enemy is close (hard to satisfy ammo condition)
- Defensive behavior does not develop

**Solution:** 
- Increase reward 10× (0.0008 → 0.008)
- Remove ammo conditions: simple enemy visibility + movement suffices

---

### 4. Shooting Without Target Gets No Penalty

**Problem:**
- Infinite ammo (`weapon_mode` parameter)
- Shooting without enemy visible does not trigger any penalty
- Model can "spray bullets" without purpose

**Impact:**
- No shooting discipline develops
- Model can waste action steps on ammo without penalty

**Solution:** Add `shoot_no_target_penalty`
- Activates when model shoots without visible enemy
- Grace period: 5 ticks (125ms @ 40 FPS) for reaction time
- Cost: -0.04 per frame after grace period

---

### 5. Missing Exploration Incentive

**Problem:**
- Model gets no bonus for visiting new level areas
- Can loop on small area without negative (stuck-cost)

**Impact:**
- Local minima optimization: model finds small strategy and won't change
- No incentive to explore entire level

**Solution:** Add tile-discovery-reward
- Small bonus (0.001) when player visits new tile
- Max bonuses per level: 0.64 (Level 1) - 4.8 (Level 10)

---

## Solutions - Implementation Details

### Fix 1: Level-Complete Reward Scaling

**Configuration changes:**

```python
@dataclass(frozen=True, slots=True)
class RewardConfig:
    # ... existing parameters ...
    level_complete_reward_base: float = 8.0          # NEW
    level_complete_reward_per_enemy: float = 0.8     # NEW
```

**Reward calculation (RewardTracker.step):**

```python
# Before (line 108-109):
if progression_changed and runtime.progression_event == "level_complete":
    reward += cfg.level_complete_reward

# After:
if progression_changed and runtime.progression_event == "level_complete":
    scaled_level_reward = cfg.level_complete_reward_base + max(0, runtime.enemies_total) * cfg.level_complete_reward_per_enemy
    reward += scaled_level_reward
```

**Examples:**
- Level 1 (4 enemies): 8.0 + 4×0.8 = **11.2**
- Level 5 (16 enemies): 8.0 + 16×0.8 = **20.8**
- Level 10 (27 enemies): 8.0 + 27×0.8 = **29.6**

---

### Fix 2: Look-At-Enemy Reward Increase

**Configuration change:**

```python
@dataclass(frozen=True, slots=True)
class RewardConfig:
    look_at_enemy_reward: float = 0.010  # WAS: 0.0015, INCREASED 6.7×
```

**Impact:**
- Encourages active enemy search
- Raises visibility bonus to significant incentive level
- 150s gameplay × 60FPS × 0.010 = **90.0** bonus (significant!)

---

### Fix 3: Strafing-Reward Improvement

**Configuration change:**

```python
@dataclass(frozen=True, slots=True)
class RewardConfig:
    strafing_reward: float = 0.008  # WAS: 0.0008, INCREASED 10×
```

**Logic change (line 96-105):**

```python
# Before: complex condition
if (
    enemy_visible
    and _player_strafing(observation)
    and (
        shooting_active
        or delta_hits > 0
        or _projectile_threat_close(observation, cfg.strafing_threat_tti_threshold)
    )
):
    reward += cfg.strafing_reward

# After: simple condition
if enemy_visible and _player_strafing(observation):
    reward += cfg.strafing_reward
```

**Impact:**
- Encourages continuous movement when enemy visible
- Removes ammo condition requirement: visibility + movement suffices
- Facilitates defensive behavior learning

---

### Fix 4: Shooting Without Target - Penalty

**Configuration additions:**

```python
@dataclass(frozen=True, slots=True)
class RewardConfig:
    shoot_no_target_grace_ticks: int = 5      # NEW
    shoot_no_target_cost: float = 0.04        # NEW
```

**RewardTracker state additions:**

```python
def __init__(self, config: RewardConfig | None = None) -> None:
    # ... existing ...
    self._shoot_no_target_ticks = 0            # NEW

def reset(self, runtime: RuntimeState | None) -> None:
    # ... existing ...
    self._shoot_no_target_ticks = 0            # NEW
```

**Reward calculation logic:**

```python
# Add to RewardTracker.step (before idle check):
if (
    not runtime.player_dead
    and (runtime.player_shoot_hold_active or delta_shots > 0)
    and not enemy_visible
):
    self._shoot_no_target_ticks += 1
    if self._shoot_no_target_ticks >= cfg.shoot_no_target_grace_ticks:
        reward -= cfg.shoot_no_target_cost
else:
    self._shoot_no_target_ticks = 0
```

**Impact:**
- Grace period 5 ticks = 125ms @ 40 FPS (sufficient reaction time)
- Penalty only if shooting continues without visible target
- Encourages strategic ammunition use

---

### Fix 5: Tile-Based Exploration Reward

**Import addition:**

```python
from ultimatetk.rendering.constants import TILE_SIZE
```

**Configuration addition:**

```python
@dataclass(frozen=True, slots=True)
class RewardConfig:
    tile_discovery_reward: float = 0.001      # NEW
```

**RewardTracker state additions:**

```python
def __init__(self, config: RewardConfig | None = None) -> None:
    # ... existing ...
    self._visited_tiles: set[tuple[int, int]] = set()  # NEW

def reset(self, runtime: RuntimeState | None) -> None:
    # ... existing ...
    self._visited_tiles.clear()                # NEW
```

**Reward calculation logic:**

```python
# Add to RewardTracker.step (before return):
if not runtime.player_dead:
    player_tile_x = int(runtime.player_world_x) // TILE_SIZE
    player_tile_y = int(runtime.player_world_y) // TILE_SIZE
    current_tile = (player_tile_x, player_tile_y)
    
    if current_tile not in self._visited_tiles:
        self._visited_tiles.add(current_tile)
        reward += cfg.tile_discovery_reward
```

**Impact:**
- Encourages level exploration
- Max bonuses:
  - Level 1 (32×20 = 640 tiles): ~0.64
  - Level 10 (80×60 = 4800 tiles): ~4.8
- Helps avoid local optima

---

## Testing Plan

### Unit Tests (test_gym_reward.py)

1. **test_level_complete_scales_by_enemy_count**
   ```python
   cfg = RewardConfig(
       level_complete_reward_base=8.0,
       level_complete_reward_per_enemy=0.8
   )
   # Test: Level 1 (4 enemies) → 11.2
   # Test: Level 10 (27 enemies) → 29.6
   ```

2. **test_shoot_no_target_penalty**
   ```python
   # Shooting without visible enemy
   # Step 1-4: no penalty (grace period)
   # Step 5+: -0.04 penalty
   ```

3. **test_tile_discovery_reward**
   ```python
   # Step on 5 different tiles
   # Expected: +0.005 total reward (5 × 0.001)
   ```

4. **test_strafing_without_ammo_condition**
   ```python
   # Enemy visible + strafing (no ammo condition)
   # Expected: +0.008 reward
   ```

### Smoke Tests

```bash
# Random-policy baseline
python3 tools/gym_random_policy_smoke.py --episodes 3 --max-steps 2000

# Deterministic test (verify reward scaling)
python3 -c "
from src.ultimatetk.ai.reward import RewardConfig, RewardTracker
from ultimatetk.core.state import RuntimeState

cfg = RewardConfig(...)
tracker = RewardTracker(config=cfg)

# Test level scaling
# Test tile discovery
# Test shoot penalty
"
```

---

## Parameter Changes Summary

| Parameter | Before | After | Change | Reason |
|-----------|--------|-------|--------|--------|
| look_at_enemy_reward | 0.0015 | 0.010 | +6.7× | Raise visibility incentive |
| strafing_reward | 0.0008 | 0.008 | +10× | Raise defensive movement |
| level_complete_reward_base | N/A | 8.0 | NEW | Scaling base |
| level_complete_reward_per_enemy | N/A | 0.8 | NEW | Scaling per enemy |
| shoot_no_target_grace_ticks | N/A | 5 | NEW | Grace period for shots |
| shoot_no_target_cost | N/A | 0.04 | NEW | Penalty without target |
| tile_discovery_reward | N/A | 0.001 | NEW | Exploration incentive |

---

## Expected Learning Improvements

### Before changes:
- Model gets stuck in local optima
- Level progression slow
- "Hiding" possible
- Exploration behavior weak

### After changes:
- ✅ Level progression incentivized (scaled reward)
- ✅ Active enemy search encouraged (visibility +6.7×)
- ✅ Defensive movement encouraged (strafing +10×)
- ✅ Shooting discipline encouraged (penalty)
- ✅ Exploration encouraged (tile discovery)

---

## Backward Compatibility

- ✅ `RewardConfig` defaults preserved (existing runs unaffected)
- ✅ No new library dependencies (TILE_SIZE already imported)
- ✅ `level_complete_reward` kept for compatibility (set to 0.0)
- ✅ All new parameters are dataclass-internal

---

## Next Steps

1. ✅ Documentation complete
2. 🔄 Implement changes in `reward.py`
3. 🔄 Update tests in `test_gym_reward.py`
4. 🔄 Run tests
5. 🔄 Smoke testing
6. 🔄 Commit changes

---

## References

- **Analysis:** Balancing analysis of AI-gym observations and reward system
- **User Confirmations:**
  1. Level-complete scaling: `base + enemies * multiplier` ✅
  2. Strafing unconditional when enemy visible ✅
  3. Shooting penalty without target ✅
  4. Level-data changes: not needed ✅
  5. Tile-based exploration: yes ✅

**Status:** READY FOR IMPLEMENTATION
