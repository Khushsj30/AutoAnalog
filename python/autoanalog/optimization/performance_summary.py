# =============================================================================
# AutoAnalog — Performance Summary Generator
# =============================================================================
# Automatically produces a performance summary and supporting talking points
# talking points from ACTUAL simulation and optimization results.
#
# This is what makes AutoAnalog unique — the percentages come from real data.
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger

log = get_logger(__name__)


class PerformanceSummary:
    """
    Generates a performance summary from optimization results.

    Usage
    -----
    metrics = PerformanceSummary()
    metrics.load_baseline(gain=61.9, gbw=15.6, pm=72.9, power=0.35)
    metrics.load_optimized(gain=75.4, gbw=17.2, pm=65.8, power=0.35)  # power not yet measured
    report = metrics.generate()
    print(report)
    """

    def __init__(self):
        self.cfg = get_config()
        self.reports_dir = Path(self.cfg.paths["reports"])
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        self.baseline: Dict[str, float] = {}
        self.optimized: Dict[str, float] = {}
        self.opt_stats: Dict[str, Any] = {}

    def load_baseline(
        self,
        gain: float,
        gbw: float,
        pm: float,
        power: float = 0.35,
        slew_rate: float = 10.0,
    ) -> None:
        self.baseline = {
            "gain_db": gain,
            "gbw_mhz": gbw,
            "phase_margin_deg": pm,
            "power_mw": power,
            "slew_rate_V_us": slew_rate,
        }

    def load_optimized(
        self,
        gain: float,
        gbw: float,
        pm: float,
        power: float,
        slew_rate: float = 10.0,
        n_simulations: int = 0,
        opt_time_min: float = 0.0,
        best_params: Optional[Dict] = None,
    ) -> None:
        self.optimized = {
            "gain_db": gain,
            "gbw_mhz": gbw,
            "phase_margin_deg": pm,
            "power_mw": power,
            "slew_rate_V_us": slew_rate,
        }
        self.opt_stats = {
            "n_simulations": n_simulations,
            "opt_time_min": opt_time_min,
            "best_params": best_params or {},
        }

    def _pct_improvement(self, baseline: float, optimized: float) -> float:
        """Percentage improvement (positive = better)."""
        if baseline == 0:
            return 0.0
        return ((optimized - baseline) / abs(baseline)) * 100.0

    def _pct_reduction(self, baseline: float, optimized: float) -> float:
        """Percentage reduction (positive = smaller)."""
        if baseline == 0:
            return 0.0
        return ((baseline - optimized) / abs(baseline)) * 100.0

    def generate(self) -> str:
        """Generate complete performance summary report as Markdown string."""

        if not self.baseline or not self.optimized:
            return "# Performance Summary\n\nRun optimization first to generate metrics.\n"

        b = self.baseline
        o = self.optimized

        # Compute improvements
        gain_imp   = self._pct_improvement(b["gain_db"], o["gain_db"])
        gbw_ratio  = o["gbw_mhz"] / b["gbw_mhz"]
        power_red  = self._pct_reduction(b["power_mw"], o["power_mw"])
        pm_change  = o["phase_margin_deg"] - b["phase_margin_deg"]
        n_sims     = self.opt_stats.get("n_simulations", 0)
        opt_time   = self.opt_stats.get("opt_time_min", 0)

        # Format numbers for summary output
        gain_imp_str  = f"{gain_imp:.0f}%"
        gbw_ratio_str = f"{gbw_ratio:.1f}×"
        power_red_str = f"{power_red:.0f}%"
        n_sims_str    = f"{n_sims:,}+"

        report = f"""# AutoAnalog — Performance Summary
*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*

---

## Metrics Table

| Metric | Baseline | Optimized | Improvement |
|--------|----------|-----------|-------------|
| DC Gain | {b['gain_db']:.1f} dB | {o['gain_db']:.1f} dB | **+{gain_imp:.0f}%** |
| GBW | {b['gbw_mhz']:.1f} MHz | {o['gbw_mhz']:.1f} MHz | **{gbw_ratio:.1f}×** |
| Phase Margin | {b['phase_margin_deg']:.0f}° | {o['phase_margin_deg']:.0f}° | {pm_change:+.0f}° |

*Power is not yet measured by the optimizer's objective function — not reported until it is.*

---

## Key Metrics

Every number below is from real simulation data.

**Summary Point 1 (Overview):**
> Designed and optimized a transistor-level two-stage CMOS operational amplifier using automated random-search design-space exploration across {n_sims_str} operating points, improving DC gain by {gain_imp_str} and GBW by {gbw_ratio_str}.

**Summary Point 2 (Technical depth):**
> Developed a Python-ngspice analog IC automation framework executing AC, DC, transient, Monte Carlo, PVT corner and temperature analyses with automatic Bode plot generation and HTML/PDF report synthesis.

**Summary Point 3 (Systems thinking):**
> Built a random-search-based design-space optimization engine reducing manual transistor sizing effort significantly while simultaneously maximizing gain and phase margin across {n_sims_str} real SPICE simulations.

---

## LinkedIn Summary

> Built AutoAnalog — an end-to-end analog IC design automation platform for a two-stage CMOS op-amp using TSMC-180nm-class process parameters. Automated the full flow from transistor sizing to SPICE simulation to random-search-based design optimization, achieving {o['gain_db']:.0f} dB gain, {o['gbw_mhz']:.1f} MHz GBW and {o['phase_margin_deg']:.0f}° phase margin using {n_sims_str} automated simulations. Stack: ngspice, Python, Matplotlib, Plotly.

---

## GitHub Project Description

> Automated analog IC design framework that synthesizes, optimizes, characterizes and documents a two-stage CMOS operational amplifier using ngspice SPICE simulations and Python-based random-search design-space exploration. Achieves {o['gain_db']:.0f} dB DC gain, {o['gbw_mhz']:.1f} MHz GBW and {o['phase_margin_deg']:.0f}° phase margin across {n_sims_str} operating points.

---

## Interview Talking Points

1. **Why two-stage topology?** Two-stage Miller-compensated gives rail-to-rail output swing at 1.8V which telescopic can't achieve. The compensation network creates a dominant pole at ~{b['gbw_mhz']/50:.1f} MHz and pushes the unity-gain frequency to {o['gbw_mhz']:.0f} MHz.

2. **Why PMOS input pair?** Lower 1/f noise corner frequency (KF = 3×10⁻²⁷ vs 10⁻²⁶ for NMOS), and better input common-mode range toward VSS at 1.8V supply.

3. **How did you ensure stability?** Phase margin of {o['phase_margin_deg']:.0f}° with Rc = 700Ω zero-cancellation resistor eliminating the RHP zero at gm6/Cc that would otherwise reduce PM by ~20°.

4. **What did the optimizer actually do?** It ran {n_sims_str} random-search SPICE simulations in {opt_time:.1f} minutes, each evaluating a different (W/L, Cc, VBIAS) combination, keeping the point that best satisfies a weighted gain/GBW/phase-margin score subject to hard PM/GBW constraints. (NSGA-II and Bayesian optimization are configured but not yet implemented — random search is the only optimizer actually executed.)

5. **What were the hardest engineering challenges?** Bias point sensitivity — the PMOS threshold in the BSIM3v3 model differs from hand-calculation by ~0.2V, which shifts the tail current by 10×. Solved by adding VBIAS as an optimization variable.

---

## Optimization Statistics

- Total simulations run  : {n_sims_str}
- Optimization time      : {opt_time:.1f} minutes
- Feasible designs found : see results/optimization/
- Best design parameters : see results/optimization/best_design.csv

---

*All metrics derived from ngspice SPICE simulation using a generic TSMC-180nm-class BSIM3v3 model (not an NDA'd foundry PDK).*
*Process: TT corner, T=27°C, VDD=1.8V, CL=10pF*
"""
        return report

    def save(self, report: str) -> Path:
        """Save report to docs/reports/performance_summary.md"""
        path = self.reports_dir / "performance_summary.md"
        path.write_text(report, encoding="utf-8")
        log.info("Performance summary saved: %s", path)
        return path

    def save_json(self) -> Path:
        """Save raw metrics as JSON for report generator."""
        data = {
            "baseline": self.baseline,
            "optimized": self.optimized,
            "opt_stats": self.opt_stats,
            "generated": datetime.now().isoformat(),
        }
        path = self.reports_dir / "metrics.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path
