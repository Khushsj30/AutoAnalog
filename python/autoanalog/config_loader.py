# =============================================================================
# AutoAnalog — Configuration Loader
# =============================================================================
# Reads design_config.yaml and exposes a validated, typed configuration
# object used by every module in the platform.
#
# Design decisions:
#   - Singleton pattern so config is loaded exactly once per process.
#   - Pydantic-free (only stdlib + PyYAML) to minimise hard dependencies.
#   - All paths are resolved to absolute paths on first access.
#   - Unknown keys in the YAML are preserved (forward-compatible).
#
# Usage:
#   from autoanalog.config_loader import get_config
#   cfg = get_config()
#   vdd = cfg.specifications["vdd"]           # 1.8
#   root = cfg.paths.root                     # /abs/path/to/AutoAnalog
# =============================================================================

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

class _DotDict(dict):
    """
    A dict subclass that allows attribute-style access in addition to
    normal key access.  Nested dicts are converted automatically.

    Example:
        d = _DotDict({"a": {"b": 1}})
        d.a.b  # → 1
        d["a"]["b"]  # → 1  (still works)
    """

    def __init__(self, data: Dict[str, Any]):
        super().__init__(data)
        for key, value in data.items():
            if isinstance(value, dict):
                self[key] = _DotDict(value)

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(
                f"Configuration has no key '{name}'. "
                f"Check design_config.yaml."
            ) from None

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def __delattr__(self, name: str) -> None:
        try:
            del self[name]
        except KeyError:
            raise AttributeError(name) from None


# ---------------------------------------------------------------------------
# AutoAnalogConfig
# ---------------------------------------------------------------------------

class AutoAnalogConfig:
    """
    Parsed and validated representation of design_config.yaml.

    Attributes
    ----------
    project       : top-level project metadata
    paths         : resolved absolute paths
    process       : process technology parameters
    specifications: electrical design targets
    initial_design: initial transistor sizing
    optimization  : optimizer hyper-parameters
    simulation    : simulation settings
    logging       : logging configuration
    reporting     : report generation settings
    git           : version-control settings
    raw           : the raw dict (full YAML contents, unmodified)
    config_file   : absolute path to the YAML file that was loaded
    project_root  : absolute path to the project root directory
    """

    # Required top-level sections — YAML must contain all of these.
    _REQUIRED_SECTIONS = [
        "project",
        "paths",
        "process",
        "specifications",
        "initial_design",
        "optimization",
        "simulation",
        "logging",
        "reporting",
        "git",
    ]

    def __init__(self, config_file: Path):
        self.config_file: Path = config_file.resolve()
        self.project_root: Path = self.config_file.parent.parent  # config/ is one below root
        self.raw: Dict[str, Any] = self._load_yaml(self.config_file)

        self._validate_sections()
        self._resolve_paths()
        self._expose_sections()

    # ------------------------------------------------------------------
    # Private methods
    # ------------------------------------------------------------------

    @staticmethod
    def _load_yaml(path: Path) -> Dict[str, Any]:
        """Load and parse YAML from *path*."""
        if not path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {path}\n"
                f"Expected location: <project_root>/config/design_config.yaml"
            )
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ValueError(
                f"design_config.yaml must be a YAML mapping at the top level. "
                f"Got {type(data).__name__}."
            )
        return data

    def _validate_sections(self) -> None:
        """Raise ValueError if any required top-level section is missing."""
        missing = [s for s in self._REQUIRED_SECTIONS if s not in self.raw]
        if missing:
            raise ValueError(
                f"design_config.yaml is missing required section(s): {missing}\n"
                f"Please check your configuration file."
            )

    def _resolve_paths(self) -> None:
        """
        Convert all relative paths in the [paths] section to absolute paths
        anchored at *project_root*.  Creates directories that do not exist.
        """
        raw_paths: Dict[str, str] = self.raw["paths"]
        resolved: Dict[str, Path] = {}

        for key, rel_path in raw_paths.items():
            abs_path = (self.project_root / rel_path).resolve()
            resolved[key] = abs_path
            # Create directory silently; exist_ok=True is safe
            abs_path.mkdir(parents=True, exist_ok=True)

        # Always ensure logs directory exists (not listed in paths section)
        log_dir_rel = self.raw.get("logging", {}).get("log_dir", "logs")
        log_dir = (self.project_root / log_dir_rel).resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        resolved["logs"] = log_dir

        # Store back as _DotDict with Path objects
        self.raw["paths"] = {k: str(v) for k, v in resolved.items()}
        self._resolved_paths: Dict[str, Path] = resolved

    def _expose_sections(self) -> None:
        """
        Create typed _DotDict attributes for every top-level section
        so callers can use cfg.specifications.gain_db_min style access.
        """
        for section in self._REQUIRED_SECTIONS:
            setattr(self, section, _DotDict(self.raw[section]))

        # paths needs special treatment: expose Path objects not strings
        self.paths = _DotDict({k: str(v) for k, v in self._resolved_paths.items()})
        self._path_objects: Dict[str, Path] = self._resolved_paths

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_path(self, key: str) -> Path:
        """
        Return the resolved absolute Path for a key in the [paths] section.

        Parameters
        ----------
        key : str
            e.g. "results", "netlists", "logs"

        Returns
        -------
        Path
        """
        if key not in self._path_objects:
            raise KeyError(
                f"Path key '{key}' not found in configuration. "
                f"Available keys: {list(self._path_objects.keys())}"
            )
        return self._path_objects[key]

    def get_result_path(self, analysis: str) -> Path:
        """
        Return the results sub-directory for a specific analysis type.

        Parameters
        ----------
        analysis : str
            e.g. "ac_sweep", "montecarlo", "corners"
        """
        base = self._path_objects["results"]
        target = base / analysis
        target.mkdir(parents=True, exist_ok=True)
        return target

    def get_plot_path(self, plot_type: str) -> Path:
        """Return (and create) the plots sub-directory for a plot category."""
        base = self._path_objects["plots"]
        target = base / plot_type
        target.mkdir(parents=True, exist_ok=True)
        return target

    def dump(self) -> str:
        """Return a YAML string of the current (possibly modified) config."""
        return yaml.dump(self.raw, default_flow_style=False, sort_keys=False)

    def __repr__(self) -> str:
        return (
            f"AutoAnalogConfig(\n"
            f"  project  = {self.project['name']} v{self.project['version']}\n"
            f"  process  = {self.process['name']}\n"
            f"  vdd      = {self.specifications['vdd']} V\n"
            f"  gain_min = {self.specifications['gain_db_min']} dB\n"
            f"  gbw_min  = {self.specifications['gbw_min_hz']/1e6:.1f} MHz\n"
            f"  pm_min   = {self.specifications['phase_margin_min_deg']}°\n"
            f"  config   = {self.config_file}\n"
            f")"
        )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_config_instance: Optional[AutoAnalogConfig] = None
_config_lock = threading.Lock()


def get_config(config_file: Optional[Path] = None) -> AutoAnalogConfig:
    """
    Return the singleton AutoAnalogConfig instance.

    On first call the config is loaded from *config_file*.  On subsequent
    calls the cached instance is returned regardless of *config_file*.

    Parameters
    ----------
    config_file : Path, optional
        Path to design_config.yaml.  If None, the function searches for
        the file by walking up from the current working directory until
        it finds a ``config/design_config.yaml``.

    Returns
    -------
    AutoAnalogConfig
    """
    global _config_instance

    if _config_instance is not None:
        return _config_instance

    with _config_lock:
        # Double-checked locking
        if _config_instance is not None:
            return _config_instance

        if config_file is None:
            config_file = _find_config()

        _config_instance = AutoAnalogConfig(config_file)

    return _config_instance


def reset_config() -> None:
    """
    Clear the singleton.  Intended for use in unit tests only.
    In production code never call this function.
    """
    global _config_instance
    with _config_lock:
        _config_instance = None


def _find_config() -> Path:
    """
    Walk up the directory tree from cwd looking for
    ``config/design_config.yaml``.  Raises FileNotFoundError if not found.
    """
    current = Path.cwd()
    for directory in [current, *current.parents]:
        candidate = directory / "config" / "design_config.yaml"
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "Could not locate config/design_config.yaml by walking up from "
        f"{Path.cwd()}.\n"
        "Either run AutoAnalog scripts from within the project directory, "
        "or pass the config_file path explicitly to get_config()."
    )
