from __future__ import annotations

import sys
from pathlib import Path

# ------------------------------------------------------------------
# Project root
# ------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ------------------------------------------------------------------
# Standard / third-party imports
# ------------------------------------------------------------------
import json
import time
from datetime import datetime, timezone
import yaml
import pandas as pd

# ------------------------------------------------------------------
# Project imports - must come AFTER ROOT is added to sys.path
# ------------------------------------------------------------------
from src.controller import run_controller
from src.evaluation import summarize_kpis
from src.special_issue_extension import run_adaptive_controller


def load_conf() -> dict:
    with open(ROOT / "config.yaml", "r") as f:
        return yaml.safe_load(f)


def load_input() -> pd.DataFrame:
    path = ROOT / "data" / "sim_input.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Simulation input missing: {path}. Generate or restore the input before running.")
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    required = (
        "pv_kw_raw", "load_kw", "cell_temp_c",
        "price_import_gbp_per_kwh", "price_export_gbp_per_kwh",
    )
    missing = [name for name in required if name not in df.columns]
    if missing:
        raise ValueError(f"Simulation input is missing required columns: {missing}")
    if df.empty or not isinstance(df.index, pd.DatetimeIndex) or df.index.hasnans:
        raise ValueError("Simulation input must have a nonempty, valid datetime index")
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError("Simulation input timestamps must be unique and increasing")
    if df[list(required)].isna().any().any():
        raise ValueError("Simulation input contains missing values in required columns")
    return df


def main():
    conf = load_conf()
    df = load_input()
    dt_h = float(conf["time"]["dt_minutes"]) / 60.0
    e_nom = float(conf["battery"]["e_nom_kwh"])

    if dt_h <= 0 or e_nom <= 0:
        raise ValueError("Time step and nominal battery energy must be positive")
    if len(df) > 1:
        step_hours = df.index.to_series().diff().dropna().dt.total_seconds() / 3600.0
        if not ((step_hours - dt_h).abs() < 1e-8).all():
            raise ValueError("Input time intervals do not match config time.dt_minutes")

    outdir = ROOT / "results" / "special_issue"
    outdir.mkdir(parents=True, exist_ok=True)

    scenarios = {}
    runtimes = {}
    for name, fn in (
        ("Baseline", lambda: run_controller(df.copy(), conf, "baseline")),
        ("Batt-Aware", lambda: run_controller(df.copy(), conf, "batt")),
        ("Batt+PV-Aware", lambda: run_controller(df.copy(), conf, "full")),
        ("Adaptive-Supervisory", lambda: run_adaptive_controller(df.copy(), conf)),
    ):
        print(f"Running {name} ...")
        tic = time.perf_counter()
        sim = fn()
        runtimes[name] = time.perf_counter() - tic
        if len(sim) != len(df) or not sim.index.equals(df.index):
            raise ValueError(f"{name}: output timestamps do not match simulation input")
        required_outputs = ("soc", "pch", "pdis", "pimp", "pexp", "pv_kw_ac",
                            "pv_inverter_loss_kw", "batt_inverter_loss_kw")
        absent = [col for col in required_outputs if col not in sim.columns]
        if absent:
            raise ValueError(f"{name}: missing output columns {absent}")
        if sim[list(required_outputs)].isna().any().any():
            raise ValueError(f"{name}: non-finite or missing dispatch outputs")
        residual = (sim["pv_kw_ac"] + sim["pdis"] + sim["pimp"]
                    - sim["load_kw"] - sim["pch"] - sim["pexp"])
        if residual.abs().max() > 1e-7:
            raise ValueError(f"{name}: AC power-balance error {residual.abs().max():.3g} kW")
        scenarios[name] = sim
        sim.to_csv(outdir / f"{name.lower().replace('+','plus').replace('-','_')}.csv")

    rows = []
    for name, sim in scenarios.items():
        k = summarize_kpis(sim.join(df, rsuffix="_in"), dt_h, e_nom, conf)
        k["scenario"] = name
        k["runtime_s"] = runtimes[name]
        k["mean_step_runtime_ms"] = runtimes[name] * 1000.0 / len(sim)
        # The corrected fixed and adaptive controllers now both report inverter losses.
        k["pv_inverter_loss_kwh"] = float(sim["pv_inverter_loss_kw"].sum() * dt_h)
        k["batt_inverter_loss_kwh"] = float(sim["batt_inverter_loss_kw"].sum() * dt_h)
        if name == "Adaptive-Supervisory":
            k["mean_lambda_batt"] = float(sim["lambda_batt_t"].mean())
            k["mean_lambda_pv"] = float(sim["lambda_pv_t"].mean())
            k["mean_supervisor_stress"] = float(sim["supervisor_stress"].mean())
        rows.append(k)

    kpis = pd.DataFrame(rows).set_index("scenario")
    base_cost = float(kpis.loc["Baseline", "annual_cost_gbp"])
    base_efc = float(kpis.loc["Baseline", "equivalent_full_cycles"])
    kpis["cost_delta_vs_baseline_pct"] = (kpis["annual_cost_gbp"] / base_cost - 1.0) * 100.0
    kpis["efc_reduction_vs_baseline_pct"] = (1.0 - kpis["equivalent_full_cycles"] / base_efc) * 100.0
    kpis.to_csv(outdir / "kpis_special_issue.csv")

    meta = {
        "experiment": "Special-Issue corrected fixed and adaptive heuristic dispatch comparison",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "code_status": "revised_methodology; not the originally submitted controller",
        "dispatch_method": "deterministic rule-based heuristic; no optimisation solver",
        "runtime_note": "Wall-clock full-simulation runtime divided by steps; includes Python loop and data handling, not isolated control latency or hardware timing.",
        "adaptive_controller_module": "src/special_issue_extension.py",
        "supervisor": "interpretable fuzzy rule-based supervisory layer",
        "inverter_model": "common steady-state PV/battery inverter conversion and rating limits in all four scenarios",
        "scenario_note": "Scenario thresholds, SoC windows and thermal rules differ; differences cannot be attributed solely to degradation weights.",
        "lambda_pv_note": "PV weighting is diagnostic only because current reduced-order PV degradation is exogenous to dispatch.",
        "n_steps": len(df),
        "input_file": "data/sim_input.csv",
        "dt_minutes": conf["time"]["dt_minutes"],
    }
    with open(outdir / "experiment_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    print("\n", kpis[["annual_cost_gbp", "equivalent_full_cycles", "cost_delta_vs_baseline_pct", "efc_reduction_vs_baseline_pct", "mean_step_runtime_ms"]].round(4))
    print(f"\nSaved outputs to {outdir}")


if __name__ == "__main__":
    main()
