"""Prepare UK-DALE + PVGIS inputs without changing the synthetic simulation.

Run from anywhere: python src/measured_data_preprocessor.py
Dependencies: pandas, numpy, PyYAML (already used by this project).

Default: reads data/ukdale.csv, verifies raw PVGIS year coverage, fetches the
missing 2013 PVGIS hourly series if necessary, and writes validated outputs.
Internet is needed only if PVGIS 2013 is absent. PVGIS location defaults to an
APPROXIMATE Oxford-area proxy, not a verified UK-DALE household coordinate.
Set --lat/--lon to the intended meteorological location before publication.

Never overwrites sim_input.csv, existing experiment results, or raw data.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
RAW = DATA / 'raw'
DT = pd.Timedelta(minutes=15)
REQUIRED = ['timestamp','load_kw','pv_kw_raw','price_import_gbp_per_kwh',
            'price_export_gbp_per_kwh','ambient_c','cell_temp_c','carbon_intensity']


def atomic_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', prefix='.tmp_',
                                     dir=path.parent, delete=False, encoding='utf-8') as f:
        tmp = Path(f.name)
        try:
            df.to_csv(f, index=False, float_format='%.10g')
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
    os.replace(tmp, path)


def read_load(path: Path) -> pd.Series:
    if not path.exists():
        raise FileNotFoundError(f'UK-DALE input missing: {path}')
    # Existing 15-minute UK-DALE processing is retained to avoid altering
    # the original source aggregation methodology in this validation run.
    df = pd.read_csv(path, usecols=['timestamp', 'load_kw'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='raise')
    if df.timestamp.isna().any() or df.timestamp.duplicated().any():
        raise ValueError('UK-DALE timestamps contain nulls or duplicates')
    if (df.timestamp.dt.minute % 15).any() or df.timestamp.dt.second.ne(0).any():
        raise ValueError('UK-DALE timestamps are not on the 15-minute grid')
    load = pd.to_numeric(df.load_kw, errors='coerce')
    if (load.dropna() < 0).any():
        raise ValueError('Negative UK-DALE power readings')
    out = pd.Series(load.to_numpy(dtype=float), index=pd.DatetimeIndex(df.timestamp), name='load_kw').sort_index()
    return out


def parse_pvgis_csv(path: Path) -> pd.DataFrame:
    # Repository CSV format: time,G(i),H_sun,T2m,WS10m,Int.
    # PVGIS hourly observations are labelled HH:11; assign to the HH:00
    # grid as an hourly representative value, then interpolate to 15 min.
    raw = pd.read_csv(path, comment='#')
    if not {'time','G(i)','T2m'}.issubset(raw.columns):
        raise ValueError(f'Invalid PVGIS CSV columns: {path}')
    ts = pd.to_datetime(raw['time'].astype(str), format='%Y%m%d:%H%M', errors='raise')
    out = pd.DataFrame({'irr_wm2': pd.to_numeric(raw['G(i)'], errors='coerce').to_numpy(),
                        'ambient_c': pd.to_numeric(raw['T2m'], errors='coerce').to_numpy()},
                       index=pd.DatetimeIndex(ts).floor('h'))
    if out.index.has_duplicates or out.isna().any().any():
        raise ValueError(f'Duplicate or invalid PVGIS hourly observations: {path}')
    if (out.irr_wm2 < 0).any() or not out.ambient_c.between(-60, 65).all():
        raise ValueError(f'Physically implausible PVGIS values: {path}')
    return out.sort_index()


def fetch_pvgis(lat: float, lon: float, startyear: int, endyear: int, timeout: int = 90) -> pd.DataFrame:
    params = {'lat': lat, 'lon': lon, 'startyear': startyear, 'endyear': endyear,
              'outputformat': 'json', 'pvcalculation': 0, 'components': 1}
    url = 'https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?' + urlencode(params)
    req = Request(url, headers={'User-Agent': 'AcademicMeasuredInputAudit/1.0'})
    with urlopen(req, timeout=timeout) as response:
        payload = json.load(response)
    hourly = payload.get('outputs', {}).get('hourly', [])
    if not hourly:
        raise ValueError('PVGIS API returned no hourly records: ' + str(payload.get('message', ''))[:250])
    df = pd.DataFrame(hourly)
    if not {'time', 'T2m'}.issubset(df.columns):
        raise ValueError('PVGIS API lacks time or T2m: ' + str(list(df.columns)))
    # With components=1, PVGIS returns beam, diffuse and reflected
    # irradiance separately instead of the combined G(i) field.
    if 'G(i)' in df.columns:
        irradiance = pd.to_numeric(df['G(i)'], errors='raise')
    elif {'Gb(i)', 'Gd(i)', 'Gr(i)'}.issubset(df.columns):
        irradiance = sum(pd.to_numeric(df[c], errors='raise')
                         for c in ('Gb(i)', 'Gd(i)', 'Gr(i)'))
    else:
        raise ValueError('PVGIS API lacks irradiance fields: ' + str(list(df.columns)))
    ts = pd.to_datetime(df['time'].astype(str), format='%Y%m%d:%H%M', errors='raise')
    result = pd.DataFrame({'irr_wm2': irradiance.to_numpy(),
                           'ambient_c': pd.to_numeric(df['T2m'], errors='raise').to_numpy()},
                          index=pd.DatetimeIndex(ts).floor('h')).sort_index()
    if result.index.has_duplicates or result.isna().any().any():
        raise ValueError('PVGIS API returned duplicate timestamps or missing weather')
    return result


def load_weather(load_index: pd.DatetimeIndex, args) -> tuple[pd.DataFrame, dict]:
    first = int(load_index.min().year)
    last = int(load_index.max().year)
    raw_files = sorted(RAW.glob('pvgis_seriescalc_*.csv'))
    frames = [parse_pvgis_csv(p) for p in raw_files]
    weather = pd.concat(frames).sort_index() if frames else pd.DataFrame(columns=['irr_wm2','ambient_c'])
    if weather.index.has_duplicates:
        raise ValueError('PVGIS raw files overlap; remove duplicate source years')
    existing_years = sorted(set(weather.index.year)) if len(weather) else []
    missing_years = [y for y in range(first, last + 1) if y not in existing_years]
    source = {'raw_files': [str(p.relative_to(ROOT)) for p in raw_files],
              'pvgis_location_lat': args.lat, 'pvgis_location_lon': args.lon,
              'pvgis_location_is_proxy': not args.location_confirmed,
              'fetched_years': []}
    if missing_years:
        if args.offline:
            raise RuntimeError(f'PVGIS years missing: {missing_years}. Add matching raw CSVs or rerun without --offline to download.')
        print(f'PVGIS missing {missing_years}; requesting historical weather from JRC PVGIS API...')
        for y in missing_years:
            extra = fetch_pvgis(args.lat, args.lon, y, y)
            # Save an explicit, auditable API-derived source file, but only
            # after successful download and basic validation.
            cache = RAW / f'pvgis_seriescalc_{y}_api.csv'
            # Build the cache from the DatetimeIndex directly.  Do not rely
            # on reset_index() producing a particular index-column name.
            cache_df = pd.DataFrame({
                'time': extra.index.strftime('%Y%m%d:%H%M'),
                'G(i)': extra['irr_wm2'].to_numpy(),
                'T2m': extra['ambient_c'].to_numpy(),
            })
            atomic_csv(cache_df, cache)
            source['fetched_years'].append(y)
            weather = pd.concat([weather, extra]).sort_index()
    # Require EVERY hourly weather timestamp from start to end, plus the
    # following hour for the final interpolation interval.
    start_hour = load_index.min().floor('h')
    end_hour = load_index.max().ceil('h')
    hourly_grid = pd.date_range(start_hour, end_hour, freq='h')
    hourly = weather.reindex(hourly_grid)
    bad = hourly.isna().any(axis=1)
    if bad.any():
        samples = [str(x) for x in hourly.index[bad][:5]]
        raise RuntimeError(f'PVGIS has {int(bad.sum())} missing hours in required coverage; first: {samples}. Refusing fill.')
    return hourly, source


def select_segments(valid: pd.DataFrame, min_days: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    starts = valid.index.to_series().diff().ne(DT).cumsum()
    segments = []
    for _, part in valid.groupby(starts, sort=True):
        n = len(part)
        segments.append({'start': str(part.index[0]), 'end': str(part.index[-1]),
                         'rows': n, 'duration_days': n / 96.0})
    seg = pd.DataFrame(segments).sort_values(['rows','start'], ascending=[False,True]).reset_index(drop=True)
    if seg.empty or seg.iloc[0]['duration_days'] < min_days:
        raise RuntimeError(f'No continuous measured-input segment of at least {min_days} days')
    best = seg.iloc[0]
    chosen = valid.loc[pd.Timestamp(best['start']):pd.Timestamp(best['end'])]
    assert len(chosen) == int(best['rows'])
    return chosen, seg


def prepare(args) -> dict:
    conf_path = ROOT / 'config.yaml'
    with conf_path.open(encoding='utf-8') as f:
        conf = yaml.safe_load(f)
    if int(conf.get('time',{}).get('dt_minutes',15)) != 15:
        raise ValueError('This preprocessing workflow requires a 15-minute controller timestep')
    load = read_load(DATA / 'ukdale.csv')
    grid = pd.date_range(load.index.min(), load.index.max(), freq='15min')
    if not load.index.equals(grid):
        # Source can be sparse, but only the missing intervals are introduced;
        # do not interpolate demand or silently bridge gaps.
        load = load.reindex(grid)
    hourly, source = load_weather(grid, args)
    weather = hourly.reindex(grid.union(hourly.index)).interpolate(method='time', limit_area='inside').reindex(grid)
    if weather.isna().any().any():
        raise RuntimeError('Incomplete weather after hourly-to-15-minute interpolation')
    if (weather.irr_wm2 < -1e-9).any():
        raise RuntimeError('Negative interpolated irradiance')
    weather['irr_wm2'] = weather.irr_wm2.clip(lower=0)
    pdc = float(conf['pv']['p_dc_stc_kw'])
    env = conf['environment']
    econ = conf['economics']
    irr_norm = weather.irr_wm2 / 1000.0
    idx = grid
    hour = idx.hour.to_numpy()
    imp = np.full(len(idx), float(econ['price_import_base_gbp_per_kwh']))
    imp[(hour >= 17) & (hour <= 21)] += float(econ['price_peak_spread_gbp_per_kwh'])
    imp[(hour >= 1) & (hour <= 5)] -= abs(float(econ['price_offpeak_reduction_gbp_per_kwh']))
    imp = np.maximum(0.05, imp)
    export = imp * float(econ['export_multiplier'])
    carbon = float(env['carbon_intensity_base_kg_per_kwh']) + float(env['carbon_intensity_amp']) * np.sin(2*np.pi*(hour/24.0))
    full = pd.DataFrame(index=idx)
    full['load_kw'] = load
    full['pv_kw_raw'] = pdc * irr_norm
    full['price_import_gbp_per_kwh'] = imp
    full['price_export_gbp_per_kwh'] = export
    full['ambient_c'] = weather.ambient_c
    full['cell_temp_c'] = weather.ambient_c + float(env['pv_temp_rise_c_at_irr1']) * irr_norm
    full['carbon_intensity'] = carbon
    valid = full.dropna(subset=['load_kw']).copy()
    if valid.empty or valid.isna().any().any():
        raise RuntimeError('No valid combined UK-DALE/PVGIS observations')
    chosen, segments = select_segments(valid, args.min_days)
    if not chosen.index.to_series().diff().iloc[1:].eq(DT).all():
        raise RuntimeError('Selected validation segment is not continuous')
    if (chosen[['load_kw','pv_kw_raw']] < 0).any().any():
        raise RuntimeError('Negative power found')
    # Guard against the historical 2013 all-zero PVGIS bug.
    daylight = chosen.index.hour.to_numpy()
    day = (daylight >= 9) & (daylight <= 15)
    if not (chosen.loc[day, 'pv_kw_raw'] > 0).any():
        raise RuntimeError('Selected segment has no positive daytime PV generation; check PVGIS dates')
    if chosen['ambient_c'].nunique() < 10:
        raise RuntimeError('Selected segment has nearly constant temperature; check PVGIS dates')
    report = {
        'status': 'passed', 'created_utc': datetime.now(timezone.utc).isoformat(),
        'data_sources': source,
        'source_load_path': 'data/ukdale.csv',
        'raw_load_file_available': (RAW/'ukdale_active_power.csv').exists(),
        'time_basis': 'naive timestamps treated as UTC; PVGIS HH:11 floored to HH:00',
        'weather_15min_method': 'time-linear interpolation of hourly PVGIS observations',
        'load_missing_policy': 'never interpolated; select longest contiguous 15-minute segment',
        'tariff_and_carbon': 'synthetic config-derived profiles; not observed market or emissions data',
        'pv_generation': 'p_dc_stc_kw * G(i)/1000; temperature effects applied by controller',
        'input_rows': len(grid), 'missing_load_rows': int(full.load_kw.isna().sum()),
        'valid_rows_all_segments': len(valid), 'number_of_segments': len(segments),
        'selected_start': str(chosen.index.min()), 'selected_end': str(chosen.index.max()),
        'selected_rows': len(chosen), 'selected_days': len(chosen)/96.0,
        'selected_load_kwh': float(chosen.load_kw.sum()*.25),
        'selected_pv_raw_kwh': float(chosen.pv_kw_raw.sum()*.25),
        'selected_daylight_positive_pv_intervals': int((chosen.loc[day,'pv_kw_raw']>0).sum()),
        'selected_ambient_range_c': [float(chosen.ambient_c.min()), float(chosen.ambient_c.max())],
        'output_columns': REQUIRED,
        'warning': 'Measured-input dispatch test; not physical PV-battery digital twin validation.'
    }
    if args.location_confirmed is False:
        print('WARNING: PVGIS coordinates are an approximate Oxford-area proxy. Confirm --lat/--lon before publication.')
    if args.dry_run:
        print(json.dumps(report, indent=2))
        print('DRY RUN: no processed output files overwritten')
        return report
    # Prepare all content and validate BEFORE replacing any derived CSVs.
    atomic_csv(load.rename_axis('timestamp').reset_index(), DATA/'ukdale.csv')
    atomic_csv(weather.rename_axis('timestamp').reset_index(), DATA/'pvgis.csv')
    atomic_csv(valid.rename_axis('timestamp').reset_index()[REQUIRED], DATA/'measured_input.csv')
    atomic_csv(chosen.rename_axis('timestamp').reset_index()[REQUIRED], DATA/'measured_validation_input.csv')
    out = ROOT/'results'/'measured_validation'
    out.mkdir(parents=True, exist_ok=True)
    atomic_csv(segments, out/'observation_segments.csv')
    (out/'preprocessing_report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print('PASS: measured-input preprocessing complete')
    print(f"Selected continuous window: {report['selected_start']} to {report['selected_end']} ({report['selected_days']:.2f} days)")
    print('Controller-ready: data/measured_validation_input.csv')
    print('Existing data/sim_input.csv and synthetic results: UNCHANGED')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--lat', type=float, default=51.752, help='PVGIS latitude (default: approximate Oxford proxy)')
    parser.add_argument('--lon', type=float, default=-1.257, help='PVGIS longitude (default: approximate Oxford proxy)')
    parser.add_argument('--location-confirmed', action='store_true', help='You have verified the PVGIS site coordinates')
    parser.add_argument('--offline', action='store_true', help='Never request PVGIS API; require complete local raw CSVs')
    parser.add_argument('--dry-run', action='store_true', help='Validate and report without changing processed CSVs')
    parser.add_argument('--min-days', type=float, default=28.0, help='Minimum acceptable continuous window')
    args = parser.parse_args()
    try:
        prepare(args)
    except Exception as exc:
        print(f'FAILED SAFELY: {type(exc).__name__}: {exc}', file=sys.stderr)
        print('Existing synthetic input and experiment outputs were not modified.', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
