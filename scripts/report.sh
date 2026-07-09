#!/usr/bin/env bash
# =============================================================================
# AutoAnalog — Report Generator
# =============================================================================
# Generates HTML, PDF, and Markdown reports from simulation and optimization
# results.  Also produces the performance summary and GitHub README update.
#
# Usage:
#   ./scripts/report.sh [--format FORMAT]
#
# Formats:  html | pdf | markdown | all (default: all)
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

GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[RPT]${NC}  $*"; }

FORMAT="all"
[[ "${1:-}" == "--format" ]] && FORMAT="${2:-all}"

info "Generating reports (format: ${FORMAT})…"
python3 -m autoanalog.reporting.generator --format "${FORMAT}"
info "Reports saved to: ${PROJECT_ROOT}/docs/reports/"
info "Performance summary: ${PROJECT_ROOT}/docs/reports/performance_summary.md"
