"""Read-only diagnosis of adaptive discharge decisions from a completed ablation.

Place in experiments/. Reads data/sim_input.csv, config.yaml and
results/adaptive_ablation/*_trace.csv. Does not run or alter controllers.
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results' / 'adaptive_ablation'


def main():
    cfg = yaml.safe_load((ROOT / 'config.yaml').read_text(encoding='utf-8'))
    a = cfg['adaptive_supervisor']
    econ = cfg['economics']
    inv = cfg['inverter']
    dt = float(cfg['time']['dt_minutes']) / 60.0
    e_nom = float(cfg['battery']['e_nom_kwh'])
    eta_dis = float(cfg['battery']['eta_dis']) * float(inv['eta_batt'])
    soc_min = max(float(cfg['battery']['soc_min']), float(a['soc_operating_min']))
    inputs = pd.read_csv(ROOT / 'data' / 'sim_input.csv', index_col=0)
    names = ['adaptive_full', 'no_battery_weight', 'no_thermal_guard', 'neither_mechanism']
    traces = {n: pd.read_csv(OUT / f'{n}_trace.csv', index_col=0) for n in names}
    if any(len(t) != len(inputs) for t in traces.values()):
        raise ValueError('Input/trace length mismatch')
    if any(not inputs.index.equals(t.index) for t in traces.values()):
        raise ValueError('Input/trace time-index mismatch')
    full = traces['adaptive_full']
    price = inputs['price_import_gbp_per_kwh'].to_numpy(float)
    lam = full['lambda_batt_t'].to_numpy(float)
    guard = full['thermal_protection'].to_numpy(float)
    soc = full['soc'].to_numpy(float)
    deficit = (inputs['load_kw'].to_numpy(float) - inputs['pv_kw_raw'].to_numpy(float))
    # Use measured AC dispatch to classify deficit; PV AC may differ from raw DC.
    # Grid/charge/discharge balance: load - PV_ac = import + discharge - charge - export.
    deficit_ac = (full['pimp'].to_numpy(float) + full['pdis'].to_numpy(float)
                  - full['pch'].to_numpy(float) - full['pexp'].to_numpy(float))
    headroom_kw = np.maximum(0, (soc - soc_min) * e_nom * eta_dis / dt)
    available = (deficit_ac > 1e-9) & (headroom_kw > 1e-9)
    base_high = float(a.get('price_high', econ.get('batt_price_high', .315)))
    penalty = lam * float(econ.get('batt_deg_marginal_gbp_per_kwh', .03))
    thermal_add = guard * float(a.get('thermal_price_guard_gbp_per_kwh', .08))
    full_margin = price - penalty - base_high - thermal_add
    no_weight_margin = price - base_high - thermal_add
    no_guard_margin = price - penalty - base_high
    neither_margin = price - base_high
    decision = lambda m: available & (m > 0)
    predicted = {k: decision(v) for k,v in {
        'adaptive_full': full_margin, 'no_battery_weight': no_weight_margin,
        'no_thermal_guard': no_guard_margin, 'neither_mechanism': neither_margin,
    }.items()}
    observed = {k: t['pdis'].to_numpy(float) > 1e-9 for k,t in traces.items()}
    summary = {
        'intervals': int(len(inputs)), 'price_min': float(price.min()),
        'price_max': float(price.max()), 'price_unique_rounded_6dp': int(np.unique(np.round(price,6)).size),
        'battery_weight_nonzero_steps': int((lam > 1e-12).sum()),
        'thermal_guard_active_steps': int((guard > 1e-12).sum()),
        'ac_deficit_steps': int((deficit_ac > 1e-9).sum()),
        'battery_energy_available_steps': int((headroom_kw > 1e-9).sum()),
        'eligible_deficit_steps': int(available.sum()),
        'full_discharge_steps': int(observed['adaptive_full'].sum()),
        'price_near_base_threshold_0p01_steps': int((np.abs(price-base_high)<=.01).sum()),
        'max_battery_penalty_gbp_per_kwh': float(penalty.max()),
        'max_thermal_threshold_addition_gbp_per_kwh': float(thermal_add.max()),
        'min_abs_full_margin_on_eligible_steps': float(np.min(np.abs(full_margin[available]))) if available.any() else None,
    }
    for k in names:
        summary[f'{k}_predicted_discharge_steps'] = int(predicted[k].sum())
        summary[f'{k}_observed_discharge_steps'] = int(observed[k].sum())
        summary[f'{k}_prediction_mismatch_steps'] = int((predicted[k] != observed[k]).sum())
        summary[f'{k}_dispatch_difference_vs_full_steps'] = int((observed[k] != observed['adaptive_full']).sum())
    for k in names[1:]:
        summary[f'{k}_threshold_flip_opportunities'] = int((predicted[k] != predicted['adaptive_full']).sum())
    table = pd.DataFrame({
        'price_import': price, 'soc': soc, 'ac_deficit_kw': deficit_ac,
        'discharge_headroom_kw': headroom_kw, 'lambda_batt': lam,
        'battery_penalty_gbp_per_kwh': penalty, 'thermal_protection': guard,
        'thermal_guard_add_gbp_per_kwh': thermal_add,
        'margin_full_gbp_per_kwh': full_margin,
        'margin_no_weight_gbp_per_kwh': no_weight_margin,
        'margin_no_guard_gbp_per_kwh': no_guard_margin,
        'margin_neither_gbp_per_kwh': neither_margin,
        'eligible': available, 'observed_discharge_full': observed['adaptive_full'],
        'predicted_discharge_full': predicted['adaptive_full'],
    }, index=inputs.index)
    OUT.mkdir(parents=True,exist_ok=True)
    table.to_csv(OUT / 'threshold_diagnostics.csv')
    (OUT / 'threshold_diagnostics_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    print('Saved diagnostic files to',OUT)
    if summary['adaptive_full_prediction_mismatch_steps']:
        print('WARNING: Predicted and recorded decisions differ; inspect traces before interpreting.')

if __name__ == '__main__':
    main()
