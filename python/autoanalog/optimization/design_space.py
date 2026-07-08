# =============================================================================
# AutoAnalog — Design Space
# =============================================================================
# Defines the parameter bounds for optimization and provides sampling methods.
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import random
import math
from typing import Dict, Any, List, Tuple

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger

log = get_logger(__name__)


# Parameter bounds: [min, max] in SI units
DESIGN_SPACE: Dict[str, Tuple[float, float]] = {
    "M1_W":  (5e-6,   40e-6),    # diff pair width
    "M1_L":  (500e-9,  2e-6),    # diff pair length (longer = more gain)
    "M3_W":  (2e-6,   15e-6),    # active load width
    "M3_L":  (500e-9,  2e-6),    # active load length
    "M5_W":  (4e-6,   20e-6),    # tail current width
    "M5_L":  (500e-9,  2e-6),    # tail current length
    "M6_W":  (20e-6,  80e-6),    # 2nd stage width
    "M6_L":  (360e-9, 800e-9),   # 2nd stage length
    "M7_W":  (20e-6,  80e-6),    # 2nd stage load width
    "M7_L":  (500e-9,  2e-6),    # 2nd stage load length
    "M8_W":  (2e-6,   10e-6),    # bias width
    "M8_L":  (500e-9,  2e-6),    # bias length
    "Cc":    (1e-12,   5e-12),   # Miller cap
    "Rc":    (200.0,  1500.0),   # zero-cancel resistor
    "VBIAS": (0.40,    0.80),    # bias voltage
}

# Fixed parameters (not optimized — determined by topology)
FIXED_PARAMS: Dict[str, Any] = {
    # M2 always matches M1 (differential pair must be symmetric)
    # M4 always matches M3 (active load mirror must match)
    # These are enforced in NetlistGenerator
}


class DesignSpace:
    """
    Manages the optimization search space.

    Provides:
      - Random sampling for initial population
      - Parameter normalisation/denormalisation for optimizers
      - Constraint checking
      - Named parameter vectors
    """

    def __init__(self):
        self.cfg = get_config()
        self.bounds = DESIGN_SPACE
        self.param_names = list(DESIGN_SPACE.keys())
        self.n_params = len(self.param_names)

        log.debug("Design space: %d parameters", self.n_params)

    def sample_random(self, seed: int = None) -> Dict[str, float]:
        """
        Sample a random feasible design point.
        Uses log-uniform sampling for widths/lengths (better coverage).
        Uses linear sampling for Cc, Rc, VBIAS.
        """
        if seed is not None:
            random.seed(seed)

        params = {}
        for name, (lo, hi) in self.bounds.items():
            if name in ("Rc", "VBIAS"):
                # Linear sampling
                params[name] = lo + random.random() * (hi - lo)
            elif name == "Cc":
                # Log-uniform for capacitor
                params[name] = math.exp(
                    math.log(lo) + random.random() * math.log(hi / lo)
                )
            else:
                # Log-uniform for W and L (span multiple decades)
                params[name] = math.exp(
                    math.log(lo) + random.random() * math.log(hi / lo)
                )

        return params

    def sample_population(self, n: int, seed: int = 42) -> List[Dict[str, float]]:
        """Sample n random design points."""
        random.seed(seed)
        return [self.sample_random() for _ in range(n)]

    def to_vector(self, params: Dict[str, float]) -> List[float]:
        """Convert params dict to ordered list (for numpy/scipy optimizers)."""
        return [params[k] for k in self.param_names]

    def from_vector(self, vector: List[float]) -> Dict[str, float]:
        """Convert ordered list back to params dict."""
        return dict(zip(self.param_names, vector))

    def normalise(self, params: Dict[str, float]) -> List[float]:
        """Normalise params to [0, 1] range for Bayesian optimizer."""
        normalised = []
        for name in self.param_names:
            lo, hi = self.bounds[name]
            val = params[name]
            if name not in ("Rc", "VBIAS", "Cc"):
                # Log-space normalisation
                val_norm = (math.log(val) - math.log(lo)) / math.log(hi / lo)
            else:
                val_norm = (val - lo) / (hi - lo)
            normalised.append(max(0.0, min(1.0, val_norm)))
        return normalised

    def denormalise(self, vector: List[float]) -> Dict[str, float]:
        """Convert [0,1] normalised vector back to physical parameters."""
        params = {}
        for i, name in enumerate(self.param_names):
            lo, hi = self.bounds[name]
            val_norm = max(0.0, min(1.0, vector[i]))
            if name not in ("Rc", "VBIAS", "Cc"):
                val = math.exp(math.log(lo) + val_norm * math.log(hi / lo))
            else:
                val = lo + val_norm * (hi - lo)
            params[name] = val
        return params

    def clip(self, params: Dict[str, float]) -> Dict[str, float]:
        """Clip parameters to valid bounds."""
        clipped = {}
        for name, val in params.items():
            if name in self.bounds:
                lo, hi = self.bounds[name]
                clipped[name] = max(lo, min(hi, val))
            else:
                clipped[name] = val
        return clipped

    def is_feasible(self, params: Dict[str, float]) -> bool:
        """Check if all parameters are within bounds."""
        for name, val in params.items():
            if name in self.bounds:
                lo, hi = self.bounds[name]
                if val < lo or val > hi:
                    return False
        return True

    def baseline(self) -> Dict[str, float]:
        """Return the verified baseline design from Chat 2."""
        return {
            "M1_W": 20e-6, "M1_L": 1e-6,
            "M3_W":  4e-6, "M3_L": 1e-6,
            "M5_W":  8e-6, "M5_L": 1e-6,
            "M6_W": 40e-6, "M6_L": 500e-9,
            "M7_W": 40e-6, "M7_L": 1e-6,
            "M8_W":  4e-6, "M8_L": 1e-6,
            "Cc": 3e-12,
            "Rc": 700.0,
            "VBIAS": 0.57,
        }

    def summary(self) -> str:
        lines = ["Design Space Summary", "=" * 50]
        for name, (lo, hi) in self.bounds.items():
            if name in ("Rc", "VBIAS"):
                lines.append(f"  {name:8s}: [{lo:.3g}, {hi:.3g}]")
            else:
                lines.append(f"  {name:8s}: [{lo*1e6:.3g}µ, {hi*1e6:.3g}µ]")
        return "\n".join(lines)
