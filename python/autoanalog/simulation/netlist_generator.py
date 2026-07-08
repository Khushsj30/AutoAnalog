# =============================================================================
# AutoAnalog — Netlist Generator
# =============================================================================
# Generates ngspice-compatible SPICE netlists from a dictionary of design
# parameters. This is the bridge between the optimizer and the simulator.
#
# Design decisions:
#   - Template-based generation: one template per analysis type
#   - Parameters injected via string formatting (no Jinja2 dependency here)
#   - All paths resolved from config — no hardcoded paths
#   - Generates netlists to a temp directory so parallel runs don't clash
#   - Every generated netlist is self-contained (model + subcircuit inlined)
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Default design parameters (used when a key is not in the params dict)
# ---------------------------------------------------------------------------

DEFAULT_PARAMS: Dict[str, Any] = {
    # Transistor widths (meters)
    "M1_W":  20e-6,
    "M1_L":  1e-6,
    "M3_W":  4e-6,
    "M3_L":  1e-6,
    "M5_W":  8e-6,
    "M5_L":  1e-6,
    "M6_W":  40e-6,
    "M6_L":  500e-9,
    "M7_W":  40e-6,
    "M7_L":  1e-6,
    "M8_W":  4e-6,
    "M8_L":  1e-6,
    # Passive components
    "Cc":    3e-12,
    "Rc":    700.0,
    # Bias
    "VBIAS": 0.57,
}


def _fmt_W(value: float) -> str:
    """Format width/length in microns for SPICE (e.g. 20e-6 → '20U')."""
    um = value * 1e6
    if um >= 1.0:
        return f"{um:.3g}U"
    nm = value * 1e9
    return f"{nm:.3g}N"


def _fmt_C(value: float) -> str:
    """Format capacitance (e.g. 3e-12 → '3P')."""
    pf = value * 1e12
    return f"{pf:.3g}P"


def _fmt_R(value: float) -> str:
    """Format resistance (e.g. 700.0 → '700')."""
    return f"{value:.4g}"


def _fmt_V(value: float) -> str:
    """Format voltage."""
    return f"{value:.4g}"


class NetlistGenerator:
    """
    Generates ngspice SPICE netlists for AutoAnalog simulations.

    Usage
    -----
    gen = NetlistGenerator()
    netlist_path = gen.generate_ac(params={"M1_W": 20e-6, "Cc": 3e-12})
    # → writes a complete .cir file and returns its Path
    """

    def __init__(self):
        self.cfg = get_config()
        self.model_file = Path(self.cfg.paths["root"]) / "models" / "tsmc180nm_tt.lib"
        self.project_root = Path(self.cfg.paths["root"])

        if not self.model_file.exists():
            log.warning("Model file not found: %s", self.model_file)

    def _resolve_params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge user params with defaults."""
        p = dict(DEFAULT_PARAMS)
        if params:
            p.update(params)
        return p

    def _subcircuit_block(self, p: Dict[str, Any]) -> str:
        """Generate the OPAMP_2STAGE subcircuit from parameters."""
        m1w = _fmt_W(p["M1_W"])
        m1l = _fmt_W(p["M1_L"])
        m2w = m1w           # M2 always matches M1
        m2l = m1l
        m3w = _fmt_W(p["M3_W"])
        m3l = _fmt_W(p["M3_L"])
        m4w = m3w           # M4 always matches M3
        m4l = m3l
        m5w = _fmt_W(p["M5_W"])
        m5l = _fmt_W(p["M5_L"])
        m6w = _fmt_W(p["M6_W"])
        m6l = _fmt_W(p["M6_L"])
        m7w = _fmt_W(p["M7_W"])
        m7l = _fmt_W(p["M7_L"])
        m8w = _fmt_W(p["M8_W"])
        m8l = _fmt_W(p["M8_L"])
        cc  = _fmt_C(p["Cc"])
        rc  = _fmt_R(p["Rc"])

        return f""".SUBCKT OPAMP_2STAGE  INP  INN  OUT  VDD  VSS  VBIAS
M8  VBIAS  VBIAS  VDD  VDD  pmos_tt  W={m8w}  L={m8l}  AD=1P AS=1P PD=10U PS=10U
M5  VTAIL  VBIAS  VDD  VDD  pmos_tt  W={m5w}  L={m5l}  AD=1P AS=1P PD=10U PS=10U
M1  VD1    INP    VTAIL  VDD  pmos_tt  W={m1w}  L={m1l}  AD=1P AS=1P PD=10U PS=10U
M2  VOUT1  INN    VTAIL  VDD  pmos_tt  W={m2w}  L={m2l}  AD=1P AS=1P PD=10U PS=10U
M3  VD1    VD1    VSS  VSS  nmos_tt  W={m3w}  L={m3l}  AD=1P AS=1P PD=10U PS=10U
M4  VOUT1  VD1    VSS  VSS  nmos_tt  W={m4w}  L={m4l}  AD=1P AS=1P PD=10U PS=10U
Cc  VOUT1  VCOMP  {cc}
Rc  VCOMP  OUT    {rc}
M6  OUT    VOUT1  VSS  VSS  nmos_tt  W={m6w}  L={m6l}  AD=1P AS=1P PD=10U PS=10U
M7  OUT    VBIAS  VDD  VDD  pmos_tt  W={m7w}  L={m7l}  AD=1P AS=1P PD=10U PS=10U
.ENDS OPAMP_2STAGE"""

    def _header(self, title: str, p: Dict[str, Any]) -> str:
        """Common netlist header: title + model include + subcircuit."""
        model_path = str(self.model_file.resolve())
        return f""".TITLE {title}
.INCLUDE '{model_path}'

{self._subcircuit_block(p)}

* Supply
VDD   VDD   0   DC {_fmt_V(self.cfg.specifications.get('vdd', 1.8))}

* Bias voltage
VBIAS VBIAS 0   DC {_fmt_V(p['VBIAS'])}"""

    def _write(self, content: str, prefix: str) -> Path:
        """Write netlist content to a temp file and return its path."""
        tmp_dir = Path(tempfile.mkdtemp(prefix="autoanalog_"))
        netlist_path = tmp_dir / f"{prefix}_{int(time.time()*1000)}.cir"
        netlist_path.write_text(content, encoding="utf-8")
        log.debug("Netlist written: %s", netlist_path)
        return netlist_path

    # ------------------------------------------------------------------
    # Public generation methods
    # ------------------------------------------------------------------

    def generate_ac(
        self,
        params: Optional[Dict[str, Any]] = None,
        freq_start: float = 1.0,
        freq_stop: float = 1e9,
        points_per_decade: int = 100,
    ) -> Path:
        """
        Generate AC analysis netlist (Bode plot).

        Returns
        -------
        Path to the generated .cir file
        """
        p = self._resolve_params(params)
        vcm = float(self.cfg.specifications.get("vcm", 0.9))
        cl = float(self.cfg.specifications.get("cl", 10e-12))
        cl_pf = cl * 1e12

        content = f"""{self._header("AutoAnalog AC Analysis", p)}

* Inputs
VIN   INP   0   DC {vcm}  AC 1.0
VINN  INN   0   DC {vcm}

* DC feedback for stable operating point
RFEEDBACK  OUT  INN  1G

* Load
CL    OUT   0   {cl_pf:.3g}P
RL    OUT   0   100K

* Op-amp instance
XOPA  INP  INN  OUT  VDD  0  VBIAS  OPAMP_2STAGE

.OP
.AC DEC {points_per_decade} {freq_start:.3g} {freq_stop:.3g}
.PRINT AC VDB(OUT) VP(OUT)
.OPTIONS NUMDGT=6 NOMOD
.END
"""
        return self._write(content, "ac")

    def generate_op(self, params: Optional[Dict[str, Any]] = None) -> Path:
        """Generate operating point analysis netlist."""
        p = self._resolve_params(params)
        vcm = float(self.cfg.specifications.get("vcm", 0.9))

        content = f"""{self._header("AutoAnalog Operating Point", p)}

VIN   INP   0   DC {vcm}
VINN  INN   0   DC {vcm}
RFEEDBACK  OUT  INN  1G
CL    OUT   0   10P
RL    OUT   0   100K

XOPA  INP  INN  OUT  VDD  0  VBIAS  OPAMP_2STAGE

.OP
.PRINT DC V(XOPA.VTAIL) V(XOPA.VOUT1) V(OUT)
.OPTIONS NUMDGT=6 NOMOD
.END
"""
        return self._write(content, "op")

    def generate_transient(self, params: Optional[Dict[str, Any]] = None) -> Path:
        """Generate transient analysis netlist (slew rate)."""
        p = self._resolve_params(params)
        cl = float(self.cfg.specifications.get("cl", 10e-12))
        cl_pf = cl * 1e12

        content = f"""{self._header("AutoAnalog Transient Analysis", p)}

* Large-signal pulse for slew rate measurement
VIN   INP   0   PULSE(0.4 1.4 100N 1N 1N 4U 8U)

* Unity-gain buffer
XOPA  INP  OUT  OUT  VDD  0  VBIAS  OPAMP_2STAGE

CL    OUT   0   {cl_pf:.3g}P
RL    OUT   0   100K

.OP
.TRAN 1N 10U
.PRINT TRAN V(OUT) V(INP)
.OPTIONS NUMDGT=6 NOMOD
.END
"""
        return self._write(content, "tran")

    def generate_dc(self, params: Optional[Dict[str, Any]] = None) -> Path:
        """Generate DC sweep netlist (transfer characteristic + offset)."""
        p = self._resolve_params(params)

        content = f"""{self._header("AutoAnalog DC Sweep", p)}

VIN   INP   0   DC 0.9

* Unity-gain buffer
XOPA  INP  OUT  OUT  VDD  0  VBIAS  OPAMP_2STAGE

CL    OUT   0   10P
RL    OUT   0   100K

.OP
.DC VIN 0 1.8 0.005
.PRINT DC V(OUT) V(INP)
.OPTIONS NUMDGT=6 NOMOD
.END
"""
        return self._write(content, "dc")

    def generate_noise(self, params: Optional[Dict[str, Any]] = None) -> Path:
        """Generate noise analysis netlist."""
        p = self._resolve_params(params)
        vcm = float(self.cfg.specifications.get("vcm", 0.9))

        content = f"""{self._header("AutoAnalog Noise Analysis", p)}

VIN   INP   0   DC {vcm}  AC 1.0
VINN  INN   0   DC {vcm}
RFEEDBACK  OUT  INN  1G
CL    OUT   0   10P
RL    OUT   0   100K

XOPA  INP  INN  OUT  VDD  0  VBIAS  OPAMP_2STAGE

.OP
.AC DEC 20 1 100MEG
.NOISE V(OUT) VIN DEC 20 1 100MEG
.PRINT NOISE INOISE ONOISE
.OPTIONS NUMDGT=6 NOMOD
.END
"""
        return self._write(content, "noise")
