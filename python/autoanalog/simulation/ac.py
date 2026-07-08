# =============================================================================
# AutoAnalog — AC Analysis Module
# =============================================================================
# High-level interface for running AC simulations.
# This is what the optimizer calls thousands of times.
#
# Usage:
#   from autoanalog.simulation.ac import ACAnalysis
#   sim = ACAnalysis()
#   result = sim.run(params={"M1_W": 20e-6, "Cc": 3e-12})
#   print(result.dc_gain_db, result.gbw_hz, result.phase_margin_deg)
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Dict, Any, Optional

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger, SimulationLogger
from autoanalog.simulation.netlist_generator import NetlistGenerator
from autoanalog.simulation.runner import NgspiceRunner
from autoanalog.simulation.parser import ACParser
from autoanalog.simulation.results import ACResult

log = get_logger(__name__)


class ACAnalysis:
    """
    Runs AC (Bode plot) analysis on the two-stage CMOS op-amp.

    This is the core simulation call used by:
      - The optimization engine (called thousands of times)
      - The characterization suite (called once per analysis)
      - The CLI (called by simulate.sh)

    Parameters
    ----------
    save_results : bool
        Whether to save CSV and raw output to results/ac_sweep/

    Example
    -------
    >>> sim = ACAnalysis()
    >>> result = sim.run()
    >>> print(f"Gain: {result.dc_gain_db:.1f} dB")
    >>> print(f"GBW:  {result.gbw_hz/1e6:.1f} MHz")
    >>> print(f"PM:   {result.phase_margin_deg:.1f}°")
    """

    def __init__(self, save_results: bool = True):
        self.cfg = get_config()
        self.save_results = save_results
        self.generator = NetlistGenerator()
        self.runner = NgspiceRunner()
        self.parser = ACParser()
        self.results_dir = Path(self.cfg.paths["results"]) / "ac_sweep"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        params: Optional[Dict[str, Any]] = None,
        run_id: Optional[int] = None,
    ) -> ACResult:
        """
        Run a complete AC analysis and return structured results.

        Parameters
        ----------
        params : dict, optional
            Design parameters. If None, uses defaults from config.
        run_id : int, optional
            Run identifier for logging (used by optimizer)

        Returns
        -------
        ACResult
        """
        with SimulationLogger("ac", run_id) as sim_log:

            # 1. Generate netlist
            sim_log.debug("Generating AC netlist...")
            netlist_path = self.generator.generate_ac(params=params)
            sim_log.debug("Netlist: %s", netlist_path)

            # 2. Run ngspice
            t_start = time.perf_counter()
            ng_output = self.runner.run(netlist_path)
            elapsed = time.perf_counter() - t_start

            # 3. Check for simulation failure
            if not ng_output.success:
                sim_log.error(
                    "ngspice failed: %s", ng_output.error_message
                )
                result = ACResult(
                    converged=False,
                    error_message=ng_output.error_message,
                    sim_time_seconds=elapsed,
                    netlist_file=str(netlist_path),
                    design_params=params or {},
                )
                return result

            # 4. Parse output
            sim_log.debug("Parsing output (%d chars)...", len(ng_output.stdout))
            result = self.parser.parse(ng_output.stdout, sim_time=elapsed)
            result.netlist_file = str(netlist_path)
            result.design_params = params or {}

            # 5. Log key results
            if result.converged:
                sim_log.info(
                    "Gain=%.1f dB | GBW=%.2f MHz | PM=%.1f° | t=%.2fs",
                    result.dc_gain_db or 0,
                    (result.gbw_hz or 0) / 1e6,
                    result.phase_margin_deg or 0,
                    elapsed,
                )

                # 6. Check specs
                specs = dict(self.cfg.specifications)
                if result.met_specs(specs):
                    sim_log.info("✅ All AC specs MET")
                else:
                    sim_log.warning("⚠️  Some AC specs NOT met")
                    self._log_spec_gaps(result, specs, sim_log)
            else:
                sim_log.error("AC analysis did not converge")

            # 7. Save results
            if self.save_results and result.converged:
                self._save(result, run_id)

            return result

    def run_baseline(self) -> ACResult:
        """
        Run AC analysis with the verified baseline parameters.
        Uses VBIAS=0.57V and sizing from Chat 2 debug session.
        """
        baseline_params = {
            "M1_W": 20e-6, "M1_L": 1e-6,
            "M3_W": 4e-6,  "M3_L": 1e-6,
            "M5_W": 8e-6,  "M5_L": 1e-6,
            "M6_W": 40e-6, "M6_L": 500e-9,
            "M7_W": 40e-6, "M7_L": 1e-6,
            "M8_W": 4e-6,  "M8_L": 1e-6,
            "Cc": 3e-12,
            "Rc": 700.0,
            "VBIAS": 0.57,
        }
        log.info("Running baseline AC analysis...")
        return self.run(params=baseline_params, run_id=0)

    def _log_spec_gaps(self, result: ACResult, specs: dict, sim_log) -> None:
        """Log which specs are not met and by how much."""
        if result.dc_gain_db is not None:
            target = float(specs.get("gain_db_min", 80))
            gap = result.dc_gain_db - target
            sim_log.warning("  Gain: %.1f dB (target %.0f, gap %.1f dB)",
                          result.dc_gain_db, target, gap)

        if result.gbw_hz is not None:
            target = float(specs.get("gbw_min_hz", 10e6))
            ratio = result.gbw_hz / target
            sim_log.warning("  GBW: %.2f MHz (target %.0f MHz, ratio %.2f×)",
                          result.gbw_hz/1e6, target/1e6, ratio)

        if result.phase_margin_deg is not None:
            target = float(specs.get("phase_margin_min_deg", 60))
            gap = result.phase_margin_deg - target
            sim_log.warning("  PM: %.1f° (target %.0f°, margin %.1f°)",
                          result.phase_margin_deg, target, gap)

    def _save(self, result: ACResult, run_id: Optional[int]) -> None:
        """Save raw data and CSV summary."""
        # CSV row
        csv_path = self.results_dir / "ac_results.csv"
        row = result.to_csv_row()
        write_header = not csv_path.exists()
        with csv_path.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()),
                                   extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(row)

        # Raw frequency/gain/phase data
        if result.frequencies and run_id is not None:
            raw_path = self.results_dir / f"ac_raw_{run_id:04d}.csv"
            with raw_path.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["frequency_hz", "gain_db", "phase_deg"])
                for freq, gdb, ph in zip(
                    result.frequencies, result.gain_db, result.phase_deg
                ):
                    writer.writerow([freq, gdb, ph])

        log.debug("AC results saved to %s", self.results_dir)
