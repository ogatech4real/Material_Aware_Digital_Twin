import numpy as np


def calendar_fade_Ah(dt_h, soc_avg, temp_c, k_cal=1.0e-6, Ea_over_R=4000.0):
    T_k = temp_c + 273.15
    f_soc = 0.5 + 0.5*float(soc_avg)
    return k_cal * np.exp(-Ea_over_R/np.maximum(T_k, 1.0)) * f_soc * dt_h


def cycle_fade_Ah_from_DoD(DoD_list, k_cyc=0.05, alpha=1.3):
    if not DoD_list:
        return 0.0
    return float(sum(k_cyc*(d**alpha) for d in DoD_list))


def pv_degraded_power_kw(pv_kw_raw, t_hours_from_start, annual_rate=0.01, hours_per_year=8760):
    factor = max(0.0, 1.0 - annual_rate*(t_hours_from_start/hours_per_year))
    return pv_kw_raw * factor


def pv_temp_correction_kw(pv_kw, temp_c, t_ref_c=25.0, beta_per_c=0.004):
    return pv_kw * (1.0 - beta_per_c*(temp_c - t_ref_c))


def pv_degradation_cost_step(pv_kw_raw, pv_kw_temp, price_ref_gbp_per_kwh, dt_h):
    lost_kw = max(0.0, pv_kw_raw - pv_kw_temp)
    return lost_kw * price_ref_gbp_per_kwh * dt_h


def simple_battery_deg_cost_step(soc_window, temp_window, dt_h, replacement_cost_gbp=3500, q_nom_Ah=1000.0):
    soc_avg = float(np.mean(soc_window))
    temp_avg = float(np.mean(temp_window))
    dQ_cal = calendar_fade_Ah(dt_h, soc_avg, temp_avg)
    # cycle fade proxy: use windowed variance of SoC as a cheap stand-in for cycling depth
    dod_proxy = float(np.clip(np.std(soc_window)*2.0, 0.0, 1.0))
    dQ_cyc = cycle_fade_Ah_from_DoD([dod_proxy])
    fade_frac = (dQ_cal + dQ_cyc) / max(q_nom_Ah, 1.0)
    return fade_frac * replacement_cost_gbp