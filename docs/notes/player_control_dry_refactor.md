# Player Control DRY Refactor Plan

## Scope
- Target file: `src/ultimatetk/systems/player_control.py`
- Goal: reduce repeated table/index/shop/collision/camera code while preserving behavior.

## Phases
- [x] Phase 1 - Safe helper extraction for table lookups and index guards.
- [ ] Phase 2 - Shop transaction dedupe (shared event + row resolvers).
- [ ] Phase 3 - Movement/camera axis dedupe with unchanged constants and feel.
- [ ] Phase 4 - Cleanup and full verification sweep.

## Verification Log
- Phase 1:
  - `pytest tests/unit/test_player_control.py -q`
  - `pytest tests/unit/test_scene_flow.py -q`
