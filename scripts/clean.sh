#!/usr/bin/env bash
# =============================================================================
# AutoAnalog — Clean Script
# =============================================================================
# Removes generated files while preserving source code and configuration.
#
# Usage:
#   ./scripts/clean.sh [--all]
#
# Without --all : removes results/, plots/, logs/ only
# With    --all : also removes docs/reports/ and __pycache__
#
# Author  : AutoAnalog Framework
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
info() { echo -e "${GREEN}[CLN]${NC}  $*"; }
warn() { echo -e "${YELLOW}[CLN]${NC}  $*"; }

CLEAN_ALL=false
[[ "${1:-}" == "--all" ]] && CLEAN_ALL=true

warn "Cleaning generated files from: ${PROJECT_ROOT}"

# Always clean
rm -rf "${PROJECT_ROOT}/results/"*/
rm -rf "${PROJECT_ROOT}/plots/"*/
rm -rf "${PROJECT_ROOT}/logs/"

# Re-create empty directories so git doesn't complain
find "${PROJECT_ROOT}/results" -type d | xargs mkdir -p
find "${PROJECT_ROOT}/plots"   -type d | xargs mkdir -p
mkdir -p "${PROJECT_ROOT}/logs"

if [[ "${CLEAN_ALL}" == "true" ]]; then
    rm -rf "${PROJECT_ROOT}/docs/reports/"*
    find "${PROJECT_ROOT}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "${PROJECT_ROOT}" -name "*.pyc" -delete 2>/dev/null || true
    info "Full clean complete."
else
    info "Partial clean complete (reports preserved). Use --all for full clean."
fi
