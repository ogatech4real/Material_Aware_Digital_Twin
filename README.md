## Important Notice

This repository accompanies an IEEE Access manuscript currently under peer review.  
It has been made publicly accessible **exclusively for reviewer and editorial evaluation**.  
No part of this work, including the code, data, figures, or manuscript text, may be copied, reused, or cited until the article has been formally accepted and published.  

For questions, collaboration requests, or clarification, please get in touch with the corresponding author directly at **hello@adewaleogabi.info, ogabi.adewale@gmail.com**.

---

# Materials-Aware Digital Twin for Solar–Battery Systems  
**A reproducible framework for lifecycle-aware optimisation of photovoltaic (PV) and battery energy storage systems**

---

## Overview

This repository contains the complete implementation of the **Materials-Aware Digital Twin (MAT-DT)** framework proposed in the IEEE Access manuscript:  
**“Materials-Aware Digital Twin for Solar–Battery Systems: Integrating Equipment Ageing into Smart Energy Optimisation.”**

The project integrates physical degradation models for both batteries and photovoltaic (PV) modules directly into an optimisation-based control system.  
It demonstrates how digital twins can move beyond monitoring to perform **active lifecycle management**, balancing short-term cost efficiency with long-term equipment health and carbon reduction.

---

## Research Motivation

Conventional energy management systems optimise PV–battery operation for short-term savings (e.g., tariff arbitrage) while ignoring battery wear and PV derating.  
Over time, this leads to reduced capacity, efficiency loss, and hidden lifecycle costs.

This project introduces a **materials-aware digital twin** that:
- Models real degradation processes (battery and PV ageing).  
- Uses forecasts and optimisation to inform daily operational decisions.  
- Quantifies trade-offs between cost, carbon emissions, and asset lifetime.  
- Provides a reproducible simulation platform ready for hardware-in-the-loop (HIL) integration.

---

## Core Features

- **Reduced-order ageing models** for battery and PV degradation (calendar + cycle ageing; temperature and environmental stress effects).  
- **Rolling-horizon optimisation** using [Pyomo](https://www.pyomo.org/) for cost–carbon–lifecycle balancing.  
- **Forecasting module** for solar generation, load demand, and tariffs.  
- **Bootstrap validation and Pareto analysis** for statistical confidence and trade-off exploration.  
- **Modular design**—each script handles a specific task (generation, modelling, optimisation, evaluation).  
- **Reproducible results** aligned with figures and tables presented in the IEEE Access paper.

---

## Methodology Summary

The framework follows a structured digital twin architecture linking six key modules:

1. **Data Generation:** Creates standardised 15-minute datasets representing PV, load, and tariff profiles.  
2. **Degradation Modelling:** Quantifies battery capacity fade and PV derating using empirical relationships.  
3. **Forecasting:** Predicts near-term irradiance, load, and tariffs using statistical or ML methods.  
4. **Optimisation:** Solves a rolling-horizon problem to minimise total cost, carbon emissions, and degradation.  
5. **Control Execution:** Applies the first decision at each step, updating system states iteratively.  
6. **Evaluation:** Computes KPIs (economic, lifecycle, environmental) and performs statistical validation.

---

## The workflow can be executed entirely via:

  ``bash
python main.py
All figures and tables in the paper can be regenerated from the results/ and figs/ directories.

---

##  Key Performance Indicators (KPIs)

  1. **Economic**: Annual electricity cost, arbitrage revenue, peak import reduction, LCOS.
  2. **Lifecycle**: Battery capacity fade (%), equivalent full cycles, PV performance ratio decline.
  3. **Environmental**: Avoided CO₂ emissions (kgCO₂e).
  4. **Reliability**: Demand served (%), reserve margin compliance.

---

## Simulation Results (Summary)

  - Battery wear reduction by 10–20% compared to the cost-only control.
  - PV degradation slowed by ≈0.1%/year.
  - Cost difference < 3% from baseline while improving lifetime economics.
  - Results statistically validated via bootstrapping and Pareto trade-off analysis.

---

## Reproducibility and Usage Guide

### 1. Repository Structure

```
├── main.py                     # Entry point for running full simulations
├── config.yaml                 # Global configuration file (time, system, economics)
├── data/                       # Input and generated time-series data
│   └── sim_input.csv           # Automatically created synthetic simulation input
├── src/                        # Core model modules
│   ├── data_generator.py       # Generates irradiance, load, and tariff time-series
│   ├── controller.py           # Scenario-aware dispatch logic
│   ├── degradation_models.py   # Calendar and cyclic ageing models
│   ├── optimizer.py            # Greedy heuristic optimiser
│   ├── evaluation.py           # KPI computation and summarisation
│   ├── plots.py                # Visualisation routines for KPIs and dispatch
│   └── analysis_extensions.py  # Pareto and statistical analysis
├── results/                    # Generated outputs (CSV, figures, metadata)
└── figs/                       # All plots saved in PNG format
```

### 2. Running the Simulation

Ensure that Python 3.10+ and the dependencies in `requirements.txt` are installed.

```bash
pip install -r requirements.txt
```

Then execute the full simulation workflow:

```bash
python main.py
```

On first execution, the script will automatically:

* Generate synthetic input data (`data/sim_input.csv`) based on configuration parameters.
* Run the simulation for all three scenarios:

  * **Baseline (Cost-Only)**
  * **Batt-Aware (Battery Degradation)**
  * **Batt+PV-Aware (Full Degradation)**
* Produce time-series outputs in `results/`.
* Generate all figures in `figs/` (e.g., `kpis_annual_cost_gbp.png`, `dispatch_full.png`, `pareto.png`).

### 3. Reproducing Figures and Tables

All figures in the manuscript correspond directly to PNGs generated by the code:

| Manuscript Figure                  | File Generated                         |
| ---------------------------------- | -------------------------------------- |
| Figure 3a (Annual Cost)            | `figs/kpis_annual_cost_gbp.png`        |
| Figure 3b (Equivalent Full Cycles) | `figs/kpis_equivalent_full_cycles.png` |
| Figure 3c (CO₂ Avoided)            | `figs/kpis_co2_avoided_kg.png`         |
| Figure 4 (Dispatch Profile)        | `figs/dispatch_full.png`               |
| Figure 5 (Pareto Frontier)         | `figs/pareto.png`                      |

Tables in the manuscript can be directly cross-referenced with the generated `results/kpis.csv` file. All numerical values (e.g., annual cost, EFCs, CO₂ avoided) are computed automatically by `evaluation.py` and are traceable to the corresponding simulation steps.

### 4. Running the Pareto Analysis

The Pareto analysis explores trade-offs between annual cost and degradation as a function of the weighting parameters $(\lambda_b, \lambda_{pv})$.

To reproduce Figure 5:

```bash
python main.py  # automatically triggers pareto_sweep() in analysis_extensions.py
```

This generates:

* `results/pareto.csv` — data points across $(\lambda_b, \lambda_{pv})$ grid.
* `figs/pareto.png` — Pareto frontier plot.

### 5. Regenerating Data

If you wish to regenerate simulation inputs (e.g., after editing `config.yaml`), delete the existing file:

```bash
rm data/sim_input.csv
```

Then rerun `python main.py` — the input dataset will be automatically recreated based on the modified configuration.

### 6. Recommended Workflow for Verification

1. Clone the repository and install dependencies.
2. Open and adjust `config.yaml` if needed (e.g., battery capacity, tariff settings).
3. Run `python main.py`.
4. Inspect results in `results/` and figures in `figs/`.
5. Compare values in `results/kpis.csv` with manuscript tables.
6. Optionally, rerun Pareto analysis for extended trade-off exploration.

### 7. Notes on Reproducibility

* All random number generators in `data_generator.py` are seeded for deterministic reproducibility.
* Each module is standalone and can be executed independently for testing.
* The system has been validated to reproduce manuscript figures within a <2% variance tolerance across platforms.

---

**Citation:** If using this repository or framework in academic work, please cite the manuscript or the associated conference/journal publication describing the MATT-AWARE Digital Twin framework.



---

## Citation

If you use this repository, please cite the following paper:

A. Ogabi, G. Aggarwal, P. M. Ushasree, and A. Alabi,

“Materials-Aware Digital Twin for Solar–Battery Systems: Integrating Equipment Ageing into Smart Energy Optimisation,”

IEEE Access, 2025. DOI: to be assigned.

---

## License

This repository is distributed under the MIT License.
You are free to use, modify, and distribute this work with appropriate credit.


---

## Contact

- Author: Adewale Ogabi
- Affiliation: School of Computing, Engineering, and Digital Technologies, Teesside University, UK
- Email: hello@adewaleogabi.info, ogabi.adewale@gmail.com

Repository: https://github.com/ogatech4real/Material_Aware_Digital_Twin


