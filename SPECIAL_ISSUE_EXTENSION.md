# Special-Issue Experiment Extension

This extension preserves the original three-scenario simulation pipeline and adds a separate, auditable experiment for an inverter-interfaced adaptive supervisory controller.

## Added modules
- `src/adaptive_supervisor.py`: interpretable fuzzy rule-based supervisory layer.
- `src/inverter_model.py`: steady-state PV/battery inverter efficiency and active-power limits.
- `src/special_issue_extension.py`: adaptive controller that reuses the existing degradation models, system parameters, SoC dynamics, and greedy lower-level dispatcher.
- `experiments/run_special_issue_experiment.py`: reproducible four-scenario experiment runner.

## Run
```bash
python experiments/run_special_issue_experiment.py
```

Outputs are written to `results/special_issue/`.

## Verified core correction
The previous Pareto routine swept `lambda_pv`, but the frozen core controller never used `lambda_pv` in dispatch. The sweep therefore implied a two-dimensional control effect that was not present. `src/analysis_extensions.py` now holds `lambda_pv` fixed and documents the limitation. No original controller behaviour was changed.

## Scientific boundary
The current reduced-order PV temperature/degradation model is exogenous to dispatch. The adaptive extension therefore records `lambda_pv(t)` as a supervisory diagnostic and does **not** force it into the dispatch price. A claim that PV degradation is actively controlled would require an additional controllable mechanism (for example curtailment/thermal/converter operating control) and new validation.

## Current synthetic full-year result
With the supplied configuration, the adaptive extension reduces EFC relative to the frozen baseline while keeping the cost delta below 3%. The exact reproducible values are in `results/special_issue/kpis_special_issue.csv`.

## Measured-data validation
The supplied repository contains `data/sim_input.csv` only. UK-DALE/PVGIS measured-input files are not present in this archive, so the extension has not fabricated a measured-data run. The same adaptive runner can be applied once the measured 15-minute input dataframe is supplied with the required columns (`load_kw`, `pv_kw_raw`, tariffs, `cell_temp_c`, and `carbon_intensity`).
