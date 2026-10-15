"""Independent UK-DALE/PVGIS-input evaluation using the unchanged corrected controllers.

Run from the repository root:
    python experiments/run_measured_validation.py

Never reads/writes data/sim_input.csv or results/special_issue.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.controller import run_controller
from src.evaluation import summarize_kpis
from src.special_issue_extension import run_adaptive_controller

INPUT = ROOT / 'data' / 'measured_validation_input.csv'
OUT = ROOT / 'results' / 'measured_validation'
REQUIRED_INPUT = (
    'load_kw', 'pv_kw_raw', 'cell_temp_c', 'ambient_c',
    'price_import_gbp_per_kwh', 'price_export_gbp_per_kwh',
    'carbon_intensity',
)
REQUIRED_OUTPUT = (
    'soc', 'pch', 'pdis', 'pimp', 'pexp', 'pv_kw_ac',
    'pv_inverter_loss_kw', 'batt_inverter_loss_kw',
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_input(dt_h: float) -> pd.DataFrame:
    if not INPUT.is_file():
        raise FileNotFoundError(f'Missing input: {INPUT}. Run measured_data_preprocessor.py first.')
    df = pd.read_csv(INPUT, index_col=0, parse_dates=True)
    if not isinstance(df.index, pd.DatetimeIndex) or df.empty or df.index.hasnans:
        raise ValueError('Input must have a valid nonempty datetime index')
    if df.index.has_duplicates or not df.index.is_monotonic_increasing:
        raise ValueError('Input timestamps must be strictly increasing and unique')
    if df.index.tz is not None:
        raise ValueError('Expected naive UTC timestamps, as documented by preprocessor')
    absent = sorted(set(REQUIRED_INPUT) - set(df.columns))
    if absent:
        raise ValueError(f'Missing required input columns: {absent}')
    for c in REQUIRED_INPUT:
        df[c] = pd.to_numeric(df[c], errors='raise')
    if not np.isfinite(df[list(REQUIRED_INPUT)].to_numpy(dtype=float)).all():
        raise ValueError('Input contains nonfinite values')
    if (df[['load_kw', 'pv_kw_raw', 'price_import_gbp_per_kwh',
            'price_export_gbp_per_kwh']] < -1e-10).any().any():
        raise ValueError('Negative load, PV power or tariff detected')
    diffs = df.index.to_series().diff().dropna().dt.total_seconds().to_numpy() / 3600.0
    if not np.allclose(diffs, dt_h, atol=1e-9, rtol=0):
        raise ValueError('Discontinuous input or mismatch with config time.dt_minutes')
    return df


def validate_dispatch(name: str, sim: pd.DataFrame, df: pd.DataFrame, conf: dict, dt_h: float) -> dict:
    if len(sim) != len(df) or not sim.index.equals(df.index):
        raise ValueError(f'{name}: output timestamps/length mismatch')
    absent = sorted(set(REQUIRED_OUTPUT) - set(sim.columns))
    if absent:
        raise ValueError(f'{name}: missing controller outputs: {absent}')
    if not np.isfinite(sim[list(REQUIRED_OUTPUT)].to_numpy(dtype=float)).all():
        raise ValueError(f'{name}: nonfinite controller outputs')
    residual = sim['pv_kw_ac'] + sim['pdis'] + sim['pimp'] - sim['load_kw'] - sim['pch'] - sim['pexp']
    max_balance = float(residual.abs().max())
    if max_balance > 1e-7:
        raise ValueError(f'{name}: AC power balance violation {max_balance:.4g} kW')
    soc_min = float(conf['battery']['soc_min']) if 'soc_min' in conf['battery'] else 0.0
    soc_max = float(conf['battery']['soc_max']) if 'soc_max' in conf['battery'] else 1.0
    if sim['soc'].min() < soc_min - 1e-7 or sim['soc'].max() > soc_max + 1e-7:
        raise ValueError(f'{name}: SoC outside configured limits [{soc_min},{soc_max}]')
    return {'max_ac_balance_residual_kw': max_balance,
            'min_soc': float(sim['soc'].min()), 'max_soc': float(sim['soc'].max())}


def main() -> None:
    config_path = ROOT / 'config.yaml'
    with config_path.open(encoding='utf-8') as f:
        conf = yaml.safe_load(f)
    dt_h = float(conf['time']['dt_minutes']) / 60.0
    e_nom = float(conf['battery']['e_nom_kwh'])
    if not math.isfinite(dt_h) or not math.isfinite(e_nom) or min(dt_h, e_nom) <= 0:
        raise ValueError('Invalid time step or battery nominal capacity')
    df = load_input(dt_h)
    duration_days = len(df) * dt_h / 24.0
    print(f'INPUT PASS: {len(df):,} consecutive intervals, {duration_days:.2f} days')
    print(f'Window: {df.index[0]} to {df.index[-1]}')
    print('Synthetic annual data/results will not be read or modified.')

    runners = (
        ('Baseline', lambda: run_controller(df.copy(), conf, 'baseline')),
        ('Batt-Aware', lambda: run_controller(df.copy(), conf, 'batt')),
        ('Batt+PV-Aware', lambda: run_controller(df.copy(), conf, 'full')),
        ('Adaptive-Supervisory', lambda: run_adaptive_controller(df.copy(), conf)),
    )
    rows, validation, results = [], {}, {}
    for name, run in runners:
        print(f'Running {name} ...', flush=True)
        tic = time.perf_counter()
        sim = run()
        elapsed = time.perf_counter() - tic
        validation[name] = validate_dispatch(name, sim, df, conf, dt_h)
        k = summarize_kpis(sim.join(df, rsuffix='_in'), dt_h, e_nom, conf)
        k.update({
            'scenario': name,
            'runtime_s': elapsed,
            'mean_step_runtime_ms': elapsed * 1000.0 / len(sim),
            'pv_inverter_loss_kwh': float(sim['pv_inverter_loss_kw'].sum() * dt_h),
            'batt_inverter_loss_kwh': float(sim['batt_inverter_loss_kw'].sum() * dt_h),
        })
        if name == 'Adaptive-Supervisory':
            for col, key in [('lambda_batt_t', 'mean_lambda_batt'),
                             ('lambda_pv_t', 'mean_lambda_pv'),
                             ('supervisor_stress', 'mean_supervisor_stress')]:
                if col in sim:
                    k[key] = float(sim[col].mean())
        rows.append(k)
        results[name] = sim
        print(f'  PASS: cost GBP {k["annual_cost_gbp"]:.3f} (period total); EFC {k["equivalent_full_cycles"]:.3f}; AC residual {validation[name]["max_ac_balance_residual_kw"]:.2e}')

    kpis = pd.DataFrame(rows).set_index('scenario')
    # Legacy evaluator names this 'annual_cost_gbp', but the evaluation is NOT annual.
    kpis = kpis.rename(columns={'annual_cost_gbp': 'period_cost_gbp'})
    kpis['cost_difference_vs_baseline_gbp'] = kpis['period_cost_gbp'] - kpis.loc['Baseline', 'period_cost_gbp']
    # A negative period cost denotes net export revenue; ratios to negative baseline cost are misleading.
    kpis['cost_improvement_vs_baseline_pct_of_abs_baseline'] = 100 * (kpis.loc['Baseline', 'period_cost_gbp'] - kpis['period_cost_gbp']) / abs(kpis.loc['Baseline', 'period_cost_gbp']) if abs(kpis.loc['Baseline', 'period_cost_gbp']) > 1e-9 else float('nan')
    kpis['efc_reduction_vs_baseline_pct'] = 100 * (1 - kpis['equivalent_full_cycles'] / kpis.loc['Baseline', 'equivalent_full_cycles'])
    kpis['cost_gbp_per_day'] = kpis['period_cost_gbp'] / duration_days
    kpis['efc_per_day'] = kpis['equivalent_full_cycles'] / duration_days
    # Write only after all four policies pass numerical checks.
    OUT.mkdir(parents=True, exist_ok=True)
    for name, sim in results.items():
        filename = name.lower().replace('+', 'plus').replace('-', '_') + '.csv'
        sim.to_csv(OUT / filename)
    kpis.to_csv(OUT / 'kpis_measured_validation.csv')
    meta = {
        'experiment': 'Supplementary UK-DALE demand and PVGIS meteorological input dispatch comparison',
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'input_file': 'data/measured_validation_input.csv',
        'input_sha256': sha256(INPUT),
        'config_sha256': sha256(config_path),
        'n_steps': len(df), 'dt_minutes': dt_h * 60,
        'start_timestamp': str(df.index[0]), 'end_timestamp': str(df.index[-1]),
        'period_days': duration_days,
        'source_qualification': 'UK-DALE measured demand; PVGIS model-derived historical weather; PV generation calculated, not measured',
        'weather_location_qualification': 'PVGIS coordinates currently approximate Oxford proxy; confirm before publication',
        'time_qualification': 'Input preprocessing treats naive timestamps as UTC and floors PVGIS HH:11 to HH:00; verify source conventions',
        'tariff_qualification': 'Tariff and carbon-intensity profiles are synthetic assumptions, not observed market/emissions data',
        'kpi_qualification': 'Legacy evaluator annual_cost_gbp renamed period_cost_gbp; no annual extrapolation; negative cost is net export revenue; EFC is discharge-throughput proxy',
        'controller_qualification': 'Same corrected fixed and adaptive rule-based controllers as synthetic experiment; no solver or hardware validation',
        'scenario_qualification': 'Fixed policies have different operating rules/SoC windows; differences cannot be attributed solely to degradation weights',
        'runtime_qualification': 'Full Python simulation elapsed time / intervals, not isolated embedded controller latency',
        'checks': validation,
    }
    with (OUT / 'experiment_metadata.json').open('w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    print('\nRESULTS: 198.25-day totals, not annualized')
    print(kpis[['period_cost_gbp', 'equivalent_full_cycles', 'cost_difference_vs_baseline_gbp',
                'efc_reduction_vs_baseline_pct', 'capacity_fade_pct']].round(4).to_string())
    print(f'\nPASS: four-policy measured-input evaluation saved to {OUT}')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        print('FAILED: measured experiment incomplete; synthetic inputs/results not modified.', file=sys.stderr)
        sys.exit(1)
