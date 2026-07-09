import io

def patch(path, replacements, required=True):
    p = path
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new in replacements:
        if old not in content:
            print(f"[WARN] pattern not found in {p}:\n  {old[:80]}...")
            continue
        content = content.replace(old, new, 1)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] patched {p}")

# -----------------------------------------------------------------------
# 1. README.md — fix headline vs verified-results mismatch, retire
#    NSGA-II/Bayesian as "done", soften TSMC-authenticity claim
# -----------------------------------------------------------------------
patch("README.md", [
    (
'''> *Designed and optimized a transistor-level two-stage CMOS operational amplifier using
> automated design-space exploration across 3,200+ operating points, improving DC gain by 31%,
> GBW by 3.8× and reducing power by 42%.*''',
'''> *Designed and optimized a transistor-level two-stage CMOS operational amplifier using
> automated random-search design-space exploration across 2,000+ operating points, improving
> DC gain by 22% and GBW by 1.1×, verified against ngspice SPICE simulation.*'''
    ),
    (
'''| Typical Student Project | AutoAnalog |
|---|---|
| Manual transistor sizing | Automated multi-objective optimization (NSGA-II + Bayesian) |''',
'''| Typical Student Project | AutoAnalog |
|---|---|
| Manual transistor sizing | Automated random-search optimization over 2,000+ SPICE-simulated points (NSGA-II/Bayesian scaffolded, not yet implemented) |'''
    ),
    (
'''## Optimization Engine

AutoAnalog implements four optimization strategies:

1. **Random Search** — establishes a performance baseline quickly
2. **Grid Search** — exhaustive 2D parameter sweeps for insight
3. **NSGA-II** — true multi-objective Pareto front optimization
4. **Bayesian Optimization** — Gaussian Process surrogate model, most sample-efficient''',
'''## Optimization Engine

AutoAnalog currently implements and runs:

1. **Random Search** — the optimizer actually used to produce every number in the Results
   section below: 2,000+ real ngspice simulations, each a different transistor sizing.

The config file also defines parameter bounds/hyperparameters for **Grid Search**, **NSGA-II**,
and **Bayesian Optimization** — these are scaffolded (config + design-space code exist) but not
yet implemented/executed. Listed under Future Work until they actually run.'''
    ),
    (
'''## Future Work

- [ ] Layout automation with Magic VLSI DRC/LVS integration
- [ ] Extended Monte Carlo with Pelgrom mismatch model
- [ ] Three-stage op-amp topology support
- [ ] Folded-cascode variant
- [ ] Web-based interactive dashboard (Dash/Streamlit)
- [ ] CI/CD pipeline with GitHub Actions for regression testing
- [ ] Docker container for zero-setup deployment''',
'''## Future Work

- [ ] Implement and run NSGA-II multi-objective optimization (DEAP)
- [ ] Implement and run Bayesian optimization (scikit-learn GP surrogate)
- [ ] Implement Grid Search
- [ ] Add real power measurement to the objective function (currently not simulated/scored)
- [ ] Layout automation with Magic VLSI DRC/LVS integration
- [ ] Extended Monte Carlo with Pelgrom mismatch model
- [ ] Three-stage op-amp topology support
- [ ] Folded-cascode variant
- [ ] Web-based interactive dashboard (Dash/Streamlit)
- [ ] CI/CD pipeline with GitHub Actions for regression testing
- [ ] Docker container for zero-setup deployment'''
    ),
    (
'''| Process | TSMC 180nm | — |''',
'''| Process | TSMC-180nm-class (generic BSIM3v3 model, not an NDA'd foundry PDK) | — |'''
    ),
])

# -----------------------------------------------------------------------
# 2. config/design_config.yaml — fix stale baseline GBW (12.9 -> 15.6,
#    the number that actually came out of ngspice)
# -----------------------------------------------------------------------
patch("config/design_config.yaml", [
    (
'''baseline_results:
  dc_gain_db: 61.9
  gbw_mhz: 12.9
  phase_margin_deg: 75.0
  vbias_v: 0.57
  status: verified_ngspice
  note: Baseline before optimization. GBW and PM meet spec. Gain needs optimizer.''',
'''baseline_results:
  dc_gain_db: 61.9
  gbw_mhz: 15.6
  phase_margin_deg: 72.9
  vbias_v: 0.57
  status: verified_ngspice
  note: Baseline before optimization (matches results/optimization/random_search_progress.csv row 1). GBW and PM meet spec. Gain needs optimizer.'''
    ),
])

# -----------------------------------------------------------------------
# 3. netlists/subcircuits/opamp_2stage.cir — same stale-GBW fix in the
#    header comment
# -----------------------------------------------------------------------
patch("netlists/subcircuits/opamp_2stage.cir", [
    (
'''* Verified operating point (ngspice, TSMC 180nm TT, T=27C, VBIAS=0.57V):
*   DC Gain      = 61.9 dB
*   GBW          = 12.9 MHz  [TARGET: 10 MHz ✓]
*   Phase Margin = 75°       [TARGET: 60°    ✓]''',
'''* Verified operating point (ngspice, TSMC-180nm-class model, T=27C, VBIAS=0.57V):
*   DC Gain      = 61.9 dB
*   GBW          = 15.6 MHz  [TARGET: 10 MHz  OK]
*   Phase Margin = 72.9°     [TARGET: 60 deg  OK]'''
    ),
])

# -----------------------------------------------------------------------
# 4. performance_summary.py — the actual template that generates
#    docs/reports/performance_summary.md. Drop the never-measured power claim,
#    drop NSGA-II/Bayesian claims, soften TSMC wording.
# -----------------------------------------------------------------------
patch("python/autoanalog/optimization/performance_summary.py", [
    (
'''    metrics.load_baseline(gain=61.9, gbw=12.9, pm=75.0, power=0.35)
    metrics.load_optimized(gain=82.4, gbw=14.1, pm=68.2, power=0.21)''',
'''    metrics.load_baseline(gain=61.9, gbw=15.6, pm=72.9, power=0.35)
    metrics.load_optimized(gain=75.4, gbw=17.2, pm=65.8, power=0.35)  # power not yet measured'''
    ),
    (
'''| Phase Margin | {b['phase_margin_deg']:.0f}° | {o['phase_margin_deg']:.0f}° | {pm_change:+.0f}° |
| Power | {b['power_mw']:.2f} mW | {o['power_mw']:.2f} mW | **-{power_red:.0f}%** |''',
'''| Phase Margin | {b['phase_margin_deg']:.0f}° | {o['phase_margin_deg']:.0f}° | {pm_change:+.0f}° |

*Power is not yet measured by the optimizer's objective function — not reported until it is.*'''
    ),
    (
'''> Designed and optimized a transistor-level two-stage CMOS operational amplifier using automated design-space exploration across {n_sims_str} operating points, improving DC gain by {gain_imp_str}, GBW by {gbw_ratio_str} and reducing power by {power_red_str}.''',
'''> Designed and optimized a transistor-level two-stage CMOS operational amplifier using automated random-search design-space exploration across {n_sims_str} operating points, improving DC gain by {gain_imp_str} and GBW by {gbw_ratio_str}.'''
    ),
    (
'''> Built a multi-objective optimization engine (Random Search + NSGA-II + Bayesian) reducing manual transistor sizing effort by over 90% while simultaneously maximizing gain, stability and energy efficiency across {n_sims_str} SPICE simulations.''',
'''> Built a random-search-based design-space optimization engine reducing manual transistor sizing effort significantly while simultaneously maximizing gain and phase margin across {n_sims_str} real SPICE simulations.'''
    ),
    (
'''> Built AutoAnalog — an end-to-end analog IC design automation platform for a two-stage CMOS op-amp in TSMC 180nm. Automated the full flow from transistor sizing to SPICE simulation to multi-objective optimization, achieving {o['gain_db']:.0f} dB gain, {o['gbw_mhz']:.1f} MHz GBW and {o['phase_margin_deg']:.0f}° phase margin using {n_sims_str} automated simulations. Stack: ngspice, Python, NSGA-II, Bayesian optimization, Matplotlib, Plotly.''',
'''> Built AutoAnalog — an end-to-end analog IC design automation platform for a two-stage CMOS op-amp using TSMC-180nm-class process parameters. Automated the full flow from transistor sizing to SPICE simulation to random-search-based design optimization, achieving {o['gain_db']:.0f} dB gain, {o['gbw_mhz']:.1f} MHz GBW and {o['phase_margin_deg']:.0f}° phase margin using {n_sims_str} automated simulations. Stack: ngspice, Python, Matplotlib, Plotly.'''
    ),
    (
'''> Automated analog IC design framework that synthesizes, optimizes, characterizes and documents a two-stage CMOS operational amplifier using ngspice SPICE simulations and Python-based design-space exploration. Achieves {o['gain_db']:.0f} dB DC gain, {o['gbw_mhz']:.1f} MHz GBW and {o['phase_margin_deg']:.0f}° phase margin through multi-objective optimization across {n_sims_str} operating points.''',
'''> Automated analog IC design framework that synthesizes, optimizes, characterizes and documents a two-stage CMOS operational amplifier using ngspice SPICE simulations and Python-based random-search design-space exploration. Achieves {o['gain_db']:.0f} dB DC gain, {o['gbw_mhz']:.1f} MHz GBW and {o['phase_margin_deg']:.0f}° phase margin across {n_sims_str} operating points.'''
    ),
    (
'''4. **What did the optimizer actually do?** It ran {n_sims_str} SPICE simulations in {opt_time:.0f} minutes, each evaluating a different (W/L, Cc, VBIAS) combination. NSGA-II found the Pareto front between gain and power consumption.''',
'''4. **What did the optimizer actually do?** It ran {n_sims_str} random-search SPICE simulations in {opt_time:.1f} minutes, each evaluating a different (W/L, Cc, VBIAS) combination, keeping the point that best satisfies a weighted gain/GBW/phase-margin score subject to hard PM/GBW constraints. (NSGA-II and Bayesian optimization are configured but not yet implemented — random search is the only optimizer actually executed.)'''
    ),
    (
'''*All metrics derived from ngspice SPICE simulation on TSMC 180nm BSIM3v3 model.*''',
'''*All metrics derived from ngspice SPICE simulation using a generic TSMC-180nm-class BSIM3v3 model (not an NDA'd foundry PDK).*'''
    ),
])

print("\\nAll patches applied.")
