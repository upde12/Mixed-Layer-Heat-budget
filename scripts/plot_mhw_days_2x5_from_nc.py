#!/usr/bin/env python3
"""Render a 2×5 panel of MHW days composites from a monthly NetCDF.

Rows: ELT mean, NT mean
Cols: Annual(mean of 12 months), JFM, AMJ, JAS, OND (means of the 3-month windows)

Input NetCDF is expected to contain monthly MHW days as a variable named
`mhw_days(time, lat, lon)` where `mhw_days` can be numeric days or
`timedelta64` convertible to days. Time must be monthly timestamps.

Usage (example):
  python llm-ops/scripts/plot_mhw_days_2x5_from_nc.py \
    --nc-file /Volumes/HJPARK4/MHW/source/detect_hobday/mhw_days_wnp_1982_2022_bl1987_2017.nc \
    --elt 1983,1988,1995,1998,2010,2016,2020 \
    --nt 1984,1991,1994,1999,2001,2004,2008,2013,2017,2021 \
    --out /Volumes/HJPARK4/MHW/source/detect_hobday/mhw_days_abs_ELT_NT_2x5.png
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
from statistics import NormalDist

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
except Exception:
    ccrs = None
    cfeature = None


def parse_years(spec: str) -> List[int]:
    return [int(s) for s in spec.split(',') if s.strip()]


def cmap_white_inferno(white_frac: float = 0.06) -> mcolors.Colormap:
    """Sequential map: white → inferno (widely used for heat metrics).

    white_frac controls how much of the lower range is forced to white to make
    0 stand out while retaining inferno’s warm mid/high tones (purple→orange→yellow).
    """
    base = plt.get_cmap('inferno')
    N = 256
    cols = base(np.linspace(0, 1, N))
    k = max(1, min(N-1, int(round(N * float(white_frac)))))
    cols[:k, :3] = 1.0  # force low values to white
    return mcolors.ListedColormap(cols, name='white_inferno')


def cmap_white_red(lighten: float = 0.0) -> mcolors.Colormap:
    """White→deep red ramp with richer midtones (pink/salmon) for readability."""
    stops = np.array([
        [1.00, 1.00, 1.00],  # white
        [1.00, 0.955, 0.955],
        [1.00, 0.880, 0.880],
        [1.00, 0.760, 0.760],
        [1.00, 0.600, 0.600],
        [0.98, 0.35, 0.35],
        [0.88, 0.12, 0.12],
        [0.60, 0.00, 0.00],
    ], dtype=float)
    if lighten > 0:
        stops = stops * (1.0 - lighten) + lighten
    return mcolors.LinearSegmentedColormap.from_list('white_to_red', stops, N=256)


def cmap_white_orange_red() -> mcolors.Colormap:
    """White → peach → orange → red → maroon.

    Monotonic deepening with subtle hue change favored for heat metrics.
    """
    stops = np.array([
        [1.00, 1.00, 1.00],  # white
        [0.99, 0.94, 0.91],  # peach
        [0.99, 0.80, 0.60],  # light orange
        [0.98, 0.55, 0.35],  # orange-red
        [0.88, 0.20, 0.12],  # strong red
        [0.60, 0.00, 0.00],  # maroon
    ], dtype=float)
    return mcolors.LinearSegmentedColormap.from_list('white_orange_red', stops, N=256)


def cmap_white_blue_green_yellow_red() -> mcolors.Colormap:
    """White → Blue → Green → Yellow → Red continuous ramp."""
    stops = [
        (1.00, 1.00, 1.00),  # white
        (0.88, 0.95, 1.00),  # very light blue
        (0.55, 0.75, 0.98),  # sky blue
        (0.25, 0.55, 0.90),  # blue
        (0.20, 0.75, 0.55),  # green
        (0.60, 0.85, 0.30),  # yellow‑green
        (0.98, 0.92, 0.30),  # yellow
        (0.98, 0.60, 0.15),  # orange
        (0.90, 0.20, 0.10),  # red
    ]
    return mcolors.LinearSegmentedColormap.from_list('white_blue_green_yellow_red', stops, N=256)


def add_map(ax, left: bool, bottom: bool) -> None:
    if ccrs is None:
        if bottom: ax.set_xlabel("Longitude")
        if left: ax.set_ylabel("Latitude")
        return
    try:
        land50 = cfeature.NaturalEarthFeature('physical', 'land', '50m', edgecolor='black', facecolor='lightgrey', linewidth=0.6)
        ax.add_feature(land50, zorder=0)
    except Exception:
        ax.add_feature(cfeature.LAND, facecolor='lightgrey', edgecolor='black', linewidth=0.6, zorder=0)
    ax.coastlines(resolution='50m', color='black', linewidth=0.8)
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.4, linestyle=':')
    gl.xlocator = mticker.MultipleLocator(5); gl.ylocator = mticker.MultipleLocator(5)
    try:
        gl.xformatter = LongitudeFormatter(number_format='.0f', degree_symbol='°')
        gl.yformatter = LatitudeFormatter(number_format='.0f', degree_symbol='°')
    except Exception:
        pass
    try:
        gl.top_labels = False; gl.right_labels = False; gl.left_labels = bool(left); gl.bottom_labels = bool(bottom)
    except Exception:
        gl.xlabels_top = False; gl.ylabels_right = False; gl.ylabels_left = bool(left); gl.xlabels_bottom = bool(bottom)
    gl.xlabel_style = {"size": 9, "rotation": 0}; gl.ylabel_style = {"size": 9}


def monthly_days(da: xr.DataArray) -> xr.DataArray:
    """Return days as float32 from `da` which may be numeric or timedelta64."""
    if np.issubdtype(da.dtype, np.timedelta64):
        out = (da / np.timedelta64(1, 'D')).astype('float32')
    else:
        out = da.astype('float32')
    return out


def window_months() -> List[Tuple[str, List[int]]]:
    return [
        ("Annual", list(range(1, 13))),
        ("JFM", [1, 2, 3]),
        ("AMJ", [4, 5, 6]),
        ("JAS", [7, 8, 9]),
        ("OND", [10, 11, 12]),
    ]


def composite_for_years(da_mon: xr.DataArray, years: List[int]) -> dict[str, np.ndarray]:
    """Compute per-window mean fields for the given `years`.

    - Annual: mean over 12 months in each year, then average over years
    - Seasonal windows: mean of the 3 months in each year, then average over years
    """
    results: dict[str, np.ndarray] = {}
    for wname, months in window_months():
        fields = []
        for y in years:
            sel = da_mon.sel(time=da_mon['time'].dt.year == y)
            if sel.sizes.get('time', 0) == 0:
                continue
            # monthly subset for the window
            wsel = sel.sel(time=sel['time'].dt.month.isin(months))
            if wsel.sizes.get('time', 0) == 0:
                continue
            fields.append(wsel.mean('time', skipna=True).values)
        if fields:
            results[wname] = np.nanmean(np.stack(fields, axis=0), axis=0)
    return results


def draw_box(ax, lon0: float, lon1: float, lat0: float, lat1: float, color: str = 'black', lw: float = 1.2) -> None:
    import matplotlib.patches as mpatches
    x0, x1 = float(min(lon0, lon1)), float(max(lon0, lon1))
    y0, y1 = float(min(lat0, lat1)), float(max(lat0, lat1))
    rect = mpatches.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec=color, lw=lw,
                              transform=ccrs.PlateCarree() if ccrs is not None else None, zorder=5)
    try:
        ax.add_patch(rect)
    except Exception:
        pass


def normalize_latlon(ds: xr.Dataset) -> xr.Dataset:
    """Ensure ds has lat/lon coordinate names and 0..360 lon if needed."""
    if 'lon' not in ds.coords:
        if 'longitude' in ds.coords:
            ds = ds.rename({'longitude': 'lon'})
    if 'lat' not in ds.coords:
        if 'latitude' in ds.coords:
            ds = ds.rename({'latitude': 'lat'})
    if 'lon' in ds.coords and float(ds['lon'].min()) < 0:
        ds = ds.assign_coords(lon=((ds['lon'] + 360.0) % 360.0)).sortby('lon')
    return ds


def monthly_overlay(da: xr.DataArray, mode: str = 'absolute', clim: Tuple[int, int] | None = None) -> xr.DataArray:
    """Return monthly series for overlay variable, optionally as anomaly.

    - mode: 'absolute' | 'anomaly'
    - clim: (y0, y1) years window for anomaly baseline when mode='anomaly'
    """
    out = da.astype('float32')
    if mode == 'anomaly':
        years = out['time'].dt.year
        if clim is not None:
            y0, y1 = int(clim[0]), int(clim[1])
            mask = (years >= y0) & (years <= y1)
            base = out.sel(time=mask)
        else:
            base = out
        # monthly climatology
        clim_mean = base.groupby('time.month').mean('time', skipna=True)
        out = out.groupby('time.month') - clim_mean
    return out


def per_year_samples(da_mon: xr.DataArray, years: List[int], months: List[int]) -> np.ndarray:
    """Return samples array with shape (Ny, lat, lon) where each sample is the
    mean of the selected months in a given year."""
    acc = []
    for y in years:
        sel_y = da_mon.sel(time=da_mon['time'].dt.year == y)
        if sel_y.sizes.get('time', 0) == 0:
            continue
        sel_win = sel_y.sel(time=sel_y['time'].dt.month.isin(months))
        if sel_win.sizes.get('time', 0) == 0:
            continue
        acc.append(sel_win.mean('time', skipna=True).values)
    return np.stack(acc, axis=0) if acc else None


def welch_ttest(mu1: np.ndarray, s1: np.ndarray, n1: np.ndarray,
                mu2: np.ndarray, s2: np.ndarray, n2: np.ndarray,
                alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
    """Welch's t-test (two-sided) returning (tval, significant_mask).

    Uses Satterthwaite degrees-of-freedom and a normal approximation for the
    two-sided critical value at 1 - alpha/2 (accurate for large df).
    """
    with np.errstate(invalid='ignore', divide='ignore'):
        v1 = (s1**2) / np.maximum(n1, 1)
        v2 = (s2**2) / np.maximum(n2, 1)
        denom = np.sqrt(v1 + v2)
        tval = (mu1 - mu2) / denom
        num = (v1 + v2)**2
        term1 = (v1**2) / np.maximum(n1 - 1, 1)
        term2 = (v2**2) / np.maximum(n2 - 1, 1)
        df = num / (term1 + term2 + 1e-12)
    zcrit = NormalDist().inv_cdf(1.0 - float(alpha)/2.0)
    sig = (n1 >= 2) & (n2 >= 2) & np.isfinite(tval) & (np.abs(tval) > zcrit)
    return tval, sig


def main(argv: Iterable[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--nc-file', required=True, help='Monthly NetCDF with mhw_days(time,lat,lon)')
    p.add_argument('--elt', required=True, help='Comma-separated ELT years')
    p.add_argument('--nt', required=True, help='Comma-separated NT years')
    p.add_argument('--out', required=True, help='Output PNG path')
    p.add_argument('--dpi', type=int, default=170)
    p.add_argument('--prc', type=float, default=98.0, help='Upper percentile for absolute color scale')
    p.add_argument('--palette', choices=['wbgyred','white_blue_green_yellow_red','white_orange_red','white_inferno','white_red','ylorrd'], default='wbgyred',
                   help='Color palette for absolute values')
    p.add_argument('--cmap-lighten', type=float, default=0.0, help='Lighten factor for white_red (0–0.5)')
    p.add_argument('--white-frac', type=float, default=0.06, help='White fraction for white_inferno (0–0.15)')
    p.add_argument('--title', default='MHW days (absolute) — ELT vs NT composites')
    p.add_argument('--box', default='120,155,15,35', help='Overlay box lon0,lon1,lat0,lat1 (e.g., 120,155,15,35)')
    p.add_argument('--box-color', default='black')
    p.add_argument('--box-lw', type=float, default=1.2)
    # Overlay (net heating) options
    p.add_argument('--overlay-nc', default=None, help='Optional NetCDF with overlay variable (e.g., net heating)')
    p.add_argument('--overlay-var', default='qnet', help='Variable name in overlay NetCDF')
    p.add_argument('--overlay-mode', choices=['absolute','anomaly'], default='absolute', help='Overlay data mode')
    p.add_argument('--overlay-clim-start', type=int, default=None, help='Overlay anomaly climatology start year')
    p.add_argument('--overlay-clim-end', type=int, default=None, help='Overlay anomaly climatology end year')
    p.add_argument('--overlay-prc', type=float, default=95.0, help='Percentile to set overlay contour amplitude (symmetric)')
    p.add_argument('--overlay-nlevels', type=int, default=9, help='Number of overlay contour levels (odd preferred)')
    p.add_argument('--overlay-lw', type=float, default=0.8, help='Line width for overlay contours')
    p.add_argument('--overlay-alpha', type=float, default=0.85, help='Alpha for overlay contours')
    p.add_argument('--overlay-col-neg', default='#3b6fb6', help='Color for negative overlay contours')
    p.add_argument('--overlay-col-pos', default='#b63b3b', help='Color for positive overlay contours')
    p.add_argument('--overlay-col-zero', default='black', help='Color for zero overlay contour')
    # Significance (absolute mode): none | one-sample vs 0 | Welch vs climatology
    p.add_argument('--sig-abs', choices=['off','zero','clim'], default='clim',
                   help='Significance mode for absolute composites: off | zero (one-sample vs 0) | clim (Welch vs climatology)')
    p.add_argument('--sig-alpha', type=float, default=0.05, help='Two-sided alpha for significance (e.g., 0.05, 0.10, 0.20)')
    p.add_argument('--clim-start', type=int, default=1993, help='Climatology start year (for --sig-abs clim)')
    p.add_argument('--clim-end', type=int, default=2021, help='Climatology end year (for --sig-abs clim)')
    p.add_argument('--sig-exclude-elt', action='store_true', default=True,
                   help='Exclude group years from climatology pool (default True)')
    args = p.parse_args(argv)

    ds = xr.open_dataset(Path(args.nc_file))
    if 'mhw_days' not in ds:
        raise SystemExit('Variable mhw_days not found in NetCDF')
    da = monthly_days(ds['mhw_days'])  # (time, lat, lon)

    elt_years = parse_years(args.elt)
    nt_years = parse_years(args.nt)

    comp_elt = composite_for_years(da, elt_years)
    comp_nt = composite_for_years(da, nt_years)
    # Optional overlay dataset
    overlay = None
    comp_ovr_elt: dict[str, np.ndarray] | None = None
    comp_ovr_nt: dict[str, np.ndarray] | None = None
    if args.overlay_nc:
        ds2 = xr.open_dataset(Path(args.overlay_nc))
        ds2 = normalize_latlon(ds2)
        if args.overlay_var not in ds2:
            raise SystemExit(f"Overlay variable {args.overlay_var} not found in {args.overlay_nc}")
        ov = ds2[args.overlay_var]
        if {'time','lat','lon'}.issubset(set(ov.dims)):
            pass
        else:
            # Attempt common alternative names
            if 'latitude' in ov.dims or 'longitude' in ov.dims:
                ov = ov.rename({'latitude':'lat','longitude':'lon'})
        overlay = monthly_overlay(ov, mode=str(args.overlay_mode), clim=(args.overlay_clim_start, args.overlay_clim_end) if (args.overlay_clim_start and args.overlay_clim_end) else None)
        # Build composites for overlay
        comp_ovr_elt = {}
        comp_ovr_nt = {}
        for wname, months in window_months():
            # ELT
            fields = []
            for y in elt_years:
                sel = overlay.sel(time=overlay['time'].dt.year == y)
                wsel = sel.sel(time=sel['time'].dt.month.isin(months))
                if wsel.sizes.get('time', 0) == 0:
                    continue
                fields.append(wsel.mean('time', skipna=True).values)
            if fields:
                comp_ovr_elt[wname] = np.nanmean(np.stack(fields, axis=0), axis=0)
            # NT
            fields = []
            for y in nt_years:
                sel = overlay.sel(time=overlay['time'].dt.year == y)
                wsel = sel.sel(time=sel['time'].dt.month.isin(months))
                if wsel.sizes.get('time', 0) == 0:
                    continue
                fields.append(wsel.mean('time', skipna=True).values)
            if fields:
                comp_ovr_nt[wname] = np.nanmean(np.stack(fields, axis=0), axis=0)
    sig_elt: dict[str, np.ndarray] = {}
    sig_nt: dict[str, np.ndarray] = {}
    # Significance for each window using per-year samples
    if args.sig_abs != 'off':
        windows = window_months()
        # Year axis for climatology pool
        years_axis = np.unique(da['time'].dt.year.values)
        clim_pool = [int(y) for y in years_axis if (int(y) >= int(args.clim_start) and int(y) <= int(args.clim_end))]
        if args.sig_exclude_elt:
            clim_pool_elt = [y for y in clim_pool if y not in elt_years]
            clim_pool_nt = [y for y in clim_pool if y not in nt_years]
        else:
            clim_pool_elt = clim_pool[:]
            clim_pool_nt = clim_pool[:]
        for wname, months in windows:
            # ELT
            A = per_year_samples(da, elt_years, months)
            if A is not None:
                muA = np.nanmean(A, axis=0)
                sA = np.nanstd(A, axis=0, ddof=1)
                nA = np.sum(np.isfinite(A), axis=0).astype(np.int32)
                if args.sig_abs == 'zero':
                    with np.errstate(invalid='ignore', divide='ignore'):
                        tval = muA / (sA / np.sqrt(np.maximum(nA, 1)))
                    # t-critical via normal approx, consistent with grid script
                    zcrit = NormalDist().inv_cdf(1.0 - float(args.sig_alpha)/2.0)
                    sig = (nA >= 2) & np.isfinite(tval) & (np.abs(tval) > zcrit)
                else:
                    B = per_year_samples(da, clim_pool_elt, months)
                    if B is None:
                        sig = None
                    else:
                        muB = np.nanmean(B, axis=0)
                        sB = np.nanstd(B, axis=0, ddof=1)
                        nB = np.sum(np.isfinite(B), axis=0).astype(np.int32)
                        _t, sig = welch_ttest(muA, sA, nA, muB, sB, nB, alpha=float(args.sig_alpha))
                if sig is not None:
                    sig_elt[wname] = sig
            # NT
            A = per_year_samples(da, nt_years, months)
            if A is not None:
                muA = np.nanmean(A, axis=0)
                sA = np.nanstd(A, axis=0, ddof=1)
                nA = np.sum(np.isfinite(A), axis=0).astype(np.int32)
                if args.sig_abs == 'zero':
                    with np.errstate(invalid='ignore', divide='ignore'):
                        tval = muA / (sA / np.sqrt(np.maximum(nA, 1)))
                    zcrit = NormalDist().inv_cdf(1.0 - float(args.sig_alpha)/2.0)
                    sig = (nA >= 2) & np.isfinite(tval) & (np.abs(tval) > zcrit)
                else:
                    B = per_year_samples(da, clim_pool_nt, months)
                    if B is None:
                        sig = None
                    else:
                        muB = np.nanmean(B, axis=0)
                        sB = np.nanstd(B, axis=0, ddof=1)
                        nB = np.sum(np.isfinite(B), axis=0).astype(np.int32)
                        _t, sig = welch_ttest(muA, sA, nA, muB, sB, nB, alpha=float(args.sig_alpha))
                if sig is not None:
                    sig_nt[wname] = sig

    # Determine common color scale from all available panels
    vals = []
    for d in (comp_elt, comp_nt):
        for wname, fld in d.items():
            v = fld[np.isfinite(fld)]
            if v.size:
                vals.append(v)
    stack = np.concatenate(vals) if vals else np.array([1.0])
    vmax = float(np.nanpercentile(stack, float(args.prc))) if stack.size else 10.0
    if not np.isfinite(vmax) or vmax <= 0:
        vmax = 1.0
    vmax_i = int(np.ceil(vmax))
    levels = np.arange(0, vmax_i + 1, 1, dtype=float)
    # Palette selection per guidelines: widely used warm scheme with contrast
    if args.palette in ('wbgyred','white_blue_green_yellow_red'):
        cmap = cmap_white_blue_green_yellow_red()
    elif args.palette == 'white_orange_red':
        cmap = cmap_white_orange_red()
    elif args.palette == 'white_inferno':
        cmap = cmap_white_inferno(float(args.white_frac))
    elif args.palette == 'white_red':
        cmap = cmap_white_red(float(args.cmap_lighten))
    else:
        # fallback to YlOrRd with optional lightening towards white
        base = plt.get_cmap('YlOrRd')
        cols = base(np.linspace(0,1,256))
        lf = float(args.cmap_lighten)
        if lf > 0:
            cols[:, :3] = cols[:, :3] * (1.0 - lf) + lf
        cmap = mcolors.ListedColormap(cols)
    try:
        cmap = cmap.copy(); cmap.set_bad('lightgrey'); cmap.set_under('white')
    except Exception:
        pass

    # Derive overlay contour levels (symmetric) if overlay provided
    overlay_levels = None
    if overlay is not None and comp_ovr_elt and comp_ovr_nt:
        ovals = []
        for d in (comp_ovr_elt, comp_ovr_nt):
            for _k, fld in d.items():
                v = fld[np.isfinite(fld)]
                if v.size:
                    ovals.append(np.abs(v))
        if ovals:
            stacko = np.concatenate(ovals)
            vabs = float(np.nanpercentile(stacko, float(args.overlay_prc))) if stacko.size else 1.0
            if not np.isfinite(vabs) or vabs <= 0:
                vabs = 1.0
            nlev = max(3, int(args.overlay_nlevels))
            # Ensure zero in levels
            overlay_levels = np.linspace(-vabs, vabs, nlev)

    # Figure 2×5
    windows = [w for w, _m in window_months()]
    proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
    fig = plt.figure(figsize=(12.5, 5.6))
    gs = fig.add_gridspec(2, 5, left=0.05, right=0.995, top=0.92, bottom=0.13, wspace=0.05, hspace=0.06)

    lat = ds['lat'].values
    lon = ds['lon'].values
    if lat.ndim == 1 and lon.ndim == 1:
        Lon, Lat = np.meshgrid(lon, lat)
    else:
        Lon, Lat = lon, lat

    row_defs = [("ELT", comp_elt), ("NT", comp_nt)]
    # Parse overlay box
    try:
        b_lon0, b_lon1, b_lat0, b_lat1 = [float(x) for x in str(args.box).split(',')]
    except Exception:
        b_lon0, b_lon1, b_lat0, b_lat1 = 120.0, 155.0, 15.0, 35.0
    last_mappable = None
    for ri, (rname, comp) in enumerate(row_defs):
        for ci, wname in enumerate(windows):
            ax = fig.add_subplot(gs[ri, ci], **proj)
            field = comp.get(wname)
            if field is not None:
                h = ax.contourf(Lon, Lat, field, levels=levels, cmap=cmap, extend='both',
                                transform=ccrs.PlateCarree() if ccrs is not None else None)
                last_mappable = h
            # Overlay contours
            if overlay_levels is not None:
                ocomp = (comp_ovr_elt if rname == 'ELT' else comp_ovr_nt)
                if ocomp and wname in ocomp and ocomp[wname].shape == field.shape:
                    fld = ocomp[wname]
                    # Negative and positive contours separately for style
                    try:
                        # Negative (dashed)
                        neg_levels = [lv for lv in overlay_levels if lv < 0]
                        pos_levels = [lv for lv in overlay_levels if lv > 0]
                        if neg_levels:
                            ax.contour(Lon, Lat, fld, levels=neg_levels, colors=[str(args.overlay_col_neg)], linewidths=float(args.overlay_lw), linestyles='--', alpha=float(args.overlay_alpha), transform=ccrs.PlateCarree() if ccrs is not None else None)
                        if pos_levels:
                            ax.contour(Lon, Lat, fld, levels=pos_levels, colors=[str(args.overlay_col_pos)], linewidths=float(args.overlay_lw), linestyles='-', alpha=float(args.overlay_alpha), transform=ccrs.PlateCarree() if ccrs is not None else None)
                        # Zero contour bold
                        if 0.0 >= overlay_levels.min() and 0.0 <= overlay_levels.max():
                            ax.contour(Lon, Lat, fld, levels=[0.0], colors=[str(args.overlay_col_zero)], linewidths=float(max(args.overlay_lw, 1.2)), linestyles='-', alpha=float(args.overlay_alpha), transform=ccrs.PlateCarree() if ccrs is not None else None)
                    except Exception:
                        pass
            # Significance hatching (if computed)
            sig_map = (sig_elt if rname == 'ELT' else sig_nt)
            sig = sig_map.get(wname)
            if sig is not None:
                try:
                    ax.contourf(Lon, Lat, sig.astype(float), levels=[0.5, 1.5], hatches=['..'], colors='none',
                                transform=ccrs.PlateCarree() if ccrs is not None else None)
                except Exception:
                    pass
            # Overlay target-domain box on every panel
            draw_box(ax, b_lon0, b_lon1, b_lat0, b_lat1, color=str(args.box_color), lw=float(args.box_lw))
            add_map(ax, left=(ci==0), bottom=(ri==1))
            if ci == 0:
                ax.set_ylabel(rname, fontsize=9)
            if ri == 0:
                ax.set_title(wname, fontsize=9)

    # Colorbar
    if last_mappable is not None:
        poss = [ax.get_position() for ax in fig.axes]
        x0 = min(p.x0 for p in poss); x1 = max(p.x1 for p in poss)
        y0 = max(0.04, min(p.y0 for p in poss) - 0.05)
        cax = fig.add_axes([x0, y0, x1-x0, 0.02])
        cb = fig.colorbar(last_mappable, cax=cax, orientation='horizontal'); cb.set_label('MHW days (absolute)')

    if args.title:
        fig.suptitle(args.title, y=0.97, fontsize=11)

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    tmp = outp.with_suffix('.tmp.png')
    fig.savefig(tmp, dpi=int(args.dpi))
    plt.close(fig)
    tmp.replace(outp)
    print(f"[OK] saved → {outp}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
