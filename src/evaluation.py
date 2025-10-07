import numpy as np


def kpi_economic(df, dt_h):
    energy = (df["pimp"]*df["price_import_gbp_per_kwh"] - df["pexp"]*df["price_export_gbp_per_kwh"])*dt_h
    return {
        "annual_cost_gbp": float(energy.sum()),
        "mean_hourly_cost_gbp": float(energy.mean())
    }


def kpi_lifecycle(df):
    # proxy based on discharge energy
    dis_kwh = float((df["pdis"].clip(lower=0)).sum())*df.attrs.get("dt_h", 0.25)
    return {"equivalent_full_cycles": float(dis_kwh/max(df.attrs.get("e_nom_kwh", 10.0), 1.0))}


def kpi_environmental(df, dt_h):
    if "carbon_intensity" not in df.columns:
        return {"co2_avoided_kg": None}
    avoided = (df["pexp"] + df["pdis"] - df["pimp"]).clip(lower=0) * df["carbon_intensity"] * dt_h
    return {"co2_avoided_kg": float(avoided.sum())}


def summarize_kpis(df, dt_h, e_nom_kwh):
    df = df.copy()
    df.attrs["dt_h"] = dt_h
    df.attrs["e_nom_kwh"] = e_nom_kwh
    out = {}
    out.update(kpi_economic(df, dt_h))
    out.update(kpi_lifecycle(df))
    out.update(kpi_environmental(df, dt_h))
    return out