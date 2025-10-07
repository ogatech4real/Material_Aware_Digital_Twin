import numpy as np
import pandas as pd
import yaml
from .system_model import SystemParams, soc_next
from .forecast_models import load_stl_forecast, day_ahead_repeat
from .degradation_models import (
    pv_degraded_power_kw, pv_temp_correction_kw, pv_degradation_cost_step, simple_battery_deg_cost_step
)
from .optimizer import greedy_heuristic_step


def run_controller(df, conf, horizon_steps=96, lookback_steps=96, scenario="full"):
    params = SystemParams(conf)
    dt_h = params.dt_h
    out = df.copy()
    for col in ["soc","pch","pdis","pimp","pexp","deg_cost_batt","deg_cost_pv"]:
        out[col] = 0.0
    soc = conf["battery"]["soc_max"]

    for t0 in range(len(df)):
        # For demo we just use current step (no MILP solver here)
        pv_raw = float(df["pv_kw_raw"].iloc[t0])
        temp_c = float(df["cell_temp_c"].iloc[t0])
        price_imp = float(df["price_import_gbp_per_kwh"].iloc[t0])
        price_exp = float(df["price_export_gbp_per_kwh"].iloc[t0])
        load_kw = float(df["load_kw"].iloc[t0])

        pv_deg = pv_degraded_power_kw(pv_raw, t0*dt_h, conf["pv"]["annual_deg_rate"])
        pv_temp = pv_temp_correction_kw(pv_deg, temp_c, conf["pv"]["t_ref_c"], conf["pv"]["temp_coeff_per_c"])

        # Heuristic dispatch
        pch, pdis, pimp, pexp = greedy_heuristic_step(pv_temp, load_kw, price_imp, price_exp, soc, params)

        # Degradation costs (monetized) per step
        soc_hist = np.array([soc])
        temp_hist = np.array([temp_c])
        deg_batt = simple_battery_deg_cost_step(soc_hist, temp_hist, dt_h,
                                                conf["battery"]["replacement_cost_gbp"], 1000.0)
        deg_pv = pv_degradation_cost_step(pv_raw, pv_temp, price_imp, dt_h)

        out.iloc[t0, out.columns.get_loc("soc")] = soc
        out.iloc[t0, out.columns.get_loc("pch")] = pch
        out.iloc[t0, out.columns.get_loc("pdis")] = pdis
        out.iloc[t0, out.columns.get_loc("pimp")] = pimp
        out.iloc[t0, out.columns.get_loc("pexp")] = pexp
        out.iloc[t0, out.columns.get_loc("deg_cost_batt")] = deg_batt if scenario in ["batt","full"] else 0.0
        out.iloc[t0, out.columns.get_loc("deg_cost_pv")] = deg_pv if scenario in ["full"] else 0.0

        soc = soc_next(soc, pch, pdis, dt_h, params.eta_ch, params.eta_dis, params.e_nom_kwh)
    return out