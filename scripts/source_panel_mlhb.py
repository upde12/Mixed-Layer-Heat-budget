#!/usr/bin/env python3
"""Decadal MLHB panels from monthly NetCDF (full domain).

Reads a monthly MLHB NetCDF (time×lat×lon) produced by the mainline pipeline
and generates:
 - Trend-offset map: slope(2011–2022) − slope(1993–2022) of annual-mean T_ML, in K decade^-1
 - RHS 3×2 panel (native DIFFV): annual-mean anomalies averaged over 2011–2022,
   scaled to K decade^-1 (respecting units K day^-1 or K s^-1)

Defaults are aligned to recent operations: centered ADV, forward TEN, deepening we-mode.
ADV smoothing is disabled by default; enable with --adv-smooth-iter if desired.

Example
  python llm-ops/scripts/source_panel_mlhb.py \
    --monthly /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly_main_1993_2022.nc \
    --trend-output /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/decadal_mlhb_trend_offset.png \
    --rhs-output /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/decadal_mlhb_rhs_native.png
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
except Exception:  # optional dependency
    ccrs = None
    cfeature = None


SECONDS_PER_DAY = 86400.0
DAYS_PER_YEAR = 365.0

Shape2D = Tuple[int, int]


def _format_level_label(value: float) -> str:
    if not np.isfinite(value):
        return ""
    if abs(value) < 1e-12:
        return "0"
    text = f"{value:.6f}"
    cleaned = text.rstrip("0").rstrip(".")
    if cleaned in {"-0", "-0."}:
        return "0"
    return cleaned


def _select_tick_values(levels: Iterable[float], max_labels: int = 8) -> np.ndarray:
    values = np.asarray(list(levels), dtype=float)
    if values.size <= max_labels:
        return values
    first, last = values[0], values[-1]
    size = values.size
    min_step = 1
    while (size - 1) // min_step + 1 > max_labels:
        min_step += 1
    zero_idx = int(np.argmin(np.abs(values))) if first < 0 < last else None
    candidate_steps = [s for s in range(min_step, size) if (size - 1) // s + 1 <= max_labels]
    if not candidate_steps:
        candidate_steps = [min_step]
    chosen_step = candidate_steps[0]
    if zero_idx is not None:
        prioritized = [s for s in candidate_steps if zero_idx % s == 0 and (size - 1) % s == 0]
        if not prioritized:
            prioritized = [s for s in candidate_steps if zero_idx % s == 0]
        if prioritized:
            chosen_step = prioritized[0]
    else:
        divisible = [s for s in candidate_steps if (size - 1) % s == 0]
        if divisible:
            chosen_step = divisible[0]
    indices = list(range(0, size, chosen_step))
    if indices[-1] != size - 1:
        indices.append(size - 1)
    if zero_idx is not None and zero_idx not in indices:
        indices.append(zero_idx)
    indices = sorted(set(indices))
    base_values = values[indices]
    if zero_idx is not None:
        zero_value = values[zero_idx]
        neg = base_values[base_values < 0]
        pos = base_values[base_values > 0]
        spacing = values[1] - values[0]
        mirrored_neg = [-p for p in pos]
        mirrored_pos = [-n for n in neg]
        combined = np.concatenate((base_values, mirrored_neg, mirrored_pos, [zero_value]))
        base_values = np.unique(np.round(combined, decimals=6))
    return np.sort(base_values)


def _set_colorbar_ticks(cbar, values: Iterable[float]) -> None:
    numeric = np.asarray(list(values), dtype=float)
    labels = [_format_level_label(val) for val in numeric]
    if cbar.orientation == "horizontal":
        cbar.ax.set_xticks(numeric)
        cbar.ax.set_xticklabels(labels)
    else:
        cbar.ax.set_yticks(numeric)
        cbar.ax.set_yticklabels(labels)


def linear_regression_slope(time: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Least-squares slope along axis 0 while respecting NaNs.

    time shape: (T,)
    values shape: (T, ...)
    Returns slope per year in same trailing shape as values[0].
    """
    t = np.asarray(time, dtype=np.float64)
    v = np.asarray(values, dtype=np.float64)
    if v.shape[0] != t.size:
        raise ValueError("Time axis length must match the first dimension of values")
    demeaned_t = t - t.mean()
    reshape = (t.size,) + (1,) * (v.ndim - 1)
    t_reshaped = demeaned_t.reshape(reshape)
    mask = np.isfinite(v)
    v_masked = np.where(mask, v, np.nan)
    mean_vals = np.nanmean(v_masked, axis=0)
    numerator = np.nansum(t_reshaped * (v_masked - mean_vals), axis=0)
    denominator = np.nansum((demeaned_t**2).reshape(reshape) * mask, axis=0)
    slope = np.full_like(mean_vals, np.nan, dtype=np.float64)
    valid = denominator > 0
    slope[valid] = numerator[valid] / denominator[valid]
    return slope


def to_mesh(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if lat.ndim == 1 and lon.ndim == 1:
        X, Y = np.meshgrid(lon, lat)
        return X, Y
    return lon, lat


def infer_rhs_scale(units: str | None) -> float:
    """Return multiplier to convert monthly mean units to K decade^-1.

    If units are K s^-1 → ×86400×365×10
       units are K day^-1 → ×365×10
       otherwise default to ×365×10 (repo storage convention).
    """
    if not units:
        return DAYS_PER_YEAR * 10.0
    u = units.replace(" ", "").lower()
    if "kday-1" in u or "k/day" in u or "kperday" in u:
        return DAYS_PER_YEAR * 10.0
    if "ks-1" in u or "k/s" in u or "kpers" in u:
        return SECONDS_PER_DAY * DAYS_PER_YEAR * 10.0
    return DAYS_PER_YEAR * 10.0


def _nice_abs(v: float) -> float:
    """Return a 'nice' symmetric abs max >= v using {1,1.5,2,2.5,3,5,6,8,10}×10^k.

    Helps produce clean colorbar ticks (e.g., ±6, ±100) instead of awkward values.
    """
    if not np.isfinite(v) or v <= 0:
        return 1.0
    mag = 10.0 ** np.floor(np.log10(v))
    base = v / mag
    steps = [1.0, 1.5, 2.0, 2.5, 3.0, 5.0, 6.0, 8.0, 10.0]
    for s in steps:
        if base <= s + 1e-12:
            return s * mag
    return 10.0 * mag


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--monthly",
        type=Path,
        default=Path("/Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly_main_*.nc"),
        help="Monthly MLHB NetCDF (time×lat×lon), single file or glob pattern (*.nc)",
    )
    p.add_argument(
        "--trend-output",
        type=Path,
        default=Path("/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/decadal_mlhb_trend_offset.png"),
        help="Output PNG for trend-offset map",
    )
    p.add_argument(
        "--rhs-output",
        type=Path,
        default=Path("/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/decadal_mlhb_rhs_native.png"),
        help="Output PNG for RHS panel (native DIFFV)",
    )
    p.add_argument("--adv-smooth-iter", type=int, default=0, help="Apply 9-point smoothing to ADV this many times (default 0)")
    p.add_argument("--year-start", type=int, default=1993)
    p.add_argument("--year-end", type=int, default=2022)
    p.add_argument("--short-start", type=int, default=2011)
    p.add_argument("--short-end", type=int, default=2022)
    p.add_argument("--dpi", type=int, default=170)
    p.add_argument("--diffv-mode", choices=["native", "residual"], default="native", help="Use DIFFV from file (native) or residual TEN-(QNET+ADV+ENT+DIFF)")
    p.add_argument("--no-annot", action="store_true", help="Disable policy/settings caption annotation on figures")
    p.add_argument("--annot", action="store_true", help="Force show policy/settings caption annotation on figures")
    p.add_argument("--flip-diffv-sign", action="store_true", help="Flip DIFFV sign only for visualization (caption annotated)")
    # scaling controls (guideline: choose scale from data; keep ≤21 levels)
    p.add_argument("--rhs-prc", type=float, default=98.0, help="Percentile for symmetric RHS scale if --rhs-vclip unset")
    p.add_argument("--rhs-vclip", type=float, default=None, help="Fixed abs max for RHS scale (K/decade)")
    p.add_argument("--trend-prc", type=float, default=None, help="Percentile for symmetric trend scale if --trend-vclip unset (default fixed 2.5)")
    p.add_argument("--trend-vclip", type=float, default=None, help="Fixed abs max for trend scale (K/decade; default 2.5)")
    p.add_argument("--strict-cartopy", action="store_true", help="Fail if Cartopy is unavailable (report mode)")
    return p.parse_args(argv)


def shift_lat(arr: np.ndarray, offset: int) -> np.ndarray:
    if offset == 0:
        return arr.copy()
    result = np.full_like(arr, np.nan)
    if offset > 0:
        result[offset:, :] = arr[:-offset, :]
    else:
        result[:offset, :] = arr[-offset:, :]
    return result


def shift_lon(arr: np.ndarray, offset: int, wrap: bool) -> np.ndarray:
    if offset == 0:
        return arr.copy()
    if wrap:
        return np.roll(arr, shift=offset, axis=-1)
    result = np.full_like(arr, np.nan)
    if offset > 0:
        result[:, offset:] = arr[:, :-offset]
    else:
        result[:, :offset] = arr[:, -offset:]
    return result


def smth9_2d(data: np.ndarray, p: float = 0.50, q: float = 0.25, wrap: bool = True) -> np.ndarray:
    if data.ndim != 2:
        raise ValueError("smth9_2d expects 2-D input")
    ny, nx = data.shape
    centre = data
    north = shift_lat(centre, -1)
    south = shift_lat(centre, 1)
    west = shift_lon(centre, -1, wrap)
    east = shift_lon(centre, 1, wrap)
    northwest = shift_lon(north, -1, wrap)
    northeast = shift_lon(north, 1, wrap)
    southwest = shift_lon(south, -1, wrap)
    southeast = shift_lon(south, 1, wrap)
    valid = (
        np.isfinite(centre)
        & np.isfinite(north)
        & np.isfinite(south)
        & np.isfinite(east)
        & np.isfinite(west)
        & np.isfinite(northwest)
        & np.isfinite(northeast)
        & np.isfinite(southwest)
        & np.isfinite(southeast)
    )
    out = centre.copy()
    if np.any(valid):
        sides = west + east + north + south
        corners = northwest + northeast + southwest + southeast
        updated = centre[valid] + (p / 4.0) * (sides[valid] - 4.0 * centre[valid]) + (q / 4.0) * (corners[valid] - 4.0 * centre[valid])
        out[valid] = updated
    out[~np.isfinite(centre)] = np.nan
    return out


def maybe_smooth_adv(yearly_adv: xr.DataArray, n_iter: int) -> xr.DataArray:
    if n_iter <= 0:
        return yearly_adv
    # apply per-year smoothing on 2D planes
    adv = yearly_adv.copy()
    years = adv["year"].values
    arr = adv.values  # shape: (year, lat, lon)
    for k in range(arr.shape[0]):
        a = arr[k]
        for _ in range(n_iter):
            a = smth9_2d(a, p=0.50, q=0.25, wrap=True)
        arr[k] = a
    adv.values = arr
    return adv


@dataclass
class BudgetNative:
    lat: np.ndarray
    lon: np.ndarray
    trend_offset: np.ndarray  # K decade^-1
    rhs_anom_native: np.ndarray  # shape (6, lat, lon), K decade^-1


def compute_from_monthly(ds: xr.Dataset, *, year_start: int, year_end: int, short_start: int, short_end: int, adv_smooth_iter: int, diffv_mode: str = "native") -> BudgetNative:
    # Ensure coordinates
    lat = ds["lat"].values if "lat" in ds.coords else ds["latitude"].values
    lon = ds["lon"].values if "lon" in ds.coords else ds["longitude"].values

    # Slice requested years
    ds_sel = ds.sel(time=slice(f"{year_start}-01-01", f"{year_end}-12-31"))
    # Annual means
    annual = ds_sel.groupby("time.year").mean("time", skipna=True, keep_attrs=True)

    # Variables
    def pick_var(name: str) -> xr.DataArray:
        for k in ds_sel.data_vars:
            if k.lower() == name.lower():
                return annual[k]
        # allow fallback for common aliases
        aliases = {
            "t_ml": ("t_ml", "tml", "tmean", "tm"),
            "qnet": ("qnet",),
            "adv": ("adv",),
            "ent": ("ent",),
            "diff": ("diff", "diffh", "lateral_diff", "kappa_h"),
            "diffv": ("diffv", "diff_v", "vertical_diff"),
            "ten": ("ten", "tend", "tendency"),
        }
        keys = aliases.get(name.lower(), (name,))
        for key in keys:
            for k in ds_sel.data_vars:
                if key == k.lower():
                    return annual[k]
        raise KeyError(f"variable '{name}' not found in dataset")

    T_ML = pick_var("T_ML")
    QNET = pick_var("QNET")
    ADV = pick_var("ADV")
    ENT = pick_var("ENT")
    DIFF = pick_var("DIFF")
    DIFFV = pick_var("DIFFV")
    # Optional smooth on annual ADV
    ADV = maybe_smooth_adv(ADV, adv_smooth_iter)

    # Trend offset from annual-mean T_ML
    years_full = annual["year"].values.astype(int)
    Tm = T_ML  # already annual mean
    Tmm = Tm.mean(dim="year", skipna=True)
    Ta = Tm - Tmm
    # Full and short windows
    def _window_index(years: np.ndarray, y0: int, y1: int) -> np.ndarray:
        return (years >= y0) & (years <= y1)

    mask_full = _window_index(years_full, year_start, year_end)
    mask_short = _window_index(years_full, short_start, short_end)

    t_full = years_full[mask_full].astype(float)
    t_short = years_full[mask_short].astype(float)
    Ta_full = Ta.sel(year=years_full[mask_full]).values  # (T, lat, lon)
    Ta_short = Ta.sel(year=years_full[mask_short]).values

    full_slope = linear_regression_slope(t_full, Ta_full)  # K/year
    short_slope = linear_regression_slope(t_short, Ta_short)  # K/year
    trend_offset = (short_slope - full_slope) * 10.0  # K/decade

    # RHS anomalies (native DIFFV): annual mean anomaly averaged over short
    # Sum of subsurface terms
    if diffv_mode == "residual":
        TEN = pick_var("TEN")
        SUBS = ADV + ENT + DIFF + (TEN - (QNET + ADV + ENT + DIFF))
    else:
        SUBS = ADV + ENT + DIFF + DIFFV
    def _anom_mean(da: xr.DataArray, mask: np.ndarray) -> np.ndarray:
        a = da - da.mean(dim="year", skipna=True)
        return a.sel(year=years_full[mask]).mean(dim="year", skipna=True).values

    rhs_units = QNET.attrs.get("units") if hasattr(QNET, "attrs") else None
    scale = infer_rhs_scale(rhs_units)

    rhs_native = np.empty((6, lat.shape[0], lon.shape[0]), dtype=np.float64)
    rhs_native[0] = _anom_mean(QNET, mask_short) * scale
    rhs_native[1] = _anom_mean(SUBS, mask_short) * scale
    rhs_native[2] = _anom_mean(ADV, mask_short) * scale
    rhs_native[3] = _anom_mean(ENT, mask_short) * scale
    rhs_native[4] = _anom_mean(DIFF, mask_short) * scale
    rhs_native[5] = (_anom_mean((TEN - (QNET + ADV + ENT + DIFF)) if diffv_mode == "residual" else DIFFV, mask_short) * scale)

    return BudgetNative(lat=lat, lon=lon, trend_offset=trend_offset, rhs_anom_native=rhs_native)


def add_common_map_decor(ax, *, left_labels: bool = True, bottom_labels: bool = True) -> None:
    if ccrs is None:
        if bottom_labels:
            ax.set_xlabel("Longitude")
        if left_labels:
            ax.set_ylabel("Latitude")
        return
    # Land with visible outline and coastlines in black
    try:
        land50 = cfeature.NaturalEarthFeature(
            "physical", "land", "50m", edgecolor="black", facecolor="lightgrey", linewidth=0.6
        )
        ax.add_feature(land50, zorder=0)
    except Exception:
        ax.add_feature(cfeature.LAND, facecolor="lightgrey", edgecolor="black", linewidth=0.6, zorder=0)
    ax.coastlines(resolution="50m", color="black", linewidth=0.8)
    # 5-degree grid with degree symbols
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.4, linestyle=":")
    gl.xlocator = mticker.MultipleLocator(5)
    gl.ylocator = mticker.MultipleLocator(5)
    try:
        gl.xformatter = LongitudeFormatter(number_format=".0f", degree_symbol="°")
        gl.yformatter = LatitudeFormatter(number_format=".0f", degree_symbol="°")
    except Exception:
        pass
    # show labels only on requested sides to avoid crowding
    try:
        gl.top_labels = False
        gl.right_labels = False
        gl.left_labels = bool(left_labels)
        gl.bottom_labels = bool(bottom_labels)
    except Exception:
        # fall back: hide labels and set axes labels instead
        gl.xlabels_top = False
        gl.ylabels_right = False
        gl.ylabels_left = bool(left_labels)
        gl.xlabels_bottom = bool(bottom_labels)
    # Increase label size (~+20%) for readability
    gl.xlabel_style = {"size": 10, "rotation": 0}
    gl.ylabel_style = {"size": 10}


def plot_trend_map(lat: np.ndarray, lon: np.ndarray, trend_offset: np.ndarray, output: Path, dpi: int = 170, note: str | None = None, vmax: float | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subplot_kwargs = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
    fig = plt.figure(figsize=(8.0, 4.8))
    ax = fig.add_subplot(1, 1, 1, **subplot_kwargs)
    X, Y = to_mesh(lat if lat.ndim == 2 else lat, lon if lon.ndim == 2 else lon)
    try:
        cmap = plt.get_cmap("RdBu_r").copy(); cmap.set_bad('lightgrey')
    except Exception:
        cmap = plt.get_cmap("RdBu_r")
        try: cmap.set_bad('lightgrey')
        except Exception: pass
    # symmetric levels for trend (K/decade)
    vabs = 2.5 if (vmax is None or vmax <= 0) else float(vmax)
    vabs = _nice_abs(vabs)
    levels = np.linspace(-vabs, vabs, 21)
    cs = ax.contourf(lon if lon.ndim == 1 else lon, lat if lat.ndim == 1 else lat, trend_offset, levels=levels, cmap=cmap, extend="both", transform=ccrs.PlateCarree() if ccrs is not None else None)
    # lock extent to data bounds to avoid clipping
    if ccrs is not None:
        lmin = float(np.nanmin(lon if lon.ndim == 1 else lon))
        lmax = float(np.nanmax(lon if lon.ndim == 1 else lon))
        bmin = float(np.nanmin(lat if lat.ndim == 1 else lat))
        bmax = float(np.nanmax(lat if lat.ndim == 1 else lat))
        ax.set_extent([lmin, lmax, bmin, bmax], crs=ccrs.PlateCarree())
    add_common_map_decor(ax)
    ax.set_title("Trend Offset (2011–2022 minus 1993–2022)")
    pos = ax.get_position()
    # increase gap below x tick labels to avoid overlap
    y0 = max(0.06, pos.y0 - 0.08)
    cax = fig.add_axes([pos.x0, y0, pos.width, 0.025])
    ticks = _select_tick_values(levels, max_labels=7)
    cbar = fig.colorbar(cs, cax=cax, orientation="horizontal", ticks=ticks)
    cbar.set_label(r"K decade$^{-1}$")
    _set_colorbar_ticks(cbar, ticks)
    if note:
        fig.text(0.01, 0.01, note, fontsize=7, ha="left", va="bottom")
    tmp = output.with_name(output.stem + ".tmp" + output.suffix)
    fig.savefig(tmp, dpi=dpi)
    plt.close(fig)
    tmp.replace(output)


def plot_rhs_panel(lat: np.ndarray, lon: np.ndarray, rhs_native: np.ndarray, output: Path, dpi: int = 170, note: str | None = None, vmax: float | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subplot_kwargs = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
    # Layout: 3×2
    fig_height = 11.0
    left, right = 0.055, 0.985
    top, bottom = 0.97, 0.12
    hspace = 0.12
    wspace = 0.10
    lon_span = float((lon[-1] - lon[0]) if lon.ndim == 1 else (np.nanmax(lon) - np.nanmin(lon)))
    lat_span = float((lat[-1] - lat[0]) if lat.ndim == 1 else (np.nanmax(lat) - np.nanmin(lat)))
    available_height = fig_height * (top - bottom)
    axis_height = available_height / (3 + 2 * hspace)
    axis_width = axis_height * (lon_span / lat_span) if lat_span != 0 else axis_height * 1.2
    available_width = axis_width * (2 + wspace)
    fig_width = available_width / (right - left)

    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(3, 2, left=left, right=right, top=top, bottom=bottom, wspace=wspace, hspace=hspace)
    axes = np.array([[fig.add_subplot(gs[r, c], **subplot_kwargs) for c in range(2)] for r in range(3)])

    titles = [
        "Surface Heat Flux (Qnet)",
        "ADV+ENT+DIFF(+V)",
        "Horizontal Advection",
        "Entrainment",
        "Lateral Diffusion",
        "Vertical Diffusion",
    ]
    # symmetric levels for RHS (K/decade), default 17 levels (≤21 guideline)
    vabs = 100.0 if (vmax is None or vmax <= 0) else float(vmax)
    vabs = _nice_abs(vabs)
    levels = np.linspace(-vabs, vabs, 17)
    try:
        cmap = plt.get_cmap("RdBu_r").copy(); cmap.set_bad('lightgrey')
    except Exception:
        cmap = plt.get_cmap("RdBu_r")
        try: cmap.set_bad('lightgrey')
        except Exception: pass

    lon2d, lat2d = (np.meshgrid(lon, lat) if (lat.ndim == 1 and lon.ndim == 1) else (lon, lat))
    mappables = []
    for idx in range(6):
        row, col = divmod(idx, 2)
        ax = axes[row, col]
        cs = ax.contourf(lon2d, lat2d, rhs_native[idx, ...], levels=levels, cmap=cmap, extend="both", transform=ccrs.PlateCarree() if ccrs is not None else None)
        # lock extent to data bounds to avoid clipping
        if ccrs is not None:
            lmin = float(np.nanmin(lon2d))
            lmax = float(np.nanmax(lon2d))
            bmin = float(np.nanmin(lat2d))
            bmax = float(np.nanmax(lat2d))
            ax.set_extent([lmin, lmax, bmin, bmax], crs=ccrs.PlateCarree())
        add_common_map_decor(ax, left_labels=(col == 0), bottom_labels=(row == 2))
        label = f"({chr(ord('a') + idx)})"
        ax.set_title(f"{label} {titles[idx]}", pad=6, loc="left")
        mappables.append(cs)

    positions = [ax.get_position() for ax in axes.ravel()]
    x0 = min(pos.x0 for pos in positions)
    x1 = max(pos.x1 for pos in positions)
    y0_axes = min(pos.y0 for pos in positions)
    # place colorbar with sufficient gap from bottom tick labels
    y0 = max(0.06, y0_axes - 0.08)
    cax = fig.add_axes([x0, y0, x1 - x0, 0.025])
    ticks = _select_tick_values(levels, max_labels=9)
    cbar = fig.colorbar(mappables[0], cax=cax, orientation="horizontal", ticks=ticks)
    cbar.set_label(r"K decade$^{-1}$")
    _set_colorbar_ticks(cbar, ticks)
    if note:
        fig.text(0.01, 0.01, note, fontsize=7, ha="left", va="bottom")
    tmp = output.with_name(output.stem + ".tmp" + output.suffix)
    fig.savefig(tmp, dpi=dpi)
    plt.close(fig)
    tmp.replace(output)


def _open_monthly(path: Path) -> xr.Dataset:
    """Open monthly dataset. Supports single file or glob pattern.

    Returns a dataset with time×lat×lon and required variables.
    """
    s = str(path)
    if any(ch in s for ch in "*?["):
        files = sorted([str(p) for p in Path(path.parent).glob(path.name)])
        if not files:
            raise FileNotFoundError(f"No files matched pattern: {path}")
        # open without dask by loading sequentially and concat on time
        dsets = [xr.open_dataset(f) for f in files]
        try:
            ds = xr.concat(dsets, dim="time")
        finally:
            for d in dsets:
                try:
                    d.close()
                except Exception:
                    pass
        return ds
    if path.is_dir():
        # try common filename pattern in directory
        patt = sorted([str(p) for p in path.glob("mlhb_monthly_main_*.nc")])
        if not patt:
            patt = sorted([str(p) for p in path.glob("*.nc")])
        if not patt:
            raise FileNotFoundError(f"No NetCDF files in directory: {path}")
        dsets = [xr.open_dataset(f) for f in patt]
        try:
            ds = xr.concat(dsets, dim="time")
        finally:
            for d in dsets:
                try:
                    d.close()
                except Exception:
                    pass
        return ds
    return xr.open_dataset(path)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    if args.strict_cartopy and (ccrs is None):
        raise SystemExit("Cartopy is required (--strict-cartopy) but not available. Install cartopy/shapely/pyproj.")
    ds = _open_monthly(args.monthly)
    fields = compute_from_monthly(
        ds,
        year_start=args.year_start,
        year_end=args.year_end,
        short_start=args.short_start,
        short_end=args.short_end,
        adv_smooth_iter=args.adv_smooth_iter,
        diffv_mode=args.diffv_mode,
    )
    # Optionally flip only DIFFV (panel index 5) for visualization
    if args.flip_diffv_sign:
        try:
            # keep a copy of DIFFV contribution before flipping (K decade^-1)
            _diffv_before = fields.rhs_anom_native[5, ...].copy()
            # flip DIFFV panel
            fields.rhs_anom_native[5, ...] *= -1.0
            # if SUBS (panel b) included DIFFV (native mode), reflect the flip: SUBS' = SUBS - 2*DIFFV
            if args.diffv_mode == "native":
                fields.rhs_anom_native[1, ...] = fields.rhs_anom_native[1, ...] - 2.0 * _diffv_before
        except Exception:
            pass
    note = None
    if getattr(args, 'annot', False) and not getattr(args, 'no_annot', False):
        note = (
            f"Windows: full {args.year_start}-{args.year_end}, short {args.short_start}-{args.short_end}; "
            f"ADV smooth={args.adv_smooth_iter}; DIFFV={args.diffv_mode}; DIFFV_flip={'yes' if args.flip_diffv_sign else 'no'}; "
            f"land=lightgrey; levels≤21; units: K decade^-1"
        )
    # determine symmetric scales from args or data percentiles
    trend_vmax = None
    if args.trend_vclip and args.trend_vclip > 0:
        trend_vmax = float(args.trend_vclip)
    elif args.trend_prc is not None:
        a = np.abs(np.asarray(fields.trend_offset))
        trend_vmax = float(np.nanpercentile(a, float(args.trend_prc)))
    rhs_vmax = None
    if args.rhs_vclip and args.rhs_vclip > 0:
        rhs_vmax = float(args.rhs_vclip)
    else:
        a = np.abs(np.asarray(fields.rhs_anom_native))
        rhs_vmax = float(np.nanpercentile(a, float(args.rhs_prc)))

    plot_trend_map(fields.lat, fields.lon, fields.trend_offset, args.trend_output, dpi=args.dpi, note=note, vmax=trend_vmax)
    plot_rhs_panel(fields.lat, fields.lon, fields.rhs_anom_native, args.rhs_output, dpi=args.dpi, note=note, vmax=rhs_vmax)


if __name__ == "__main__":
    main()
