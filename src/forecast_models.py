import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL


def persistence(series: pd.Series, horizon_steps: int):
    last = float(series.iloc[-1]) if len(series) else 0.0
    return np.full(horizon_steps, last)


def load_stl_forecast(load_hist: pd.Series, horizon_steps: int):
    if len(load_hist) < 200:
        return persistence(load_hist, horizon_steps)
    stl = STL(load_hist, period=96, robust=True).fit()
    trend = float(stl.trend.iloc[-1])
    season_next = np.resize(stl.seasonal[-96:], horizon_steps)
    resid_last = float(np.mean(stl.resid[-96:]))
    return np.maximum(0.0, trend + season_next + resid_last)


def day_ahead_repeat(series: pd.Series, horizon_steps: int):
    if len(series) >= 96:
        return np.tile(series.iloc[-96:].values, int(np.ceil(horizon_steps/96)))[:horizon_steps]
    return np.resize(series.values, horizon_steps)