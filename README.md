# Intelligent Degradation-Aware Dispatch for PV-Battery Energy Systems

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Dashboard](https://img.shields.io/badge/Simulation%20Dashboard-Streamlit-FF4B4B.svg)](https://pvbattdt.streamlit.app/)
[![License](https://img.shields.io/badge/License-See%20LICENSE-lightgrey.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Research%20Implementation-success.svg)](#)

A reproducible implementation of an **intelligent degradation-aware
supervisory dispatch framework** for inverter-interfaced photovoltaic
(PV) and battery energy storage systems (BESS).

The framework moves beyond cost-only energy management by embedding
**battery ageing**, **PV performance loss**, **inverter constraints**,
and **adaptive degradation weighting** into operational dispatch. It provides a lightweight, **simulation-based, digital-twin-inspired**
decision-support architecture for degradation-informed energy management.
The implemented controller is a **deterministic rule-based heuristic**, not
a numerical optimisation solver.

> **Interactive simulation dashboard:**
> [pvbattdt.streamlit.app](https://pvbattdt.streamlit.app/)

------------------------------------------------------------------------

## Framework at a Glance

<p align="center">
<img src="figs/overview%20framework.png" alt="Overview of the degradation-aware PV-battery simulation framework" width="850">
</p>
The implementation conceptually couples four functional layers:

-   **System physics** --- PV generation, battery state of charge, grid
    exchange, tariffs and inverter conversion.
-   **Asset ageing** --- reduced-order battery calendar/cycle ageing and
    PV temperature/degradation effects.
-   **Supervisory intelligence** --- degradation-weighted operational
    decisions with fixed or adaptive control weights.
-   **Evaluation** --- operating cost, equivalent full cycles,
    degradation indicators, inverter losses and runtime.

Four operating strategies are supported:

  -----------------------------------------------------------------------
  Strategy                            Operational role
  ----------------------------------- -----------------------------------
  **Baseline**                        Reference cost-oriented rule-based
                                      dispatch policy

  **Battery-Aware**                   Conservative battery operating
                                      constraints and degradation accounting

  **Battery+PV-Aware**                Uses modelled PV cell temperature
                                      to restrict battery discharge; PV
                                      ageing remains prescribed

  **Adaptive-Supervisory**            Adjusts battery degradation weight
                                      using normalised operating-state
                                      indicators
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## Research Basis

This repository accompanies:

**Intelligent degradation-aware dispatch for inverter-based
photovoltaic-battery energy systems**

**Authors:** Adewale Ogabi, Geetika Aggarwal, Palat Meethale Ushasree,
and Gobind Pillai.

The study evaluates the framework over a **full-year simulation at
15-minute resolution**, with additional tariff-sensitivity and
equal-constraints experiments, and supplements these with measured
residential demand and historical meteorological inputs.

### Reported outcomes (revised manuscript)

The annual comparison uses **35,040 intervals at 15-minute resolution**.
Results are deterministic and policy-specific; the fixed and adaptive
strategies also differ in operating constraints.

| Strategy | Annual grid operating cost (GBP) | Battery EFCs | EFC reduction vs. baseline |
| --- | ---: | ---: | ---: |
| Baseline | 1,076.27 | 281.59 | — |
| Battery-Aware | 1,075.13 | 230.81 | 18.03% |
| Battery+PV-Aware | 1,096.49 | 199.66 | 29.10% |
| Adaptive-Supervisory | 1,056.74 | 257.68 | 8.49% |

**Interpretation:** The fixed Battery+PV-Aware policy achieves the largest
cycling reduction, while the adaptive policy exhibits a different
cost–cycling balance. Because the policies have different constraints,
these headline differences **do not isolate the effect of adaptive weighting**.

Controlled equal-constraints experiments and a separate supervisory
ablation investigate the reference time-of-use (TOU), causally smoothed
TOU and independently generated variable synthetic tariffs. Under the
reference TOU, changes to the battery weighting do not change dispatch;
under the supplementary tariff profiles, weighting can influence cycling
and cost. Adaptive weighting is **conditionally useful**, not universally
superior to fixed weighting.

Supplementary simulation uses **UK-DALE measured residential demand** and
**PVGIS historical meteorological inputs** over approximately 198.25 days
(19,032 15-minute intervals). PV generation remains **model-derived**,
and electricity tariffs are prescribed. The measured-input evaluation
supports qualitative comparisons but is **not physical PV–BESS validation**.

Battery capacity-fade outputs are **model-derived relative indicators**
using illustrative, non-chemistry-calibrated coefficients; they are not
validated lifetime-extension estimates. Reported per-step runtimes are
software execution measurements, not controller hardware latency.

------------------------------------------------------------------------

## Interactive Simulation Dashboard

<p align="center">
<a href="https://pvbattdt.streamlit.app/">
<img src="figs/Streamlit%20dashboard.jpg" alt="Streamlit dashboard for the PV-battery simulation framework" width="900">
</a>
</p>
The Streamlit interface provides an interactive layer for:

-   scenario selection;
-   degradation-weight exploration;
-   dispatch visualisation;
-   battery cycling and degradation indicators;
-   operating-cost comparison;
-   PV and battery performance assessment; and
-   KPI inspection.

### [Launch the hosted dashboard →](https://pvbattdt.streamlit.app/)

------------------------------------------------------------------------

## Repository Architecture

The tree below reflects the structure documented in the supplied README;
individual scripts and generated artefacts should be checked against the
current repository checkout.

``` text
Material_Aware_Digital_Twin/
│
├── main.py
├── streamlit_app.py
├── config.yaml
├── requirements.txt
│
├── src/
│   ├── system_model.py
│   ├── controller.py
│   ├── degradation_models.py
│   ├── inverter_model.py
│   ├── optimizer.py
│   ├── adaptive_supervisor.py
│   ├── special_issue_extension.py
│   ├── evaluation.py
│   ├── analysis_extensions.py
│   └── plots.py
│
├── experiments/
│   └── run_special_issue_experiment.py
│
├── results/
│   ├── baseline.csv
│   ├── battaware.csv
│   ├── fullaware.csv
│   ├── kpis.csv
│   ├── pareto.csv
│   └── special_issue/
│
├── figs/
│   ├── overview framework.png
│   ├── Streamlit dashboard.jpg
│   ├── Workflow.png
│   ├── dispatch_full.png
│   └── ...
│
├── SPECIAL_ISSUE_EXTENSION.md
├── LICENSE
└── README.md
```

Large raw datasets are intentionally excluded from Git history. This
keeps the repository lightweight while separating source code and
reproducible research artefacts from externally sourced raw data.

------------------------------------------------------------------------

## Quick Start

### 1. Clone

``` bash
git clone https://github.com/ogatech4real/Material_Aware_Digital_Twin.git
cd Material_Aware_Digital_Twin
```

### 2. Create a virtual environment

**Windows**

``` bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux/macOS**

``` bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

``` bash
pip install -r requirements.txt
```

### 4. Run the research workflow

``` bash
python main.py
```

### 5. Launch the dashboard locally

``` bash
streamlit run streamlit_app.py
```

------------------------------------------------------------------------

## Computational Workflow

``` text
Input profiles
     ↓
PV + load + tariff inputs
     ↓
System and inverter models
     ↓
Battery / PV degradation evaluation
     ↓
Fixed or adaptive supervisory weighting
     ↓
Deterministic dispatch execution
     ↓
Operational trajectories
     ↓
KPI + degradation + cost + runtime evaluation
```

The architecture deliberately separates **physical constraints**,
**degradation modelling**, **supervisory decision logic**, and
**evaluation**, allowing individual components to evolve without
redesigning the complete workflow.

------------------------------------------------------------------------

## Outputs

Primary simulation artefacts are written under `results/`.

Typical outputs include:

-   time-resolved dispatch trajectories;
-   battery state-of-charge evolution;
-   grid import/export;
-   battery throughput and equivalent full cycles;
-   degradation-related indicators;
-   annual or horizon-level operating cost;
-   inverter conversion losses;
-   operational carbon indicators; and
-   scenario-level KPI summaries.

`results/special_issue/` contains outputs associated with the extended
supervisory experiments.

------------------------------------------------------------------------

## Reproducibility and Data

The implementation supports reproducible computational experimentation
through:

-   explicit configuration;
-   modular physical and degradation models;
-   consistent scenario definitions;
-   fixed simulation resolution;
-   stored experiment outputs; and
-   deterministic data-generation settings where applicable.

The associated research uses controlled full-year simulation and
supplementary validation with **UK-DALE residential demand data** and
**PVGIS meteorological inputs**.

Large/raw third-party datasets are not bundled in this repository. Users
should obtain external datasets from their original providers and comply
with their respective licences and citation requirements.

------------------------------------------------------------------------

## Scope and Responsible Use

This repository is a **research-grade decision-support implementation**,
not a production battery-management or safety-critical inverter-control
system.

The current framework uses reduced-order degradation models to preserve
interpretability and computational tractability. Its battery ageing
coefficients are illustrative and not calibrated to a specific chemistry.
The Battery+PV-Aware policy uses **modelled PV cell temperature** as a
supervisory signal to restrict battery discharge above a threshold;
this does **not** actively control PV material degradation. PV ageing
follows a prescribed, dispatch-independent trajectory. The PV-loss
weighting coefficient is retained for assessment and does not directly
modify dispatch.

The controlled annual experiments use deterministic synthetic operating
profiles; supplementary experiments apply measured load and historical
meteorological inputs to the same simulated system. No real-time data
synchronisation, bidirectional physical-system interaction, hardware-in-
the-loop testing or physical PV–BESS validation is demonstrated. Cost
differences are deterministic; statistical significance has not been
established. This is **not a deployed, physically synchronised digital
twin**, certified battery-health estimator or safety-critical controller.

------------------------------------------------------------------------

## Forward Roadmap

The codebase is structured for progressive extension rather than one-off
reproduction.

### Higher-fidelity asset ageing

Physics-informed and hybrid data-driven battery models incorporating
nonlinear electrochemical, thermal and resistance-growth effects.

### Uncertainty-aware operation

Probabilistic, stochastic or robust treatment of load, irradiance,
tariff and forecast uncertainty.

### Learning-enabled supervision

Operational-data-driven adaptation of degradation weights rather than
exclusive reliance on predefined stress-response rules.

### Lifecycle environmental assessment

Develop and validate a physically grounded emissions or lifecycle
assessment model before reporting carbon-related performance. **No
operational carbon index or avoided-emissions estimate is reported in
the revised manuscript.**

### Hardware and field validation

Hardware-in-the-loop testing, inverter/controller integration and
longitudinal evaluation on operational PV-BESS assets.

### Multi-context deployment

Extension from residential systems toward commercial facilities,
community energy systems and microgrids.

The longer-term architecture targets a digital twin capable of
coordinating **economics, asset health, uncertainty, environmental assessment
and operational resilience** through a unified supervisory layer.

------------------------------------------------------------------------

## Extending the Framework

The modular design supports replacement or extension of:

-   battery degradation models;
-   PV performance/degradation models;
-   dispatch heuristics;
-   adaptive supervisory policies;
-   inverter representations;
-   tariff structures;
-   carbon-intensity signals;
-   uncertainty models; and
-   validation datasets.

New methods should be benchmarked against the existing baseline and
degradation-aware scenarios under equivalent boundary conditions.

------------------------------------------------------------------------

## Citation

If you use this repository, please cite the associated manuscript or
research article once its final bibliographic record is available.
The manuscript is under revision; no final publication DOI is claimed.

``` bibtex
@article{ogabi_degradation_aware_dispatch_2026,
  title  = {Intelligent degradation-aware dispatch for inverter-based photovoltaic-battery energy systems},
  author = {Ogabi, Adewale and Aggarwal, Geetika and Ushasree, Palat Meethale and Pillai, Gobind},
  year   = {2026},
  note   = {Manuscript under revision; publication metadata pending}
}
```

The citation will be updated with the final journal metadata and DOI
when available.

------------------------------------------------------------------------

## Authors

**Adewale Ogabi**\
School of Computing, Engineering & Digital Technologies, Teesside
University, UK

**Geetika Aggarwal** *(Corresponding Author)*\
School of Computing, Engineering & Digital Technologies, Teesside
University, UK

**Palat Meethale Ushasree**\
School of Computing, Engineering & Digital Technologies, Teesside
University, UK

**Gobind Pillai**\
School of Computing, Engineering & Digital Technologies, Teesside
University, UK

------------------------------------------------------------------------

## Research Links

-   **Repository:**
    [github.com/ogatech4real/Material_Aware_Digital_Twin](https://github.com/ogatech4real/Material_Aware_Digital_Twin)
-   **Simulation Dashboard:**
    [pvbattdt.streamlit.app](https://pvbattdt.streamlit.app/)

------------------------------------------------------------------------

## Licence

See [`LICENSE`](LICENSE) for repository reuse conditions. Third-party
datasets and external services remain subject to their respective
licences and terms.

------------------------------------------------------------------------

## Project Status

**Active research implementation --- 2026**

The repository documents a simulation-based, digital-twin-inspired
degradation-aware dispatch research implementation. The revised manuscript
reports deterministic comparisons, controlled weighting experiments and
measured-input simulation, with physical validation and lifecycle
environmental assessment reserved for future work.
