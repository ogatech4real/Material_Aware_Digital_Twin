"""Special-Issue supplementary experiment.

Adds an interpretable adaptive supervisory layer and explicit steady-state inverter
interface while reusing the frozen degradation models and greedy dispatcher.
"""
from __future__ import annotations
import pandas as pd

from .adaptive_supervisor import adaptive_weights
from .degradation_models import pv_degraded_power_kw, pv_temp_correction_kw, pv_degradation_cost_step
from .inverter_model import InverterParams, pv_ac_power, battery_ac_to_dc
from .optimizer import greedy_heuristic_step
from .system_model import SystemParams, soc_next


def run_adaptive_controller(df: pd.DataFrame, conf: dict) -> pd.DataFrame:
    params = SystemParams(conf)
    inv = InverterParams.from_config(conf)
    dt_h = params.dt_h
    out = df.copy()
    cols = (
        "soc", "pch", "pdis", "pimp", "pexp", "pv_kw_eff", "pv_kw_ac",
        "deg_cost_pv", "lambda_batt_t", "lambda_pv_t", "thermal_protection",
        "supervisor_stress", "pv_inverter_loss_kw", "batt_inverter_loss_kw",
    )
    for col in cols:
        out[col] = 0.0

    a = conf.get("adaptive_supervisor", {})
    soc_lo = max(params.soc_min, float(a.get("soc_operating_min", 0.15)))
    soc_hi = min(params.soc_max, float(a.get("soc_operating_max", 0.85)))
    soc = float((soc_lo + soc_hi) / 2.0)

    econ = conf.get("economics", {})
    price_low = float(a.get("price_low", econ.get("batt_price_low", 0.25)))
    price_high = float(a.get("price_high", econ.get("batt_price_high", 0.315)))
    batt_deg_pen = float(econ.get("batt_deg_marginal_gbp_per_kwh", 0.03))
    eps = 1e-9

    annual_deg = float(conf["pv"]["annual_deg_rate"])
    t_ref_c = float(conf["pv"]["t_ref_c"])
    beta_per_c = float(conf["pv"]["temp_coeff_per_c"])

    class _ParamView:
        dt_h = params.dt_h
        e_nom_kwh = params.e_nom_kwh
        eta_ch = params.eta_ch
        eta_dis = params.eta_dis
        p_ch_max = min(params.p_ch_max, inv.p_batt_rated_kw)
        p_dis_max = min(params.p_dis_max, inv.p_batt_rated_kw)
        soc_min = soc_lo
        soc_max = soc_hi
        min_economic_spread_gbp_per_kwh = params.min_economic_spread_gbp_per_kwh

    for t in range(len(out)):
        pv_raw = float(out["pv_kw_raw"].iloc[t])
        load_kw = float(out["load_kw"].iloc[t])
        temp_c = float(out["cell_temp_c"].iloc[t])
        price_imp = float(out["price_import_gbp_per_kwh"].iloc[t])
        price_exp = float(out["price_export_gbp_per_kwh"].iloc[t])

        pv_age = pv_degraded_power_kw(pv_raw, t * dt_h, annual_rate=annual_deg)
        pv_eff_dc = pv_temp_correction_kw(pv_age, temp_c, t_ref_c=t_ref_c, beta_per_c=beta_per_c)
        pv_ac, pv_inv_loss = pv_ac_power(pv_eff_dc, inv)
        pv_loss_cost = pv_degradation_cost_step(pv_raw, pv_eff_dc, price_imp, dt_h)

        sup = adaptive_weights(
            soc=soc, cell_temp_c=temp_c, load_kw=load_kw, pv_kw=pv_eff_dc,
            price_import=price_imp, conf=conf,
        )

        # Battery degradation is a direct marginal dispatch penalty.
        price_imp_eff = price_imp + sup.lambda_batt * batt_deg_pen

        # PV loss is exogenous to dispatch in the current reduced-order model.
        # lambda_pv is therefore recorded as a supervisory diagnostic rather than
        # incorrectly forcing it into the dispatch price. This closes the prior
        # code/manuscript ambiguity without inventing a controllable PV-ageing path.
        pv_loss_marginal = pv_loss_cost / (max(pv_ac, 0.0) * dt_h + eps)

        # Thermal supervisory protection raises the discharge trigger smoothly.
        high_use = price_high + float(a.get("thermal_price_guard_gbp_per_kwh", 0.08)) * sup.thermal_protection

        pch_ac, pdis_ac, pimp, pexp = greedy_heuristic_step(
            pv_kw=pv_ac, load_kw=load_kw, price_imp=price_imp_eff, price_exp=price_exp,
            soc=soc, params=_ParamView, price_low=price_low, price_high=high_use,
        )

        # Existing policy: battery does not export for arbitrage; PV surplus may export.
        pv_surplus = max(0.0, pv_ac - load_kw)
        if pexp > pv_surplus:
            over = pexp - pv_surplus
            pexp -= over
            pdis_ac = max(0.0, pdis_ac - over)

        pch_dc, pdis_dc, batt_inv_loss = battery_ac_to_dc(pch_ac, pdis_ac, inv)

        out.iat[t, out.columns.get_loc("soc")] = soc
        out.iat[t, out.columns.get_loc("pch")] = pch_ac
        out.iat[t, out.columns.get_loc("pdis")] = pdis_ac
        out.iat[t, out.columns.get_loc("pimp")] = pimp
        out.iat[t, out.columns.get_loc("pexp")] = pexp
        out.iat[t, out.columns.get_loc("pv_kw_eff")] = pv_ac  # AC-side value used in balance/KPIs
        out.iat[t, out.columns.get_loc("pv_kw_ac")] = pv_ac
        out.iat[t, out.columns.get_loc("deg_cost_pv")] = pv_loss_cost
        out.iat[t, out.columns.get_loc("lambda_batt_t")] = sup.lambda_batt
        out.iat[t, out.columns.get_loc("lambda_pv_t")] = sup.lambda_pv
        out.iat[t, out.columns.get_loc("thermal_protection")] = sup.thermal_protection
        out.iat[t, out.columns.get_loc("supervisor_stress")] = sup.stress_index
        out.iat[t, out.columns.get_loc("pv_inverter_loss_kw")] = pv_inv_loss
        out.iat[t, out.columns.get_loc("batt_inverter_loss_kw")] = batt_inv_loss

        soc = soc_next(soc, pch_dc, pdis_dc, dt_h, params.eta_ch, params.eta_dis, params.e_nom_kwh)
        soc = min(soc_hi, max(soc_lo, soc))

    for c in ("pch", "pdis", "pimp", "pexp"):
        out[c] = out[c].clip(lower=0.0)
    out["soc"] = out["soc"].clip(lower=soc_lo, upper=soc_hi)
    out.attrs["pv_loss_marginal_definition"] = "diagnostic_only"
    return out
