from __future__ import annotations

import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ultimatetk.ai.training_device import TorchCapabilities, resolve_torch_device


class TrainingDeviceTests(unittest.TestCase):
    def test_auto_prefers_cuda_then_cpu(self) -> None:
        self.assertEqual(
            resolve_torch_device(
                "auto",
                capabilities=TorchCapabilities(
                    torch_installed=True,
                    cuda_available=True,
                    mps_available=True,
                ),
            ),
            "cuda",
        )
        self.assertEqual(
            resolve_torch_device(
                "auto",
                capabilities=TorchCapabilities(
                    torch_installed=True,
                    cuda_available=False,
                    mps_available=True,
                ),
            ),
            "cpu",
        )
        self.assertEqual(
            resolve_torch_device(
                "auto",
                capabilities=TorchCapabilities(
                    torch_installed=True,
                    cuda_available=False,
                    mps_available=False,
                ),
            ),
            "cpu",
        )

    def test_explicit_cuda_or_mps_requires_backend_availability(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_torch_device(
                "cuda",
                capabilities=TorchCapabilities(
                    torch_installed=True,
                    cuda_available=False,
                    mps_available=True,
                ),
            )

        with self.assertRaises(RuntimeError):
            resolve_torch_device(
                "mps",
                capabilities=TorchCapabilities(
                    torch_installed=True,
                    cuda_available=True,
                    mps_available=False,
                ),
            )

    def test_cpu_always_available_when_torch_installed(self) -> None:
        self.assertEqual(
            resolve_torch_device(
                "cpu",
                capabilities=TorchCapabilities(
                    torch_installed=True,
                    cuda_available=False,
                    mps_available=False,
                ),
            ),
            "cpu",
        )

    def test_torch_missing_raises_runtime_error(self) -> None:
        with self.assertRaises(RuntimeError):
            resolve_torch_device(
                "auto",
                capabilities=TorchCapabilities(
                    torch_installed=False,
                    cuda_available=False,
                    mps_available=False,
                ),
            )

    def test_invalid_token_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            resolve_torch_device(
                "metal",
                capabilities=TorchCapabilities(
                    torch_installed=True,
                    cuda_available=False,
                    mps_available=True,
                ),
            )


if __name__ == "__main__":
    unittest.main()
