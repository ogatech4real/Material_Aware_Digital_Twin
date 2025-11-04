# src/controller.py
from __future__ import annotations
import pandas as pd
from .system_model import SystemParams, soc_next
from .degradation_models import pv_degraded_power_kw, pv_temp_correction_kw, pv_degradation_cost_step
from .optimizer import greedy_heuristic_step

def _thresholds(conf: dict, scenario: str) -> tuple[float, float]:
    e = conf.get("economics", {})
    if scenario == "baseline":
        return float(e.get("baseline_price_low", 0.19)), float(e.get("baseline_price_high", 0.33))
    if scenario == "batt":
        return float(e.get("batt_price_low", 0.21)), float(e.get("batt_price_high", 0.32))
    return float(e.get("full_price_low", 0.22)), float(e.get("full_price_high", 0.34))

def _lambda_batt(conf: dict, scenario: str) -> float:
    e = conf.get("economics", {})
    if scenario == "baseline":
        return 0.0
    if scenario == "batt":
        return float(e.get("lambda_batt", 0.8))          # ← nudge
    return float(e.get("lambda_batt_full", 1.2))         # ← stronger in Full

def run_controller(df: pd.DataFrame, conf: dict, scenario: str = "full") -> pd.DataFrame:
    params = SystemParams(conf); dt_h = params.dt_h
    out = df.copy()
    for col in ("soc","pch","pdis","pimp","pexp","pv_kw_eff","deg_cost_pv"): out[col] = 0.0

    soc = float((conf["battery"]["soc_min"] + conf["battery"]["soc_max"])/2.0)
    price_low, price_high = _thresholds(conf, scenario)
    lam_b = _lambda_batt(conf, scenario)
    batt_deg_pen = float(conf.get("economics", {}).get("batt_deg_marginal_gbp_per_kwh", 0.02))

    annual_deg = float(conf["pv"]["annual_deg_rate"])
    t_ref_c = float(conf["pv"]["t_ref_c"]); beta_per_c = float(conf["pv"]["temp_coeff_per_c"])

    soc_win = {
        "baseline": (params.soc_min, params.soc_max),
        "batt":     (max(params.soc_min, 0.15), min(params.soc_max, 0.85)),
        "full":     (max(params.soc_min, 0.20), min(params.soc_max, 0.80)),
    }[scenario]
    temp_discharge_limit_c = 35.0  # a touch stricter for UK summers

    class _ParamView:
        dt_h=params.dt_h; e_nom_kwh=params.e_nom_kwh
        eta_ch=params.eta_ch; eta_dis=params.eta_dis
        p_ch_max=params.p_ch_max; p_dis_max=params.p_dis_max
        soc_min=soc_win[0]; soc_max=soc_win[1]
        min_economic_spread_gbp_per_kwh = params.min_economic_spread_gbp_per_kwh

    econ = conf.get("economics", {})
    # export discouraged—keeps CO2 and cost deltas tight
    peak_export_thr = float(econ.get("peak_export_threshold_gbp_per_kwh", 0.30))
    allow_export = False  # keep export only from PV, not from battery arbitrage

    for t in range(len(out)):
        pv_raw   = float(out["pv_kw_raw"].iloc[t])
        load_kw  = float(out["load_kw"].iloc[t])
        temp_c   = float(out["cell_temp_c"].iloc[t])
        price_imp = float(out["price_import_gbp_per_kwh"].iloc[t])
        price_exp = float(out["price_export_gbp_per_kwh"].iloc[t])

        t_hours = t*dt_h
        pv_age = pv_degraded_power_kw(pv_raw, t_hours, annual_rate=annual_deg)
        pv_eff = pv_temp_correction_kw(pv_age, temp_c, t_ref_c=t_ref_c, beta_per_c=beta_per_c)
        out.iat[t, out.columns.get_loc("pv_kw_eff")] = pv_eff

        price_imp_eff = price_imp + lam_b*batt_deg_pen

        # TOU nudges for Baseline: 0–6 charge, 16–22 discharge
        try: hour = int(out.index[t].hour)
        except: hour = None
        p_low_use, p_high_use = price_low, price_high
        if scenario == "baseline" and hour is not None:
            if 0 <= hour <= 6:  p_low_use  = 1e6
            if 16 <= hour <= 22: p_high_use = -1e6

        if scenario == "full" and temp_c >= temp_discharge_limit_c:
            p_high_use = 1e9  # suppress discharging

        pch, pdis, pimp, pexp = greedy_heuristic_step(
            pv_kw=pv_eff, load_kw=load_kw, price_imp=price_imp_eff, price_exp=price_exp,
            soc=soc, params=_ParamView, price_low=p_low_use, price_high=p_high_use,
        )

        # Optional: suppress peak-time discharge->export pathway
        if not allow_export and pexp > max(0.0, pv_eff - load_kw):
            # cap export to PV surplus only
            over = pexp - max(0.0, pv_eff - load_kw)
            pexp -= over; pdis = max(0.0, pdis - over)

        out.iat[t, out.columns.get_loc("soc")]  = soc
        out.iat[t, out.columns.get_loc("pch")]  = pch
        out.iat[t, out.columns.get_loc("pdis")] = pdis
        out.iat[t, out.columns.get_loc("pimp")] = pimp
        out.iat[t, out.columns.get_loc("pexp")] = pexp
        out.iat[t, out.columns.get_loc("deg_cost_pv")] = pv_degradation_cost_step(pv_raw, pv_eff, price_imp, dt_h)

        soc = soc_next(soc, pch, pdis, dt_h, params.eta_ch, params.eta_dis, params.e_nom_kwh)
        if soc < soc_win[0]: soc = soc_win[0]
        elif soc > soc_win[1]: soc = soc_win[1]

    for c in ("pch","pdis","pimp","pexp"): out[c] = out[c].clip(lower=0.0)
    out["soc"] = out["soc"].clip(lower=soc_win[0], upper=1.0)
    return out
