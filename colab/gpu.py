from __future__ import annotations

from typing import Any


def gpu_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "device": "cpu",
        "gpu_name": None,
        "vram_total_gb": None,
        "vram_free_gb": None,
        "cuda_available": False,
    }
    try:
        import torch
    except Exception:
        return info

    info["cuda_available"] = bool(torch.cuda.is_available())
    if not info["cuda_available"]:
        return info
    info["device"] = "cuda"
    try:
        info["gpu_name"] = torch.cuda.get_device_name(0)
        free, total = torch.cuda.mem_get_info(0)
        info["vram_total_gb"] = round(total / (1024**3), 2)
        info["vram_free_gb"] = round(free / (1024**3), 2)
    except Exception:
        pass
    return info
