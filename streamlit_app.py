from __future__ import annotations
import os
from typing import Dict, Tuple

import streamlit as st
import pandas as pd
import numpy as np
import yaml
import plotly.express as px

from src.data_generator import generate_time_index, build_dataframe
from src.controller import run_controller
from src.evaluation import summarize_kpis
from src.analysis_extensions import pareto_sweep


# ---------- Config / IO helpers ----------

@st.cache_resource
def load_conf(path: str = "config.yaml") -> Dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


@st.cache_data
def load_or_generate_inputs(conf: Dict, regen: bool = False) -> pd.DataFrame:
    """
    Load data/sim_input.csv if present; otherwise generate it.
    regen=True forces regeneration using current config.
    """
    path = "data/sim_input.csv"
    if regen or not os.path.exists(path):
        os.makedirs("data", exist_ok=True)
        idx = generate_time_index(
            start=conf.get("time", {}).get("start", "2024-01-01"),
            periods=int(conf.get("time", {}).get("periods", 96 * 365)),
            freq=f"{conf['time']['dt_minutes']}min",
        )
        df = build_dataframe(idx, conf)
        df.to_csv(path)
    return pd.read_csv(path, index_col=0, parse_dates=True)


def _update_lambdas(conf: Dict, lam_batt: float, lam_pv: float) -> Dict:
    """Return a shallow copy of conf with updated λ_batt / λ_pv values."""
    new = dict(conf)
    econ = dict(new.get("economics", {}))
    econ["lambda_batt"] = lam_batt
    econ["lambda_batt_full"] = lam_batt  # keep full-aware aligned unless you want them separate
    econ["lambda_pv"] = lam_pv
    new["economics"] = econ
    return new


def _run_scenarios(df_in: pd.DataFrame, conf: Dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Run Baseline, Batt-Aware, Full-aware and return:
      - baseline dispatch df
      - batt-aware dispatch df
      - full-aware dispatch df
      - KPI dataframe (index = scenarios)
    """
    dt_h = conf["time"]["dt_minutes"] / 60.0
    e_nom = conf["battery"]["e_nom_kwh"]

    base = run_controller(df_in.copy(), conf, scenario="baseline")
    batt = run_controller(df_in.copy(), conf, scenario="batt")
    full = run_controller(df_in.copy(), conf, scenario="full")

    kb = summarize_kpis(base.join(df_in, rsuffix="_in"), dt_h, e_nom, conf)
    ka = summarize_kpis(batt.join(df_in, rsuffix="_in"), dt_h, e_nom, conf)
    kf = summarize_kpis(full.join(df_in, rsuffix="_in"), dt_h, e_nom, conf)

    kpi_df = pd.DataFrame([kb, ka, kf], index=["Baseline", "Batt-Aware", "Batt+PV-Aware"])
    return base, batt, full, kpi_df


def _load_pareto() -> pd.DataFrame | None:
    path = "results/pareto.csv"
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    # Expect columns: lambda_batt, lambda_pv, annual_cost_gbp, equivalent_full_cycles, etc.
    return df


# ---------- Plot helpers ----------

def _kpi_bar_fig(kpis: pd.DataFrame, metric: str, title: str, y_label: str) -> px.bar:
    df = kpis.reset_index().rename(columns={"index": "Scenario"})
    base_val = df.loc[df["Scenario"] == "Baseline", metric].iloc[0]

    df["Δ_vs_Base_%"] = (df[metric] - base_val) / base_val * 100.0
    df["Label"] = df.apply(
        lambda r: f"{r[metric]:.0f} ({r['Δ_vs_Base_%']:+.1f}%)" if r["Scenario"] != "Baseline"
        else f"{r[metric]:.0f}",
        axis=1,
    )

    fig = px.bar(
        df,
        x="Scenario",
        y=metric,
        color="Scenario",
        text="Label",
        color_discrete_map={
            "Baseline": "#4C72B0",
            "Batt-Aware": "#55A868",
            "Batt+PV-Aware": "#C44E52",
        },
        title=title,
    )
    fig.update_traces(textposition="outside")
    fig.update_yaxes(title=y_label, rangemode="tozero")
    fig.update_layout(
        xaxis_title=None,
        legend_title=None,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _dispatch_fig(df: pd.DataFrame, title_suffix: str = "Battery+PV-Aware") -> px.line:
    """
    Simple SoC + power overlay for first 7 days (scaled onto two y-axes).
    If your reviewers prefer the 3-panel Matplotlib PNG, you can instead
    just show the static image from figs/dispatch_full.png.
    """
    if isinstance(df.index, pd.DatetimeIndex):
        start = df.index.min()
        end = start + pd.Timedelta(days=7)
        dfw = df.loc[(df.index >= start) & (df.index < end)].copy()
    else:
        dfw = df.iloc[:7 * 96].copy()

    df_plot = pd.DataFrame({
        "time": dfw.index,
        "SoC": dfw["soc"].clip(0, 1.0).values,
        "P_ch": dfw["pch"].values,
        "P_dis": dfw["pdis"].values,
        "Import": dfw["pimp"].values,
        "Export": dfw["pexp"].values,
    })

    # Plot SoC and net battery power on separate axes for a “live” feel
    fig = px.line(
        df_plot,
        x="time",
        y=["SoC", "P_ch", "P_dis", "Import", "Export"],
        title=f"Seven-Day Dispatch Profile – {title_suffix}",
    )
    fig.update_layout(
        xaxis_title="Time",
        yaxis_title="Per-Unit / kW",
        legend_title=None,
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def _pareto_fig(df: pd.DataFrame) -> px.scatter:
    fig = px.scatter(
        df,
        x="equivalent_full_cycles",
        y="annual_cost_gbp",
        color="lambda_batt",
        size="lambda_pv",
        color_continuous_scale="Viridis",
        labels={
            "equivalent_full_cycles": "Equivalent Full Cycles [year]",
            "annual_cost_gbp": "Annual Cost [£]",
            "lambda_batt": "λ_batt",
            "lambda_pv": "λ_pv",
        },
        title="Pareto Frontier: Cost vs. Battery Wear",
    )
    fig.update_layout(
        margin=dict(l=40, r=20, t=60, b=40),
        coloraxis_colorbar=dict(title="λ_batt"),
    )
    return fig


# ---------- Streamlit layout ----------

def main():
    conf = load_conf()

    st.set_page_config(
        page_title="Materials-Aware Digital Twin Dashboard",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Hide default Streamlit chrome to keep it “product-like”
    st.markdown(
        """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}
        .block-container {padding-top: 1.2rem; padding-bottom: 1.2rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )

    # --- Header / Hero ---
    st.markdown(
        "<h2 style='margin-bottom:0.2rem;'>Materials-Aware Digital Twin for PV–Battery Systems</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#555;margin-top:0;'>Interactive dashboard for cost, lifecycle, and CO₂ performance under different control policies.</p>",
        unsafe_allow_html=True,
    )

    # --- Control strip ---
    c1, c2, c3, c4 = st.columns([2, 2, 2, 2])

    with c1:
        regen = st.checkbox("Regenerate synthetic year", value=False,
                            help="Rebuild input profiles from config.yaml")

    with c2:
        lam_batt = st.slider("Battery degradation weight λ_batt",
                             min_value=0.0, max_value=2.0, value=float(conf.get("economics", {}).get("lambda_batt", 0.8)),
                             step=0.1)
    with c3:
        lam_pv = st.slider("PV degradation weight λ_pv",
                           min_value=0.0, max_value=2.0, value=float(conf.get("economics", {}).get("lambda_pv", 0.5)),
                           step=0.1)
    with c4:
        run_btn = st.button("Run Simulation", type="primary")

    # --- Core compute path ---
    if run_btn or True:
        # Update λ-weights on the fly (do not overwrite file)
        conf_eff = _update_lambdas(conf, lam_batt=lam_batt, lam_pv=lam_pv)
        df_in = load_or_generate_inputs(conf_eff, regen=regen)
        base, batt, full, kpis = _run_scenarios(df_in, conf_eff)

        # --- KPI tiles ---
        st.markdown("### Key annual indicators")
        k1, k2, k3 = st.columns(3)

        base_cost = kpis.loc["Baseline", "annual_cost_gbp"]
        base_efc = kpis.loc["Baseline", "equivalent_full_cycles"]
        base_co2 = kpis.loc["Baseline", "co2_avoided_kg"]

        def _delta(v, base):
            return f"{((v - base)/base)*100:.1f} %"

        k1.metric(
            "Annual Cost [£]",
            f"{base_cost:,.0f}",
            delta=None,
        )
        k1.metric(
            "Batt-Aware",
            f"{kpis.loc['Batt-Aware','annual_cost_gbp']:,.0f}",
            delta=_delta(kpis.loc["Batt-Aware","annual_cost_gbp"], base_cost),
        )
        k1.metric(
            "Batt+PV-Aware",
            f"{kpis.loc['Batt+PV-Aware','annual_cost_gbp']:,.0f}",
            delta=_delta(kpis.loc["Batt+PV-Aware","annual_cost_gbp"], base_cost),
        )

        k2.metric(
            "EFCs – Baseline [cycles]",
            f"{base_efc:.0f}",
        )
        k2.metric(
            "Batt-Aware",
            f"{kpis.loc['Batt-Aware','equivalent_full_cycles']:.0f}",
            delta=_delta(kpis.loc["Batt-Aware","equivalent_full_cycles"], base_efc),
        )
        k2.metric(
            "Batt+PV-Aware",
            f"{kpis.loc['Batt+PV-Aware','equivalent_full_cycles']:.0f}",
            delta=_delta(kpis.loc["Batt+PV-Aware","equivalent_full_cycles"], base_efc),
        )

        k3.metric(
            "CO₂ Avoided – Baseline [kg]",
            f"{base_co2:,.0f}",
        )
        k3.metric(
            "Batt-Aware",
            f"{kpis.loc['Batt-Aware','co2_avoided_kg']:,.0f}",
            delta=_delta(kpis.loc["Batt-Aware","co2_avoided_kg"], base_co2),
        )
        k3.metric(
            "Batt+PV-Aware",
            f"{kpis.loc['Batt+PV-Aware','co2_avoided_kg']:,.0f}",
            delta=_delta(kpis.loc["Batt+PV-Aware","co2_avoided_kg"], base_co2),
        )

        st.markdown("---")

        # --- KPI charts row ---
        st.markdown("### KPI comparisons by control strategy")
        p1, p2, p3 = st.columns(3)

        with p1:
            fig_cost = _kpi_bar_fig(kpis, "annual_cost_gbp", "Annual Electricity Cost", "Cost [£/year]")
            st.plotly_chart(fig_cost, use_container_width=True)

        with p2:
            fig_efc = _kpi_bar_fig(kpis, "equivalent_full_cycles", "Equivalent Full Cycles", "Cycles [year]")
            st.plotly_chart(fig_efc, use_container_width=True)

        with p3:
            fig_co2 = _kpi_bar_fig(kpis, "co2_avoided_kg", "CO₂ Emissions Avoided", "CO₂ Saved [kg/year]")
            st.plotly_chart(fig_co2, use_container_width=True)

        st.markdown("---")

        # --- Dispatch and Pareto ---
        d1, d2 = st.columns([2, 1.6])

        with d1:
            st.markdown("### Seven-day dispatch")
            disp_fig = _dispatch_fig(full, title_suffix="Batt+PV-Aware")
            st.plotly_chart(disp_fig, use_container_width=True)

        with d2:
            st.markdown("### Pareto trade-off")
            pareto_df = _load_pareto()
            if pareto_df is None:
                if st.button("Generate Pareto frontier (λ grid sweep)"):
                    # Run Pareto sweep into results/pareto.csv using existing backend
                    pareto_sweep(df_in.copy(), conf_eff)
                    pareto_df = _load_pareto()
            if pareto_df is not None:
                pareto_fig = _pareto_fig(pareto_df)
                st.plotly_chart(pareto_fig, use_container_width=True)
            else:
                st.info("Pareto results not yet generated. Click the button above to run the sweep.")

    else:
        st.info("Adjust λ-weights and click **Run Simulation** to initialise the digital twin.")


if __name__ == "__main__":
    main()
