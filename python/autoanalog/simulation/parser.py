# =============================================================================
# AutoAnalog — ngspice Output Parser
# =============================================================================
# Parses raw ngspice text output into structured Python objects.
# Each analysis type has its own parse method.
#
# Parser design:
#   - Line-by-line state machine (no regex for performance)
#   - Robust to ngspice version differences in output format
#   - Returns None for values that could not be extracted (never raises)
#   - Phase margin computed from phase array (more accurate than .MEASURE)
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Dict
from pathlib import Path

from autoanalog.logger import get_logger
from autoanalog.simulation.results import ACResult, OPResult, TransientResult, NoiseResult

log = get_logger(__name__)


class ACParser:
    """
    Parses ngspice AC analysis output (.PRINT AC VDB(OUT) VP(OUT)).

    Expected line format (from ngspice batch mode):
        row_index   frequency   vdb_out   vp_out
        0           1.000000e+00   6.187e+01   3.141e+00
    """

    def parse(self, raw_output: str, sim_time: float = 0.0) -> ACResult:
        """
        Parse raw ngspice stdout into an ACResult.

        Parameters
        ----------
        raw_output : str
            Complete stdout from ngspice -b
        sim_time : float
            Elapsed simulation time in seconds

        Returns
        -------
        ACResult
        """
        result = ACResult(sim_time_seconds=sim_time)

        frequencies, gain_db, phase_rad = self._extract_ac_table(raw_output)

        if not frequencies:
            log.warning("AC parser: no data rows found in output")
            result.converged = False
            result.error_message = "No AC data rows parsed"
            return result

        result.frequencies = frequencies
        result.gain_db = gain_db

        # Convert phase from radians to degrees
        phase_deg = [p * 180.0 / math.pi for p in phase_rad]
        result.phase_deg = phase_deg

        # --- DC gain: first row (lowest frequency) ---
        result.dc_gain_db = gain_db[0] if gain_db else None

        # --- GBW: interpolate where gain crosses 0 dB ---
        gbw, phase_at_gbw = self._find_gbw(frequencies, gain_db, phase_deg)
        result.gbw_hz = gbw
        result.unity_gain_freq_hz = gbw

        # --- Phase margin from ngspice VP() output ---
        # ngspice VP() returns phase in radians, converted to degrees above.
        # For our RFEEDBACK open-loop testbench:
        #   DC phase ≈ +180° (π rad)
        #   At GBW our simulation showed phase ≈ +75° → PM = 75° directly
        # Rule: if phase_at_gbw > 0, PM = phase_at_gbw
        #       if phase_at_gbw < 0, PM = 180 + phase_at_gbw
        if phase_at_gbw is not None:
            if phase_at_gbw > 0:
                result.phase_margin_deg = phase_at_gbw
            else:
                result.phase_margin_deg = 180.0 + phase_at_gbw
            log.debug(
                "Phase at GBW: %.1f° → Phase Margin: %.1f°",
                phase_at_gbw,
                result.phase_margin_deg,
            )

        # --- Gain margin: gain when phase = -180° ---
        result.gain_margin_db = self._find_gain_margin(frequencies, gain_db, phase_deg)

        # --- Dominant pole: frequency where gain drops 3 dB from DC ---
        result.dominant_pole_hz = self._find_dominant_pole(
            frequencies, gain_db, result.dc_gain_db
        )

        log.info(
            "AC parsed: Gain=%.1f dB, GBW=%.2f MHz, PM=%.1f°",
            result.dc_gain_db or 0,
            (result.gbw_hz or 0) / 1e6,
            result.phase_margin_deg or 0,
        )

        return result

    def _extract_ac_table(
        self, output: str
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Extract (frequency, gain_db, phase_rad) columns from ngspice output.

        ngspice prints AC data as:
            index   freq   vdb(out)   vp(out)
        Lines start with an integer index.
        """
        frequencies, gain_db, phase_rad = [], [], []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            # Data rows: first token is integer index, then 3 floats
            if len(parts) >= 4:
                try:
                    int(parts[0])       # must be integer row index
                    freq = float(parts[1])
                    gdb  = float(parts[2])
                    ph   = float(parts[3])
                    frequencies.append(freq)
                    gain_db.append(gdb)
                    phase_rad.append(ph)
                except (ValueError, IndexError):
                    continue

        return frequencies, gain_db, phase_rad

    def _find_gbw(
        self,
        freqs: List[float],
        gains: List[float],
        phases: List[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Find GBW by linear interpolation between the two rows that straddle 0 dB.
        Returns (gbw_hz, phase_at_gbw_deg).
        """
        for i in range(len(gains) - 1):
            g0, g1 = gains[i], gains[i + 1]
            if g0 >= 0 and g1 < 0:
                # Linear interpolation
                t = g0 / (g0 - g1)
                f0, f1 = freqs[i], freqs[i + 1]
                # Log-space interpolation for frequency
                gbw = math.exp(
                    math.log(f0) + t * (math.log(f1) - math.log(f0))
                )
                p0, p1 = phases[i], phases[i + 1]
                phase_at_gbw = p0 + t * (p1 - p0)
                return gbw, phase_at_gbw
        return None, None

    def _find_gain_margin(
        self,
        freqs: List[float],
        gains: List[float],
        phases: List[float],
    ) -> Optional[float]:
        """
        Find gain margin: gain (dB) at the frequency where phase = -180°.
        For a non-inverting measurement setup this is where phase crosses -180°.
        """
        # Phase starts near 180° (inverted) and decreases
        # Gain margin is gain at the -180° crossing (second crossing)
        target = -180.0
        for i in range(len(phases) - 1):
            p0, p1 = phases[i], phases[i + 1]
            if p0 >= target and p1 < target:
                t = (target - p0) / (p1 - p0)
                gm = gains[i] + t * (gains[i + 1] - gains[i])
                return -gm  # gain margin = -gain_at_crossover
        return None

    def _find_dominant_pole(
        self,
        freqs: List[float],
        gains: List[float],
        dc_gain: Optional[float],
    ) -> Optional[float]:
        """Find -3dB frequency from DC gain."""
        if dc_gain is None or not freqs:
            return None
        target = dc_gain - 3.0
        for i in range(len(gains) - 1):
            if gains[i] >= target and gains[i + 1] < target:
                t = (target - gains[i]) / (gains[i + 1] - gains[i])
                f = math.exp(
                    math.log(freqs[i]) + t * (math.log(freqs[i + 1]) - math.log(freqs[i]))
                )
                return f
        return None


class OPParser:
    """Parses ngspice .OP output to extract node voltages and currents."""

    def parse(self, raw_output: str, sim_time: float = 0.0) -> OPResult:
        result = OPResult(sim_time_seconds=sim_time)

        lines = raw_output.splitlines()
        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Node voltages printed in OP section
            if "xopa.vtail" in line_lower:
                result.v_vtail = self._extract_value(line)
            elif "xopa.vout1" in line_lower:
                result.v_vout1 = self._extract_value(line)
            elif "xopa.vd1" in line_lower:
                result.v_vd1 = self._extract_value(line)
            elif "xopa.vcomp" in line_lower:
                pass  # internal node, skip
            elif line_lower.strip().startswith("out ") or "node out" in line_lower:
                result.v_out = self._extract_value(line)

            # Supply current
            elif "vdd#branch" in line_lower:
                val = self._extract_value(line)
                if val is not None:
                    # ngspice reports current into VDD as negative (current out)
                    result.i_vdd_ua = abs(val) * 1e6
                    result.power_mw = abs(val) * 1.8 * 1e3

        log.debug(
            "OP parsed: VTAIL=%.3fV, VOUT1=%.3fV, Power=%.3f mW",
            result.v_vtail or 0,
            result.v_vout1 or 0,
            result.power_mw or 0,
        )
        return result

    @staticmethod
    def _extract_value(line: str) -> Optional[float]:
        """Extract the last float from a line like '  xopa.vtail   1.648e+00'."""
        parts = line.split()
        for part in reversed(parts):
            try:
                return float(part)
            except ValueError:
                continue
        return None


class TransientParser:
    """Parses ngspice transient output to extract slew rate and settling time."""

    def parse(self, raw_output: str, sim_time: float = 0.0) -> TransientResult:
        result = TransientResult(sim_time_seconds=sim_time)

        times, v_out, v_in = self._extract_tran_table(raw_output)

        if not times:
            result.converged = False
            result.error_message = "No transient data rows parsed"
            return result

        result.times = times
        result.voltages_out = v_out
        result.voltages_in = v_in

        # Compute slew rate from steepest slope
        sr_pos, sr_neg = self._compute_slew_rate(times, v_out)
        result.slew_rate_pos_V_us = sr_pos
        result.slew_rate_neg_V_us = sr_neg

        log.info(
            "Transient parsed: SR+ = %.2f V/µs, SR- = %.2f V/µs",
            sr_pos or 0,
            sr_neg or 0,
        )
        return result

    def _extract_tran_table(
        self, output: str
    ) -> Tuple[List[float], List[float], List[float]]:
        times, v_out, v_in = [], [], []
        for line in output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 4:
                try:
                    int(parts[0])
                    times.append(float(parts[1]))
                    v_out.append(float(parts[2]))
                    v_in.append(float(parts[3]))
                except (ValueError, IndexError):
                    continue
        return times, v_out, v_in

    def _compute_slew_rate(
        self, times: List[float], voltages: List[float]
    ) -> Tuple[Optional[float], Optional[float]]:
        """Compute max positive and negative dV/dt in V/µs."""
        if len(times) < 2:
            return None, None

        max_pos = 0.0
        max_neg = 0.0
        for i in range(1, len(times)):
            dt = times[i] - times[i - 1]
            if dt <= 0:
                continue
            dv_dt = (voltages[i] - voltages[i - 1]) / dt
            if dv_dt > max_pos:
                max_pos = dv_dt
            if dv_dt < max_neg:
                max_neg = dv_dt

        # Convert V/s to V/µs
        return max_pos / 1e6, abs(max_neg) / 1e6


class NoiseParser:
    """Parses ngspice noise analysis output."""

    def parse(self, raw_output: str, sim_time: float = 0.0) -> NoiseResult:
        result = NoiseResult(sim_time_seconds=sim_time)
        freqs, inoise = [], []

        for line in raw_output.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3:
                try:
                    int(parts[0])
                    freqs.append(float(parts[1]))
                    inoise.append(float(parts[2]))
                except (ValueError, IndexError):
                    continue

        if not freqs:
            result.converged = False
            result.error_message = "No noise data rows parsed"
            return result

        result.frequencies = freqs
        result.input_noise = inoise

        # Extract noise at standard frequencies
        result.noise_1khz_V_rtHz = self._noise_at(freqs, inoise, 1e3)
        result.noise_10khz_V_rtHz = self._noise_at(freqs, inoise, 10e3)
        result.noise_1mhz_V_rtHz = self._noise_at(freqs, inoise, 1e6)

        log.info(
            "Noise parsed: %.1f nV/√Hz @ 1kHz",
            (result.noise_1khz_V_rtHz or 0) * 1e9,
        )
        return result

    @staticmethod
    def _noise_at(
        freqs: List[float], noise: List[float], target_freq: float
    ) -> Optional[float]:
        """Find noise value at target frequency by nearest-neighbour lookup."""
        if not freqs:
            return None
        idx = min(range(len(freqs)), key=lambda i: abs(freqs[i] - target_freq))
        return noise[idx] if noise else None
