from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TorchCapabilities:
    torch_installed: bool
    cuda_available: bool
    mps_available: bool


def detect_torch_capabilities() -> TorchCapabilities:
    try:
        import torch
    except ModuleNotFoundError:
        return TorchCapabilities(
            torch_installed=False,
            cuda_available=False,
            mps_available=False,
        )

    cuda_available = bool(torch.cuda.is_available())
    mps_available = False
    backends = getattr(torch, "backends", None)
    if backends is not None and hasattr(backends, "mps"):
        mps_backend = backends.mps
        is_built = getattr(mps_backend, "is_built", lambda: False)
        is_available = getattr(mps_backend, "is_available", lambda: False)
        mps_available = bool(is_built() and is_available())

    return TorchCapabilities(
        torch_installed=True,
        cuda_available=cuda_available,
        mps_available=mps_available,
    )


def resolve_torch_device(
    requested: str,
    *,
    capabilities: TorchCapabilities | None = None,
) -> str:
    token = requested.strip().lower()
    if token not in {"auto", "cpu", "mps", "cuda"}:
        raise ValueError("device must be one of: auto, cpu, mps, cuda")

    caps = capabilities or detect_torch_capabilities()
    if not caps.torch_installed:
        raise RuntimeError(
            "PyTorch is not installed. Install with conda, for example: "
            "conda install -n ultimatetk -c conda-forge pytorch",
        )

    if token == "cpu":
        return "cpu"
    if token == "cuda":
        if caps.cuda_available:
            return "cuda"
        raise RuntimeError("CUDA requested but not available in this environment")
    if token == "mps":
        if caps.mps_available:
            return "mps"
        raise RuntimeError("MPS requested but not available in this environment")

    if caps.cuda_available:
        return "cuda"
    return "cpu"
