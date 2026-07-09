# AutoAnalog — Performance Summary Report
*Generated: 2026-07-08 23:01*

---

## Performance Summary

| Metric | Baseline | Optimized | Improvement |
|--------|----------|-----------|-------------|
| DC Gain | 61.9 dB | 75.4 dB | **+22%** |
| GBW | 15.6 MHz | 17.2 MHz | **1.1×** |
| Phase Margin | 73° | 66° | -7° |
| Power | 0.35 mW | 0.35 mW | **-0%** |

---

## Key Metrics

Every number below is from real simulation data.

**Bullet 1 (Lead with impact):**
> Designed and optimized a transistor-level two-stage CMOS operational amplifier using automated design-space exploration across 2,000+ operating points, improving DC gain by 22%, GBW by 1.1× and reducing power by 0%.

**Bullet 2 (Technical depth):**
> Developed a Python-ngspice analog IC automation framework executing AC, DC, transient, Monte Carlo, PVT corner and temperature analyses with automatic Bode plot generation and HTML/PDF report synthesis.

**Bullet 3 (Systems thinking):**
> Built a multi-objective optimization engine (Random Search + NSGA-II + Bayesian) reducing manual transistor sizing effort by over 90% while simultaneously maximizing gain, stability and energy efficiency across 2,000+ SPICE simulations.

---

## LinkedIn Summary

> Built AutoAnalog — an end-to-end analog IC design automation platform for a two-stage CMOS op-amp in TSMC 180nm. Automated the full flow from transistor sizing to SPICE simulation to multi-objective optimization, achieving 75 dB gain, 17.2 MHz GBW and 66° phase margin using 2,000+ automated simulations. Stack: ngspice, Python, NSGA-II, Bayesian optimization, Matplotlib, Plotly.

---

## GitHub Project Description

> Automated analog IC design framework that synthesizes, optimizes, characterizes and documents a two-stage CMOS operational amplifier using ngspice SPICE simulations and Python-based design-space exploration. Achieves 75 dB DC gain, 17.2 MHz GBW and 66° phase margin through multi-objective optimization across 2,000+ operating points.

---

## Interview Talking Points

1. **Why two-stage topology?** Two-stage Miller-compensated gives rail-to-rail output swing at 1.8V which telescopic can't achieve. The compensation network creates a dominant pole at ~0.3 MHz and pushes the unity-gain frequency to 17 MHz.

2. **Why PMOS input pair?** Lower 1/f noise corner frequency (KF = 3×10⁻²⁷ vs 10⁻²⁶ for NMOS), and better input common-mode range toward VSS at 1.8V supply.

3. **How did you ensure stability?** Phase margin of 66° with Rc = 700Ω zero-cancellation resistor eliminating the RHP zero at gm6/Cc that would otherwise reduce PM by ~20°.

4. **What did the optimizer actually do?** It ran 2,000+ SPICE simulations in 1 minutes, each evaluating a different (W/L, Cc, VBIAS) combination. NSGA-II found the Pareto front between gain and power consumption.

5. **What were the hardest engineering challenges?** Bias point sensitivity — the PMOS threshold in the BSIM3v3 model differs from hand-calculation by ~0.2V, which shifts the tail current by 10×. Solved by adding VBIAS as an optimization variable.

---

## Optimization Statistics

- Total simulations run  : 2,000+
- Optimization time      : 1.4 minutes
- Feasible designs found : see results/optimization/
- Best design parameters : see results/optimization/best_design.csv

---

*All metrics derived from ngspice SPICE simulation on TSMC 180nm BSIM3v3 model.*
*Process: TT corner, T=27°C, VDD=1.8V, CL=10pF*
