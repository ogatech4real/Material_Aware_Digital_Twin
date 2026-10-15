"""Isolated, reproducible synthetic tariff sensitivity and 2x2 adaptive ablation.

Run from any directory: python experiments/run_tariff_sensitivity.py
Never overwrites original input files or published-reference results.
The smoothed tariff is a synthetic experimental perturbation, NOT measured prices.
"""
from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.special_issue_extension import run_adaptive_controller
from src.evaluation import summarize_kpis


def main():
    conf = yaml.safe_load((ROOT / 'config.yaml').read_text(encoding='utf-8'))
    original = pd.read_csv(ROOT / 'data' / 'sim_input.csv', index_col=0, parse_dates=True)
    dt_h = float(conf['time']['dt_minutes']) / 60
    e_nom = float(conf['battery']['e_nom_kwh'])
    if dt_h <= 0 or e_nom <= 0:
        raise ValueError('Invalid time step or battery capacity')
    price_col = 'price_import_gbp_per_kwh'
    if price_col not in original or original[price_col].isna().any():
        raise ValueError('Missing/nonfinite import price')
    # Eight 15-min intervals = two-hour *causal* trailing smoothing. This
    # intentionally introduces intermediate tariff values, not real tariffs.
    window = max(2, round(2.0 / dt_h))
    synthetic = original.copy()
    synthetic[price_col] = original[price_col].rolling(window=window, min_periods=1).mean()
    # Independently specified, deterministic synthetic time-varying import price.
    # This is a stress test, not a claim about real-world retail tariffs.
    # Parameters are fixed before examining its outcomes.
    elapsed_h = np.arange(len(original), dtype=float) * dt_h
    independent = original.copy()
    independent[price_col] = (0.30
        + 0.055 * np.sin(2 * np.pi * elapsed_h / 24.0)
        + 0.025 * np.sin(2 * np.pi * elapsed_h / (24.0 * 7.0) + 0.7))
    # Preserve the original export tariff independently; the test isolates
    # the influence of import-price threshold reachability.
    cases = {
        'Adaptive_full': (True, True),
        'No_battery_weight': (False, True),
        'No_thermal_guard': (True, False),
        'Neither_mechanism': (False, False),
    }
    outdir = ROOT / 'results' / 'tariff_sensitivity'
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for profile_name, input_df in [('original_reference', original), ('synthetic_smoothed', synthetic), ('synthetic_independent', independent)]:
        traces = {}
        input_df[[price_col]].to_csv(outdir / f'{profile_name}_import_prices.csv', index=True)
        for name, (weight_on, guard_on) in cases.items():
            c = copy.deepcopy(conf)
            a = c['adaptive_supervisor']
            if not weight_on:
                a['lambda_batt_min'] = a['lambda_batt_max'] = 0.0
            if not guard_on:
                a['thermal_price_guard_gbp_per_kwh'] = 0.0
            print(f'Running {profile_name} / {name}', flush=True)
            sim = run_adaptive_controller(input_df.copy(), c)
            residual = sim['pv_kw_ac'] + sim['pdis'] + sim['pimp'] - sim['load_kw'] - sim['pch'] - sim['pexp']
            max_error = float(residual.abs().max())
            if max_error > 1e-7:
                raise RuntimeError(f'AC power balance failure: {profile_name} / {name}: {max_error}')
            if (sim[['pch', 'pdis', 'pimp', 'pexp']] < -1e-9).any().any():
                raise RuntimeError('Negative power flows')
            lo = max(float(c['battery']['soc_min']), float(a['soc_operating_min']))
            hi = min(float(c['battery']['soc_max']), float(a['soc_operating_max']))
            if sim['soc'].min() < lo - 1e-8 or sim['soc'].max() > hi + 1e-8:
                raise RuntimeError('Recorded SoC violates operating bounds')
            kpis = summarize_kpis(sim.join(input_df, rsuffix='_input'), dt_h, e_nom, c)
            rows.append({
                'profile': profile_name, 'variant': name,
                'annual_cost_gbp': float(kpis['annual_cost_gbp']),
                'equivalent_full_cycles': float(kpis['equivalent_full_cycles']),
                'max_ac_balance_error_kw': max_error,
                'discharge_intervals': int((sim['pdis'] > 1e-9).sum()),
                'mean_battery_weight': float(sim['lambda_batt_t'].mean()),
                'thermal_signal_active_intervals': int((sim['thermal_protection'] > 1e-9).sum()),
            })
            trace_cols = [col for col in ['soc', 'pch', 'pdis', 'pimp', 'pexp', 'lambda_batt_t', 'lambda_pv_t', 'thermal_protection', 'pv_kw_ac', 'load_kw'] if col in sim.columns]
            trace = sim[trace_cols].copy()
            trace['price_import_gbp_per_kwh'] = input_df[price_col].to_numpy()
            trace.to_csv(outdir / f'{profile_name}__{name}_trace.csv', index=True)
            traces[name] = trace[['soc', 'pch', 'pdis', 'pimp', 'pexp']].copy()
        full = traces['Adaptive_full']
        for row in rows:
            if row['profile'] != profile_name:
                continue
            comparison = traces[row['variant']]
            row['dispatch_difference_intervals_vs_full'] = int(
                ((comparison[['pch','pdis','pimp','pexp']] - full[['pch','pdis','pimp','pexp']]).abs() > 1e-9).any(axis=1).sum()
            )
        neither = next(r for r in rows if r['profile'] == profile_name and r['variant'] == 'Neither_mechanism')
        for row in rows:
            if row['profile'] == profile_name:
                row['cost_change_vs_neither_pct'] = 100 * (row['annual_cost_gbp'] / neither['annual_cost_gbp'] - 1)
                row['efc_reduction_vs_neither_pct'] = 100 * (1 - row['equivalent_full_cycles'] / neither['equivalent_full_cycles'])
    results = pd.DataFrame(rows)
    results.to_csv(outdir / 'tariff_sensitivity_kpis.csv', index=False)
    metadata = {
        'reference': 'data/sim_input.csv; unchanged',
        'sensitivity': 'synthetic causal trailing two-hour mean of import price only',
        'synthetic_not_measured': True,
        'rolling_window_intervals': window,
        'input_rows': len(original),
        'original_unique_import_prices': int(original[price_col].round(6).nunique()),
        'synthetic_unique_import_prices': int(synthetic[price_col].round(6).nunique()),
        'other_input_columns_identical': bool(original.drop(columns=[price_col]).equals(synthetic.drop(columns=[price_col]))),
        'model_parameters_unchanged': True,
        'independent_synthetic_tariff': '0.30 + 0.055*sin(2*pi*t_hours/24) + 0.025*sin(2*pi*t_hours/168 + 0.7) GBP/kWh',
        'independent_synthetic_not_measured': True,
        'independent_unique_import_prices': int(independent[price_col].round(6).nunique()),
        'independent_other_input_columns_identical': bool(original.drop(columns=[price_col]).equals(independent.drop(columns=[price_col]))),
        'reference_input_sha256': hashlib.sha256((ROOT / 'data' / 'sim_input.csv').read_bytes()).hexdigest(),
    }
    (outdir / 'tariff_sensitivity_metadata.json').write_text(json.dumps(metadata, indent=2))
    # Each trace is saved independently to allow retrospective comparison of
    # discharge decisions, physical constraints, and supervisory signals.
    print(results[['profile','variant','annual_cost_gbp','equivalent_full_cycles','dispatch_difference_intervals_vs_full']].round(4).to_string(index=False))
    print('Saved:', outdir)

if __name__ == '__main__':
    main()
