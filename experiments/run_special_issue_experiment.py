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
    return pd.read_csv(ROOT / "data" / "sim_input.csv", index_col=0, parse_dates=True)


def main():
    conf = load_conf()
    df = load_input()
    dt_h = float(conf["time"]["dt_minutes"]) / 60.0
    e_nom = float(conf["battery"]["e_nom_kwh"])

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
        scenarios[name] = sim
        sim.to_csv(outdir / f"{name.lower().replace('+','plus').replace('-','_')}.csv")

    rows = []
    for name, sim in scenarios.items():
        k = summarize_kpis(sim.join(df, rsuffix="_in"), dt_h, e_nom, conf)
        k["scenario"] = name
        k["runtime_s"] = runtimes[name]
        k["mean_step_runtime_ms"] = runtimes[name] * 1000.0 / len(sim)
        if name == "Adaptive-Supervisory":
            k["mean_lambda_batt"] = float(sim["lambda_batt_t"].mean())
            k["mean_lambda_pv"] = float(sim["lambda_pv_t"].mean())
            k["mean_supervisor_stress"] = float(sim["supervisor_stress"].mean())
            k["pv_inverter_loss_kwh"] = float(sim["pv_inverter_loss_kw"].sum() * dt_h)
            k["batt_inverter_loss_kwh"] = float(sim["batt_inverter_loss_kw"].sum() * dt_h)
        rows.append(k)

    kpis = pd.DataFrame(rows).set_index("scenario")
    base_cost = float(kpis.loc["Baseline", "annual_cost_gbp"])
    base_efc = float(kpis.loc["Baseline", "equivalent_full_cycles"])
    kpis["cost_delta_vs_baseline_pct"] = (kpis["annual_cost_gbp"] / base_cost - 1.0) * 100.0
    kpis["efc_reduction_vs_baseline_pct"] = (1.0 - kpis["equivalent_full_cycles"] / base_efc) * 100.0
    kpis.to_csv(outdir / "kpis_special_issue.csv")

    meta = {
        "experiment": "Special-Issue adaptive supervisory + inverter extension",
        "core_controller_preserved": True,
        "adaptive_controller_module": "src/special_issue_extension.py",
        "supervisor": "interpretable fuzzy rule-based supervisory layer",
        "inverter_model": "steady-state efficiency and active-power rating constraints",
        "lambda_pv_note": "PV weighting is diagnostic only because current reduced-order PV degradation is exogenous to dispatch.",
        "n_steps": len(df),
        "dt_minutes": conf["time"]["dt_minutes"],
    }
    with open(outdir / "experiment_metadata.json", "w") as f:
        json.dump(meta, f, indent=2)

    print("\n", kpis[["annual_cost_gbp", "equivalent_full_cycles", "cost_delta_vs_baseline_pct", "efc_reduction_vs_baseline_pct", "mean_step_runtime_ms"]].round(4))
    print(f"\nSaved outputs to {outdir}")


if __name__ == "__main__":
    main()
