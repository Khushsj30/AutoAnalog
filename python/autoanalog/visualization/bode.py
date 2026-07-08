# =============================================================================
# AutoAnalog — Bode Plot Generator
# =============================================================================
# Generates publication-quality Bode plots from ngspice AC simulation data.
# Produces both static PNG (for reports) and interactive HTML (for GitHub).
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Optional, Tuple

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger

log = get_logger(__name__)


class BodePlotter:
    """
    Generates Bode plots from AC simulation results.

    Reads frequency/gain/phase data and produces:
      - PNG: static plot for PDF reports
      - HTML: interactive Plotly chart for GitHub README
    """

    def __init__(self):
        self.cfg = get_config()
        self.plots_dir = Path(self.cfg.paths["plots"]) / "bode"
        self.plots_dir.mkdir(parents=True, exist_ok=True)

    def plot_from_ngspice_output(
        self,
        raw_output: str,
        title: str = "AutoAnalog — Open-Loop Bode Plot",
        label: str = "Baseline",
        save_png: bool = True,
        save_html: bool = True,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """
        Parse raw ngspice output and generate Bode plot.

        Parameters
        ----------
        raw_output : str
            Raw stdout from ngspice AC simulation
        title : str
            Plot title
        label : str
            Legend label for this trace
        save_png : bool
            Save static PNG
        save_html : bool
            Save interactive HTML

        Returns
        -------
        (png_path, html_path) — None if save flag is False
        """
        freqs, gains, phases = self._parse_ac_data(raw_output)
        if not freqs:
            log.error("No AC data found in output")
            return None, None

        return self._generate_plot(freqs, gains, phases, title, label,
                                   save_png, save_html)

    def plot_from_csv(
        self,
        csv_path: Path,
        title: str = "AutoAnalog — Open-Loop Bode Plot",
        label: str = "Optimized",
        save_png: bool = True,
        save_html: bool = True,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """Generate Bode plot from saved CSV file."""
        freqs, gains, phases = [], [], []
        with csv_path.open() as f:
            reader = csv.DictReader(f)
            for row in reader:
                freqs.append(float(row["frequency_hz"]))
                gains.append(float(row["gain_db"]))
                phases.append(float(row["phase_deg"]))

        if not freqs:
            log.error("No data in CSV: %s", csv_path)
            return None, None

        return self._generate_plot(freqs, gains, phases, title, label,
                                   save_png, save_html)

    def _parse_ac_data(
        self, output: str
    ) -> Tuple[List[float], List[float], List[float]]:
        """Parse ngspice .PRINT AC output."""
        import math
        freqs, gains, phases = [], [], []
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 4:
                try:
                    int(parts[0])
                    freqs.append(float(parts[1]))
                    gains.append(float(parts[2]))
                    phases.append(float(parts[3]) * 180.0 / math.pi)
                except (ValueError, IndexError):
                    continue
        return freqs, gains, phases

    def _generate_plot(
        self,
        freqs: List[float],
        gains: List[float],
        phases: List[float],
        title: str,
        label: str,
        save_png: bool,
        save_html: bool,
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """Generate the actual plot using matplotlib."""
        try:
            import matplotlib
            matplotlib.use("Agg")   # non-interactive backend
            import matplotlib.pyplot as plt
            import matplotlib.gridspec as gridspec
        except ImportError:
            log.error("matplotlib not installed")
            return None, None

        # --- Find key metrics for annotations ---
        gbw_freq, gbw_idx = self._find_gbw(freqs, gains)
        pm = phases[gbw_idx] if gbw_idx is not None else None
        dc_gain = gains[0] if gains else None
        pole_freq = self._find_pole(freqs, gains, dc_gain)

        # --- Create figure ---
        fig = plt.figure(figsize=(12, 8))
        fig.patch.set_facecolor("#0d1117")
        gs = gridspec.GridSpec(2, 1, hspace=0.05)

        ax_gain  = fig.add_subplot(gs[0])
        ax_phase = fig.add_subplot(gs[1], sharex=ax_gain)

        # Colours
        GAIN_COLOR   = "#58a6ff"
        PHASE_COLOR  = "#3fb950"
        GRID_COLOR   = "#21262d"
        TEXT_COLOR   = "#e6edf3"
        ANNOT_COLOR  = "#f78166"
        BG_COLOR     = "#161b22"

        for ax in [ax_gain, ax_phase]:
            ax.set_facecolor(BG_COLOR)
            ax.tick_params(colors=TEXT_COLOR, labelsize=10)
            ax.spines[:].set_color(GRID_COLOR)
            ax.grid(True, color=GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.7)
            ax.set_xscale("log")

        # --- Gain subplot ---
        ax_gain.plot(freqs, gains, color=GAIN_COLOR, linewidth=2, label=label)
        ax_gain.axhline(0, color=ANNOT_COLOR, linestyle="--",
                        linewidth=1, alpha=0.8, label="0 dB")
        ax_gain.axhline(dc_gain - 3 if dc_gain else 0,
                        color="#d29922", linestyle=":",
                        linewidth=1, alpha=0.6, label="−3 dB")

        if gbw_freq:
            ax_gain.axvline(gbw_freq, color=ANNOT_COLOR, linestyle=":",
                           linewidth=1, alpha=0.6)
            ax_gain.annotate(
                f"GBW = {gbw_freq/1e6:.1f} MHz",
                xy=(gbw_freq, 0),
                xytext=(gbw_freq * 2, dc_gain * 0.3 if dc_gain else 10),
                color=ANNOT_COLOR, fontsize=9,
                arrowprops=dict(arrowstyle="->", color=ANNOT_COLOR, lw=1),
            )

        if dc_gain:
            ax_gain.annotate(
                f"DC Gain = {dc_gain:.1f} dB",
                xy=(freqs[0], dc_gain),
                xytext=(freqs[0] * 5, dc_gain - 8),
                color=TEXT_COLOR, fontsize=9,
                arrowprops=dict(arrowstyle="->", color=TEXT_COLOR, lw=1),
            )

        ax_gain.set_ylabel("Gain (dB)", color=TEXT_COLOR, fontsize=11)
        ax_gain.set_ylim(min(gains) - 5, max(gains) + 10)
        ax_gain.legend(facecolor=BG_COLOR, edgecolor=GRID_COLOR,
                      labelcolor=TEXT_COLOR, fontsize=9)
        ax_gain.set_title(title, color=TEXT_COLOR, fontsize=13,
                         fontweight="bold", pad=12)
        plt.setp(ax_gain.get_xticklabels(), visible=False)

        # --- Phase subplot ---
        ax_phase.plot(freqs, phases, color=PHASE_COLOR, linewidth=2, label="Phase")

        if pm is not None and gbw_freq:
            ax_phase.axvline(gbw_freq, color=ANNOT_COLOR, linestyle=":",
                            linewidth=1, alpha=0.6)
            ax_phase.annotate(
                f"PM = {pm:.1f}°",
                xy=(gbw_freq, pm),
                xytext=(gbw_freq * 0.3, pm - 30),
                color=PHASE_COLOR, fontsize=9,
                arrowprops=dict(arrowstyle="->", color=PHASE_COLOR, lw=1),
            )

        ax_phase.set_ylabel("Phase (°)", color=TEXT_COLOR, fontsize=11)
        ax_phase.set_xlabel("Frequency (Hz)", color=TEXT_COLOR, fontsize=11)
        ax_phase.legend(facecolor=BG_COLOR, edgecolor=GRID_COLOR,
                       labelcolor=TEXT_COLOR, fontsize=9)

        # Spec annotations
        specs_text = (
            f"Process: TSMC 180nm | VDD: 1.8V | CL: 10pF | T: 27°C\n"
            f"DC Gain: {dc_gain:.1f} dB | GBW: {gbw_freq/1e6:.1f} MHz | PM: {pm:.1f}°"
            if dc_gain and gbw_freq and pm else ""
        )
        fig.text(0.5, 0.01, specs_text, ha="center", color="#8b949e",
                fontsize=8, style="italic")

        plt.tight_layout(rect=[0, 0.04, 1, 1])

        # --- Save ---
        png_path = html_path = None

        if save_png:
            png_path = self.plots_dir / "bode_plot.png"
            fig.savefig(png_path, dpi=150, bbox_inches="tight",
                       facecolor=fig.get_facecolor())
            log.info("Bode plot saved: %s", png_path)

        if save_html:
            html_path = self._save_interactive(freqs, gains, phases,
                                               gbw_freq, pm, dc_gain, title)

        plt.close(fig)
        return png_path, html_path

    def _save_interactive(
        self,
        freqs, gains, phases,
        gbw_freq, pm, dc_gain, title
    ) -> Optional[Path]:
        """Save interactive Plotly Bode plot."""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            log.warning("plotly not installed — skipping interactive plot")
            return None

        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            subplot_titles=("Gain (dB)", "Phase (°)"),
            vertical_spacing=0.08,
        )

        fig.add_trace(go.Scatter(
            x=freqs, y=gains, name="Gain",
            line=dict(color="#58a6ff", width=2),
            hovertemplate="f=%{x:.2e} Hz<br>Gain=%{y:.1f} dB<extra></extra>",
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=freqs, y=phases, name="Phase",
            line=dict(color="#3fb950", width=2),
            hovertemplate="f=%{x:.2e} Hz<br>Phase=%{y:.1f}°<extra></extra>",
        ), row=2, col=1)

        # Annotations
        if gbw_freq:
            for row in [1, 2]:
                fig.add_vline(x=gbw_freq, line_dash="dot",
                             line_color="#f78166", opacity=0.7, row=row, col=1)
            fig.add_hline(y=0, line_dash="dash",
                         line_color="#f78166", opacity=0.5, row=1, col=1)

        fig.update_layout(
            title=dict(text=title, font=dict(size=16, color="#e6edf3")),
            template="plotly_dark",
            paper_bgcolor="#0d1117",
            plot_bgcolor="#161b22",
            font=dict(color="#e6edf3"),
            height=600,
            legend=dict(bgcolor="#161b22", bordercolor="#21262d"),
            annotations=[dict(
                x=0.5, y=-0.08, xref="paper", yref="paper",
                text=(f"DC Gain: {dc_gain:.1f} dB | GBW: {gbw_freq/1e6:.1f} MHz | "
                      f"PM: {pm:.1f}° | TSMC 180nm TT | VDD=1.8V | CL=10pF"
                      if dc_gain and gbw_freq and pm else ""),
                showarrow=False, font=dict(size=10, color="#8b949e"),
            )],
        )

        for ax in ["xaxis", "xaxis2"]:
            fig.update_layout(**{ax: dict(type="log", title="Frequency (Hz)")})

        html_path = self.plots_dir / "bode_plot.html"
        fig.write_html(str(html_path), include_plotlyjs="cdn")
        log.info("Interactive Bode plot saved: %s", html_path)
        return html_path

    @staticmethod
    def _find_gbw(
        freqs: List[float], gains: List[float]
    ) -> Tuple[Optional[float], Optional[int]]:
        for i in range(len(gains) - 1):
            if gains[i] >= 0 and gains[i + 1] < 0:
                t = gains[i] / (gains[i] - gains[i + 1])
                import math
                f = math.exp(
                    math.log(freqs[i]) + t * (math.log(freqs[i+1]) - math.log(freqs[i]))
                )
                return f, i
        return None, None

    @staticmethod
    def _find_pole(
        freqs: List[float], gains: List[float], dc_gain: Optional[float]
    ) -> Optional[float]:
        if not dc_gain:
            return None
        target = dc_gain - 3.0
        for i in range(len(gains) - 1):
            if gains[i] >= target > gains[i + 1]:
                import math
                t = (target - gains[i]) / (gains[i+1] - gains[i])
                return math.exp(
                    math.log(freqs[i]) + t * (math.log(freqs[i+1]) - math.log(freqs[i]))
                )
        return None
