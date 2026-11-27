# -*- coding: utf-8 -*-
"""In-process GPU energy measurement (PLAN v1.6 §6.9 decision).

Usage
-----
    with GpuEnergyMeter(device_index=0, stage='train') as m:
        train(...)
    rec = m.result()      # dict ready for L2/resource_usage

Strategy: (1) NVML total-energy counter (nvmlDeviceGetTotalEnergyConsumption, mJ) read at enter/exit;
(2) fallback: 1 Hz power sampling (nvmlDeviceGetPowerUsage, mW) integrated over wall time;
(3) if pynvml is missing or NVML fails: energy fields are None with null_reason TELEMETRY_UNAVAILABLE
and energy_measurement_type = 'UNAVAILABLE'. The measurement boundary is always GPU_ONLY.
CO2e is only derived when a sourced carbon intensity is supplied (co2e_from_energy).
"""
from __future__ import annotations

import threading
import time
from typing import Dict, Optional

try:  # optional dependency
    import pynvml  # type: ignore
except Exception:  # pragma: no cover
    pynvml = None


class GpuEnergyMeter:
    def __init__(self, device_index: int = 0, stage: str = 'run', sample_hz: float = 1.0, force_sampling: bool = False):
        self.device_index = device_index
        self.stage = stage
        self.sample_hz = sample_hz
        self.force_sampling = force_sampling
        self._handle = None
        self._method: Optional[str] = None
        self._e0_mj: Optional[int] = None
        self._samples = []           # (t, watts)
        self._missed = 0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._t0 = None
        self._t1 = None
        self._gpu_name = None
        self._error: Optional[str] = None
        self._energy_kwh: Optional[float] = None

    # ----- lifecycle -----
    def __enter__(self):
        self._t0 = time.time()
        if pynvml is None:
            self._error = 'pynvml_not_installed'
            return self
        try:
            pynvml.nvmlInit()
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(self.device_index)
            name = pynvml.nvmlDeviceGetName(self._handle)
            self._gpu_name = name.decode() if isinstance(name, bytes) else str(name)
        except Exception as e:  # pragma: no cover
            self._error = f'nvml_init_failed:{e}'
            return self
        if not self.force_sampling:
            try:
                self._e0_mj = int(pynvml.nvmlDeviceGetTotalEnergyConsumption(self._handle))
                self._method = 'NVML_ENERGY_COUNTER'
                return self
            except Exception:
                self._e0_mj = None
        self._method = 'NVML_POWER_INTEGRATION'
        self._thread = threading.Thread(target=self._sampler, daemon=True)
        self._thread.start()
        return self

    def _sampler(self):
        period = 1.0 / self.sample_hz
        while not self._stop.is_set():
            try:
                mw = pynvml.nvmlDeviceGetPowerUsage(self._handle)
                self._samples.append((time.time(), mw / 1000.0))
            except Exception:
                self._missed += 1
            self._stop.wait(period)

    def __exit__(self, exc_type, exc, tb):
        self._t1 = time.time()
        if self._method == 'NVML_ENERGY_COUNTER':
            try:
                e1 = int(pynvml.nvmlDeviceGetTotalEnergyConsumption(self._handle))
                self._energy_kwh = (e1 - self._e0_mj) / 3.6e9
            except Exception as e:  # pragma: no cover
                self._error = f'nvml_counter_read_failed:{e}'
        elif self._method == 'NVML_POWER_INTEGRATION':
            self._stop.set()
            if self._thread is not None:
                self._thread.join(timeout=5)
            self._energy_kwh = self._integrate()
        if pynvml is not None and self._handle is not None:
            try:
                pynvml.nvmlShutdown()
            except Exception:  # pragma: no cover
                pass
        return False

    def _integrate(self) -> Optional[float]:
        if len(self._samples) < 2:
            return None
        e_j = 0.0
        for (t0, w0), (t1, w1) in zip(self._samples[:-1], self._samples[1:]):
            e_j += 0.5 * (w0 + w1) * (t1 - t0)          # trapezoid, joules
        return e_j / 3.6e6

    # ----- output -----
    def result(self) -> Dict[str, object]:
        dur = (self._t1 or time.time()) - (self._t0 or time.time())
        ok = self._energy_kwh is not None
        n_expected = max(1, int(dur * self.sample_hz)) if self._method == 'NVML_POWER_INTEGRATION' else 1
        missing_rate = (self._missed / (self._missed + len(self._samples))) if self._method == 'NVML_POWER_INTEGRATION' and (self._missed + len(self._samples)) else 0.0
        return {
            'stage': self.stage,
            f'energy_gpu_{self.stage}_kwh': self._energy_kwh if ok else None,
            'energy_boundary': 'GPU_ONLY',
            'energy_measurement_type': 'MEASURED' if ok else 'UNAVAILABLE',
            'energy_method': self._method if ok else None,
            'telemetry_missing_rate': float(missing_rate) if ok else 1.0,
            'null_reason': None if ok else 'TELEMETRY_UNAVAILABLE',
            'telemetry_error': self._error,
            'gpu_name': self._gpu_name,
            'duration_s': dur,
            'n_power_samples': len(self._samples),
            'n_samples_expected': n_expected,
        }


def co2e_from_energy(energy_kwh: Optional[float], carbon_intensity_g_per_kwh: Optional[float],
                     ci_source_version: Optional[str]) -> Dict[str, object]:
    """CO2e only when a sourced carbon intensity is given (PLAN §6.9); otherwise NULL with reason."""
    if energy_kwh is None:
        return {'co2e_gpu_run_g': None, 'null_reason': 'TELEMETRY_UNAVAILABLE'}
    if carbon_intensity_g_per_kwh is None or not ci_source_version:
        return {'co2e_gpu_run_g': None, 'null_reason': 'NOT_COMPUTED', 'note': 'no sourced carbon intensity'}
    return {'co2e_gpu_run_g': energy_kwh * carbon_intensity_g_per_kwh, 'carbon_intensity_g_per_kwh': carbon_intensity_g_per_kwh,
            'ci_source_version': ci_source_version, 'null_reason': None}


def cost_basis_for_group(rows) -> str:
    """rec_rule cost basis: ENERGY only when every candidate in the rec_group is MEASURED, else TIME."""
    measured = all(r.get('energy_measurement_type') == 'MEASURED' and r.get('energy_gpu_run_kwh') is not None for r in rows)
    return 'ENERGY' if measured else 'TIME'
