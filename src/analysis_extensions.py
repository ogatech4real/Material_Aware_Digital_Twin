# analysis_extensions.py
import numpy as np
import pandas as pd
from pathlib import Path
import yaml

from src.evaluation import summarize_kpis
from src.controller import run_controller
from src.data_generator import generate_time_index, build_dataframe


def _ensure_dirs():
    Path("results").mkdir(exist_ok=True)
    Path("figs").mkdir(exist_ok=True)


def bootstrap_kpis(df, conf, scenario="full", n_samples=1000, seed=0):
    """
    Bootstrap daily mean cost to produce 95% CI.
    Uses your original controller and KPI pipeline.
    """
    dt_h = conf["time"]["dt_minutes"] / 60.0
    e_nom = conf["battery"]["e_nom_kwh"]

    # Run the scenario once to get full-year (or month) series
    out = run_controller(df.copy(), conf, scenario=scenario)

    # Daily cost series
    energy_cost = (out["pimp"] * out["price_import_gbp_per_kwh"]
                   - out["pexp"] * out["price_export_gbp_per_kwh"]) * dt_h
    daily_sum = energy_cost.groupby(out.index.date).sum().values

    rng = np.random.default_rng(seed)
    boot_means = []
    for _ in range(n_samples):
        sample = rng.choice(daily_sum, size=len(daily_sum), replace=True)
        boot_means.append(sample.mean())

    return np.percentile(boot_means, [2.5, 97.5])


def pareto_frontier(df, conf,
                    lambdas_batt=(0.00, 0.10, 0.20, 0.40, 0.60, 1.00),
                    lambdas_pv=(0.00, 0.05, 0.10, 0.20)):
    """
    Sweep (lambda_batt, lambda_pv) and collect annual cost + degradation KPIs.
    Returns DataFrame with columns:
    lambda_batt, lambda_pv, annual_cost_gbp, equivalent_full_cycles, capacity_fade_pct, co2_avoided_kg
    """
    dt_h = conf["time"]["dt_minutes"] / 60.0
    e_nom = conf["battery"]["e_nom_kwh"]
    results = []

    for lb in lambdas_batt:
        for lpv in lambdas_pv:
            # Deep copy via YAML round-trip to avoid in-place edits
            conf_mod = yaml.safe_load(yaml.dump(conf))
            conf_mod["economics"]["lambda_batt"] = float(lb)
            conf_mod["economics"]["lambda_pv"] = float(lpv)

            # Full (materials-aware) scenario
            out = run_controller(df.copy(), conf_mod, scenario="full")
            kpi = summarize_kpis(out.join(df, rsuffix="_in"), dt_h, e_nom)

            results.append({
                "lambda_batt": lb,
                "lambda_pv": lpv,
                "annual_cost_gbp": kpi.get("annual_cost_gbp", np.nan),
                "equivalent_full_cycles": kpi.get("equivalent_full_cycles", np.nan),
                "capacity_fade_pct": kpi.get("capacity_fade_pct", np.nan),
                "co2_avoided_kg": kpi.get("co2_avoided_kg", np.nan),
                "arbitrage_gbp": kpi.get("arbitrage_gbp", np.nan),
            })

    df_res = pd.DataFrame(results).sort_values(["annual_cost_gbp", "equivalent_full_cycles"])
    return df_res


if __name__ == "__main__":
    _ensure_dirs()

    # ---- Load config and build data ----
    with open("config.yaml", "r") as f:
        conf = yaml.safe_load(f)

    # Use full year unless you’re doing a quick test.
    # periods = 96 * 365  # full year @ 15-min
    periods = conf.get("time", {}).get("periods", 96 * 365)
    idx = generate_time_index(periods=periods)
    df = build_dataframe(idx)

    # ---- Bootstrap CI on daily cost ----
    ci = bootstrap_kpis(df, conf, scenario="full", n_samples=1000)
    print("95% CI for mean daily cost [GBP]:", ci)

    # ---- Pareto sweep & save ----
    df_pareto = pareto_frontier(df, conf)
    df_pareto.to_csv("results/pareto.csv", index=False)
    print(f"Saved results/pareto.csv with {len(df_pareto)} rows.")
