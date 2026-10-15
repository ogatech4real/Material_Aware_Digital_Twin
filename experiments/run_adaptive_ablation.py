"""Controlled adaptive-supervisor ablation, using existing project functions.
Place in experiments/ and run from any working directory.
No existing results or source files are modified.
"""
from __future__ import annotations
import copy
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'src').is_dir():
    ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from src.special_issue_extension import run_adaptive_controller
from src.evaluation import summarize_kpis


def main():
    conf = yaml.safe_load((ROOT / 'config.yaml').read_text(encoding='utf-8'))
    df = pd.read_csv(ROOT / 'data' / 'sim_input.csv', index_col=0, parse_dates=True)
    dt_h = float(conf['time']['dt_minutes']) / 60
    e_nom = float(conf['battery']['e_nom_kwh'])
    assert len(df) > 0
    outdir = ROOT / 'results' / 'adaptive_ablation'
    outdir.mkdir(parents=True, exist_ok=True)
    cases = {
        'Adaptive_full': (True, True),
        'No_battery_weight': (False, True),
        'No_thermal_guard': (True, False),
        'Neither_mechanism': (False, False),
    }
    records = []
    for name, (use_weight, use_guard) in cases.items():
        c = copy.deepcopy(conf)
        a = c['adaptive_supervisor']
        if not use_weight:
            a['lambda_batt_min'] = 0.0
            a['lambda_batt_max'] = 0.0
        if not use_guard:
            a['thermal_price_guard_gbp_per_kwh'] = 0.0
        print('Running', name, flush=True)
        sim = run_adaptive_controller(df.copy(), c)
        residual = sim['pv_kw_ac'] + sim['pdis'] + sim['pimp'] - sim['load_kw'] - sim['pch'] - sim['pexp']
        if residual.abs().max() > 1e-7:
            raise RuntimeError(f'{name}: power balance residual {residual.abs().max()}')
        lo = float(a['soc_operating_min']); hi = float(a['soc_operating_max'])
        if (sim['soc'].min() < lo - 1e-8 or sim['soc'].max() > hi + 1e-8):
            raise RuntimeError(f'{name}: SoC outside limits')
        k = summarize_kpis(sim.join(df, rsuffix='_input'), dt_h, e_nom, c)
        k['scenario'] = name
        k['max_balance_error_kw'] = float(residual.abs().max())
        k['mean_lambda_batt'] = float(sim['lambda_batt_t'].mean())
        k['thermal_guard_enabled'] = use_guard
        k['battery_weight_enabled'] = use_weight
        records.append(k)
        sim[['soc','pch','pdis','pimp','pexp','lambda_batt_t','thermal_protection']].to_csv(outdir / f'{name.lower()}_trace.csv')
    result = pd.DataFrame(records).set_index('scenario')
    base = result.loc['Neither_mechanism']
    result['cost_change_vs_neither_pct'] = (result['annual_cost_gbp'] / base['annual_cost_gbp'] - 1) * 100
    result['efc_reduction_vs_neither_pct'] = (1 - result['equivalent_full_cycles'] / base['equivalent_full_cycles']) * 100
    result.to_csv(outdir / 'ablation_kpis.csv')
    (outdir / 'ablation_metadata.json').write_text(json.dumps({'comparison':'identical adaptive dispatch with 2x2 mechanism ablation', 'input':'data/sim_input.csv','dt_h':dt_h,'cases':{k:{'battery_weight':v[0],'thermal_guard':v[1]} for k,v in cases.items()}},indent=2))
    print(result[['annual_cost_gbp','equivalent_full_cycles','cost_change_vs_neither_pct','efc_reduction_vs_neither_pct']].round(4).to_string())
    print('Saved:',outdir)

if __name__ == '__main__':
    main()
