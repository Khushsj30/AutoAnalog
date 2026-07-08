# =============================================================================
# AutoAnalog — Optimization Visualization
# =============================================================================
# Generates plots from optimization run data:
#   - Convergence curve (best score vs iteration)
#   - Gain distribution histogram (all feasible designs)
#   - Scatter: gain vs GBW (Pareto-front view)
#   - Scatter: gain vs phase margin
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Dict, Optional

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger

log = get_logger(__name__)

# Dark-theme colour palette (matches bode.py)
BG      = "#0d1117"
PANEL   = "#161b22"
GRID    = "#21262d"
TEXT    = "#e6edf3"
MUTED   = "#8b949e"
BLUE    = "#58a6ff"
GREEN   = "#3fb950"
ORANGE  = "#d29922"
RED     = "#f78166"
PURPLE  = "#bc8cff"


class OptimizationPlotter:
    """
    Generates plots from optimization results CSV.

    Usage
    -----
    plotter = OptimizationPlotter()
    plotter.plot_all()   # generates all plots from saved CSV
    """

    def __init__(self):
        self.cfg = get_config()
        self.results_dir = Path(self.cfg.paths["results"]) / "optimization"
        self.plots_dir = Path(self.cfg.paths["plots"])
        self.plots_dir.mkdir(parents=True, exist_ok=True)

    def plot_all(self) -> List[Path]:
        """Generate all optimization plots. Returns list of saved paths."""
        data = self._load_data()
        if not data:
            log.warning("No optimization data found")
            return []

        saved = []
        p = self._plot_convergence(data)
        if p: saved.append(p)
        p = self._plot_gain_histogram(data)
        if p: saved.append(p)
        p = self._plot_gain_vs_gbw(data)
        if p: saved.append(p)
        p = self._plot_interactive_scatter(data)
        if p: saved.append(p)

        log.info("Generated %d optimization plots", len(saved))
        return saved

    def _load_data(self) -> List[Dict]:
        csv_path = self.results_dir / "random_search_progress.csv"
        if not csv_path.exists():
            log.warning("No progress CSV found: %s", csv_path)
            return []
        rows = []
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    rows.append({
                        "score":    float(row.get("score", 1e6)),
                        "gain_db":  float(row.get("gain_db") or 0),
                        "gbw_mhz":  float(row.get("gbw_mhz") or 0),
                        "phase_margin": float(row.get("phase_margin") or 0),
                    })
                except (ValueError, TypeError):
                    continue
        log.info("Loaded %d optimization results", len(rows))
        return rows

    def _plot_convergence(self, data: List[Dict]) -> Optional[Path]:
        """Best score vs iteration number."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return None

        scores = [d["score"] for d in data]
        best_so_far = []
        best = float("inf")
        for s in scores:
            if s < 1e5:   # feasible only
                best = min(best, s)
            best_so_far.append(best if best < float("inf") else None)

        # Filter out None
        iters = list(range(1, len(scores) + 1))
        valid_iters = [i for i, b in zip(iters, best_so_far) if b is not None]
        valid_best  = [b for b in best_so_far if b is not None]

        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=TEXT)
        ax.spines[:].set_color(GRID)
        ax.grid(True, color=GRID, linestyle="--", linewidth=0.5, alpha=0.7)

        if valid_iters:
            ax.plot(valid_iters, valid_best, color=BLUE, linewidth=2,
                   label="Best feasible score")
            ax.scatter(valid_iters[-1], valid_best[-1], color=GREEN,
                      s=80, zorder=5, label=f"Final best: {valid_best[-1]:.4f}")

        ax.set_xlabel("Iteration", color=TEXT, fontsize=11)
        ax.set_ylabel("Objective Score (lower = better)", color=TEXT, fontsize=11)
        ax.set_title("Optimization Convergence — AutoAnalog Random Search",
                    color=TEXT, fontsize=13, fontweight="bold")
        ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT)

        path = self.plots_dir / "convergence.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(fig)
        log.info("Convergence plot saved: %s", path)
        return path

    def _plot_gain_histogram(self, data: List[Dict]) -> Optional[Path]:
        """Distribution of DC gain across all feasible designs."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import numpy as np
        except ImportError:
            return None

        feasible_gains = [d["gain_db"] for d in data
                         if d["score"] < 1e5 and d["gain_db"] > 0]
        if not feasible_gains:
            return None

        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=TEXT)
        ax.spines[:].set_color(GRID)
        ax.grid(True, color=GRID, linestyle="--", linewidth=0.5, alpha=0.5,
               axis="y")

        n, bins, patches = ax.hist(feasible_gains, bins=30,
                                   color=BLUE, alpha=0.8, edgecolor=GRID)

        # Colour bars by gain level
        for patch, left in zip(patches, bins[:-1]):
            if left >= 70:
                patch.set_facecolor(GREEN)
            elif left >= 60:
                patch.set_facecolor(ORANGE)

        # Annotations
        best_gain = max(feasible_gains)
        baseline  = 61.9
        ax.axvline(baseline, color=ORANGE, linestyle="--", linewidth=1.5,
                  label=f"Baseline: {baseline} dB")
        ax.axvline(best_gain, color=GREEN, linestyle="--", linewidth=1.5,
                  label=f"Best: {best_gain:.1f} dB")
        ax.axvline(80, color=RED, linestyle=":", linewidth=1,
                  alpha=0.7, label="Target: 80 dB")

        ax.set_xlabel("DC Gain (dB)", color=TEXT, fontsize=11)
        ax.set_ylabel("Count", color=TEXT, fontsize=11)
        ax.set_title(
            f"DC Gain Distribution — {len(feasible_gains)} Feasible Designs",
            color=TEXT, fontsize=13, fontweight="bold"
        )
        ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT)

        path = self.plots_dir / "gain_histogram.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(fig)
        log.info("Gain histogram saved: %s", path)
        return path

    def _plot_gain_vs_gbw(self, data: List[Dict]) -> Optional[Path]:
        """Scatter plot of gain vs GBW — shows Pareto front."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            return None

        feasible = [d for d in data
                   if d["score"] < 1e5 and d["gain_db"] > 0 and d["gbw_mhz"] > 0]
        if not feasible:
            return None

        gains = [d["gain_db"] for d in feasible]
        gbws  = [d["gbw_mhz"] for d in feasible]
        pms   = [d["phase_margin"] for d in feasible]

        fig, ax = plt.subplots(figsize=(10, 6))
        fig.patch.set_facecolor(BG)
        ax.set_facecolor(PANEL)
        ax.tick_params(colors=TEXT)
        ax.spines[:].set_color(GRID)
        ax.grid(True, color=GRID, linestyle="--", linewidth=0.5, alpha=0.5)

        sc = ax.scatter(gains, gbws, c=pms, cmap="viridis",
                       alpha=0.7, s=20, edgecolors="none")

        cbar = fig.colorbar(sc, ax=ax)
        cbar.set_label("Phase Margin (°)", color=TEXT)
        cbar.ax.yaxis.set_tick_params(color=TEXT)
        plt.setp(cbar.ax.yaxis.get_ticklabels(), color=TEXT)

        # Mark baseline and best
        ax.scatter([61.9], [15.6], color=ORANGE, s=120, zorder=5,
                  marker="*", label="Baseline (61.9 dB, 15.6 MHz)")
        best = max(feasible, key=lambda d: d["gain_db"])
        ax.scatter([best["gain_db"]], [best["gbw_mhz"]],
                  color=GREEN, s=120, zorder=5, marker="*",
                  label=f"Best ({best['gain_db']:.1f} dB, {best['gbw_mhz']:.1f} MHz)")

        # Spec lines
        ax.axvline(80, color=RED, linestyle=":", linewidth=1,
                  alpha=0.7, label="Gain target (80 dB)")
        ax.axhline(10, color=PURPLE, linestyle=":", linewidth=1,
                  alpha=0.7, label="GBW target (10 MHz)")

        ax.set_xlabel("DC Gain (dB)", color=TEXT, fontsize=11)
        ax.set_ylabel("GBW (MHz)", color=TEXT, fontsize=11)
        ax.set_title("Design Space Exploration — Gain vs GBW",
                    color=TEXT, fontsize=13, fontweight="bold")
        ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=9)

        path = self.plots_dir / "gain_vs_gbw.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=BG)
        plt.close(fig)
        log.info("Gain vs GBW scatter saved: %s", path)
        return path

    def _plot_interactive_scatter(self, data: List[Dict]) -> Optional[Path]:
        """Interactive Plotly scatter — hover to see all metrics."""
        try:
            import plotly.graph_objects as go
        except ImportError:
            return None

        feasible = [d for d in data
                   if d["score"] < 1e5 and d["gain_db"] > 0]
        if not feasible:
            return None

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=[d["gain_db"] for d in feasible],
            y=[d["gbw_mhz"] for d in feasible],
            mode="markers",
            marker=dict(
                color=[d["phase_margin"] for d in feasible],
                colorscale="Viridis",
                size=6, opacity=0.7,
                colorbar=dict(title="PM (°)"),
            ),
            text=[
                f"Gain: {d['gain_db']:.1f} dB<br>"
                f"GBW: {d['gbw_mhz']:.1f} MHz<br>"
                f"PM: {d['phase_margin']:.1f}°<br>"
                f"Score: {d['score']:.4f}"
                for d in feasible
            ],
            hoverinfo="text",
            name="Design points",
        ))

        # Baseline
        fig.add_trace(go.Scatter(
            x=[61.9], y=[15.6], mode="markers",
            marker=dict(color="#d29922", size=14, symbol="star"),
            name="Baseline",
            hovertext="Baseline: 61.9 dB, 15.6 MHz, 73°",
        ))

        best = max(feasible, key=lambda d: d["gain_db"])
        fig.add_trace(go.Scatter(
            x=[best["gain_db"]], y=[best["gbw_mhz"]], mode="markers",
            marker=dict(color="#3fb950", size=14, symbol="star"),
            name=f"Best: {best['gain_db']:.1f} dB",
            hovertext=f"Best: {best['gain_db']:.1f} dB, {best['gbw_mhz']:.1f} MHz",
        ))

        fig.update_layout(
            title="AutoAnalog Design Space — Gain vs GBW (hover for details)",
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#161b22",
            xaxis_title="DC Gain (dB)",
            yaxis_title="GBW (MHz)",
            font=dict(color="#e6edf3"),
            height=500,
        )

        path = self.plots_dir / "design_space.html"
        fig.write_html(str(path), include_plotlyjs="cdn")
        log.info("Interactive scatter saved: %s", path)
        return path
