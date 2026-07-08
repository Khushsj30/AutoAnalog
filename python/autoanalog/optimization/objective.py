# =============================================================================
# AutoAnalog — Objective Function
# =============================================================================
# Defines how to score a design point for optimization.
# This is the bridge between the optimizer and the simulator.
#
# Design decisions:
#   - Hard constraints: PM ≥ 60°, GBW ≥ 10 MHz (infeasible = large penalty)
#   - Soft objectives: maximize gain, minimize power
#   - Weighted scalarization for single-objective search
#   - Returns raw metrics for Pareto (multi-objective) search
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import math
from typing import Dict, Any, Tuple, Optional

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger
from autoanalog.simulation.ac import ACAnalysis
from autoanalog.simulation.results import ACResult

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Penalty constants
# ---------------------------------------------------------------------------
INFEASIBLE_PENALTY = 1e6    # returned when hard constraints are violated
CONVERGENCE_PENALTY = 1e7   # returned when simulation fails to converge


class ObjectiveFunction:
    """
    Evaluates a design parameter vector and returns a scalar score.

    Lower score = better design (minimization convention).

    Hard constraints (violation → INFEASIBLE_PENALTY):
        - Phase margin ≥ 60°
        - GBW ≥ 10 MHz

    Soft objectives (weighted sum):
        - Maximize gain (weight 0.50)
        - Maximize GBW  (weight 0.25)
        - Minimize power (weight 0.25)

    Parameters
    ----------
    sim : ACAnalysis, optional
        Simulation engine instance. Created if not provided.
    """

    def __init__(self, sim: Optional[ACAnalysis] = None):
        self.cfg = get_config()
        self.specs = self.cfg.specifications
        self.sim = sim or ACAnalysis(save_results=False)

        # Targets (used for normalisation)
        self.gain_target  = float(self.specs.get("gain_db_min", 80.0))
        self.gbw_target   = float(self.specs.get("gbw_min_hz", 10e6))
        self.pm_target    = float(self.specs.get("phase_margin_min_deg", 60.0))
        self.power_target = float(self.specs.get("power_max_w", 1e-3)) * 1e3  # mW

        self.eval_count = 0

    def __call__(self, params: Dict[str, Any]) -> float:
        """Evaluate design and return scalar score (lower = better)."""
        return self.evaluate(params)[0]

    def evaluate(
        self, params: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Optional[float]]]:
        """
        Run simulation and compute score.

        Returns
        -------
        score : float
            Scalar score (lower = better). INFEASIBLE_PENALTY if constraints violated.
        metrics : dict
            Raw simulation metrics for logging and Pareto analysis.
        """
        self.eval_count += 1

        # Run AC simulation
        result: ACResult = self.sim.run(params=params, run_id=self.eval_count)

        # Handle convergence failure
        if not result.converged or result.dc_gain_db is None:
            log.debug("Run %d: convergence failure", self.eval_count)
            return CONVERGENCE_PENALTY, self._empty_metrics()

        gain = result.dc_gain_db
        gbw  = result.gbw_hz or 0.0
        pm   = result.phase_margin_deg or 0.0

        metrics = {
            "gain_db":        gain,
            "gbw_mhz":        gbw / 1e6,
            "phase_margin":   pm,
            "dc_gain_db":     gain,
            "gbw_hz":         gbw,
        }

        # --- Hard constraint check ---
        if pm < self.pm_target:
            penalty = INFEASIBLE_PENALTY + (self.pm_target - pm) * 1000
            log.debug("Run %d: PM=%.1f° < %.0f° → infeasible", self.eval_count, pm, self.pm_target)
            return penalty, metrics

        if gbw < self.gbw_target * 0.5:   # allow 50% tolerance for optimizer exploration
            penalty = INFEASIBLE_PENALTY + (self.gbw_target - gbw) * 0.001
            log.debug("Run %d: GBW=%.1f MHz too low → infeasible", self.eval_count, gbw/1e6)
            return penalty, metrics

        # --- Soft objective: weighted sum (minimise) ---
        # Normalise each objective to ~[0, 1] range
        # gain: higher is better → negate and normalise
        gain_score  = max(0, (self.gain_target - gain) / self.gain_target)

        # GBW: higher is better → negate normalised excess (reward overshooting)
        gbw_score   = max(0, (self.gbw_target - gbw) / self.gbw_target)

        # PM: bonus for exceeding target (more stable = better)
        pm_score    = max(0, (self.pm_target - pm) / self.pm_target)

        # Weighted sum
        score = (
            0.60 * gain_score +
            0.25 * gbw_score  +
            0.15 * pm_score
        )

        log.debug(
            "Run %d: Gain=%.1fdB GBW=%.1fMHz PM=%.1f° → score=%.4f",
            self.eval_count, gain, gbw/1e6, pm, score
        )

        return score, metrics

    def evaluate_multi(
        self, params: Dict[str, Any]
    ) -> Tuple[float, float, Dict[str, Optional[float]]]:
        """
        Multi-objective evaluation for NSGA-II.

        Returns
        -------
        obj1 : float  — negative gain (minimise → maximise gain)
        obj2 : float  — negative GBW  (minimise → maximise GBW)
        metrics : dict
        """
        score, metrics = self.evaluate(params)

        if score >= INFEASIBLE_PENALTY:
            return INFEASIBLE_PENALTY, INFEASIBLE_PENALTY, metrics

        obj1 = -(metrics.get("gain_db", 0))    # maximise gain
        obj2 = -(metrics.get("gbw_mhz", 0))    # maximise GBW

        return obj1, obj2, metrics

    @staticmethod
    def _empty_metrics() -> Dict[str, Optional[float]]:
        return {
            "gain_db": None, "gbw_mhz": None,
            "phase_margin": None, "dc_gain_db": None, "gbw_hz": None,
        }
