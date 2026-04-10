# Ultimate TK Python Port

This repository hosts the Python refactor at root level.

## Current status
- Phases 1-9 are completed (runtime, formats, rendering, controls/combat, UI/progression, parity tuning, regression suite, and data-colocation hardening).
- Phase 10 is completed:
  - root-level project layout is active (no `python/` wrapper directory),
  - legacy DOS-era payload is archived under `ARCHIVE/`,
  - legacy parity checks are optional (default verification works without legacy root asset folders).
- Phase 11 is completed:
  - optional pygame runtime backend is wired behind `--platform pygame`,
  - gameplay/menu/progression visual frames are available for window presentation,
  - pygame dependency remains optional.
- Phase 12 is completed:
  - Gymnasium training env is available under `ultimatetk.ai`,
  - headless gameplay-first reset starts directly at level 1,
  - shop controls and multi-level progression are wired for AI runs,
  - deterministic replay checks and AI integration coverage are included.
- Phase 13 is in progress:
  - PPO trainer/eval tooling is being added on top of the Gymnasium env,
  - checkpoint + periodic evaluation loops are included,
  - runtime device selection supports `cpu`, `mps`, and `cuda`.

## Run

Run from repository root:

```bash
PYTHONPATH=src python3 -m ultimatetk --max-seconds 2 --autostart-gameplay --status-print-interval 40
```

## Conda setup

Create/update a conda environment and install project requirements:

```bash
./scripts/setup_conda_env.sh
```

Optional custom environment name:

```bash
./scripts/setup_conda_env.sh my-env-name
```

Replay scripted input in headless mode:

```bash
PYTHONPATH=src python3 -m ultimatetk --max-seconds 1.2 --autostart-gameplay --status-print-interval 20 --input-script "5:+MOVE_FORWARD;25:-MOVE_FORWARD;30:+TURN_LEFT;36:-TURN_LEFT"
```

Run with terminal keyboard input (interactive TTY required):

```bash
PYTHONPATH=src python3 -m ultimatetk --platform terminal --autostart-gameplay --status-print-interval 20
```

Run with pygame window backend (optional dependency):

```bash
PYTHONPATH=src python3 -m ultimatetk --platform pygame --autostart-gameplay --window-scale 3
```

Optional scale examples:

- `--window-scale 2` -> `640x400`
- `--window-scale 3` -> `960x600`

Install pygame extras (if needed):

```bash
python3 -m pip install -e ".[pygame]"
```

Install AI/Gymnasium extras (optional):

```bash
python3 -m pip install -e ".[ai]"
```

Install PPO trainer dependencies (optional):

```bash
python3 -m pip install -e ".[ai_train]"
```

Conda-first install for AI training in env `ultimatetk`:

```bash
conda install -y -n ultimatetk -c conda-forge numpy gymnasium pytorch stable-baselines3 tensorboard "setuptools<81"
```

## Gymnasium training env (Phase 12)

Run random-policy smoke check:

```bash
python3 tools/gym_random_policy_smoke.py --episodes 1 --max-steps 300
```

Minimal usage example:

```python
from ultimatetk.ai.gym_env import UltimateTKEnv

env = UltimateTKEnv(max_episode_steps=6000)
obs, info = env.reset(seed=123)
done = False
while not done:
    action = env.action_space.sample()
    obs, reward, terminated, truncated, info = env.step(action)
    done = terminated or truncated
env.close()
```

Training-mode contract:

- Environment starts headless directly in gameplay at level 1.
- Shop controls are enabled for policy actions (`toggle_shop`, buy/sell via gameplay controls).
- Level progression continues through subsequent levels.
- Terminal signals:
  - player death -> `terminated=True`, `info["terminal_reason"] == "death"`
  - run completion -> `terminated=True`, `info["game_completed"] == True`
  - max step cap -> `truncated=True`, `info["terminal_reason"] == "time_limit"`

## PPO trainer loop (Phase 13 slice)

Train PPO with periodic checkpoints and eval:

```bash
python3 tools/ppo_train.py --total-timesteps 200000 --n-envs 1 --device auto
```

Max-throughput training (no scene rendering, no periodic eval/checkpoint callbacks):

```bash
python3 tools/ppo_train.py --total-timesteps 200000 --device auto --eval-freq 0 --checkpoint-freq 0
```

Resume from checkpoint:

```bash
python3 tools/ppo_train.py --total-timesteps 200000 --resume-from runs/ai/ppo/<run>/checkpoints/ppo_model_50000_steps.zip --device auto
```

Evaluate a checkpoint/final model:

```bash
python3 tools/ppo_eval.py --model runs/ai/ppo/<run>/final_model.zip --episodes 5 --deterministic --device auto
```

Device notes:

- Apple Silicon: use `--device auto` for highest throughput (defaults to `cpu`), or `--device mps` if you explicitly want Metal acceleration.
- CUDA hosts: use `--device auto` (prefers `cuda` when available) or `--device cuda`.
- CPU fallback remains available via `--device cpu`.

## Release verification

Default release bundle (no legacy root dependency):

```bash
python3 tools/release_verification.py
```

Optional strict parity against archived legacy sources:

```bash
python3 tools/release_verification.py --legacy-compare-root ARCHIVE
```

Runtime controls (terminal and pygame):
- Main menu: `W/S` or `A/D` selects, `Space`/`Enter`/`Tab` confirms
- Movement/turn: `WASD` or arrow keys
- Strafe: `Q` / `E`
- Shoot: `Space`
- Next weapon: `Tab` (pygame also supports mouse wheel + `PageUp/PageDown`)
- Toggle shop: `R` or `Enter`
- Shop controls (while open): `W/S` rows, `A/D` columns, `Space` buy, `Tab` sell
- Direct weapon slot: `` ` ``, `1..0`, `-` (pygame also supports numpad `0..9` and `F1..F12`)
- Quit: `Esc`
- The terminal backend attempts to apply player1 keybinds from `game_data/options.cfg`; unsupported legacy scan codes fall back to defaults above.

## Data layout

- Runtime assets: `game_data/`
- Archived original payload: `ARCHIVE/`
- Runtime diagnostics: `runs/`
- Phase notes: `docs/notes/`

## Tooling

Regenerate manifest and gap list:

```bash
python3 tools/asset_manifest_report.py
```

Copy legacy assets into `game_data/` from `ARCHIVE/`:

```bash
python3 tools/migrate_legacy_data.py
```

Probe format loaders against migrated data:

```bash
python3 tools/format_probe.py
```

Render a baseline gameplay frame to a screenshot:

```bash
python3 tools/render_probe.py --output runs/screenshots/phase3_render_probe.ppm
```
