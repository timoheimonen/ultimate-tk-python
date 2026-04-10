from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.assets.repository import _resolve_case_insensitive


class AssetRepositoryPathIsolationTests(unittest.TestCase):
    def test_resolve_case_insensitive_matches_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "efps"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "cool.efp").write_bytes(b"dummy")

            path = _resolve_case_insensitive(data_dir, "COOL.EFP")
            self.assertTrue(path.is_file())
            self.assertTrue(path.samefile(data_dir / "cool.efp"))

    def test_resolve_case_insensitive_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "efps"
            data_dir.mkdir(parents=True, exist_ok=True)

            outside_dir = root / "outside"
            outside_dir.mkdir(parents=True, exist_ok=True)
            outside_file = outside_dir / "COOL.EFP"
            outside_file.write_bytes(b"dummy")

            symlink_path = data_dir / "COOL.EFP"
            symlink_path.symlink_to(outside_file)

            with self.assertRaises(FileNotFoundError):
                _resolve_case_insensitive(data_dir, "COOL.EFP")


if __name__ == "__main__":
    unittest.main()
