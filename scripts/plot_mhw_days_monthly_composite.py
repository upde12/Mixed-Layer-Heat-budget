#!/usr/bin/env python3
"""Monthly composite of MHW days (duration) for selected ELT years.

Reads monthly MHW duration data from a raw binary file (float32) shaped as
time×lat×lon = (468, 101, 145) covering 39 years × 12 months over the WNP
region (lat 19.875–44.875, lon 109.375–145.375 at 0.25°).

Outputs a 12‑month 6×2 panel of anomalies (relative to monthly climatology),
averaged over the requested ELT years (e.g., 1998,2010,2016,2020).
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
from typing import Iterable, List

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
except Exception:
    ccrs = None
    cfeature = None


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dur-file", default="/Volumes/HJPARK4/MHW/source/detect/dur_mon_ECS.data", help="Raw float32 file of monthly MHW days (468×101×145)")
    p.add_argument("--years", default="1998,2010,2016,2020", help="Comma-separated ELT years to composite")
    p.add_argument("--out", default="/Volumes/HJPARK4/Decadal/Figure/elt_composite/elt_comp_MHW_DAYS_12months_6x2.png", help="Output PNG path")
    p.add_argument("--dpi", type=int, default=170)
    p.add_argument("--prc", type=float, default=98.0, help="Percentile for symmetric color scale")
    p.add_argument("--mode", choices=["anomaly","absolute"], default="anomaly", help="Plot anomaly (default) or absolute monthly mean across ELT years")
    p.add_argument("--cmap", default=None, help="Colormap override (default: RdBu_r for anomaly, YlOrRd for absolute)")
    p.add_argument("--clim-start", type=int, default=None, help="Climatology start year (e.g., 1993). If unset, use full period in file")
    p.add_argument("--clim-end", type=int, default=None, help="Climatology end year (e.g., 2021). If unset, use full period in file")
    p.add_argument("--last-year", type=int, default=2021, help="Last calendar year contained in the binary (used to infer start year)")
    p.add_argument("--ctl", default=None, help="Optional CTL file to infer absolute years (parses TDEF to validate last-year)")
    return p.parse_args(argv)


def load_duration(path: Path) -> np.ndarray:
    arr = np.fromfile(path, dtype=np.float32)
    # Infer time dimension by total size
    per_slice = 101 * 145
    if arr.size % per_slice != 0:
        raise SystemExit(f"Unexpected element count {arr.size}; not divisible by 101*145")
    t = arr.size // per_slice
    arr = arr.reshape(t, 101, 145)
    return arr


def infer_last_year_from_ctl(ctl_path: Path) -> int | None:
    try:
        text = ctl_path.read_text(errors='ignore')
    except Exception:
        return None
    # Example: TDEF 39 LINEAR 01Jan1983 1yr
    m = re.search(r"TDEF\s+(\d+)\s+LINEAR\s+\w+\s*(\d{4})\s+1yr", text, re.IGNORECASE)
    if not m:
        m = re.search(r"TDEF\s+(\d+)\s+LINEAR\s+01Jan(\d{4})\s+1yr", text, re.IGNORECASE)
    if not m:
        return None
    ny = int(m.group(1)); y0 = int(m.group(2))
    return y0 + ny - 1


def monthly_anomaly(dur: np.ndarray) -> np.ndarray:
    # dur shape: T×101×145; T=years×12
    if dur.shape[0] % 12 != 0:
        raise SystemExit("Time length is not a multiple of 12 months")
    years = dur.shape[0] // 12
    durx = dur.reshape(years, 12, 101, 145)
    clim = np.nanmean(durx, axis=0)  # 12×101×145
    anom = durx - clim[None, ...]
    return anom  # 39×12×101×145


def nice(v: float) -> float:
    if not np.isfinite(v) or v <= 0:
        return 1.0
    mag = 10.0 ** np.floor(np.log10(v))
    base = v / mag
    for s in [1, 1.5, 2, 2.5, 3, 5, 6, 8, 10]:
        if base <= s + 1e-12:
            return s * mag
    return 10.0 * mag


def to_mesh(lat: np.ndarray, lon: np.ndarray):
    if lat.ndim == 1 and lon.ndim == 1:
        X, Y = np.meshgrid(lon, lat)
        return X, Y
    return lon, lat


def add_map(ax, left: bool, bottom: bool) -> None:
    if ccrs is None:
        if bottom:
            ax.set_xlabel("Longitude")
        if left:
            ax.set_ylabel("Latitude")
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
    gl.xlabel_style = {"size": 10, "rotation": 0}; gl.ylabel_style = {"size": 10}


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    years = [int(s) for s in args.years.split(',') if s.strip()]

    path = Path(args.dur_file)
    dur = load_duration(path)  # 468×101×145
    # Reshape to years×12×lat×lon
    if dur.shape[0] % 12 != 0:
        raise SystemExit("Time length is not a multiple of 12 months")
    years_count = dur.shape[0] // 12
    durx = dur.reshape(years_count, 12, 101, 145)

    # Monthly anomalies for all years if needed (full-period baseline)
    anom_full = monthly_anomaly(dur)

    # Infer/validate absolute years
    last_year = int(args.last_year)
    ctl_path = Path(args.ctl) if args.ctl else Path(args.dur_file).with_suffix('.ctl')
    if ctl_path.exists():
        inferred = infer_last_year_from_ctl(ctl_path)
        if inferred is not None and inferred != last_year:
            raise SystemExit(f"last_year mismatch: --last-year={last_year} vs CTL-inferred={inferred} ({ctl_path}); set --last-year {inferred} or provide correct CTL")
    start_year = last_year - (years_count - 1)
    idx = [y - start_year for y in years]
    for i in idx:
        if i < 0 or i >= years_count:
            raise SystemExit(f"Year index out of range for year list {years}; check start_year={start_year}")

    if args.mode == 'anomaly':
        # If a climatology window is provided, recompute anomalies using that baseline
        if args.clim_start is not None or args.clim_end is not None:
            # year numbers array
            years_axis = np.arange(start_year, start_year + years_count)
            y0 = args.clim_start if args.clim_start is not None else int(years_axis.min())
            y1 = args.clim_end if args.clim_end is not None else int(years_axis.max())
            mask = (years_axis >= y0) & (years_axis <= y1)
            if not np.any(mask):
                raise SystemExit(f"No years in climatology window {y0}-{y1}")
            clim = np.nanmean(durx[mask, ...], axis=0)  # 12×101×145
            anom_sel = durx - clim[None, ...]
            comp = np.nanmean(anom_sel[idx, ...], axis=0)
        else:
            # 12×101×145 using full-period baseline
            comp = np.nanmean(anom_full[idx, ...], axis=0)
    else:
        # Absolute monthly means across the selected ELT years
        comp = np.nanmean(durx[idx, ...], axis=0)  # 12×101×145

    # Coordinates (as in NCL):
    lat = np.linspace(19.875, 44.875, 101)
    lon = np.linspace(109.375, 145.375, 145)
    lon2d, lat2d = to_mesh(lat, lon)

    # Determine symmetric levels from percentile across months
    if args.mode == 'anomaly':
        vals = np.abs(comp)
        vals = vals[np.isfinite(vals)]
        vabs = nice(float(np.nanpercentile(vals, float(args.prc))) if vals.size else 1.0)
        levels = np.linspace(-vabs, vabs, 21)
    else:
        vals = comp[np.isfinite(comp)]
        vmax = float(np.nanpercentile(vals, float(args.prc))) if vals.size else 10.0
        if vmax <= 0:
            vmax = 1.0
        levels = np.linspace(0.0, vmax, 17)

    # Plot 6×2 panel
    proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
    fig = plt.figure(figsize=(14.0, 5.8))
    gs = fig.add_gridspec(2, 6, left=0.05, right=0.995, top=0.95, bottom=0.14, wspace=0.06, hspace=0.10)
    month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    # Colormap
    if args.cmap:
        cmap = plt.get_cmap(args.cmap)
    else:
        cmap = plt.get_cmap('RdBu_r' if args.mode == 'anomaly' else 'YlOrRd')
    try:
        cmap = cmap.copy(); cmap.set_bad('lightgrey')
    except Exception:
        pass
    mapp = []
    for idx_m, m in enumerate(range(1, 13)):
        r = 0 if idx_m < 6 else 1
        c = idx_m if idx_m < 6 else idx_m - 6
        ax = fig.add_subplot(gs[r, c], **proj)
        h = ax.contourf(lon2d, lat2d, comp[m-1, ...], levels=levels, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
        if ccrs is not None:
            ax.set_extent([float(np.nanmin(lon2d)), float(np.nanmax(lon2d)), float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
        add_map(ax, left=(c==0), bottom=(r==1))
        ax.set_title(month_names[m-1], fontsize=10)
        if idx_m == 0:
            mapp.append(h)
    # colorbar
    poss = [ax.get_position() for ax in fig.axes]
    x0 = min(p.x0 for p in poss); x1 = max(p.x1 for p in poss); y0 = max(0.06, min(p.y0 for p in poss) - 0.05)
    cax = fig.add_axes([x0, y0, x1 - x0, 0.022])
    label = 'MHW days (anomaly)' if args.mode == 'anomaly' else 'MHW days (absolute)'
    cb = fig.colorbar(mapp[0], cax=cax, orientation='horizontal'); cb.set_label(label)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".tmp" + out.suffix)
    fig.savefig(tmp, dpi=args.dpi)
    plt.close(fig)
    tmp.replace(out)


if __name__ == "__main__":
    main()
