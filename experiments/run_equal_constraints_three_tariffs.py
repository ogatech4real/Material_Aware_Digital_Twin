"""Controlled battery-weight comparison across three established tariff profiles.

Install as experiments/run_equal_constraints_three_tariffs.py.
Run from anywhere: python experiments/run_equal_constraints_three_tariffs.py
Does not modify inputs, model source, or previously published results.
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


def main() -> None:
    source = ROOT / 'data' / 'sim_input.csv'
    if not source.is_file():
        raise FileNotFoundError(f'Missing {source}. Generate reference input first.')
    cfg = yaml.safe_load((ROOT / 'config.yaml').read_text(encoding='utf-8'))
    original = pd.read_csv(source, index_col=0, parse_dates=True)
    if original.empty or not original.index.is_unique:
        raise ValueError('Empty input or duplicate time indices')
    price_col = 'price_import_gbp_per_kwh'
    if price_col not in original or not np.isfinite(original[price_col].to_numpy(dtype=float)).all():
        raise ValueError('Missing or nonfinite import prices')
    dt_h = float(cfg['time']['dt_minutes']) / 60.0
    e_nom = float(cfg['battery']['e_nom_kwh'])
    if dt_h <= 0 or e_nom <= 0:
        raise ValueError('Invalid time step or battery capacity')
    adaptive_cfg = cfg['adaptive_supervisor']
    low = float(adaptive_cfg['lambda_batt_min'])
    high = float(adaptive_cfg['lambda_batt_max'])
    if not (0 <= low <= high):
        raise ValueError('Invalid adaptive weight bounds')

    # Exactly matches experiments/run_tariff_sensitivity.py.
    window = max(2, round(2.0 / dt_h))
    smoothed = original.copy()
    smoothed[price_col] = original[price_col].rolling(window=window, min_periods=1).mean()
    elapsed_h = np.arange(len(original), dtype=float) * dt_h
    independent = original.copy()
    independent[price_col] = (
        0.30
        + 0.055 * np.sin(2 * np.pi * elapsed_h / 24.0)
        + 0.025 * np.sin(2 * np.pi * elapsed_h / (24.0 * 7.0) + 0.7)
    )
    profiles = {
        'original_reference': original,
        'synthetic_smoothed': smoothed,
        'synthetic_independent': independent,
    }
    variants = {
        'No_battery_penalty': (0.0, 0.0),
        'Fixed_low_weight': (low, low),
        'Fixed_mid_weight': ((low + high) / 2.0, (low + high) / 2.0),
        'Fixed_high_weight': (high, high),
        'Adaptive_weight': (low, high),
    }
    outdir = ROOT / 'results' / 'equal_constraints_three_tariffs'
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for profile_name, input_df in profiles.items():
        print(f'\n===== {profile_name} =====', flush=True)
        if not original.drop(columns=[price_col]).equals(input_df.drop(columns=[price_col])):
            raise AssertionError('Non-import-price inputs were changed')
        traces = {}
        profile_rows = []
        for case, (w_min, w_max) in variants.items():
            c = copy.deepcopy(cfg)
            c['adaptive_supervisor']['lambda_batt_min'] = w_min
            c['adaptive_supervisor']['lambda_batt_max'] = w_max
            sim = run_adaptive_controller(input_df.copy(), c)
            residual = (sim['pv_kw_ac'] + sim['pdis'] + sim['pimp']
                        - sim['load_kw'] - sim['pch'] - sim['pexp'])
            balance_error = float(residual.abs().max())
            if balance_error > 1e-7:
                raise RuntimeError(f'{profile_name}/{case}: AC balance error {balance_error}')
            if (sim[['pch', 'pdis', 'pimp', 'pexp']] < -1e-9).any().any():
                raise RuntimeError(f'{profile_name}/{case}: negative power flow')
            soc_lo = max(float(c['battery']['soc_min']), float(c['adaptive_supervisor']['soc_operating_min']))
            soc_hi = min(float(c['battery']['soc_max']), float(c['adaptive_supervisor']['soc_operating_max']))
            if sim['soc'].min() < soc_lo - 1e-8 or sim['soc'].max() > soc_hi + 1e-8:
                raise RuntimeError(f'{profile_name}/{case}: SoC violation')
            kpis = summarize_kpis(sim.join(input_df, rsuffix='_input'), dt_h, e_nom, c)
            trace = sim[['soc', 'pch', 'pdis', 'pimp', 'pexp']].copy()
            traces[case] = trace
            row = {
                'profile': profile_name,
                'case': case,
                'cost_gbp': float(kpis['annual_cost_gbp']),
                'efc': float(kpis['equivalent_full_cycles']),
                'mean_lambda_batt': float(sim['lambda_batt_t'].mean()),
                'discharge_intervals': int((sim['pdis'] > 1e-9).sum()),
                'max_ac_balance_error_kw': balance_error,
            }
            profile_rows.append(row)
            trace['lambda_batt_t'] = sim['lambda_batt_t']
            trace['thermal_protection'] = sim['thermal_protection']
            trace['price_import_gbp_per_kwh'] = input_df[price_col].to_numpy()
            trace.to_csv(outdir / f'{profile_name}__{case}.csv', index=True)
            print(f'  {case}: cost=£{row["cost_gbp"]:.4f}; EFC={row["efc"]:.4f}', flush=True)
        base = profile_rows[0]
        ref = traces['No_battery_penalty'][['soc', 'pch', 'pdis', 'pimp', 'pexp']]
        adaptive = traces['Adaptive_weight'][['soc', 'pch', 'pdis', 'pimp', 'pexp']]
        for row in profile_rows:
            tr = traces[row['case']][['soc', 'pch', 'pdis', 'pimp', 'pexp']]
            row['cost_change_vs_no_penalty_pct'] = 100 * (row['cost_gbp'] / base['cost_gbp'] - 1)
            row['efc_reduction_vs_no_penalty_pct'] = 100 * (1 - row['efc'] / base['efc'])
            row['different_dispatch_intervals_vs_no_penalty'] = int(((tr - ref).abs() > 1e-9).any(axis=1).sum())
            row['different_dispatch_intervals_vs_adaptive'] = int(((tr - adaptive).abs() > 1e-9).any(axis=1).sum())
        rows.extend(profile_rows)

    results = pd.DataFrame(rows)
    results.to_csv(outdir / 'equal_constraints_three_tariffs_kpis.csv', index=False)
    metadata = {
        'reference_input': 'data/sim_input.csv',
        'reference_input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'input_intervals': len(original),
        'time_step_hours': dt_h,
        'rolling_window_intervals': window,
        'smoothed_tariff': 'Causal trailing two-hour rolling mean of original import tariff',
        'independent_tariff': '0.30 + 0.055*sin(2*pi*t_hours/24) + 0.025*sin(2*pi*t_hours/168 + 0.7) GBP/kWh',
        'synthetic_tariffs_are_not_measured': True,
        'unchanged_across_weight_variants': 'All controller, thermal-guard, battery, PV, load, import/export parameters except lambda_batt_min/max',
        'variants': {name: {'lambda_min': lo, 'lambda_max': hi} for name, (lo, hi) in variants.items()},
        'original_unique_import_prices': int(original[price_col].round(6).nunique()),
        'smoothed_unique_import_prices': int(smoothed[price_col].round(6).nunique()),
        'independent_unique_import_prices': int(independent[price_col].round(6).nunique()),
        'existing_source_files_modified': False,
    }
    (outdir / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print('\n===== CONSOLIDATED RESULTS =====')
    print(results[['profile', 'case', 'cost_gbp', 'efc', 'different_dispatch_intervals_vs_no_penalty']].round(4).to_string(index=False))
    print('\nSaved:', outdir)


if __name__ == '__main__':
    main()
