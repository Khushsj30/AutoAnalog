# =============================================================================
# AutoAnalog — ngspice Subprocess Runner
# =============================================================================
# Wraps ngspice as a Python subprocess with:
#   - Configurable timeout
#   - Stdout/stderr capture
#   - Exit code checking
#   - Automatic retry on transient failures
#   - Structured return value
#
# Author  : AutoAnalog Framework
# =============================================================================

from __future__ import annotations

import subprocess
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

from autoanalog.config_loader import get_config
from autoanalog.logger import get_logger

log = get_logger(__name__)


@dataclass
class NgspiceOutput:
    """Raw output from one ngspice run."""
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    netlist_file: Path
    success: bool
    error_message: Optional[str] = None


class NgspiceRunner:
    """
    Runs ngspice as a subprocess and returns captured output.

    Usage
    -----
    runner = NgspiceRunner()
    result = runner.run(netlist_path)
    if result.success:
        print(result.stdout)
    """

    def __init__(self):
        self.cfg = get_config()
        self.simulator = self._find_ngspice()
        self.timeout = int(
            self.cfg.raw.get("simulation", {}).get("timeout_seconds", 120)
        )

    def _find_ngspice(self) -> str:
        """Find ngspice binary on PATH."""
        # Try config value first
        sim_path = self.cfg.raw.get("simulation", {}).get("simulator_path", "ngspice")

        if shutil.which(sim_path):
            log.debug("ngspice found: %s", sim_path)
            return sim_path

        # Common alternative locations on Ubuntu
        candidates = [
            "ngspice",
            "/usr/bin/ngspice",
            "/usr/local/bin/ngspice",
        ]
        for c in candidates:
            if shutil.which(c):
                log.debug("ngspice found at: %s", c)
                return c

        log.error("ngspice not found on PATH. Run: sudo apt install ngspice")
        return "ngspice"   # will fail gracefully at run time

    def run(
        self,
        netlist_path: Path,
        retries: int = 1,
    ) -> NgspiceOutput:
        """
        Run ngspice on *netlist_path* in batch mode.

        Parameters
        ----------
        netlist_path : Path
            Absolute path to the .cir file
        retries : int
            Number of additional attempts if first run fails

        Returns
        -------
        NgspiceOutput
        """
        netlist_path = Path(netlist_path).resolve()

        if not netlist_path.exists():
            return NgspiceOutput(
                returncode=-1,
                stdout="",
                stderr="",
                elapsed_seconds=0.0,
                netlist_file=netlist_path,
                success=False,
                error_message=f"Netlist not found: {netlist_path}",
            )

        log.debug("Running ngspice: %s", netlist_path.name)

        for attempt in range(retries + 1):
            result = self._run_once(netlist_path)
            if result.success:
                return result
            if attempt < retries:
                log.warning(
                    "ngspice attempt %d failed, retrying: %s",
                    attempt + 1,
                    result.error_message,
                )
                time.sleep(0.1)

        return result

    def _run_once(self, netlist_path: Path) -> NgspiceOutput:
        """Single ngspice execution."""
        cmd = [self.simulator, "-b", str(netlist_path)]

        t_start = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,   # merge stderr into stdout
                timeout=self.timeout,
                cwd=str(self.cfg.project_root),  # run from project root
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            elapsed = time.perf_counter() - t_start
            combined = proc.stdout or ""

            # ngspice signals errors in stdout text even with returncode=0
            error_msg = self._check_for_errors(combined)
            success = (proc.returncode == 0) and (error_msg is None)

            if success:
                log.debug(
                    "ngspice OK: %s (%.2fs, %d lines)",
                    netlist_path.name,
                    elapsed,
                    combined.count("\n"),
                )
            else:
                log.warning(
                    "ngspice FAILED: %s — %s",
                    netlist_path.name,
                    error_msg or f"exit code {proc.returncode}",
                )

            return NgspiceOutput(
                returncode=proc.returncode,
                stdout=combined,
                stderr="",
                elapsed_seconds=elapsed,
                netlist_file=netlist_path,
                success=success,
                error_message=error_msg,
            )

        except subprocess.TimeoutExpired:
            elapsed = time.perf_counter() - t_start
            log.error("ngspice timeout (%.0fs): %s", elapsed, netlist_path.name)
            return NgspiceOutput(
                returncode=-2,
                stdout="",
                stderr="",
                elapsed_seconds=elapsed,
                netlist_file=netlist_path,
                success=False,
                error_message=f"Timeout after {self.timeout}s",
            )
        except FileNotFoundError:
            log.error("ngspice binary not found: %s", self.simulator)
            return NgspiceOutput(
                returncode=-3,
                stdout="",
                stderr="",
                elapsed_seconds=0.0,
                netlist_file=netlist_path,
                success=False,
                error_message="ngspice not found. Install with: sudo apt install ngspice",
            )

    @staticmethod
    def _check_for_errors(output: str) -> Optional[str]:
        """
        Scan ngspice output for error indicators.
        Returns error message string or None if clean.
        """
        error_patterns = [
            "Simulation interrupted due to error",
            "Fatal error",
            "doAnalyses: operation not supported",
            "run simulation(s) aborted",
            "Error on line",
            "could not find a valid modelname",
            "unimplemented dot command",
        ]
        lines = output.splitlines()
        for line in lines:
            for pat in error_patterns:
                if pat.lower() in line.lower():
                    return line.strip()
        return None

    def check_available(self) -> bool:
        """Return True if ngspice is accessible."""
        return shutil.which(self.simulator) is not None
