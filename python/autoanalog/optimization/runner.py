# =============================================================================
# AutoAnalog — Optimization Runner
# =============================================================================
# Orchestrates the full optimization pipeline:
#   1. Random Search  (fast exploration, ~200 runs)
#   2. Saves results and generates performance summary
#
# Usage (CLI):
#   python3 -m autoanalog.optimization.runner
#
# Usage (Python):
#   from autoanalog.optimization.runner import OptimizationRunner
#   runner = OptimizationRunner(n_random=200)
#   best = runner.run()
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, Dict, Any

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger
from autoanalog.optimization.random_search import RandomSearchOptimizer, RandomSearchResult
from autoanalog.optimization.performance_summary import PerformanceSummary

log = get_logger(__name__)


class OptimizationRunner:
    """
    Runs the full AutoAnalog optimization pipeline.

    Parameters
    ----------
    n_random : int
        Number of random search iterations (default 200)
    seed : int
        Random seed for reproducibility
    """

    def __init__(self, n_random: int = 200, seed: int = 42):
        self.cfg = get_config()
        self.n_random = n_random
        self.seed = seed
        self.results_dir = Path(self.cfg.paths["results"]) / "optimization"
        self.results_dir.mkdir(parents=True, exist_ok=True)

        # Baseline from Chat 2 verified simulation
        self.baseline_metrics = {
            "gain_db": 61.9,
            "gbw_mhz": 15.63,
            "phase_margin_deg": 72.9,
            "power_mw": 0.35,
        }

    def run(self) -> Dict[str, Any]:
        """
        Run complete optimization pipeline.

        Returns
        -------
        dict with best_params, best_metrics, improvement stats
        """
        t_start = time.perf_counter()

        log.info("╔══════════════════════════════════════════════════╗")
        log.info("║     AutoAnalog Optimization Engine               ║")
        log.info("║     Random Search: %d iterations                ║", self.n_random)
        log.info("╚══════════════════════════════════════════════════╝")

        # --- Stage 1: Random Search ---
        log.info("\n[Stage 1] Random Search (%d runs)...", self.n_random)
        random_opt = RandomSearchOptimizer(
            n_iterations=self.n_random,
            seed=self.seed,
        )
        rs_result: RandomSearchResult = random_opt.run()

        total_time = (time.perf_counter() - t_start) / 60.0
        n_sims = rs_result.n_total

        # --- Generate Performance Summary ---
        self._generate_performance_summary(rs_result, n_sims, total_time)

        # --- Final Summary ---
        self._print_final_summary(rs_result, n_sims, total_time)

        return {
            "best_params": rs_result.best_params,
            "best_metrics": rs_result.best_metrics,
            "n_simulations": n_sims,
            "elapsed_minutes": total_time,
            "baseline": self.baseline_metrics,
        }

    def _generate_performance_summary(
        self,
        rs_result: RandomSearchResult,
        n_sims: int,
        opt_time_min: float,
    ) -> None:
        """Generate and save performance summary from optimization results."""
        b = self.baseline_metrics
        opt = rs_result.best_metrics

        if not opt or not opt.get("gain_db"):
            log.warning("No valid optimized metrics to generate performance summary from")
            return

        summary = PerformanceSummary()
        summary.load_baseline(
            gain=b["gain_db"],
            gbw=b["gbw_mhz"],
            pm=b["phase_margin_deg"],
            power=b["power_mw"],
        )
        summary.load_optimized(
            gain=opt.get("gain_db", b["gain_db"]),
            gbw=opt.get("gbw_mhz", b["gbw_mhz"]),
            pm=opt.get("phase_margin", b["phase_margin_deg"]),
            power=opt.get("power_mw", b["power_mw"]),
            n_simulations=n_sims,
            opt_time_min=opt_time_min,
            best_params=rs_result.best_params,
        )

        report = summary.generate()
        saved_path = summary.save(report)
        summary.save_json()

        log.info("Performance summary generated: %s", saved_path)
        log.info("\n" + "=" * 55)
        log.info("KEY METRICS SUMMARY:")
        log.info("=" * 55)

        # Extract and print the first bullet
        for line in report.splitlines():
            if line.startswith("> Designed and optimized"):
                log.info(line[2:])  # strip "> "
                break

    def _print_final_summary(
        self,
        rs_result: RandomSearchResult,
        n_sims: int,
        total_time: float,
    ) -> None:
        b = self.baseline_metrics
        opt = rs_result.best_metrics

        gain_b = b["gain_db"]
        gain_o = opt.get("gain_db", gain_b)
        gbw_b  = b["gbw_mhz"]
        gbw_o  = opt.get("gbw_mhz", gbw_b)

        gain_imp = ((gain_o - gain_b) / abs(gain_b)) * 100 if gain_b else 0
        gbw_ratio = gbw_o / gbw_b if gbw_b else 1

        log.info("\n" + "=" * 55)
        log.info("  OPTIMIZATION COMPLETE")
        log.info("=" * 55)
        log.info("  Simulations run  : %d", n_sims)
        log.info("  Time elapsed     : %.1f minutes", total_time)
        log.info("  Feasible designs : %d (%.0f%%)",
                rs_result.n_feasible,
                100*rs_result.n_feasible/max(1, n_sims))
        log.info("")
        log.info("  Performance:")
        log.info("    DC Gain  : %.1f → %.1f dB  (+%.0f%%)", gain_b, gain_o, gain_imp)
        log.info("    GBW      : %.1f → %.1f MHz  (%.1f×)", gbw_b, gbw_o, gbw_ratio)
        log.info("    PM       : %.0f° → %.0f°",
                b["phase_margin_deg"],
                opt.get("phase_margin", b["phase_margin_deg"]))
        log.info("")
        log.info("  Results saved to : results/optimization/")
        log.info("  Performance summary: docs/reports/performance_summary.md")
        log.info("=" * 55)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AutoAnalog Optimization Runner")
    parser.add_argument("--n-random", type=int, default=50,
                       help="Number of random search iterations (default: 50)")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed (default: 42)")
    parser.add_argument("--algorithm", type=str, default="random",
                       choices=["random", "all"],
                       help="Algorithm to run (default: random)")
    args = parser.parse_args()

    from pathlib import Path
    from autoanalog.config_loader import get_config
    get_config(config_file=Path("config/design_config.yaml"))

    runner = OptimizationRunner(
        n_random=args.n_random,
        seed=args.seed,
    )
    runner.run()
