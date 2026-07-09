#!/usr/bin/env bash
# =============================================================================
# AutoAnalog — Optimization Runner
# =============================================================================
# Runs the multi-objective optimization engine.
# Optimizer choice is controlled by config/design_config.yaml.
#
# Usage:
#   ./scripts/optimize.sh [--algorithm ALGO]
#
# Algorithms:
#   random     Random search (fast, good baseline)
#   nsga2      NSGA-II genetic algorithm (Pareto front)
#   bayesian   Bayesian optimization (sample-efficient)
#   all        Run all algorithms and compare (default)
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

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()  { echo -e "${GREEN}[OPT]${NC}  $*"; }
error() { echo -e "${RED}[ERR]${NC}  $*" >&2; }

ALGORITHM="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --algorithm) ALGORITHM="$2"; shift ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

info "Starting optimization engine — algorithm: ${ALGORITHM}"
info "Results will be saved to: ${PROJECT_ROOT}/results/"

python3 -m autoanalog.optimization.runner --algorithm "${ALGORITHM}"

info "Optimization complete."
info "Pareto front saved to: ${PROJECT_ROOT}/results/"
info "performance summary saved to: ${PROJECT_ROOT}/docs/reports/"
