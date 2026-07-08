#!/usr/bin/env bash
# =============================================================================
# AutoAnalog — Backup Script
# =============================================================================
# Creates a timestamped archive of results, plots, and reports.
# Source code is version-controlled in git; this backs up run artifacts.
#
# Usage:
#   ./scripts/backup.sh [--output DIR]
#
# Default output: ~/autoanalog_backups/
#
# Author  : AutoAnalog Framework
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info() { echo -e "${GREEN}[BAK]${NC}  $*"; }

OUTPUT_DIR="${HOME}/autoanalog_backups"
[[ "${1:-}" == "--output" ]] && OUTPUT_DIR="${2}"

mkdir -p "${OUTPUT_DIR}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ARCHIVE="${OUTPUT_DIR}/autoanalog_backup_${TIMESTAMP}.tar.gz"

info "Creating backup archive: ${ARCHIVE}"

tar -czf "${ARCHIVE}" \
    --exclude="*.pyc" \
    --exclude="__pycache__" \
    -C "${PROJECT_ROOT}" \
    results/ plots/ docs/reports/ config/ logs/ 2>/dev/null || true

SIZE=$(du -sh "${ARCHIVE}" | cut -f1)
info "Backup complete: ${ARCHIVE} (${SIZE})"
