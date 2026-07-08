# =============================================================================
# AutoAnalog Python Package
# =============================================================================
# AI-Assisted Design and Optimization Platform for a Two-Stage CMOS Op-Amp
#
# Author  : Khush
# GitHub  : https://github.com/Khushsj30/AutoAnalog
# License : MIT
# =============================================================================

__version__ = "1.0.0"
__author__ = "Khush"
__email__ = ""
__github__ = "https://github.com/Khushsj30/AutoAnalog"
__description__ = (
    "Automated analog IC design framework for two-stage CMOS op-amp "
    "synthesis, optimization, and characterization using ngspice and Python."
)

# Public API — these imports are available as `from autoanalog import X`
# Each submodule is imported lazily to avoid circular dependencies and
# to allow the package to be imported even if optional dependencies
# (e.g. plotly, scipy) are not installed in the current environment.

import importlib as _importlib
import sys as _sys


def _lazy_import(module_name: str):
    """Return module on first access, raising ImportError with a clear message."""
    try:
        return _importlib.import_module(f"autoanalog.{module_name}")
    except ImportError as exc:
        raise ImportError(
            f"autoanalog.{module_name} could not be imported. "
            f"Ensure all dependencies are installed: pip install -r requirements.txt\n"
            f"Original error: {exc}"
        ) from exc


# Version tuple for programmatic comparison
VERSION = tuple(int(x) for x in __version__.split("."))

__all__ = [
    "__version__",
    "__author__",
    "__github__",
    "__description__",
    "VERSION",
]
