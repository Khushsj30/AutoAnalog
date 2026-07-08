#!/usr/bin/env bash
# =============================================================================
# AutoAnalog — Simulation Runner
# =============================================================================
# Executes the full ngspice simulation suite sequentially.
# In a future release, analyses marked [PARALLEL] can be run concurrently
# using GNU parallel or Python's multiprocessing module.
#
# Usage:
#   ./scripts/simulate.sh [--quick]
#
# Options:
#   --quick    Run only operating-point and AC analyses (fast verification)
#
# Author  : AutoAnalog Framework
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${PROJECT_ROOT}/python"
export PYTHONPATH="${PYTHON}:${PYTHONPATH:-}"
export AUTOANALOG_CONFIG="${PROJECT_ROOT}/config/design_config.yaml"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'
BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${GREEN}[SIM]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERR]${NC}   $*" >&2; }

QUICK=false
[[ "${1:-}" == "--quick" ]] && QUICK=true

info "Simulation suite starting…"
info "Quick mode: ${QUICK}"

# Each analysis is driven by a Python module.
# Modules will be implemented in Chat 3.
# This script is the orchestration layer — it calls them in the correct order.

run_analysis() {
    local name="$1"
    local module="$2"
    info "Running: ${name}…"
    if python3 -m "${module}" 2>&1; then
        echo -e "${GREEN}[✓]${NC} ${name} complete"
    else
        echo -e "${RED}[✗]${NC} ${name} FAILED"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Core analyses (always run)
# ---------------------------------------------------------------------------
run_analysis "Operating Point"     "autoanalog.simulation.op"
run_analysis "AC Sweep (Bode)"     "autoanalog.simulation.ac"
run_analysis "DC Sweep"            "autoanalog.simulation.dc"

if [[ "${QUICK}" == "false" ]]; then
    # ---------------------------------------------------------------------------
    # Full suite
    # ---------------------------------------------------------------------------
    run_analysis "Transient / Slew Rate"  "autoanalog.simulation.transient"
    run_analysis "Noise Analysis"         "autoanalog.simulation.noise"
    run_analysis "CMRR"                   "autoanalog.simulation.cmrr"
    run_analysis "PSRR"                   "autoanalog.simulation.psrr"
    run_analysis "Output Swing"           "autoanalog.simulation.swing"

    # Advanced
    run_analysis "Monte Carlo"            "autoanalog.simulation.montecarlo"
    run_analysis "PVT Corners"            "autoanalog.simulation.corners"
    run_analysis "Temperature Sweep"      "autoanalog.simulation.temperature"
fi

info "All simulations complete. Results saved to: ${PROJECT_ROOT}/results/"
