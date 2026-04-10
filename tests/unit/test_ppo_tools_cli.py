from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PPOToolsCliTests(unittest.TestCase):
    def test_ppo_train_help(self) -> None:
        result = subprocess.run(
            (sys.executable, "tools/ppo_train.py", "--help"),
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Train PPO policy", result.stdout)

    def test_ppo_eval_help(self) -> None:
        result = subprocess.run(
            (sys.executable, "tools/ppo_eval.py", "--help"),
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("Evaluate PPO checkpoint", result.stdout)


if __name__ == "__main__":
    unittest.main()
