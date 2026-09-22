# Intelligent Degradation-Aware Dispatch for PV-Battery Energy Systems

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Dashboard](https://img.shields.io/badge/Interactive%20Digital%20Twin-Streamlit-FF4B4B.svg)](https://pvbattdt.streamlit.app/)
[![License](https://img.shields.io/badge/License-See%20LICENSE-lightgrey.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Research%20Implementation-success.svg)](#)

A reproducible implementation of an **intelligent degradation-aware
supervisory dispatch framework** for inverter-interfaced photovoltaic
(PV) and battery energy storage systems (BESS).

The framework moves beyond cost-only energy management by embedding
**battery ageing**, **PV performance loss**, **inverter constraints**,
and **adaptive degradation weighting** into operational dispatch. It
provides a lightweight digital-twin decision-support architecture for
lifecycle-aware energy management.

> **Interactive digital twin:**
> [pvbattdt.streamlit.app](https://pvbattdt.streamlit.app/)

------------------------------------------------------------------------

## Framework at a Glance

```{=html}
<p align="center">
```
`<img src="figs/overview%20framework.png" alt="Overview of the degradation-aware PV-battery digital twin framework" width="850">`{=html}
```{=html}
</p>
```
The implementation couples four functional layers:

-   **System physics** --- PV generation, battery state of charge, grid
    exchange, tariffs and inverter conversion.
-   **Asset ageing** --- reduced-order battery calendar/cycle ageing and
    PV temperature/degradation effects.
-   **Supervisory intelligence** --- degradation-weighted operational
    decisions with fixed or adaptive control weights.
-   **Evaluation** --- operating cost, equivalent full cycles,
    degradation indicators, inverter losses, carbon indicators and
    runtime.

Four operating strategies are supported:

  -----------------------------------------------------------------------
  Strategy                            Operational role
  ----------------------------------- -----------------------------------
  **Baseline**                        Cost-oriented dispatch without
                                      degradation weighting

  **Battery-Aware**                   Introduces battery degradation
                                      penalties

  **Battery+PV-Aware**                Adds PV performance/degradation
                                      awareness to supervisory evaluation

  **Adaptive-Supervisory**            Dynamically adjusts degradation
                                      weights according to
                                      operating-state stress
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## Research Basis

This repository accompanies:

**Intelligent degradation-aware dispatch for inverter-based
photovoltaic-battery energy systems**

**Authors:** Adewale Ogabi, Geetika Aggarwal, Palat Meethale Ushasree,
and Gobind Pillai.

The study evaluates the framework over a **full-year simulation at
15-minute resolution** and supplements the controlled experiments with
measured residential demand and meteorological inputs.

### Reported outcomes

-   **18--29% reduction** in annual battery cycling for the fixed
    degradation-aware strategies relative to baseline.
-   Annual operating-cost increases maintained **below 3%** in the
    full-year analysis.
-   **Adaptive-Supervisory:** **11.5% cycling reduction** relative to
    baseline with a **2.52% annual cost increase**.
-   Mean adaptive control-step runtime of approximately **0.295 ms**.
-   Measured-data validation preserves the degradation--cost trade-off,
    with **24--27% lower equivalent full cycles** while mean daily
    operating cost remains approximately **within ±1% of baseline**.

These results should be interpreted within the assumptions and
validation scope of the associated manuscript.

------------------------------------------------------------------------

## Interactive Digital Twin

```{=html}
<p align="center">
```
`<a href="https://pvbattdt.streamlit.app/">`{=html}
`<img src="figs/Streamlit%20dashboard.jpg" alt="Streamlit dashboard for the materials-aware PV-battery digital twin" width="900">`{=html}
`</a>`{=html}
```{=html}
</p>
```
The Streamlit interface provides an interactive layer for:

-   scenario selection;
-   degradation-weight exploration;
-   dispatch visualisation;
-   battery cycling and degradation indicators;
-   operating-cost comparison;
-   PV and battery performance assessment; and
-   KPI inspection.

### [Launch the hosted Digital Twin →](https://pvbattdt.streamlit.app/)

------------------------------------------------------------------------

## Repository Architecture

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
PV + load + tariff + carbon signals
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

The current framework intentionally uses reduced-order degradation
models to preserve interpretability and computational tractability. PV
degradation contributes to supervisory evaluation but remains exogenous
to lower-level battery dispatch in the present implementation.

The current experimental formulation also assumes deterministic load,
irradiance and tariff inputs. The implementation therefore should not be
interpreted as providing certified battery-health estimation,
field-deployment guarantees, or safety-critical control.

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

### Carbon-aware dispatch

Activation and validation of time-varying carbon objectives alongside
cost and asset-health objectives.

### Hardware and field validation

Hardware-in-the-loop testing, inverter/controller integration and
longitudinal evaluation on operational PV-BESS assets.

### Multi-context deployment

Extension from residential systems toward commercial facilities,
community energy systems and microgrids.

The longer-term architecture targets a digital twin capable of
coordinating **economics, asset health, uncertainty, carbon performance
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

If you use this repository, please cite the associated research article
once its final bibliographic record is available.

``` bibtex
@article{ogabi_degradation_aware_dispatch_2026,
  title  = {Intelligent degradation-aware dispatch for inverter-based photovoltaic-battery energy systems},
  author = {Ogabi, Adewale and Aggarwal, Geetika and Ushasree, Palat Meethale and Pillai, Gobind},
  year   = {2026},
  note   = {Associated research article}
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
-   **Interactive Digital Twin:**
    [pvbattdt.streamlit.app](https://pvbattdt.streamlit.app/)

------------------------------------------------------------------------

## Licence

See [`LICENSE`](LICENSE) for repository reuse conditions. Third-party
datasets and external services remain subject to their respective
licences and terms.

------------------------------------------------------------------------

## Project Status

**Active research implementation --- 2026**

The repository reflects the current degradation-aware digital-twin
architecture and provides a forward-compatible foundation for
uncertainty-aware control, higher-fidelity ageing models, carbon-aware
operation and deployment-oriented validation.
