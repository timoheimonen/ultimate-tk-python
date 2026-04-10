## Enemy AI improvement plan

### Current behavior baseline

- Enemies run a small state machine: see player -> engage, lost sight -> short chase, otherwise patrol.
- Detection requires line-of-sight, front vision cone, and vision distance.
- Some short-range enemies can stall in a narrow no-fire/no-move gap.

### Phase 1 (implemented)

- Remove short-range dead-zone in engage movement distance selection.
- Add movement fallback: if forward push is blocked, try a strafe direction and opposite strafe.
- Keep existing attack cadence and weapon balance untouched.

### Phase 2 (implemented, tuned conservative)

- Add explicit "investigate last seen player position" state after line-of-sight break.
- Add lightweight anti-clump separation force so multiple enemies do not body-block each other.
- Tune investigate behavior to avoid over-aggressive pressure (`investigate_ticks=45`, `investigate_speed_scale=0.75`).
- Keep per-type vision/range tuning as a separate follow-up.

### Phase 3 (optional)

- Add tile-based path probes for long chases around walls.
- Add limited flanking behavior for ranged enemies in open areas.

### Test strategy

- Unit: short-range enemy closes distance inside previous dead-zone band.
- Unit: blocked forward move triggers strafe fallback attempt.
- Unit: enemy investigates last-seen position after LOS break and chase window.
- Unit: nearby enemies apply separation angle adjustment while solo enemies keep baseline angle.
- Regression: keep full combat unit suite green.
