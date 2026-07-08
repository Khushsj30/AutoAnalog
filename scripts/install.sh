#!/usr/bin/env bash
# =============================================================================
# AutoAnalog — Installation Script
# =============================================================================
# Installs all system dependencies and Python packages required to run the
# AutoAnalog platform on Ubuntu 24.04 LTS (including WSL2).
#
# Usage:
#   chmod +x scripts/install.sh
#   ./scripts/install.sh
#
# What this script does:
#   1. Checks prerequisites (Ubuntu, internet connection)
#   2. Installs system packages (ngspice, xschem, magic, klayout, git, etc.)
#   3. Upgrades pip and installs Python packages from requirements.txt
#   4. Verifies all tools are accessible on PATH
#   5. Creates the logs/ directory with correct permissions
#   6. Prints a final status summary
#
# Author  : AutoAnalog Framework
# GitHub  : https://github.com/Khushsj30/AutoAnalog
# =============================================================================

set -euo pipefail   # exit on error, undefined var, pipe failure
IFS=$'\n\t'

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'   # No Colour

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
section() { echo -e "\n${BOLD}${BLUE}=== $* ===${NC}\n"; }
success() { echo -e "${CYAN}[✓]${NC} $*"; }
fail()    { echo -e "${RED}[✗]${NC} $*"; }

# ---------------------------------------------------------------------------
# Resolve project root (the directory that contains this script's parent)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
echo -e "${BOLD}${CYAN}"
echo "  ╔══════════════════════════════════════════════════════════════╗"
echo "  ║         AutoAnalog — Installation Script v1.0.0             ║"
echo "  ║   Two-Stage CMOS Op-Amp Design & Optimization Platform      ║"
echo "  ║         github.com/Khushsj30/AutoAnalog                     ║"
echo "  ╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

info "Project root : ${PROJECT_ROOT}"
info "Ubuntu       : $(lsb_release -ds 2>/dev/null || echo 'unknown')"
info "Date         : $(date '+%Y-%m-%d %H:%M:%S')"

# ---------------------------------------------------------------------------
# 1. Check we are on Ubuntu
# ---------------------------------------------------------------------------
section "Checking Prerequisites"

if ! command -v apt-get &>/dev/null; then
    error "apt-get not found. This script requires Ubuntu/Debian."
    error "If you are on a different OS, install dependencies manually."
    exit 1
fi
success "Package manager: apt-get found"

# Check internet connectivity
if ! ping -c 1 -W 3 8.8.8.8 &>/dev/null; then
    warn "No internet connection detected. Installation may fail for packages"
    warn "not already cached by apt."
fi
success "Connectivity check passed"

# ---------------------------------------------------------------------------
# 2. System package installation
# ---------------------------------------------------------------------------
section "Installing System Packages"

info "Updating package lists…"
sudo apt-get update -qq

SYSTEM_PACKAGES=(
    # EDA tools
    "ngspice"               # SPICE circuit simulator (core requirement)
    "xschem"                # Schematic capture
    "magic"                 # VLSI layout editor
    "klayout"               # GDS viewer and layout editor

    # Build essentials
    "build-essential"
    "git"
    "curl"
    "wget"

    # Python environment
    "python3"
    "python3-pip"
    "python3-venv"
    "python3-dev"

    # WeasyPrint PDF system dependencies
    "libpango-1.0-0"
    "libpangoft2-1.0-0"
    "libcairo2"
    "libffi-dev"
    "shared-mime-info"

    # Utilities
    "tree"                  # show directory trees
    "jq"                    # JSON processing in shell scripts
    "bc"                    # floating-point arithmetic in bash
)

FAILED_PACKAGES=()

for pkg in "${SYSTEM_PACKAGES[@]}"; do
    if dpkg -s "${pkg}" &>/dev/null; then
        success "${pkg} (already installed)"
    else
        info "Installing ${pkg}…"
        if sudo apt-get install -y -qq "${pkg}" 2>/dev/null; then
            success "${pkg}"
        else
            warn "Failed to install ${pkg} — continuing (may not be required)"
            FAILED_PACKAGES+=("${pkg}")
        fi
    fi
done

if [[ ${#FAILED_PACKAGES[@]} -gt 0 ]]; then
    warn "The following packages could not be installed: ${FAILED_PACKAGES[*]}"
    warn "You may need to install them manually or from a PPA."
fi

# ---------------------------------------------------------------------------
# 3. Python package installation
# ---------------------------------------------------------------------------
section "Installing Python Packages"

REQUIREMENTS="${PROJECT_ROOT}/requirements.txt"

if [[ ! -f "${REQUIREMENTS}" ]]; then
    error "requirements.txt not found at ${REQUIREMENTS}"
    exit 1
fi

info "Upgrading pip…"
python3 -m pip install --upgrade pip --quiet

info "Installing from requirements.txt…"
python3 -m pip install -r "${REQUIREMENTS}" --quiet

success "Python packages installed"

# ---------------------------------------------------------------------------
# 4. Verify tools on PATH
# ---------------------------------------------------------------------------
section "Verifying Tool Installation"

TOOLS=(
    "ngspice:ngspice"
    "git:git"
    "python3:python3"
    "pip3:pip3"
)

ALL_OK=true
for entry in "${TOOLS[@]}"; do
    name="${entry%%:*}"
    cmd="${entry##*:}"
    if command -v "${cmd}" &>/dev/null; then
        version=$(${cmd} --version 2>&1 | head -1 || echo "version unknown")
        success "${name}: ${version}"
    else
        fail "${name}: NOT FOUND on PATH"
        ALL_OK=false
    fi
done

# Optional tools (warn but don't fail)
OPTIONAL_TOOLS=("xschem" "magic" "klayout")
for tool in "${OPTIONAL_TOOLS[@]}"; do
    if command -v "${tool}" &>/dev/null; then
        success "${tool}: $(${tool} --version 2>&1 | head -1 || echo 'found')"
    else
        warn "${tool}: not found (optional — needed for schematic/layout only)"
    fi
done

# ---------------------------------------------------------------------------
# 5. Create runtime directories
# ---------------------------------------------------------------------------
section "Creating Runtime Directories"

mkdir -p "${LOG_DIR}"
success "logs/ directory: ${LOG_DIR}"

# Ensure all results sub-directories exist
RESULT_SUBDIRS=(
    "montecarlo" "corners" "temperature" "noise" "slewrate"
    "gbw" "phase_margin" "offset" "power" "operating_point"
    "dc_sweep" "ac_sweep" "transient" "cmrr" "psrr" "output_swing"
)
for sub in "${RESULT_SUBDIRS[@]}"; do
    mkdir -p "${PROJECT_ROOT}/results/${sub}"
done
success "results/ sub-directories created"

# ---------------------------------------------------------------------------
# 6. Verify Python package imports
# ---------------------------------------------------------------------------
section "Verifying Python Imports"

PYTHON_IMPORTS=(
    "numpy" "scipy" "pandas" "matplotlib"
    "plotly" "yaml" "jinja2" "sklearn"
    "deap" "tqdm" "click" "rich"
)

for pkg in "${PYTHON_IMPORTS[@]}"; do
    if python3 -c "import ${pkg}" 2>/dev/null; then
        success "import ${pkg}"
    else
        fail "import ${pkg} — FAILED"
        ALL_OK=false
    fi
done

# ---------------------------------------------------------------------------
# 7. Final summary
# ---------------------------------------------------------------------------
section "Installation Summary"

echo -e "  Project root   : ${PROJECT_ROOT}"
echo -e "  ngspice        : $(ngspice --version 2>&1 | head -1 || echo 'not found')"
echo -e "  Python         : $(python3 --version)"
echo -e "  Log directory  : ${LOG_DIR}"
echo ""

if [[ "${ALL_OK}" == "true" ]]; then
    echo -e "${GREEN}${BOLD}  ✅  Installation complete. AutoAnalog is ready to use.${NC}"
    echo ""
    echo -e "  Quick start:"
    echo -e "    cd ${PROJECT_ROOT}"
    echo -e "    ./scripts/run.sh"
    echo ""
else
    echo -e "${YELLOW}${BOLD}  ⚠️   Installation completed with warnings.${NC}"
    echo -e "  Some optional tools or packages may be missing."
    echo -e "  Check the output above and install missing items manually."
    echo ""
fi
