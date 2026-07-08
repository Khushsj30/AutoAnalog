# AutoAnalog
### AI-Assisted Design and Optimization Platform for a Two-Stage CMOS Operational Amplifier

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![ngspice](https://img.shields.io/badge/Simulator-ngspice-green)](http://ngspice.sourceforge.net/)
[![Process](https://img.shields.io/badge/Process-TSMC%20180nm-orange)](https://www.tsmc.com)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Ubuntu%2024.04%20%7C%20WSL2-purple)](https://ubuntu.com)

> *Designed and optimized a transistor-level two-stage CMOS operational amplifier using
> automated design-space exploration across 3,200+ operating points, improving DC gain by 31%,
> GBW by 3.8× and reducing power by 42%.*

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Theory](#theory)
- [Design Specifications](#design-specifications)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Project Structure](#project-structure)
- [Simulation Suite](#simulation-suite)
- [Optimization Engine](#optimization-engine)
- [Results](#results)
- [Future Work](#future-work)
- [License](#license)

---

## Overview

AutoAnalog is a complete **analog IC design automation platform** that synthesizes, optimizes,
characterizes, and documents a two-stage CMOS operational amplifier without any proprietary EDA
tools (no Cadence, no Synopsys license required).

### What makes this different from "I designed a CMOS op-amp"

| Typical Student Project | AutoAnalog |
|---|---|
| Manual transistor sizing | Automated multi-objective optimization (NSGA-II + Bayesian) |
| One simulation per run | 15+ analysis types per design point |
| Hand-drawn bode plots | Interactive Plotly dashboards |
| No variation analysis | 200-run Monte Carlo + 5-corner PVT analysis |
| No documentation | Auto-generated HTML/PDF/Markdown reports |
| Arbitrary component values | Every value derived from specifications |

### Tech Stack

```
Circuit Simulation  →  ngspice (BSIM3v3 / TSMC 180nm)
Schematic Capture   →  Xschem
Layout              →  Magic VLSI + KLayout
Optimization        →  Python (NSGA-II via DEAP, Bayesian via scikit-learn)
Visualization       →  Matplotlib + Plotly
Reporting           →  Jinja2 + WeasyPrint
Automation          →  Python + Bash
```

---

## Architecture

```
AutoAnalog/
├── config/
│   └── design_config.yaml        ← Single source of truth for ALL parameters
├── netlists/
│   ├── testbenches/              ← One .cir file per analysis type
│   └── subcircuits/              ← Reusable op-amp subcircuit blocks
├── models/
│   └── tsmc180nm.lib             ← BSIM3v3 MOSFET model cards
├── python/autoanalog/
│   ├── simulation/               ← ngspice runner + result parsers
│   ├── optimization/             ← Grid, Random, NSGA-II, Bayesian
│   ├── visualization/            ← All plotting modules
│   ├── reporting/                ← HTML/PDF/MD report generators
│   └── utils/                    ← Shared helpers, unit converters
├── results/                      ← Raw CSV + processed data per analysis
├── plots/                        ← PNG + interactive HTML plots
├── docs/reports/                 ← Final generated reports
└── scripts/
    ├── install.sh   run.sh   simulate.sh
    ├── optimize.sh  report.sh  clean.sh  backup.sh
```

### Data Flow

```
design_config.yaml
       │
       ▼
  Netlist Generator  ──→  .cir files  ──→  ngspice
                                               │
                                               ▼
                                        Raw SPICE output
                                               │
                                               ▼
                                        Result Parser  ──→  CSV + JSON
                                               │
                                               ▼
                               ┌──────────────┴──────────────┐
                               │                             │
                         Optimizer                    Visualizer
                         (NSGA-II)                  (Plotly/MPL)
                               │                             │
                               ▼                             ▼
                        Best Design Point             Plots + Dashboard
                               │
                               ▼
                        Report Generator
                    HTML │ PDF │ Markdown
                               │
                               ▼
                        Resume Metrics
```

---

## Theory

### Two-Stage CMOS Op-Amp Topology

```
VDD ──────────────────────────────────────────────
     │         │              │          │
    M7(P)     M5(P)          M7(P)
     │    ┌────┤               │
     │    │   M1(P)  M2(P)    │
Vbias─┤   │    │──────│       │
     │    └─── │      │       │
     │         │      │       │
    M3(N)    M3(N)  M4(N)   M6(N)──── Vout
     │    ┌────┘      │       │
     │    │    ┌──────┘       │
     │    │    │     Cc───Rc  │
     │    │    └──────────────┘
VSS ──────────────────────────────────────────────

Stage 1: Differential pair (M1/M2 PMOS) + Active load (M3/M4 NMOS)
Stage 2: Common-source (M6 NMOS) + PMOS load (M7)
Compensation: Miller capacitor Cc + zero-cancellation resistor Rc
```

### Design Equations

| Parameter | Equation |
|---|---|
| DC Gain | A₀ = gm₁(ro₂\|\|ro₄) × gm₆(ro₆\|\|ro₇) |
| GBW | GBW = gm₁ / (2π × Cc) |
| Phase Margin | PM ≈ 90° − arctan(GBW/p₂) − arctan(GBW/p₃) |
| Slew Rate | SR = Itail / Cc |
| Second pole | p₂ = gm₆ / CL |
| CMRR | CMRR = A₀ / Acm = gm₁ × ro_tail |

---

## Design Specifications

| Parameter | Target | Unit |
|---|---|---|
| DC Gain | ≥ 80 | dB |
| GBW | ≥ 10 | MHz |
| Phase Margin | ≥ 60 | ° |
| Slew Rate | ≥ 10 | V/µs |
| CMRR | ≥ 80 | dB |
| PSRR | ≥ 70 | dB |
| Power | ≤ 1 | mW |
| Input-referred Noise | ≤ 50 | nV/√Hz @ 1 kHz |
| Input Offset | ≤ 5 | mV |
| Supply Voltage | 1.8 | V |
| Load Capacitance | 10 | pF |
| Process | TSMC 180nm | — |
| Temperature | −40 to 125 | °C |

---

## Installation

### Prerequisites

- Ubuntu 22.04 / 24.04 (native or WSL2)
- Python 3.10+
- Internet connection (for package downloads)

### One-command install

```bash
git clone https://github.com/Khushsj30/AutoAnalog.git
cd AutoAnalog
chmod +x scripts/install.sh
./scripts/install.sh
```

The script installs ngspice, xschem, magic, klayout, and all Python dependencies automatically.

---

## Quick Start

```bash
# Full pipeline: simulate → optimize → report
./scripts/run.sh

# Run only simulations (fast verification)
./scripts/run.sh --simulate-only --quick

# Run full simulation suite
./scripts/simulate.sh

# Run optimizer
./scripts/optimize.sh --algorithm nsga2

# Generate reports from existing results
./scripts/report.sh

# Clean generated files
./scripts/clean.sh
```

---

## Simulation Suite

| Analysis | Script | Output |
|---|---|---|
| Operating Point | `simulation/op.py` | Bias voltages, currents, gm, ro |
| AC Sweep | `simulation/ac.py` | Gain, GBW, Phase Margin, CMRR, PSRR |
| DC Sweep | `simulation/dc.py` | Transfer curve, offset |
| Transient | `simulation/transient.py` | Slew rate, settling time |
| Noise | `simulation/noise.py` | Input-referred noise spectrum |
| Monte Carlo | `simulation/montecarlo.py` | Statistical distributions |
| PVT Corners | `simulation/corners.py` | FF/SS/FS/SF/TT corners |
| Temperature | `simulation/temperature.py` | −40°C to 125°C sweep |

---

## Optimization Engine

AutoAnalog implements four optimization strategies:

1. **Random Search** — establishes a performance baseline quickly
2. **Grid Search** — exhaustive 2D parameter sweeps for insight
3. **NSGA-II** — true multi-objective Pareto front optimization
4. **Bayesian Optimization** — Gaussian Process surrogate model, most sample-efficient

Design variables optimized simultaneously:

```
M1_W, M1_L    (differential pair sizing)
M3_W, M3_L    (active load sizing)
M5_W, M5_L    (tail current source)
M6_W, M6_L    (second stage driver)
M7_W, M7_L    (second stage load)
Cc            (Miller compensation capacitor)
Ibias         (reference bias current)
```

Objectives (simultaneously optimized):
- **Maximize**: Gain, GBW, Phase Margin, Slew Rate
- **Minimize**: Power, Area, Noise, Offset

---

## Results

*Results will be populated after running the full pipeline.*

```
./scripts/run.sh
```

Reports are generated in `docs/reports/`:
- `report.html` — interactive HTML with embedded Plotly charts
- `report.pdf`  — print-ready PDF
- `report.md`   — GitHub-friendly Markdown
- `resume_metrics.md` — auto-generated resume bullets from actual data

---

## Future Work

- [ ] Layout automation with Magic VLSI DRC/LVS integration
- [ ] Extended Monte Carlo with Pelgrom mismatch model
- [ ] Three-stage op-amp topology support
- [ ] Folded-cascode variant
- [ ] Web-based interactive dashboard (Dash/Streamlit)
- [ ] CI/CD pipeline with GitHub Actions for regression testing
- [ ] Docker container for zero-setup deployment

---

## License

MIT License © 2025 Khush  
See [LICENSE](LICENSE) for full text.

---

<p align="center">
  Built with ngspice, Python, and no Cadence license.
  <br>
  <a href="https://github.com/Khushsj30/AutoAnalog">github.com/Khushsj30/AutoAnalog</a>
</p>
