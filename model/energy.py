"""GPU-only NVML energy metering with an explicit unavailable fallback."""
from __future__ import annotations

from typing import Any


class GpuEnergyMeter:
    """Measure a whole model run from NVML's total-energy counter when present.

    Modal may not expose NVML.  That is a valid outcome: all energy/cost
    fields remain null and the reason is persisted rather than estimated.
    """
    def __init__(self) -> None:
        self.handle = None; self.start_mj = None; self.error = None; self.gpu_name = None
        self._pynvml = None

    def __enter__(self):
        try:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            self._pynvml = pynvml
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(self.handle)
            self.gpu_name = name.decode() if isinstance(name, bytes) else str(name)
            self.start_mj = int(pynvml.nvmlDeviceGetTotalEnergyConsumption(self.handle))
        except Exception as exc:  # telemetry cannot be assumed in hosted GPUs
            self.error = f"TELEMETRY_UNAVAILABLE:{type(exc).__name__}"
        return self

    def __exit__(self, *_: Any) -> bool:
        return False

    def result(self) -> dict:
        try:
            if self._pynvml is None or self.handle is None or self.start_mj is None:
                raise RuntimeError(self.error or "NVML_UNAVAILABLE")
            end_mj = int(self._pynvml.nvmlDeviceGetTotalEnergyConsumption(self.handle))
            return {"energy_gpu_run_kwh": (end_mj - self.start_mj) / 3.6e9,
                    "energy_boundary": "GPU_ONLY", "energy_measurement_type": "NVML_ENERGY_COUNTER",
                    "telemetry_missing_rate": 0.0, "energy_null_reason": None,
                    "nvml_gpu_name": self.gpu_name}
        except Exception as exc:
            return {"energy_gpu_run_kwh": None, "energy_boundary": "GPU_ONLY",
                    "energy_measurement_type": "UNAVAILABLE", "telemetry_missing_rate": 1.0,
                    "energy_null_reason": self.error or f"TELEMETRY_UNAVAILABLE:{type(exc).__name__}",
                    "nvml_gpu_name": self.gpu_name}
