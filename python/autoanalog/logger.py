# =============================================================================
# AutoAnalog — Centralized Logging
# =============================================================================
# Every module in AutoAnalog must obtain its logger through this module.
# Never use print() in production code — use logging instead.
#
# Design decisions:
#   - One rotating file handler shared across all loggers (thread-safe).
#   - Coloured console output when running in an interactive terminal.
#   - Log level is driven by design_config.yaml so it can be changed
#     without touching source code.
#   - Module loggers are named hierarchically: "autoanalog.simulation.ac"
#     so log filters can be applied per subsystem.
#
# Usage:
#   from autoanalog.logger import get_logger
#   log = get_logger(__name__)
#   log.info("Simulation started")
#   log.warning("Phase margin below target: %.1f°", pm)
#   log.error("ngspice returned non-zero exit code: %d", rc)
# =============================================================================

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# ANSI colour codes for terminal output
# ---------------------------------------------------------------------------

class _ColourFormatter(logging.Formatter):
    """
    Logging formatter that adds ANSI colour codes to the level name when
    stdout is a real terminal (not a pipe or file redirect).
    Colours are stripped automatically when output is redirected.
    """

    _COLOURS = {
        logging.DEBUG:    "\033[36m",    # Cyan
        logging.INFO:     "\033[32m",    # Green
        logging.WARNING:  "\033[33m",    # Yellow
        logging.ERROR:    "\033[31m",    # Red
        logging.CRITICAL: "\033[35m",    # Magenta
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        if sys.stdout.isatty():
            colour = self._COLOURS.get(record.levelno, "")
            record.levelname = f"{colour}{record.levelname:<8}{self._RESET}"
        else:
            record.levelname = f"{record.levelname:<8}"
        return super().format(record)


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_setup_lock = threading.Lock()
_setup_done = False


def _setup_logging(
    level: str,
    log_dir: Path,
    log_filename: str,
    max_bytes: int,
    backup_count: int,
    format: str,     # noqa: A002  (shadows builtin — intentional for **kwargs unpacking)
    date_format: str,
) -> None:
    fmt = format
    date_fmt = date_format
    """
    Configure the root 'autoanalog' logger exactly once.
    Subsequent calls are no-ops (guarded by _setup_done flag).
    """
    global _setup_done

    with _setup_lock:
        if _setup_done:
            return

        numeric_level = getattr(logging, level.upper(), logging.INFO)

        # ------------------------------------------------------------------
        # Root package logger  (all autoanalog.* loggers inherit from this)
        # ------------------------------------------------------------------
        root_logger = logging.getLogger("autoanalog")
        root_logger.setLevel(numeric_level)

        # Prevent duplicate handlers if this function is somehow called twice
        if root_logger.handlers:
            root_logger.handlers.clear()

        # ------------------------------------------------------------------
        # Console handler  (coloured, goes to stderr so stdout stays clean)
        # ------------------------------------------------------------------
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(numeric_level)
        console_fmt = _ColourFormatter(fmt=fmt, datefmt=date_fmt)
        console_handler.setFormatter(console_fmt)
        root_logger.addHandler(console_handler)

        # ------------------------------------------------------------------
        # Rotating file handler
        # ------------------------------------------------------------------
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / log_filename

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)   # file always gets DEBUG+
        file_fmt = logging.Formatter(fmt=fmt, datefmt=date_fmt)
        file_handler.setFormatter(file_fmt)
        root_logger.addHandler(file_handler)

        # Suppress noisy third-party loggers
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("numexpr").setLevel(logging.WARNING)

        _setup_done = True


def _bootstrap_from_config() -> dict:
    """
    Try to read logging config from design_config.yaml.
    Falls back to sensible defaults if config is not yet available
    (e.g., during config_loader's own initialisation).
    """
    defaults = {
        "level":        "INFO",
        "log_dir":      Path("logs"),
        "log_filename": "autoanalog.log",
        "max_bytes":    10_485_760,
        "backup_count": 5,
        "format":       "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        "date_format":  "%Y-%m-%d %H:%M:%S",
    }

    try:
        # Import here to avoid circular import; config_loader imports logger
        from autoanalog.config_loader import get_config  # noqa: PLC0415
        cfg = get_config()
        log_cfg = cfg.raw.get("logging", {})
        log_dir_str = log_cfg.get("log_dir", "logs")

        # Resolve log_dir relative to project root
        project_root = cfg.project_root
        log_dir = (project_root / log_dir_str).resolve()

        return {
            "level":        log_cfg.get("level", defaults["level"]),
            "log_dir":      log_dir,
            "log_filename": log_cfg.get("log_filename", defaults["log_filename"]),
            "max_bytes":    log_cfg.get("max_bytes", defaults["max_bytes"]),
            "backup_count": log_cfg.get("backup_count", defaults["backup_count"]),
            "format":       log_cfg.get("format", defaults["format"]),
            "date_format":  log_cfg.get("date_format", defaults["date_format"]),
        }
    except Exception:
        # Config not yet loaded — use defaults with cwd/logs
        defaults["log_dir"] = (Path.cwd() / "logs").resolve()
        return defaults


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Return a logger named *name*, initialising the logging system on the
    first call.

    Parameters
    ----------
    name : str
        Typically ``__name__`` from the calling module.
        If the name does not already start with "autoanalog", it is
        prefixed automatically so all loggers appear under the same tree.

    Returns
    -------
    logging.Logger

    Example
    -------
    >>> log = get_logger(__name__)
    >>> log.info("Config loaded: %s", cfg)
    """
    if not _setup_done:
        params = _bootstrap_from_config()
        _setup_logging(**params)

    # Normalise name so all loggers live under "autoanalog.*"
    if not name.startswith("autoanalog"):
        name = f"autoanalog.{name}"

    return logging.getLogger(name)


def set_level(level: str) -> None:
    """
    Change the log level of the root autoanalog logger at runtime.

    Parameters
    ----------
    level : str
        One of "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
    """
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger("autoanalog").setLevel(numeric)
    # Also update all child loggers that have been created
    for name, logger in logging.Logger.manager.loggerDict.items():
        if name.startswith("autoanalog") and isinstance(logger, logging.Logger):
            logger.setLevel(numeric)


class SimulationLogger:
    """
    Context-manager wrapper that adds a per-simulation log section with
    a clear header and footer, making it easy to find simulation runs
    in long log files.

    Usage
    -----
    with SimulationLogger("ac_sweep", run_id=42) as log:
        log.info("Frequency range: 1 Hz – 1 GHz")
        run_ngspice(...)
    """

    def __init__(self, analysis_name: str, run_id: Optional[int] = None):
        self.analysis_name = analysis_name
        self.run_id = run_id
        self.log = get_logger(f"autoanalog.simulation.{analysis_name}")

    def __enter__(self) -> logging.Logger:
        divider = "=" * 60
        run_str = f" [run {self.run_id}]" if self.run_id is not None else ""
        self.log.info(divider)
        self.log.info("START  %s%s", self.analysis_name.upper(), run_str)
        self.log.info(divider)
        return self.log

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        divider = "-" * 60
        if exc_type is None:
            self.log.info("END    %s — OK", self.analysis_name.upper())
        else:
            self.log.error(
                "END    %s — FAILED: %s: %s",
                self.analysis_name.upper(),
                exc_type.__name__,
                exc_val,
            )
        self.log.info(divider)
        return False   # do not suppress exceptions
