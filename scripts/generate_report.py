#!/usr/bin/env python3
# =============================================================================
# AutoAnalog — Master Visualization + Report Generator
# =============================================================================
# Runs the full visualization pipeline:
#   1. Generate Bode plot from AC simulation data
#   2. Generate optimization plots (convergence, histogram, scatter)
#   3. Generate HTML report
#   4. Update README with results
#
# Usage:
#   python3 scripts/generate_report.py
#   python3 scripts/generate_report.py --skip-bode
#
# Author  : AutoAnalog Framework
# =============================================================================

import sys
import argparse
from pathlib import Path

# Bootstrap
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger

cfg = get_config(config_file=Path("config/design_config.yaml"))
log = get_logger("autoanalog.generate_report")


def run_bode_plot():
    """Generate Bode plot by running AC simulation."""
    log.info("Generating Bode plot...")
    from autoanalog.simulation.ac import ACAnalysis
    from autoanalog.visualization.bode import BodePlotter

    sim = ACAnalysis(save_results=True)
    result = sim.run_baseline()

    if not result.converged or not result.frequencies:
        log.error("AC simulation failed — cannot generate Bode plot")
        return False

    plotter = BodePlotter()
    # Reconstruct raw output format for plotter
    import math
    lines = []
    for i, (f, g, p) in enumerate(zip(
        result.frequencies, result.gain_db, result.phase_deg
    )):
        lines.append(f"{i}\t{f:.6e}\t{g:.6e}\t{p * math.pi / 180:.6e}")
    raw = "\n".join(lines)

    png_path, html_path = plotter.plot_from_ngspice_output(
        raw_output=raw,
        title="AutoAnalog — Two-Stage CMOS Op-Amp Open-Loop Response",
        label=f"Optimized (Gain={result.dc_gain_db:.1f} dB)",
    )

    if png_path:
        log.info("Bode PNG: %s", png_path)
    if html_path:
        log.info("Bode HTML: %s", html_path)

    log.info("Bode plot: Gain=%.1f dB, GBW=%.1f MHz, PM=%.1f°",
            result.dc_gain_db or 0,
            (result.gbw_hz or 0) / 1e6,
            result.phase_margin_deg or 0)
    return True


def run_optimization_plots():
    """Generate optimization result plots."""
    log.info("Generating optimization plots...")
    from autoanalog.visualization.optimization_plots import OptimizationPlotter

    plotter = OptimizationPlotter()
    paths = plotter.plot_all()

    if paths:
        log.info("Generated %d optimization plots:", len(paths))
        for p in paths:
            log.info("  %s", p)
    else:
        log.warning("No optimization data found — run optimizer first")
    return bool(paths)


def run_html_report():
    """Generate HTML report."""
    log.info("Generating HTML report...")
    from autoanalog.reporting.html_report import HTMLReportGenerator

    gen = HTMLReportGenerator()
    path = gen.generate()
    log.info("HTML report: %s", path)
    return path


def main():
    parser = argparse.ArgumentParser(description="AutoAnalog Report Generator")
    parser.add_argument("--skip-bode", action="store_true",
                       help="Skip Bode plot generation (use existing)")
    parser.add_argument("--skip-opt-plots", action="store_true",
                       help="Skip optimization plots")
    parser.add_argument("--report-only", action="store_true",
                       help="Only generate HTML report from existing data")
    args = parser.parse_args()

    log.info("=" * 55)
    log.info("  AutoAnalog Report Generator")
    log.info("=" * 55)

    if not args.report_only and not args.skip_bode:
        run_bode_plot()

    if not args.report_only and not args.skip_opt_plots:
        run_optimization_plots()

    report_path = run_html_report()

    log.info("")
    log.info("=" * 55)
    log.info("  Report generation complete!")
    log.info("=" * 55)
    log.info("  HTML report  : %s", report_path)
    log.info("  Bode plot    : %s/bode/bode_plot.png",
            cfg.paths["plots"])
    log.info("  Resume       : %s/resume_metrics.md",
            cfg.paths["reports"])
    log.info("")
    log.info("  Open the report:")
    log.info("  explorer.exe docs/reports/report.html  (WSL)")
    log.info("  or: python3 -m http.server 8080 --directory docs/reports/")


if __name__ == "__main__":
    main()
