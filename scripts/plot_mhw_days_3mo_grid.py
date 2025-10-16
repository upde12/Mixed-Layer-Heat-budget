#!/usr/bin/env python3
"""Render a 3-month (prevOND/JFM/AMJ/JAS/OND) grid for MHW days.

Style matches the recent MLHB 3-mo grid with MEAN row and significance (t-test) hatching:
- Rows: [MEAN (optional)] + ELT years
- Cols: prevOND (prev Oct–Dec), JFM, AMJ, JAS, OND
- Shading: monthly anomalies (days), lightened RdBu_r, symmetric percentile scale
- Significance (MEAN only): 2-sided t-test vs 0 at 95%; samples = months×years; N_eff via lag-1 autocorr
- No heat-flux contour overlay

Inputs
- Raw float32 monthly MHW duration (T×101×145) at 0.25° ECS grid
  default: /Volumes/HJPARK4/MHW/source/detect/dur_mon_ECS.data

Outputs
- A single PNG saved under --out-root: mhw_days_grid_rows-years.png
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.colors as mcolors
from statistics import NormalDist

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
except Exception:
    ccrs = None
    cfeature = None


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dur-file", default="/Volumes/HJPARK4/MHW/source/detect/dur_mon_ECS.data",
                   help="Raw float32 monthly MHW days (T×101×145)")
    p.add_argument("--years", required=True, help="Comma-separated ELT years: e.g., 1983,1988,1998,2010,2016,2020")
    p.add_argument("--out-root", required=True, help="Output directory for PNGs")
    p.add_argument("--last-year", type=int, default=2021, help="Last calendar year in the raw binary (for start-year inference)")
    p.add_argument("--clim-start", type=int, default=None, help="Climatology start year (optional)")
    p.add_argument("--clim-end", type=int, default=None, help="Climatology end year (optional)")
    p.add_argument("--rhs-prc", type=float, default=90.0, help="Percentile for color scale (symmetric for anomaly; upper for absolute)")
    p.add_argument("--mode", choices=["anomaly","absolute"], default="absolute",
                   help="Plot anomalies (relative to climatology) or absolute raw MHW days (default)")
    p.add_argument("--grid-include-mean", action="store_true", help="Add a top MEAN row across selected years")
    p.add_argument("--grid-mean-scale", type=float, default=1.0, help="Visual scale factor for MEAN row only")
    p.add_argument("--grid-mean-sig", choices=["off","hatch"], default="hatch",
                   help="Significance marking for MEAN row (two-sided t-test vs 0 at 95%%): hatch or off")
    p.add_argument("--sig-mode", choices=["plain","neff","year"], default="plain",
                   help="t-test sample mode for MEAN row: 'plain'=months×years, 'neff'=lag-1 corrected, 'year'=3-month means per year (e.g., N=6)")
    p.add_argument("--dpi", type=int, default=170)
    # Absolute-mean significance options
    p.add_argument("--sig-abs", choices=["off","zero","clim"], default="clim",
                   help="Significance mode for MEAN in absolute mode: off | zero(one-sample vs 0) | clim(two-sample Welch vs climatology years)")
    p.add_argument("--sig-exclude-elt", action="store_true", default=True,
                   help="Exclude ELT years from climatology pool when --sig-abs=clim (default: True)")
    p.add_argument("--sig-alpha", type=float, default=0.05,
                   help="Two-sided significance alpha (e.g., 0.05 for 95%, 0.20 for 80%)")
    # Styling & masking controls
    p.add_argument("--cmap-lighten", type=float, default=0.35,
                   help="Lighten factor for colormap blending towards white (0=no change, 0.35=default)")
    p.add_argument("--auto-land-mask", dest="auto_land_mask", action="store_true",
                   help="Infer land mask from MEAN(absolute) fields and mask them (default: on)")
    p.add_argument("--no-auto-land-mask", dest="auto_land_mask", action="store_false",
                   help="Disable auto land mask inference")
    p.set_defaults(auto_land_mask=True)
    p.add_argument("--mask-threshold", type=float, default=1e-8,
                   help="Threshold for considering MEAN(absolute)==0 (<=thresh) as land when auto-masking")
    return p.parse_args(argv)


def load_duration(path: Path) -> np.ndarray:
    a = np.fromfile(path, dtype=np.float32)
    per = 101 * 145
    if a.size % per != 0:
        raise SystemExit(f"Unexpected size {a.size}; not divisible by 101*145")
    t = a.size // per
    return a.reshape(t, 101, 145)


def years_from_spec(s: str) -> List[int]:
    return [int(x) for x in s.split(',') if x.strip()]


def light_cmap(base: str = 'RdBu_r', lighten: float = 0.25) -> mcolors.Colormap:
    base_cmap = plt.get_cmap(base)
    N = 256
    cols = base_cmap(np.linspace(0, 1, N))
    cols[:, :3] = cols[:, :3] * (1.0 - lighten) + lighten
    return mcolors.ListedColormap(cols)


def add_map(ax, left: bool, bottom: bool) -> None:
    if ccrs is None:
        if bottom: ax.set_xlabel("Longitude")
        if left: ax.set_ylabel("Latitude")
        return
    try:
        land50 = cfeature.NaturalEarthFeature('physical','land','50m', edgecolor='black', facecolor='lightgrey', linewidth=0.6)
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
        gl.top_labels=False; gl.right_labels=False; gl.left_labels=bool(left); gl.bottom_labels=bool(bottom)
    except Exception:
        gl.xlabels_top=False; gl.ylabels_right=False; gl.ylabels_left=bool(left); gl.xlabels_bottom=bool(bottom)
    gl.xlabel_style={"size":10,"rotation":0}; gl.ylabel_style={"size":10}


def ttest_significance_plain(stack: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Plain t-test (no N_eff): use N = count of finite samples along stack.

    Returns (mu, std, sig95) for stack shaped (S, NY, NX).
    """
    mu = np.nanmean(stack, axis=0)
    std = np.nanstd(stack, axis=0, ddof=1)
    n = np.sum(np.isfinite(stack), axis=0).astype(np.int32)
    with np.errstate(invalid='ignore', divide='ignore'):
        tval = mu / (std / np.sqrt(np.where(n > 0, n, 1)))
    # t-critical (two-sided 0.975) lookup up to 30
    tcrit_tbl = np.array([
        np.nan, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262,
        2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093,
        2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045,
        2.042
    ], dtype=float)
    df = np.clip(n - 1, 1, len(tcrit_tbl) - 1)
    tcrit = tcrit_tbl[df]
    sig95 = (n >= 2) & np.isfinite(tval) & (np.abs(tval) > tcrit)
    return mu, std, sig95


def ttest_significance_neff(stack: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """N_eff via lag-1 autocorr; 2-sided t-test vs 0 at 95%."""
    mu = np.nanmean(stack, axis=0)
    std = np.nanstd(stack, axis=0, ddof=1)
    n = np.sum(np.isfinite(stack), axis=0).astype(np.int32)
    S = stack.shape[0]
    r1 = np.zeros_like(mu, dtype=np.float64)
    if S >= 3:
        a = stack[:-1, :, :]
        b = stack[1:, :, :]
        # compute pixelwise lag-1 correlation
        for j in range(mu.shape[0]):
            x = a[:, j, :]
            y = b[:, j, :]
            for i in range(mu.shape[1]):
                xx = x[:, i]; yy = y[:, i]
                m = np.isfinite(xx) & np.isfinite(yy)
                if np.count_nonzero(m) >= 2:
                    xv = xx[m] - np.nanmean(xx[m]); yv = yy[m] - np.nanmean(yy[m])
                    denom = np.sqrt(np.sum(xv*xv) * np.sum(yv*yv))
                    r1[j, i] = (np.sum(xv*yv)/denom) if denom > 0 else 0.0
                else:
                    r1[j, i] = 0.0
    with np.errstate(invalid='ignore', divide='ignore'):
        ratio = (1.0 - r1) / (1.0 + r1)
    neff = np.where(n > 0, n * ratio, 0.0)
    neff = np.where(np.isfinite(neff), neff, 0.0)
    neff_int = np.clip(neff, 0.0, n.astype(float)).astype(np.int32)
    with np.errstate(invalid='ignore', divide='ignore'):
        tval = mu / (std / np.sqrt(np.where(neff_int > 0, neff_int, 1)))
    # t-critical (two-sided 0.975) table up to 30
    tcrit_tbl = np.array([
        np.nan, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262,
        2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093,
        2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045,
        2.042
    ], dtype=float)
    df = np.clip(neff_int - 1, 1, len(tcrit_tbl) - 1)
    tcrit = tcrit_tbl[df]
    sig95 = (neff_int >= 2) & np.isfinite(tval) & (np.abs(tval) > tcrit)
    return mu, std, sig95


def ttest_significance_year(samples: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-year samples t-test: `samples` has shape (Ny, NY, NX) where Ny = #years.

    Use standard one-sample t-test vs 0 with N = Ny (no autocorr correction).
    Returns (mu, std, sig95).
    """
    mu = np.nanmean(samples, axis=0)
    std = np.nanstd(samples, axis=0, ddof=1)
    n = np.sum(np.isfinite(samples), axis=0).astype(np.int32)
    with np.errstate(invalid='ignore', divide='ignore'):
        tval = mu / (std / np.sqrt(np.where(n > 0, n, 1)))
    tcrit_tbl = np.array([
        np.nan, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262,
        2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093,
        2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045,
        2.042
    ], dtype=float)
    df = np.clip(n - 1, 1, len(tcrit_tbl) - 1)
    tcrit = tcrit_tbl[df]
    sig95 = (n >= 2) & np.isfinite(tval) & (np.abs(tval) > tcrit)
    return mu, std, sig95

def welch_ttest(mu1: np.ndarray, s1: np.ndarray, n1: np.ndarray,
                mu2: np.ndarray, s2: np.ndarray, n2: np.ndarray,
                alpha: float = 0.05) -> Tuple[np.ndarray, np.ndarray]:
    """Welch's t-test (two-sided alpha) returning (tval, sig).

    Arrays are pixelwise fields. Degrees of freedom use Satterthwaite approximation.
    """
    with np.errstate(invalid='ignore', divide='ignore'):
        v1 = (s1**2) / np.maximum(n1, 1)
        v2 = (s2**2) / np.maximum(n2, 1)
        denom = np.sqrt(v1 + v2)
        tval = (mu1 - mu2) / denom
        # df
        num = (v1 + v2)**2
        term1 = (v1**2) / np.maximum(n1 - 1, 1)
        term2 = (v2**2) / np.maximum(n2 - 1, 1)
        df = num / (term1 + term2 + 1e-12)
    # Use normal approximation for two-sided critical value at (1 - alpha/2)
    # This is accurate for df >> 30 and acceptable as a practical threshold field-wide.
    q = 1.0 - float(alpha)/2.0
    zcrit = NormalDist().inv_cdf(q)
    sig = (n1 >= 2) & (n2 >= 2) & np.isfinite(tval) & (np.abs(tval) > zcrit)
    return tval, sig


def main(argv: Iterable[str] | None = None) -> int:
    a = parse_args(argv)
    years = years_from_spec(a.years)
    arr = load_duration(Path(a.dur_file))  # T×101×145
    if arr.shape[0] % 12 != 0:
        raise SystemExit("Time length is not a multiple of 12 months")
    years_count = arr.shape[0] // 12
    data = arr.reshape(years_count, 12, 101, 145)

    # Infer start year
    start_year = int(a.last_year) - (years_count - 1)
    # Build climatology (anomaly mode only)
    if a.mode == 'anomaly':
        if a.clim_start is not None or a.clim_end is not None:
            years_axis = np.arange(start_year, start_year + years_count)
            y0 = a.clim_start if a.clim_start is not None else int(years_axis.min())
            y1 = a.clim_end if a.clim_end is not None else int(years_axis.max())
            mask = (years_axis >= y0) & (years_axis <= y1)
            if not np.any(mask):
                raise SystemExit(f"No years in climatology window {y0}-{y1}")
            clim = np.nanmean(data[mask, ...], axis=0)  # 12×101×145
        else:
            clim = np.nanmean(data, axis=0)  # 12×101×145
        anom = data - clim[None, ...]  # years×12×101×145

    # Coordinates (fixed grid)
    lat = np.linspace(19.875, 44.875, 101)
    lon = np.linspace(109.375, 145.375, 145)
    lon2d, lat2d = (np.meshgrid(lon, lat))

    # Windows definition
    windows: List[Tuple[str, List[Tuple[int, bool]]]] = [
        ("prevOND", [(10, True), (11, True), (12, True)]),
        ("JFM",     [(1, False), (2, False), (3, False)]),
        ("AMJ",     [(4, False), (5, False), (6, False)]),
        ("JAS",     [(7, False), (8, False), (9, False)]),
        ("OND",     [(10, False), (11, False), (12, False)]),
    ]

    # Per-year window fields
    grid_vals: dict[Tuple[int, str], np.ndarray] = {}
    for y in years:
        for wname, spec in windows:
            cells = []
            for m, is_prev in spec:
                yy = y-1 if is_prev else y
                yi = yy - start_year
                if 0 <= yi < years_count:
                    src = (anom if a.mode == 'anomaly' else data)
                    cells.append(src[yi, m-1, ...])
            if cells:
                grid_vals[(y, wname)] = np.nanmean(np.stack(cells, axis=0), axis=0)

    # MEAN row across selected ELT years
    # - Always compute the MEAN field (absolute or anomaly)
    # - Significance hatching (MEAN only) is applicable to anomaly mode only
    mean_by_window: dict[str, np.ndarray] = {}
    sig_by_window: dict[str, np.ndarray] = {}
    if a.grid_include_mean:
        for wname, spec in windows:
            if a.mode == 'anomaly':
                # Build anomaly stacks for significance (two variants)
                if a.sig_mode == 'year':
                    # Per-year samples: each sample is the 3-month mean for that window
                    year_means = []
                    for y in years:
                        cells = []
                        for m, is_prev in spec:
                            yy = y-1 if is_prev else y
                            yi = yy - start_year
                            if 0 <= yi < years_count:
                                cells.append(anom[yi, m-1, ...])
                        if cells:
                            year_means.append(np.nanmean(np.stack(cells, axis=0), axis=0))
                    if year_means:
                        YS = np.stack(year_means, axis=0)  # (Ny, 101, 145)
                        mu, std, sig = ttest_significance_year(YS)
                        mean_by_window[wname] = mu * (a.grid_mean_scale if a.grid_mean_scale != 1.0 else 1.0)
                        sig_by_window[wname] = sig
                else:
                    # Monthly-level stack across years×months
                    stack = []
                    for y in years:
                        for m, is_prev in spec:
                            yy = y-1 if is_prev else y
                            yi = yy - start_year
                            if 0 <= yi < years_count:
                                stack.append(anom[yi, m-1, ...])
                    if stack:
                        S = np.stack(stack, axis=0)  # (samples, 101, 145)
                        if a.sig_mode == 'neff':
                            mu, std, sig = ttest_significance_neff(S)
                        else:
                            mu, std, sig = ttest_significance_plain(S)
                        mean_by_window[wname] = mu * (a.grid_mean_scale if a.grid_mean_scale != 1.0 else 1.0)
                        sig_by_window[wname] = sig
            else:
                # Absolute mode: MEAN is the average of per-year window fields
                samples = []
                for y in years:
                    key = (y, wname)
                    if key in grid_vals:
                        samples.append(grid_vals[key])
                if samples:
                    mu = np.nanmean(np.stack(samples, axis=0), axis=0)
                    mean_by_window[wname] = mu * (a.grid_mean_scale if a.grid_mean_scale != 1.0 else 1.0)

    # Absolute-mode significance for MEAN (optional)
    if (a.mode == 'absolute') and a.grid_include_mean and (a.sig_abs != 'off'):
        years_axis = np.arange(start_year, start_year + years_count)
        # Helper: compute one sample (3-month mean) for a given year/window
        def sample_for_year(y: int, spec: List[Tuple[int, bool]]):
            cells = []
            for m, is_prev in spec:
                yy = y-1 if is_prev else y
                yi = yy - start_year
                if 0 <= yi < years_count:
                    cells.append(data[yi, m-1, ...])
            if not cells:
                return None
            return np.nanmean(np.stack(cells, axis=0), axis=0)
        for wname, spec in windows:
            # Group A: ELT years
            A = []
            for y in years:
                S = sample_for_year(y, spec)
                if S is not None:
                    A.append(S)
            if not A:
                continue
            A = np.stack(A, axis=0)
            muA = np.nanmean(A, axis=0)
            sA = np.nanstd(A, axis=0, ddof=1)
            nA = np.sum(np.isfinite(A), axis=0).astype(np.int32)
            if a.sig_abs == 'zero':
                # one-sample vs 0
                with np.errstate(invalid='ignore', divide='ignore'):
                    tval = muA / (sA / np.sqrt(np.maximum(nA, 1)))
                # t-crit
                tcrit_tbl = np.array([
                    np.nan, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262,
                    2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093,
                    2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045,
                    2.042
                ], dtype=float)
                df = np.clip(nA - 1, 1, len(tcrit_tbl) - 1)
                tcrit = tcrit_tbl[df]
                sig = (nA >= 2) & np.isfinite(tval) & (np.abs(tval) > tcrit)
                sig_by_window[wname] = sig
            else:
                # 'clim' Welch two-sample vs climatology years
                y0 = a.clim_start if a.clim_start is not None else int(years_axis.min())
                y1 = a.clim_end if a.clim_end is not None else int(years_axis.max())
                pool = [int(y) for y in years_axis if (y >= y0 and y <= y1)]
                if a.sig_exclude_elt:
                    pool = [y for y in pool if y not in years]
                B = []
                for y in pool:
                    S = sample_for_year(y, spec)
                    if S is not None:
                        B.append(S)
                if not B:
                    continue
                B = np.stack(B, axis=0)
                muB = np.nanmean(B, axis=0)
                sB = np.nanstd(B, axis=0, ddof=1)
                nB = np.sum(np.isfinite(B), axis=0).astype(np.int32)
                _t, sig = welch_ttest(muA, sA, nA, muB, sB, nB, alpha=float(a.sig_alpha))
                sig_by_window[wname] = sig

    # Auto land mask based on MEAN(absolute) fields: cells that are ~0 across all windows
    land_mask = None
    if a.auto_land_mask:
        if a.mode == 'absolute' and a.grid_include_mean and mean_by_window:
            # Build boolean mask: True where all windows are near zero
            thr = float(a.mask_threshold)
            masks = []
            for wname, _ in windows:
                mu = mean_by_window.get(wname)
                if mu is None:
                    break
                masks.append(np.abs(mu) <= thr)
            if masks:
                land_mask = np.logical_and.reduce(masks)
                # Apply mask to fields for plotting and scaling stats
                for k in list(grid_vals.keys()):
                    arr = grid_vals[k]
                    grid_vals[k] = np.where(land_mask, np.nan, arr)
                for wname in list(mean_by_window.keys()):
                    arr = mean_by_window[wname]
                    mean_by_window[wname] = np.where(land_mask, np.nan, arr)
        else:
            # If anomaly mode or MEAN not available, do nothing (mask not inferable reliably)
            land_mask = None

    # Determine color scale
    vals = []
    for key, field in grid_vals.items():
        v = (np.abs(field) if a.mode=='anomaly' else field)
        v = v[np.isfinite(v)]
        if v.size: vals.append(v)
    for wname, mu in mean_by_window.items():
        v = (np.abs(mu) if a.mode=='anomaly' else mu)
        v = v[np.isfinite(v)]
        if v.size: vals.append(v)
    stack_vals = np.concatenate(vals) if vals else np.array([1.0])
    if a.mode == 'anomaly':
        vabs = np.nanpercentile(stack_vals, float(a.rhs_prc)) if stack_vals.size else 1.0
        levels = np.linspace(-vabs, vabs, 21)
        cmap = light_cmap('RdBu_r', float(a.cmap_lighten))
    else:
        vmax = np.nanpercentile(stack_vals, float(a.rhs_prc)) if stack_vals.size else 10.0
        if vmax <= 0: vmax = 1.0
        levels = np.linspace(0.0, vmax, 21)
        cmap = light_cmap('YlOrRd', float(a.cmap_lighten))
    try: cmap = cmap.copy(); cmap.set_bad('lightgrey')
    except Exception: pass

    # Figure
    rows = len(years) + (1 if a.grid_include_mean else 0)
    cols = len(windows)
    proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
    width = 2.2*cols + 1.6
    height = 1.9*rows + 1.6
    fig = plt.figure(figsize=(width, height))
    gs = fig.add_gridspec(rows, cols, left=0.05, right=0.995, top=0.96, bottom=0.10, wspace=0.03, hspace=0.03)
    # Row labels
    row_labels: List[object] = ([] if not a.grid_include_mean else ["MEAN"]) + years
    for ri, rlab in enumerate(row_labels):
        for ci, (wname, _spec) in enumerate(windows):
            ax = fig.add_subplot(gs[ri, ci], **proj)
            if rlab == "MEAN":
                field = mean_by_window.get(wname)
                sig = sig_by_window.get(wname)
            else:
                field = grid_vals.get((int(rlab), wname))
                sig = None
            if field is not None:
                if land_mask is not None:
                    field = np.where(land_mask, np.nan, field)
                h = ax.contourf(lon2d, lat2d, field, levels=levels, cmap=cmap, extend='both',
                                transform=ccrs.PlateCarree() if ccrs is not None else None)
                # MEAN significance hatching
                if (rlab == "MEAN") and (a.grid_mean_sig == 'hatch') and (sig is not None):
                    try:
                        ax.contourf(lon2d, lat2d, sig.astype(float), levels=[0.5, 1.5], hatches=['..'], colors='none',
                                    transform=ccrs.PlateCarree() if ccrs is not None else None)
                    except Exception:
                        pass
            if ccrs is not None:
                ax.set_extent([float(np.nanmin(lon2d)), float(np.nanmax(lon2d)), float(np.nanmin(lat2d)), float(np.nanmax(lat2d))],
                              crs=ccrs.PlateCarree())
            add_map(ax, left=(ci==0), bottom=(ri==rows-1))
            if ci == 0:
                ax.set_ylabel("MEAN" if rlab == "MEAN" else str(rlab), fontsize=9)
            if ri == 0:
                ax.set_title(wname, fontsize=9)

    # Colorbar (pushed lower to avoid label overlap)
    poss = [ax.get_position() for ax in fig.axes]
    x0 = min(p.x0 for p in poss); x1 = max(p.x1 for p in poss)
    y0 = max(0.03, min(p.y0 for p in poss)-0.06)
    cax = fig.add_axes([x0, y0, x1-x0, 0.018])
    cb = fig.colorbar(h, cax=cax, orientation='horizontal'); cb.set_label('days' if a.mode=='absolute' else 'days (anom)', labelpad=4)

    outdir = Path(a.out_root); outdir.mkdir(parents=True, exist_ok=True)
    outp = outdir / "mhw_days_grid_rows-years.png"
    tmp = outp.with_suffix('.tmp.png')
    fig.savefig(tmp, dpi=a.dpi)
    plt.close(fig)
    tmp.replace(outp)
    print(f"[OK] saved → {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
