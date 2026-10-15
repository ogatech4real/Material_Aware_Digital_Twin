"""Controlled fixed-versus-adaptive weighting experiment.

All cases use the same dispatch engine, SoC limits, thresholds, input data,
thermal-guard configuration, and physical model. Only lambda_batt varies.
Run: python experiments/run_equal_constraints_comparison.py
"""
from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.special_issue_extension import run_adaptive_controller
from src.evaluation import summarize_kpis


def main() -> None:
    path = ROOT / 'data' / 'sim_input.csv'
    if not path.exists():
        raise FileNotFoundError(f'Missing {path}; generate the reference input using the existing project workflow first.')
    cfg = yaml.safe_load((ROOT / 'config.yaml').read_text(encoding='utf-8'))
    data = pd.read_csv(path, index_col=0, parse_dates=True)
    if data.empty:
        raise ValueError('Input data is empty')
    dt_h = float(cfg['time']['dt_minutes']) / 60
    e_nom = float(cfg['battery']['e_nom_kwh'])
    a = cfg['adaptive_supervisor']
    low = float(a['lambda_batt_min'])
    high = float(a['lambda_batt_max'])
    if not 0 <= low <= high:
        raise ValueError('Invalid adaptive battery-weight bounds')

    # Thermal guard is kept enabled and IDENTICAL in every case.
    # This isolates the marginal effect of dynamic versus constant battery weighting.
    variants = {
        'No_battery_penalty': (0.0, 0.0),
        'Fixed_low_weight': (low, low),
        'Fixed_mid_weight': ((low + high) / 2, (low + high) / 2),
        'Fixed_high_weight': (high, high),
        'Adaptive_weight': (low, high),
    }
    outdir = ROOT / 'results' / 'equal_constraints'
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    traces = {}
    for name, (w_min, w_max) in variants.items():
        c = copy.deepcopy(cfg)
        c['adaptive_supervisor']['lambda_batt_min'] = w_min
        c['adaptive_supervisor']['lambda_batt_max'] = w_max
        sim = run_adaptive_controller(data.copy(), c)
        residual = sim['pv_kw_ac'] + sim['pdis'] + sim['pimp'] - sim['load_kw'] - sim['pch'] - sim['pexp']
        balance_error = float(residual.abs().max())
        if balance_error > 1e-7:
            raise RuntimeError(f'{name}: AC balance error {balance_error}')
        soc_lo = max(float(c['battery']['soc_min']), float(c['adaptive_supervisor']['soc_operating_min']))
        soc_hi = min(float(c['battery']['soc_max']), float(c['adaptive_supervisor']['soc_operating_max']))
        if sim['soc'].min() < soc_lo - 1e-8 or sim['soc'].max() > soc_hi + 1e-8:
            raise RuntimeError(f'{name}: SoC constraint violation')
        k = summarize_kpis(sim.join(data, rsuffix='_input'), dt_h, e_nom, c)
        rows.append({
            'case': name,
            'cost_gbp': float(k['annual_cost_gbp']),
            'efc': float(k['equivalent_full_cycles']),
            'mean_lambda_batt': float(sim['lambda_batt_t'].mean()),
            'discharge_intervals': int((sim['pdis'] > 1e-9).sum()),
            'max_ac_balance_error_kw': balance_error,
        })
        traces[name] = sim[['pch', 'pdis', 'pimp', 'pexp']].copy()
        sim[['soc','pch','pdis','pimp','pexp','lambda_batt_t','thermal_protection']].to_csv(outdir / f'{name}.csv')
        print(f'{name}: cost={k["annual_cost_gbp"]:.4f} GBP; EFC={k["equivalent_full_cycles"]:.4f}', flush=True)

    results = pd.DataFrame(rows).set_index('case')
    ref = results.loc['No_battery_penalty']
    results['cost_change_vs_no_penalty_pct'] = 100 * (results['cost_gbp'] / ref['cost_gbp'] - 1)
    results['efc_reduction_vs_no_penalty_pct'] = 100 * (1 - results['efc'] / ref['efc'])
    ref_trace = traces['No_battery_penalty']
    for name, trace in traces.items():
        results.loc[name, 'different_dispatch_intervals'] = int(((trace - ref_trace).abs() > 1e-9).any(axis=1).sum())
    results.to_csv(outdir / 'equal_constraints_kpis.csv')
    (outdir / 'metadata.json').write_text(json.dumps({
        'input': str(path.relative_to(ROOT)),
        'input_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'input_intervals': len(data),
        'comparison': 'Same adaptive dispatcher and all identical constraints; only battery weight is constant or state-dependent',
        'thermal_guard': 'enabled identically in all cases',
        'lambda_bounds': {'min': low, 'max': high},
        'variants': {name: {'lambda_min': lo, 'lambda_max': hi} for name, (lo, hi) in variants.items()},
        'existing_source_files_modified': False,
    }, indent=2))
    print('\n', results.round(5).to_string(), '\nSaved:', outdir)

if __name__ == '__main__':
    main()
