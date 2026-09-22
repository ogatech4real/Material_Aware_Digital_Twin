"""Interpretable fuzzy supervisory layer for the Special-Issue extension.

The supervisor is intentionally lightweight: it does not replace the deterministic
lower-level dispatcher. It maps measured operating state to adaptive degradation
weights and a thermal protection signal.
"""
from __future__ import annotations
from dataclasses import dataclass


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _ramp_up(x: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return float(x >= hi)
    return _clip01((x - lo) / (hi - lo))


def _ramp_down(x: float, lo: float, hi: float) -> float:
    return 1.0 - _ramp_up(x, lo, hi)


@dataclass(frozen=True)
class SupervisorOutput:
    lambda_batt: float
    lambda_pv: float
    thermal_protection: float
    stress_index: float


def adaptive_weights(
    *, soc: float, cell_temp_c: float, load_kw: float, pv_kw: float,
    price_import: float, conf: dict
) -> SupervisorOutput:
    """Return adaptive degradation weights using transparent fuzzy rules.

    Inputs are normalized by configured physical/economic ranges. Rules increase
    battery protection at low/high SoC and high temperature, while PV weighting
    increases with module temperature and high available PV. The output is bounded
    and deterministic, making the supervisory decision auditable.
    """
    a = conf.get("adaptive_supervisor", {})
    b = conf.get("battery", {})
    pv = conf.get("pv", {})
    econ = conf.get("economics", {})

    soc_min = float(b.get("soc_min", 0.10)); soc_max = float(b.get("soc_max", 0.95))
    soc_span = max(1e-9, soc_max - soc_min)
    soc_n = _clip01((soc - soc_min) / soc_span)

    low_soc = _ramp_down(soc_n, 0.15, 0.40)
    high_soc = _ramp_up(soc_n, 0.60, 0.85)
    soc_stress = max(low_soc, high_soc)

    temp_warn = float(a.get("temp_warn_c", 30.0))
    temp_high = float(a.get("temp_high_c", 40.0))
    thermal = _ramp_up(cell_temp_c, temp_warn, temp_high)

    pdc = max(1e-9, float(pv.get("p_dc_stc_kw", 3.6)))
    pv_avail = _clip01(max(0.0, pv_kw) / pdc)

    load_ref = max(1e-9, float(a.get("load_reference_kw", 3.0)))
    load_stress = _clip01(max(0.0, load_kw) / load_ref)

    p_lo = float(econ.get("baseline_price_low", 0.19))
    p_hi = float(econ.get("baseline_price_high", 0.33))
    price_stress = _ramp_up(price_import, p_lo, max(p_hi, p_lo + 1e-6))

    # Mamdani-style rule aggregation expressed as bounded weighted scores.
    batt_stress = _clip01(0.45 * soc_stress + 0.35 * thermal + 0.10 * load_stress + 0.10 * price_stress)
    pv_stress = _clip01(0.65 * thermal + 0.35 * pv_avail)

    lb_min = float(a.get("lambda_batt_min", 0.0)); lb_max = float(a.get("lambda_batt_max", 1.2))
    lp_min = float(a.get("lambda_pv_min", 0.0)); lp_max = float(a.get("lambda_pv_max", 0.20))

    lb = lb_min + batt_stress * (lb_max - lb_min)
    lp = lp_min + pv_stress * (lp_max - lp_min)
    return SupervisorOutput(float(lb), float(lp), float(thermal), float(max(batt_stress, pv_stress)))
