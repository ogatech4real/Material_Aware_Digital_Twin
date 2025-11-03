import numpy as np
import pandas as pd


def generate_time_index(start="2024-01-01", periods=96*14, freq="15min"):
    # default: 2 weeks for a quick demo; adjust periods for 1-year (365*96)
    return pd.date_range(start=start, periods=365*96, freq=freq)


def synthetic_load_profile(idx, base_kw=0.6, peak_kw=3.5, noise=0.2):
    tmins = idx.hour*60 + idx.minute
    dayfrac = tmins/(24*60.0)
    daily = base_kw + (peak_kw-base_kw)*np.exp(-((dayfrac-0.20)**2)/(2*0.03))  # ~5am peak
    evening = (peak_kw-base_kw)*np.exp(-((dayfrac-0.83)**2)/(2*0.02))         # ~8pm peak
    weekly = 1.0 + 0.1*np.sin(2*np.pi*(idx.dayofweek/7))
    rng = np.random.default_rng(42)
    eps = rng.normal(0, noise, size=len(idx))
    return np.maximum(0.1, (daily + evening)*weekly + eps)


def synthetic_irradiance(idx):
    doy = idx.dayofyear.values
    tmin = idx.hour + idx.minute/60.0
    season = 0.5 + 0.5*np.cos(2*np.pi*(doy-172)/365.0)  # peak in June
    diurnal = np.maximum(0, np.sin((tmin/24.0)*np.pi))  # 0..1 daylight half-wave
    ghi = season * diurnal
    return np.clip(ghi, 0, None)


def pv_dc_power_kw(irr, pdc_stc_kw=5.0):
    return pdc_stc_kw * irr


def synthetic_tariffs(idx, base=0.25, spread=0.15):
    hour = idx.hour.values
    price = np.full(len(idx), base)
    price += ((hour>=17)&(hour<=21))*spread    # evening high
    price -= ((hour>=1)&(hour<=5))*0.08        # overnight low
    return np.maximum(0.05, price)


def feed_in_tariff(import_prices):
    return 0.4*import_prices


def build_dataframe(idx):
    df = pd.DataFrame(index=idx)
    df["load_kw"] = synthetic_load_profile(idx)
    irr = synthetic_irradiance(idx)
    df["pv_kw_raw"] = pv_dc_power_kw(irr)
    df["price_import_gbp_per_kwh"] = synthetic_tariffs(idx)
    df["price_export_gbp_per_kwh"] = feed_in_tariff(df["price_import_gbp_per_kwh"])
    df["ambient_c"] = 15 + 10*np.sin(2*np.pi*(idx.dayofyear-172)/365.0)
    df["cell_temp_c"] = df["ambient_c"] + 20*irr
    df["carbon_intensity"] = 0.15 + 0.1*np.sin(2*np.pi*(idx.hour/24.0))
    return df


if __name__ == "__main__":
    idx = generate_time_index()
    df = build_dataframe(idx)
    df.to_csv("data/sim_input.csv")
    print("Saved data/sim_input.csv", df.shape)
