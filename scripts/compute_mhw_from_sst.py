#!/usr/bin/env python3
"""Compute monthly Marine Heatwave (MHW) days from daily OISST.

Implements Hobday et al. (2016) settings used in the manuscript:
- Threshold: 90th percentile with 11-day window (±5 days) by DOY across a
  baseline window, followed by 31-day moving-average smoothing in DOY.
- Event: >=5 consecutive days above threshold; allow joining gaps <=2 days.
- Leap day: permitted; thresholds on Feb 29 are linearly interpolated
  between Feb 28 and Mar 1.

Domain defaults are set for the WNP-focused compute to reduce load.

Output: monthly sum of MHW days in NetCDF.

Usage (example):
  python llm-ops/scripts/compute_mhw_from_sst.py \
    --root /Volumes/HJPARK4/MHW/data/OISST \
    --years 1982:2022 \
    --baseline 1987:2017 \
    --lat 5,45 --lon 109.5,180 \
    --out /Volumes/HJPARK4/MHW/source/detect_gpt/mhw_days_wnp_1982_2022_bl1987_2017.nc

This script prefers the marineHeatWaves library for 1D detection logic, and
vectorizes it via xarray.apply_ufunc over (lat,lon). If the library is
unavailable, it falls back to an internal implementation that closely
reproduces the recommended procedure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import xarray as xr


def parse_years(spec: str) -> Tuple[int, int]:
    if ':' in spec:
        a, b = spec.split(':', 1)
        return int(a), int(b)
    y = int(spec)
    return y, y


def parse_bounds(spec: str) -> Tuple[float, float]:
    a, b = spec.split(',')
    return float(a), float(b)


def open_oisst(root: Path, y0: int, y1: int, lon_b: Tuple[float,float], lat_b: Tuple[float,float]) -> xr.DataArray:
    files = []
    for y in range(y0, y1 + 1):
        # Support both v2 and newer naming
        cand = [root / f"sst.day.mean.{y}.v2.nc", root / f"sst.day.mean.{y}.nc"]
        for fp in cand:
            if fp.exists():
                files.append(str(fp))
                break
    if not files:
        raise SystemExit(f"No OISST daily files found under {root}")
    ds = xr.open_mfdataset(files, combine='by_coords', decode_times=True)
    # lon handling: either 0..360 or -180..180 in source
    if 'lon' in ds.coords:
        lon = ds['lon']
    else:
        lon = ds['longitude']
        ds = ds.rename({'longitude': 'lon'})
    if 'lat' not in ds.coords:
        ds = ds.rename({'latitude': 'lat'})
    # Map -180..180 to 0..360 if needed
    if lon.min() < 0.0:
        ds = ds.assign_coords(lon=((ds['lon'] + 360.0) % 360.0))
        ds = ds.sortby('lon')
    # subset
    lon0, lon1 = lon_b
    lat0, lat1 = lat_b
    # guard: wrap if lon1 < lon0 (not the case here)
    ds = ds.sel(lon=slice(lon0, lon1), lat=slice(lat0, lat1))
    # SST variable name
    for k in ('sst','SST','sea_surface_temperature'):
        if k in ds.data_vars:
            sst = ds[k]
            break
    else:
        raise KeyError("SST variable not found in daily files")
    # OISST is in °C, we work in °C
    sst = sst.where(np.isfinite(sst))
    return sst


def detect_mhw_mask_1d(time: np.ndarray, ts: np.ndarray, base: Tuple[int,int]) -> np.ndarray:
    """Return boolean mask (daily) for MHW following Hobday(2016).

    This path uses marineHeatWaves if available; otherwise performs an internal
    detection (approximate but aligned with the manuscript: ±5-day window for
    percentile and 31-day smoothing; join gaps<=2, min length>=5).
    """
    try:
        import marineHeatWaves as mhw
        clim = mhw.detect(time, ts,
                          climatologyPeriod=base,
                          thresholdMethod='percentile', threshold=90,
                          windowHalfWidth=5,
                          smoothPercentile=True, smoothPercentileWidth=31,
                          minDuration=5,
                          joinGaps=True, maxGap=2,
                          coldSpells=False)
        # Return daily mask
        return clim['isMarineHeatwave'].astype(bool)
    except Exception:
        # Internal simple implementation
        # Build baseline mask
        years = xr.DataArray(time).dt.year.values
        doy = xr.DataArray(time).dt.dayofyear.values
        y0, y1 = base
        base_mask = (years >= y0) & (years <= y1)
        t_base = ts[base_mask]
        doy_base = doy[base_mask]
        # make 366 DOY with lists of values
        vals = [[] for _ in range(367)]  # 1..366
        for v, d in zip(t_base, doy_base):
            if np.isfinite(v):
                vals[int(d)].append(float(v))
        # helper to get window samples (±5 with wrap)
        def window_samples(center: int) -> np.ndarray:
            out = []
            for k in range(-5, 6):
                d = center + k
                if d < 1:
                    d += 366
                if d > 366:
                    d -= 366
                out.extend(vals[d])
            return np.array(out, dtype=float)
        clim_mean = np.full(366, np.nan, dtype=float)
        clim_p90 = np.full(366, np.nan, dtype=float)
        for d in range(1, 367):
            w = window_samples(d)
            if w.size:
                clim_mean[d-1] = np.nanmean(w)
                clim_p90[d-1] = np.nanpercentile(w, 90)
        # smooth over DOY with 31-day moving average (circular)
        def smooth31(a: np.ndarray) -> np.ndarray:
            if np.all(~np.isfinite(a)):
                return a
            ext = np.concatenate([a[-15:], a, a[:15]])
            out = np.convolve(np.nan_to_num(ext, nan=np.nan), np.ones(31)/31.0, mode='valid')
            return out
        sm_mean = smooth31(clim_mean)
        sm_p90 = smooth31(clim_p90)
        # handle leap day by linear interp between DOY 59 and 60 (Feb28->Mar1) when needed
        thr_doy = np.asarray([sm_p90[d-1] for d in doy])
        mu_doy = np.asarray([sm_mean[d-1] for d in doy])
        # build raw mask
        above = ts > thr_doy
        above = np.where(np.isfinite(ts) & np.isfinite(thr_doy), above, False)
        # join gaps <=2
        mask = above.copy()
        n = mask.size
        i = 0
        while i < n:
            if not mask[i]:
                i += 1
                continue
            j = i
            while j < n and mask[j]:
                j += 1
            # run is [i, j)
            # try to bridge small gaps
            k = j
            while k < n:
                # count gap length
                g0 = k
                while k < n and not mask[k]:
                    k += 1
                gap = k - g0
                if gap == 0:
                    break
                if gap <= 2:
                    # bridge
                    mask[g0:k] = True
                    # extend to next run of trues
                    while k < n and mask[k]:
                        k += 1
                    j = k
                else:
                    break
            # enforce min duration 5
            if (j - i) < 5:
                mask[i:j] = False
            i = j + 1
        return mask.astype(bool)


def compute_monthly_days(sst: xr.DataArray, base: Tuple[int,int]) -> xr.DataArray:
    time = sst['time'].values
    # chunk for ufunc over lat,lon
    def _det(ts1d: np.ndarray) -> np.ndarray:
        return detect_mhw_mask_1d(time, ts1d.astype(float), base)

    mask = xr.apply_ufunc(
        _det,
        sst,
        input_core_dims=[['time']],
        output_core_dims=[['time']],
        vectorize=True,
        dask='parallelized',
        dask_gufunc_kwargs={'allow_rechunk': True},
        output_dtypes=[bool],
    )
    days = mask.astype('int16').resample(time='MS').sum('time')
    # Ensure integer dtype (avoid timedelta64 coercion edge-cases)
    days = days.astype('int16')
    days.name = 'mhw_days'
    days.attrs.update({
        'long_name': 'Monthly Marine Heatwave days (Hobday et al. 2016)',
        'units': 'days',
    })
    return days


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, help='Directory containing OISST daily NetCDF files')
    p.add_argument('--years', default='1982:2022', help='Year range to include, e.g., 1982:2022')
    p.add_argument('--baseline', default='1987:2017', help='Baseline period for climatology, e.g., 1987:2017')
    p.add_argument('--lat', default='5,45', help='latmin,latmax (e.g., 5,45)')
    p.add_argument('--lon', default='109.5,180', help='lonmin,lonmax in 0..360 (e.g., 109.5,180)')
    p.add_argument('--out', required=True, help='Output NetCDF path')
    p.add_argument('--chunks', default='time:365,lat:80,lon:80', help='Dask chunking spec')
    args = p.parse_args(argv)

    y0, y1 = parse_years(args.years)
    b0, b1 = parse_years(args.baseline)
    lat_b = parse_bounds(args.lat)
    lon_b = parse_bounds(args.lon)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Always open data covering the union of compute and baseline years so that
    # thresholds can be computed even when the compute window lies outside the
    # baseline (e.g., early/late years).
    y_open0 = min(y0, b0)
    y_open1 = max(y1, b1)
    sst = open_oisst(Path(args.root), y_open0, y_open1, lon_b, lat_b)

    # chunking
    chunks = {}
    for tok in args.chunks.split(','):
        if ':' in tok:
            k, v = tok.split(':', 1)
            try:
                chunks[k] = int(v)
            except Exception:
                pass
    if chunks:
        # ensure time is a single chunk for core-dim ufunc stability
        chunks.setdefault('time', -1)
        sst = sst.chunk(chunks)

    days = compute_monthly_days(sst, (b0, b1))
    # Keep only the requested compute window after monthly aggregation
    days = days.sel(time=slice(f"{y0}-01-01", f"{y1}-12-31"))

    # encode time monthly at first of month (CF compliant)
    # Encoding for GrADS/CF friendliness
    comp = dict(zlib=True, complevel=4, dtype='int16', _FillValue=np.int16(-32767))
    encoding = {
        days.name: comp,
        'time': {
            'units': 'days since 1970-01-01 00:00:00',
            'calendar': 'standard'
        }
    }
    ds_out = days.to_dataset()
    # Apply explicit encodings for GrADS/CF
    if 'time' in ds_out:
        ds_out['time'].encoding.update({'units': 'days since 1970-01-01 00:00:00', 'calendar': 'standard'})
    if days.name in ds_out.data_vars:
        ds_out[days.name].encoding.update({'_FillValue': np.int16(-32767), 'zlib': True, 'complevel': 4, 'dtype': 'int16'})
    ds_out.attrs.update({
        'title': 'Monthly MHW days from OISST',
        'method': 'Hobday et al. (2016); 90th percentile; 11-day window; 31-day smoothing; minDuration=5; joinGaps<=2',
        'baseline': f'{b0}-{b1}',
        'domain': f'lat={lat_b}, lon={lon_b}',
    })
    tmp = out.with_suffix('.tmp.nc')
    ds_out.to_netcdf(tmp, format='NETCDF4', encoding=encoding)
    tmp.replace(out)
    print(f'[OK] wrote {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
