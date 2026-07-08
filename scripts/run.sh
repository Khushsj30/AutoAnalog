#!/usr/bin/env bash
# =============================================================================
# AutoAnalog — Master Run Script
# =============================================================================
# Orchestrates the complete AutoAnalog pipeline:
#   simulate → optimize → visualize → report
#
# Usage:
#   ./scripts/run.sh [OPTIONS]
#
# Options:
#   --simulate-only     Run simulations, skip optimization
#   --optimize-only     Run optimizer only (requires prior simulation results)
#   --report-only       Generate reports from existing results
#   --quick             Run a reduced simulation suite (for testing)
#   --config PATH       Use an alternative config file
#   --help              Show this help message
#
# Author  : AutoAnalog Framework
# GitHub  : https://github.com/Khushsj30/AutoAnalog
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
section() { echo -e "\n${BOLD}${BLUE}━━━  $*  ━━━${NC}\n"; }

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON="${PROJECT_ROOT}/python"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"
LOGFILE="${LOG_DIR}/run_$(date +%Y%m%d_%H%M%S).log"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
RUN_SIMULATE=true
RUN_OPTIMIZE=true
RUN_REPORT=true
QUICK_MODE=false
CONFIG_FILE="${PROJECT_ROOT}/config/design_config.yaml"

usage() {
    grep "^# " "${BASH_SOURCE[0]}" | grep -v "^#!/" | sed 's/^# //'
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --simulate-only) RUN_OPTIMIZE=false; RUN_REPORT=false ;;
        --optimize-only) RUN_SIMULATE=false; RUN_REPORT=false ;;
        --report-only)   RUN_SIMULATE=false; RUN_OPTIMIZE=false ;;
        --quick)         QUICK_MODE=true ;;
        --config)        CONFIG_FILE="$2"; shift ;;
        --help|-h)       usage ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

export AUTOANALOG_CONFIG="${CONFIG_FILE}"
export PYTHONPATH="${PYTHON}:${PYTHONPATH:-}"

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo -e "${BOLD}${CYAN}" | tee -a "${LOGFILE}"
echo "  ╔═══════════════════════════════════════════════════════════╗" | tee -a "${LOGFILE}"
echo "  ║       AutoAnalog  —  Full Pipeline Run                   ║" | tee -a "${LOGFILE}"
echo "  ╚═══════════════════════════════════════════════════════════╝" | tee -a "${LOGFILE}"
echo -e "${NC}"

info "Start time  : $(date '+%Y-%m-%d %H:%M:%S')" | tee -a "${LOGFILE}"
info "Config file : ${CONFIG_FILE}"               | tee -a "${LOGFILE}"
info "Log file    : ${LOGFILE}"                   | tee -a "${LOGFILE}"
info "Quick mode  : ${QUICK_MODE}"                | tee -a "${LOGFILE}"

START_TIME=$(date +%s)

# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

if [[ "${RUN_SIMULATE}" == "true" ]]; then
    section "Stage 1 — Simulation Suite"
    bash "${SCRIPT_DIR}/simulate.sh" \
        ${QUICK_MODE:+--quick} 2>&1 | tee -a "${LOGFILE}"
fi

if [[ "${RUN_OPTIMIZE}" == "true" ]]; then
    section "Stage 2 — Optimization Engine"
    bash "${SCRIPT_DIR}/optimize.sh" 2>&1 | tee -a "${LOGFILE}"
fi

if [[ "${RUN_REPORT}" == "true" ]]; then
    section "Stage 3 — Report Generation"
    bash "${SCRIPT_DIR}/report.sh" 2>&1 | tee -a "${LOGFILE}"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
END_TIME=$(date +%s)
ELAPSED=$(( END_TIME - START_TIME ))
MINUTES=$(( ELAPSED / 60 ))
SECONDS=$(( ELAPSED % 60 ))

section "Pipeline Complete"
echo -e "${GREEN}${BOLD}  ✅  AutoAnalog pipeline finished in ${MINUTES}m ${SECONDS}s${NC}" | tee -a "${LOGFILE}"
echo "" | tee -a "${LOGFILE}"
echo -e "  Results   : ${PROJECT_ROOT}/results/"   | tee -a "${LOGFILE}"
echo -e "  Plots     : ${PROJECT_ROOT}/plots/"     | tee -a "${LOGFILE}"
echo -e "  Reports   : ${PROJECT_ROOT}/docs/reports/" | tee -a "${LOGFILE}"
echo -e "  Log file  : ${LOGFILE}"                 | tee -a "${LOGFILE}"
echo ""
