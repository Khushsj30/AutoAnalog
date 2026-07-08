# =============================================================================
# AutoAnalog — Simulation Result Dataclasses
# =============================================================================
# Every simulation module returns one of these dataclasses.
# They are the contract between the simulation engine and the optimizer.
#
# Design decisions:
#   - dataclasses for clean attribute access and repr
#   - Optional fields for measurements that may not converge
#   - to_dict() and to_csv_row() for serialization
#   - met_specs() for quick pass/fail check against config targets
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import csv
import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, List


# ---------------------------------------------------------------------------
# Base result
# ---------------------------------------------------------------------------

@dataclass
class SimulationResult:
    """Base class for all simulation results."""

    analysis_type: str          # "ac", "dc", "transient", "op", "noise"
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now().isoformat()
    )
    converged: bool = True
    error_message: Optional[str] = None
    sim_time_seconds: float = 0.0
    netlist_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_csv_row(self) -> Dict[str, Any]:
        """Flat dict suitable for CSV writing."""
        return self.to_dict()

    def is_valid(self) -> bool:
        return self.converged and self.error_message is None


# ---------------------------------------------------------------------------
# AC Analysis Result
# ---------------------------------------------------------------------------

@dataclass
class ACResult(SimulationResult):
    """
    Results from AC sweep analysis.

    All frequency values in Hz, gain in dB, phase in degrees.
    """
    analysis_type: str = "ac"

    # Primary metrics
    dc_gain_db: Optional[float] = None          # gain at 1 Hz
    gbw_hz: Optional[float] = None              # gain-bandwidth product
    phase_margin_deg: Optional[float] = None    # phase margin
    gain_margin_db: Optional[float] = None      # gain margin
    unity_gain_freq_hz: Optional[float] = None  # = gbw_hz for single-pole

    # Pole/zero locations (estimated from slope)
    dominant_pole_hz: Optional[float] = None
    second_pole_hz: Optional[float] = None

    # CMRR / PSRR (filled by separate analyses, stored here for convenience)
    cmrr_db: Optional[float] = None
    psrr_plus_db: Optional[float] = None

    # Raw data arrays (frequency, gain_db, phase_deg)
    frequencies: List[float] = field(default_factory=list)
    gain_db: List[float] = field(default_factory=list)
    phase_deg: List[float] = field(default_factory=list)

    # Design parameters used for this run (for optimizer tracking)
    design_params: Dict[str, float] = field(default_factory=dict)

    def met_specs(self, specs: Dict[str, float]) -> bool:
        """
        Check if this result meets all specifications.

        Parameters
        ----------
        specs : dict with keys like 'gain_db_min', 'gbw_min_hz', etc.
        """
        checks = []
        if self.dc_gain_db is not None and "gain_db_min" in specs:
            checks.append(self.dc_gain_db >= float(specs["gain_db_min"]))
        if self.gbw_hz is not None and "gbw_min_hz" in specs:
            checks.append(self.gbw_hz >= float(specs["gbw_min_hz"]))
        if self.phase_margin_deg is not None and "phase_margin_min_deg" in specs:
            checks.append(self.phase_margin_deg >= float(specs["phase_margin_min_deg"]))
        return all(checks) if checks else False

    def summary(self) -> str:
        lines = [
            f"  AC Analysis Results",
            f"  {'─'*40}",
            f"  DC Gain       : {self.dc_gain_db:.2f} dB" if self.dc_gain_db else "  DC Gain       : N/A",
            f"  GBW           : {self.gbw_hz/1e6:.2f} MHz" if self.gbw_hz else "  GBW           : N/A",
            f"  Phase Margin  : {self.phase_margin_deg:.1f}°" if self.phase_margin_deg else "  Phase Margin  : N/A",
            f"  Gain Margin   : {self.gain_margin_db:.1f} dB" if self.gain_margin_db else "  Gain Margin   : N/A",
            f"  Converged     : {self.converged}",
        ]
        return "\n".join(lines)

    def to_csv_row(self) -> Dict[str, Any]:
        """Flat dict for CSV — excludes raw arrays."""
        return {
            "timestamp": self.timestamp,
            "analysis_type": self.analysis_type,
            "dc_gain_db": self.dc_gain_db,
            "gbw_hz": self.gbw_hz,
            "phase_margin_deg": self.phase_margin_deg,
            "gain_margin_db": self.gain_margin_db,
            "dominant_pole_hz": self.dominant_pole_hz,
            "second_pole_hz": self.second_pole_hz,
            "converged": self.converged,
            "sim_time_seconds": self.sim_time_seconds,
            **{f"param_{k}": v for k, v in self.design_params.items()},
        }


# ---------------------------------------------------------------------------
# Operating Point Result
# ---------------------------------------------------------------------------

@dataclass
class OPResult(SimulationResult):
    """Results from .OP analysis — DC bias conditions."""
    analysis_type: str = "op"

    # Node voltages
    v_vdd: Optional[float] = None
    v_vtail: Optional[float] = None
    v_vout1: Optional[float] = None
    v_vd1: Optional[float] = None
    v_vbias: Optional[float] = None
    v_out: Optional[float] = None

    # Branch currents
    i_vdd_ua: Optional[float] = None       # total supply current in µA
    i_tail_ua: Optional[float] = None      # tail current in µA
    i_diff_pair_ua: Optional[float] = None # each diff pair transistor in µA
    i_second_stage_ua: Optional[float] = None

    # Power
    power_mw: Optional[float] = None

    # Transconductances (µA/V)
    gm1_uA_V: Optional[float] = None
    gm6_uA_V: Optional[float] = None

    design_params: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"  Operating Point",
            f"  {'─'*40}",
            f"  VTAIL  : {self.v_vtail:.3f} V" if self.v_vtail else "  VTAIL  : N/A",
            f"  VOUT1  : {self.v_vout1:.3f} V" if self.v_vout1 else "  VOUT1  : N/A",
            f"  VOUT   : {self.v_out:.3f} V" if self.v_out else "  VOUT   : N/A",
            f"  Itail  : {self.i_tail_ua:.1f} µA" if self.i_tail_ua else "  Itail  : N/A",
            f"  Power  : {self.power_mw:.3f} mW" if self.power_mw else "  Power  : N/A",
            f"  gm1    : {self.gm1_uA_V:.1f} µA/V" if self.gm1_uA_V else "  gm1    : N/A",
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Transient Result
# ---------------------------------------------------------------------------

@dataclass
class TransientResult(SimulationResult):
    """Results from transient analysis — slew rate and settling."""
    analysis_type: str = "transient"

    slew_rate_pos_V_us: Optional[float] = None   # positive SR in V/µs
    slew_rate_neg_V_us: Optional[float] = None   # negative SR in V/µs
    settling_time_1pct_ns: Optional[float] = None
    settling_time_01pct_ns: Optional[float] = None
    overshoot_pct: Optional[float] = None

    times: List[float] = field(default_factory=list)
    voltages_out: List[float] = field(default_factory=list)
    voltages_in: List[float] = field(default_factory=list)

    design_params: Dict[str, float] = field(default_factory=dict)

    def met_specs(self, specs: Dict[str, float]) -> bool:
        checks = []
        if self.slew_rate_pos_V_us and "slew_rate_min" in specs:
            sr_min_V_us = specs["slew_rate_min"] / 1e6
            checks.append(self.slew_rate_pos_V_us >= sr_min_V_us)
        return all(checks) if checks else False


# ---------------------------------------------------------------------------
# Noise Result
# ---------------------------------------------------------------------------

@dataclass
class NoiseResult(SimulationResult):
    """Results from noise analysis."""
    analysis_type: str = "noise"

    # Input-referred noise at key frequencies (V/√Hz)
    noise_1hz_V_rtHz: Optional[float] = None
    noise_1khz_V_rtHz: Optional[float] = None
    noise_10khz_V_rtHz: Optional[float] = None
    noise_1mhz_V_rtHz: Optional[float] = None

    # Flicker noise corner frequency
    flicker_corner_hz: Optional[float] = None

    # Integrated noise over bandwidth
    integrated_noise_V: Optional[float] = None

    frequencies: List[float] = field(default_factory=list)
    input_noise: List[float] = field(default_factory=list)

    design_params: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Full simulation suite result
# ---------------------------------------------------------------------------

@dataclass
class FullSimResult:
    """
    Container for all analyses run on a single design point.
    This is what the optimizer receives and scores.
    """
    design_params: Dict[str, float] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.datetime.now().isoformat()
    )

    ac: Optional[ACResult] = None
    op: Optional[OPResult] = None
    transient: Optional[TransientResult] = None
    noise: Optional[NoiseResult] = None

    # Computed score (set by optimizer)
    score: Optional[float] = None
    pareto_rank: Optional[int] = None

    def is_valid(self) -> bool:
        """True if all run analyses converged."""
        results = [r for r in [self.ac, self.op, self.transient, self.noise]
                   if r is not None]
        return all(r.is_valid() for r in results)

    def summary(self) -> str:
        lines = ["=" * 50, "  Full Simulation Result", "=" * 50]
        if self.ac:
            lines.append(self.ac.summary())
        if self.op:
            lines.append(self.op.summary())
        if self.transient:
            lines.append(f"  SR+: {self.transient.slew_rate_pos_V_us} V/µs")
        if self.score is not None:
            lines.append(f"  Score: {self.score:.4f}")
        return "\n".join(lines)

    def to_csv_row(self) -> Dict[str, Any]:
        row = {"timestamp": self.timestamp, "score": self.score}
        row.update({f"param_{k}": v for k, v in self.design_params.items()})
        if self.ac:
            row.update({
                "dc_gain_db": self.ac.dc_gain_db,
                "gbw_hz": self.ac.gbw_hz,
                "phase_margin_deg": self.ac.phase_margin_deg,
            })
        if self.op:
            row.update({
                "power_mw": self.op.power_mw,
                "i_tail_ua": self.op.i_tail_ua,
            })
        if self.transient:
            row.update({
                "slew_rate_pos": self.transient.slew_rate_pos_V_us,
            })
        return row


def save_results_csv(results: List[FullSimResult], filepath: Path) -> None:
    """Save a list of FullSimResult to CSV for later analysis."""
    if not results:
        return
    rows = [r.to_csv_row() for r in results]
    fieldnames = list(rows[0].keys())
    with filepath.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
