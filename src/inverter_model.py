"""Lightweight steady-state inverter interface for supplementary experiments."""
from __future__ import annotations
from dataclasses import dataclass


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


@dataclass(frozen=True)
class InverterParams:
    eta_pv: float = 0.97
    eta_batt: float = 0.96
    p_pv_rated_kw: float = 3.6
    p_batt_rated_kw: float = 5.0

    @classmethod
    def from_config(cls, conf: dict) -> "InverterParams":
        inv = conf.get("inverter", {})
        return cls(
            eta_pv=_clip(inv.get("eta_pv", 0.97), 1e-6, 1.0),
            eta_batt=_clip(inv.get("eta_batt", 0.96), 1e-6, 1.0),
            p_pv_rated_kw=max(0.0, float(inv.get("p_pv_rated_kw", conf.get("pv", {}).get("p_dc_stc_kw", 3.6)))),
            p_batt_rated_kw=max(0.0, float(inv.get("p_batt_rated_kw", conf.get("battery", {}).get("p_dis_max_kw", 5.0)))),
        )


def pv_ac_power(pv_dc_kw: float, params: InverterParams) -> tuple[float, float]:
    """Return (AC power, conversion/clipping loss) in kW."""
    pv_dc = max(0.0, float(pv_dc_kw))
    converted = params.eta_pv * pv_dc
    ac = min(converted, params.p_pv_rated_kw)
    return ac, max(0.0, pv_dc - ac)


def battery_ac_to_dc(pch_ac_kw: float, pdis_ac_kw: float, params: InverterParams) -> tuple[float, float, float]:
    """Map AC-side battery commands to DC-side battery powers used by SoC dynamics.

    Returns (charge_dc_kw, discharge_dc_kw, inverter_loss_kw).
    """
    pch_ac = min(max(0.0, float(pch_ac_kw)), params.p_batt_rated_kw)
    pdis_ac = min(max(0.0, float(pdis_ac_kw)), params.p_batt_rated_kw)
    pch_dc = pch_ac * params.eta_batt
    pdis_dc = pdis_ac / params.eta_batt if pdis_ac > 0.0 else 0.0
    loss = max(0.0, (pch_ac - pch_dc) + (pdis_dc - pdis_ac))
    return pch_dc, pdis_dc, loss
