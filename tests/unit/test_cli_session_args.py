from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.__main__ import _parse_args


class CliSessionArgsTests(unittest.TestCase):
    def test_parse_load_session_flag(self) -> None:
        args = _parse_args(["--load-session"])
        self.assertTrue(args.load_session)
        self.assertFalse(args.new_session)

    def test_parse_new_session_and_no_save_flags(self) -> None:
        args = _parse_args(["--new-session", "--no-save-session"])
        self.assertTrue(args.new_session)
        self.assertFalse(args.load_session)
        self.assertTrue(args.no_save_session)

    def test_parse_rejects_conflicting_session_mode_flags(self) -> None:
        with self.assertRaises(SystemExit):
            _parse_args(["--load-session", "--new-session"])


if __name__ == "__main__":
    unittest.main()
