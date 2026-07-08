# =============================================================================
# AutoAnalog — Random Search Optimizer
# =============================================================================
# Samples random design points and keeps track of the best found.
# Fast, parallelisable, good for initial exploration of the design space.
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger
from autoanalog.optimization.objective import ObjectiveFunction, INFEASIBLE_PENALTY
from autoanalog.optimization.design_space import DesignSpace

log = get_logger(__name__)


class RandomSearchResult:
    """Container for random search results."""

    def __init__(self):
        self.best_params: Optional[Dict[str, float]] = None
        self.best_score: float = float("inf")
        self.best_metrics: Dict[str, Any] = {}
        self.all_results: List[Dict[str, Any]] = []
        self.n_feasible: int = 0
        self.n_total: int = 0
        self.elapsed_seconds: float = 0.0

    def update(
        self,
        params: Dict[str, float],
        score: float,
        metrics: Dict[str, Any],
    ) -> bool:
        """Update best result. Returns True if improved."""
        self.n_total += 1
        if score < INFEASIBLE_PENALTY:
            self.n_feasible += 1

        self.all_results.append({
            "score": score,
            **{f"param_{k}": v for k, v in params.items()},
            **metrics,
        })

        if score < self.best_score:
            self.best_score = score
            self.best_params = dict(params)
            self.best_metrics = dict(metrics)
            return True
        return False

    def summary(self) -> str:
        lines = [
            "=" * 55,
            "  Random Search Results",
            "=" * 55,
            f"  Runs       : {self.n_total}",
            f"  Feasible   : {self.n_feasible} ({100*self.n_feasible/max(1,self.n_total):.0f}%)",
            f"  Best score : {self.best_score:.4f}",
            f"  Time       : {self.elapsed_seconds:.1f}s",
            "",
            "  Best Design:",
        ]
        if self.best_metrics:
            g = self.best_metrics.get("gain_db")
            gbw = self.best_metrics.get("gbw_mhz")
            pm = self.best_metrics.get("phase_margin")
            if g:   lines.append(f"    DC Gain      : {g:.1f} dB")
            if gbw: lines.append(f"    GBW          : {gbw:.2f} MHz")
            if pm:  lines.append(f"    Phase Margin : {pm:.1f}°")
        if self.best_params:
            lines.append("")
            lines.append("  Best Parameters:")
            for k, v in self.best_params.items():
                if k in ("Rc", "VBIAS"):
                    lines.append(f"    {k:8s} = {v:.3g}")
                elif k == "Cc":
                    lines.append(f"    {k:8s} = {v*1e12:.2f} pF")
                else:
                    lines.append(f"    {k:8s} = {v*1e6:.2f} µm")
        lines.append("=" * 55)
        return "\n".join(lines)


class RandomSearchOptimizer:
    """
    Random search over the analog design space.

    Evaluates random design points and tracks the best found.
    Serves as both a standalone optimizer and an initial population
    generator for more sophisticated algorithms.

    Parameters
    ----------
    n_iterations : int
        Number of random samples to evaluate
    seed : int
        Random seed for reproducibility
    """

    def __init__(
        self,
        n_iterations: int = 200,
        seed: int = 42,
    ):
        self.cfg = get_config()
        self.n_iterations = n_iterations
        self.seed = seed
        self.space = DesignSpace()
        self.objective = ObjectiveFunction()
        self.results_dir = Path(self.cfg.paths["results"]) / "optimization"
        self.results_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> RandomSearchResult:
        """
        Run random search for n_iterations evaluations.

        Returns
        -------
        RandomSearchResult
        """
        log.info("=" * 55)
        log.info("Starting Random Search: %d iterations", self.n_iterations)
        log.info("=" * 55)

        result = RandomSearchResult()
        t_start = time.perf_counter()

        # Always start with the verified baseline
        baseline = self.space.baseline()
        score, metrics = self.objective.evaluate(baseline)
        improved = result.update(baseline, score, metrics)
        log.info(
            "[%3d/%d] BASELINE  Gain=%.1fdB GBW=%.1fMHz PM=%.1f° score=%.4f",
            1, self.n_iterations,
            metrics.get("gain_db") or 0,
            metrics.get("gbw_mhz") or 0,
            metrics.get("phase_margin") or 0,
            score,
        )

        # Random samples
        population = self.space.sample_population(
            self.n_iterations - 1, seed=self.seed
        )

        for i, params in enumerate(population, start=2):
            score, metrics = self.objective.evaluate(params)
            improved = result.update(params, score, metrics)

            gain = metrics.get("gain_db") or 0
            gbw  = metrics.get("gbw_mhz") or 0
            pm   = metrics.get("phase_margin") or 0

            status = "★ NEW BEST" if improved else ""
            log.info(
                "[%3d/%d] Gain=%.1fdB GBW=%.1fMHz PM=%.1f° score=%.4f %s",
                i, self.n_iterations, gain, gbw, pm, score, status
            )

            # Save progress every 10 runs
            if i % 10 == 0:
                self._save_progress(result)

        result.elapsed_seconds = time.perf_counter() - t_start
        self._save_progress(result)
        self._save_best(result)

        log.info(result.summary())
        return result

    def _save_progress(self, result: RandomSearchResult) -> None:
        """Save all results to CSV."""
        if not result.all_results:
            return
        csv_path = self.results_dir / "random_search_progress.csv"
        fieldnames = list(result.all_results[0].keys())
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(result.all_results)

    def _save_best(self, result: RandomSearchResult) -> None:
        """Save best design to its own file."""
        if not result.best_params:
            return
        best_path = self.results_dir / "random_search_best.csv"
        row = {
            "score": result.best_score,
            **result.best_metrics,
            **{f"param_{k}": v for k, v in result.best_params.items()},
            "n_total": result.n_total,
            "n_feasible": result.n_feasible,
            "elapsed_s": result.elapsed_seconds,
        }
        with best_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(row.keys()))
            writer.writeheader()
            writer.writerow(row)
        log.info("Best design saved: %s", best_path)
