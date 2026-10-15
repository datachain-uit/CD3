"""GPU-only NVML energy metering with explicit, provenance-safe fallbacks."""
from __future__ import annotations

import threading
import time
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


class GpuPowerSampler:
    """Estimate GPU-only run energy by integrating NVML power samples.

    This is deliberately separate from :class:`GpuEnergyMeter`: a hardware
    total-energy counter is a measurement, whereas sampled power is an
    estimate.  Hosted GPUs often expose the latter but not the former.  The
    sampler never affects training and always degrades to explicit missing
    telemetry when NVML is unavailable.
    """

    def __init__(self, *, interval_seconds: float = 1.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.interval_seconds = float(interval_seconds)
        self._pynvml = None
        self.handle = None
        self.gpu_name = None
        self.error = None
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._previous: tuple[float, float] | None = None
        self._energy_joules = 0.0
        self.sample_attempt_count = 0
        self.sample_count = 0
        self.failed_sample_count = 0
        self.started_monotonic: float | None = None
        self.finished_monotonic: float | None = None

    def _sample_once(self) -> None:
        self.sample_attempt_count += 1
        try:
            if self._pynvml is None or self.handle is None:
                raise RuntimeError(self.error or "NVML_UNAVAILABLE")
            now = time.monotonic()
            # NVML exposes milliwatts.  Keep the integration in joules.
            watts = float(self._pynvml.nvmlDeviceGetPowerUsage(self.handle)) / 1000.0
            if self._previous is not None:
                previous_time, previous_watts = self._previous
                self._energy_joules += (now - previous_time) * (previous_watts + watts) / 2.0
            self._previous = (now, watts)
            self.sample_count += 1
        except Exception as exc:  # telemetry is optional on rented GPU hosts
            self.failed_sample_count += 1
            self.error = self.error or f"TELEMETRY_UNAVAILABLE:{type(exc).__name__}"

    def _run(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            self._sample_once()

    def start(self) -> "GpuPowerSampler":
        self.started_monotonic = time.monotonic()
        try:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            self._pynvml = pynvml
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(self.handle)
            self.gpu_name = name.decode() if isinstance(name, bytes) else str(name)
            self._sample_once()
            self._thread = threading.Thread(target=self._run, name="gpu-power-sampler", daemon=True)
            self._thread.start()
        except Exception as exc:
            self.error = f"TELEMETRY_UNAVAILABLE:{type(exc).__name__}"
            self.failed_sample_count += 1
            self.sample_attempt_count += 1
        return self

    def stop(self) -> dict:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.interval_seconds * 2.0))
        # The final sample closes the integration interval at run completion.
        if self._pynvml is not None and self.handle is not None:
            self._sample_once()
        self.finished_monotonic = time.monotonic()
        duration = ((self.finished_monotonic - self.started_monotonic)
                    if self.started_monotonic is not None else None)
        missing_rate = (self.failed_sample_count / self.sample_attempt_count
                        if self.sample_attempt_count else 1.0)
        base = {
            "energy_boundary": "GPU_ONLY",
            "energy_sampling_interval_seconds": self.interval_seconds,
            "energy_sample_count": self.sample_count,
            "energy_sample_attempt_count": self.sample_attempt_count,
            "energy_missing_sample_rate": missing_rate,
            "energy_sampling_duration_s": duration,
            "nvml_gpu_name": self.gpu_name,
        }
        if self.sample_count >= 2:
            return {
                **base,
                "energy_measurement": "ESTIMATED",
                "energy_measurement_type": "NVML_POWER_SAMPLING_ESTIMATE",
                "energy_gpu_estimated_kwh": self._energy_joules / 3_600_000.0,
                "energy_gpu_run_kwh": None,
                "energy_null_reason": None,
            }
        return {
            **base,
            "energy_measurement": "NOT_MEASURED",
            "energy_measurement_type": "UNAVAILABLE",
            "energy_gpu_estimated_kwh": None,
            "energy_gpu_run_kwh": None,
            "energy_null_reason": self.error or "INSUFFICIENT_POWER_SAMPLES",
        }
