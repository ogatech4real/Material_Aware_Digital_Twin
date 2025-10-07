import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from src.evaluation import summarize_kpis
from src.controller import run_controller
from src.data_generator import generate_time_index, build_dataframe
import yaml


def bootstrap_kpis(df, conf, scenario="full", n_samples=1000):
    """Bootstrap daily KPI totals to compute confidence intervals."""
    dt_h = conf["time"]["dt_minutes"]/60.0
    e_nom = conf["battery"]["e_nom_kwh"]
    # run scenario
    out = run_controller(df.copy(), conf, scenario=scenario)
    # group daily cost, degradation, emissions
    daily_cost = (out["pimp"]*out["price_import_gbp_per_kwh"] - out["pexp"]*out["price_export_gbp_per_kwh"])*dt_h
    daily_sum = daily_cost.groupby(out.index.date).sum().values
    rng = np.random.default_rng(0)
    boot_means = []
    for _ in range(n_samples):
        sample = rng.choice(daily_sum, size=len(daily_sum), replace=True)
        boot_means.append(sample.mean())
    return np.percentile(boot_means, [2.5, 97.5])


def pareto_frontier(df, conf, lambdas_batt=[0,0.5,1,2], lambdas_pv=[0,0.5,1]):
    """Sweep lambda values to explore trade-offs between cost and degradation."""
    dt_h = conf["time"]["dt_minutes"]/60.0
    e_nom = conf["battery"]["e_nom_kwh"]
    results = []
    for lb in lambdas_batt:
        for lpv in lambdas_pv:
            conf_mod = yaml.safe_load(yaml.dump(conf))
            conf_mod["economics"]["lambda_batt"] = lb
            conf_mod["economics"]["lambda_pv"] = lpv
            out = run_controller(df.copy(), conf_mod, scenario="full")
            kpi = summarize_kpis(out.join(df, rsuffix="_in"), dt_h, e_nom)
            results.append({"lambda_batt": lb, "lambda_pv": lpv,
                            "annual_cost": kpi["annual_cost_gbp"],
                            "efc": kpi["equivalent_full_cycles"]})
    return pd.DataFrame(results)


def plot_pareto(df_results, path="figs/pareto.png"):
    fig, ax = plt.subplots(figsize=(6,4))
    scatter = ax.scatter(df_results["annual_cost"], df_results["efc"],
                         c=df_results["lambda_batt"], cmap="viridis", s=80)
    ax.set_xlabel("Annual Cost [GBP]")
    ax.set_ylabel("Equivalent Full Cycles")
    ax.set_title("Pareto Frontier: Cost vs. Battery Degradation")
    fig.colorbar(scatter, ax=ax, label="lambda_batt")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    # Example run for full year or demo period
    with open("config.yaml","r") as f:
        conf = yaml.safe_load(f)
    idx = generate_time_index(periods=96*30)  # 1-month test; change to 365*96 for full year
    df = build_dataframe(idx)

    ci = bootstrap_kpis(df, conf, scenario="full")
    print("95% CI for mean daily cost:", ci)

    results = pareto_frontier(df, conf)
    results.to_csv("results/pareto.csv", index=False)
    plot_pareto(results, "figs/pareto.png")
    print("Pareto analysis saved.")
