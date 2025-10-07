import yaml, pandas as pd, numpy as np
from src.data_generator import generate_time_index, build_dataframe
from src.controller import run_controller
from src.evaluation import summarize_kpis
from src.plots import plot_dispatch, plot_kpi_bars


def load_conf(path="config.yaml"):
    with open(path,"r") as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    conf = load_conf("config.yaml")
    idx = generate_time_index()  # 2-week demo
    df = build_dataframe(idx)
    df.to_csv("data/sim_input.csv", index=True)

    # Scenarios
    print("Running Baseline (cost-only) ...")
    base = run_controller(df.copy(), conf, scenario="baseline")
    print("Running Battery-aware ...")
    batt = run_controller(df.copy(), conf, scenario="batt")
    print("Running Battery+PV-aware ...")
    full = run_controller(df.copy(), conf, scenario="full")

    # Save
    base.to_csv("results/baseline.csv")
    batt.to_csv("results/battaware.csv")
    full.to_csv("results/fullaware.csv")

    # KPIs
    dt_h = conf["time"]["dt_minutes"]/60.0
    e_nom = conf["battery"]["e_nom_kwh"]
    kpi_base = summarize_kpis(base.join(df, rsuffix="_in"), dt_h, e_nom)
    kpi_batt = summarize_kpis(batt.join(df, rsuffix="_in"), dt_h, e_nom)
    kpi_full = summarize_kpis(full.join(df, rsuffix="_in"), dt_h, e_nom)

    kpi_df = pd.DataFrame([kpi_base, kpi_batt, kpi_full], index=["Baseline","Batt-aware","Batt+PV-aware"])
    kpi_df.to_csv("results/kpis.csv")

    # Plots
    plot_dispatch(full, "figs/dispatch_full.png")
    plot_kpi_bars(kpi_base, kpi_batt, kpi_full, "figs/kpis.png")

    print("Done. Results saved under results/ and figs/.")
