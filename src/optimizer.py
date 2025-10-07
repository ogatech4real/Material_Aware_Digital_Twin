import numpy as np


def greedy_heuristic_step(pv_kw, load_kw, price_imp, price_exp, soc, params):
    # Simple rule: use PV to cover load, then charge if cheap, discharge if expensive
    dt = params.dt_h
    p_ch = 0.0; p_dis = 0.0; p_imp = 0.0; p_exp = 0.0
    net = pv_kw - load_kw
    if net >= 0:
        # PV covers load; consider charging within limits
        headroom_kwh = (params.soc_max - soc)*params.e_nom_kwh
        max_charge_kw = min(params.p_ch_max, headroom_kwh/dt)
        p_ch = min(max_charge_kw, net)
        p_exp = max(0.0, net - p_ch)
    else:
        deficit = -net
        # discharge if price is high
        available_kwh = max(0.0, (soc - params.soc_min)*params.e_nom_kwh)
        max_dis_kw = min(params.p_dis_max, available_kwh/dt)
        # threshold on high price
        if price_imp > np.quantile([price_imp, 0.30, 0.40, 0.20], 0.5):
            p_dis = min(max_dis_kw, deficit)
            deficit -= p_dis
        p_imp = max(0.0, deficit)
    return p_ch, p_dis, p_imp, p_exp
