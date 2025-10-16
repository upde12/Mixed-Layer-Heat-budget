#!/usr/bin/env python3
"""Compare ONDJ vs OND seasonal composites for MHW Days.

Loads monthly MHW duration (days) on the ECS grid (101×145 at 0.25°) and
renders a 1×3 figure: (a) ONDJ anomaly, (b) OND anomaly, (c) ONDJ − OND.

Definitions
- ONDJ: Oct(prev) + Nov(prev) + Dec(prev) + Jan(curr)
- OND:  Oct(curr) + Nov(curr) + Dec(curr)

Notes
- Anomaly mode subtracts monthly climatology (years in [--clim-start, --clim-end]).
- Colormap scaling for (a)(b) uses a common symmetric abs max from both panels
  (98th percentile by default). The diff panel uses its own symmetric scale.
- Map styling follows repository guidelines (Cartopy if available): 5° grid,
  ° labels, land=lightgrey, coastlines=50m.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple, Dict

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
    p.add_argument("--dur-file", default="/Volumes/HJPARK4/MHW/source/detect/dur_mon_ECS.data", help="Raw float32 monthly MHW days (time×101×145)")
    p.add_argument("--years", default="1998,2010,2016,2020", help="Comma-separated ELT years to composite")
    p.add_argument("--mode", choices=["anomaly","absolute"], default="anomaly", help="Use anomalies or absolute days")
    p.add_argument("--clim-start", type=int, default=1993, help="Climatology start year (anomaly mode)")
    p.add_argument("--clim-end", type=int, default=2021, help="Climatology end year (anomaly mode)")
    p.add_argument("--prc", type=float, default=98.0, help="Percentile for symmetric scale (panels a/b); diff panel uses same percentile on |diff|")
    p.add_argument("--out", default="/Volumes/HJPARK4/Decadal/Figure/elt_composite/elt_comp_MHW_DAYS_ONDJ_vs_OND.png", help="Output PNG path")
    p.add_argument("--last-year", type=int, default=2021, help="Last calendar year contained in the binary (used to infer start year)")
    p.add_argument("--dpi", type=int, default=170)
    return p.parse_args(argv)


def load_monthly(path: Path) -> np.ndarray:
    arr = np.fromfile(path, dtype=np.float32)
    per = 101 * 145
    if arr.size % per != 0:
        raise SystemExit(f"Unexpected size {arr.size}; not divisible by 101*145")
    t = arr.size // per
    return arr.reshape(t, 101, 145)


def season_defs() -> Dict[str, List[Tuple[int, int]]]:
    """Return month/year-offset pairs for seasons.

    Each item is (month, year_offset) where year_offset is relative to the ELT
    target year y: prev year = -1, current year = 0.
    """
    return {
        "ONDJ": [(10, -1), (11, -1), (12, -1), (1, 0)],
        "OND":  [(10, 0), (11, 0), (12, 0)],
    }


def nice(v: float) -> float:
    if not np.isfinite(v) or v <= 0:
        return 1.0
    mag = 10.0 ** np.floor(np.log10(v))
    base = v / mag
    for s in [1, 1.5, 2, 2.5, 3, 5, 6, 8, 10]:
        if base <= s + 1e-12:
            return s * mag
    return 10.0 * mag


def add_map(ax, *, left: bool, bottom: bool) -> None:
    if ccrs is None:
        if bottom:
            ax.set_xlabel("Longitude")
        if left:
            ax.set_ylabel("Latitude")
        return
    try:
        land50 = cfeature.NaturalEarthFeature("physical", "land", "50m", edgecolor="black", facecolor="lightgrey", linewidth=0.6)
        ax.add_feature(land50, zorder=0)
    except Exception:
        ax.add_feature(cfeature.LAND, facecolor="lightgrey", edgecolor="black", linewidth=0.6, zorder=0)
    ax.coastlines(resolution="50m", color="black", linewidth=0.8)
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.4, linestyle=":")
    gl.xlocator = mticker.MultipleLocator(5)
    gl.ylocator = mticker.MultipleLocator(5)
    try:
        gl.xformatter = LongitudeFormatter(number_format=".0f", degree_symbol="°")
        gl.yformatter = LatitudeFormatter(number_format=".0f", degree_symbol="°")
    except Exception:
        pass
    try:
        gl.top_labels = False
        gl.right_labels = False
        gl.left_labels = bool(left)
        gl.bottom_labels = bool(bottom)
    except Exception:
        gl.xlabels_top = False
        gl.ylabels_right = False
        gl.ylabels_left = bool(left)
        gl.xlabels_bottom = bool(bottom)
    gl.xlabel_style = {"size": 10, "rotation": 0}
    gl.ylabel_style = {"size": 10}


def build_composite(data: np.ndarray, years: List[int], months: List[Tuple[int, int]], *, start_year: int, mode: str, clim: np.ndarray | None) -> np.ndarray:
    """Return composite over given years and (month, year_offset) list.

    data: shape (n_years, 12, 101, 145) in absolute days
    clim: shape (12, 101, 145) monthly climatology (ignored in absolute mode)
    """
    acc = []
    for y in years:
        yi = y - start_year
        for m, off in months:
            ysel = yi + off
            if ysel < 0 or ysel >= data.shape[0]:
                continue
            mi = m - 1
            if mode == "anomaly":
                acc.append(data[ysel, mi, ...] - clim[mi, ...])
            else:
                acc.append(data[ysel, mi, ...])
    if not acc:
        raise SystemExit("No samples for composite")
    return np.nanmean(np.stack(acc, axis=0), axis=0)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    years = [int(s) for s in args.years.split(',') if s.strip()]

    dur = load_monthly(Path(args.dur_file))  # T×101×145
    if dur.shape[0] % 12 != 0:
        raise SystemExit("Time length is not a multiple of 12")
    n_years = dur.shape[0] // 12
    data = dur.reshape(n_years, 12, 101, 145)

    # Infer start year from provided last year
    last_year = int(args.last_year)
    start_year = last_year - (n_years - 1)

    # Climatology for anomaly mode
    clim = None
    if args.mode == "anomaly":
        year_axis = np.arange(start_year, start_year + n_years)
        mask = (year_axis >= args.clim_start) & (year_axis <= args.clim_end)
        if not np.any(mask):
            raise SystemExit(f"No years within climatology window {args.clim_start}-{args.clim_end}")
        clim = np.nanmean(data[mask, ...], axis=0)  # 12×101×145

    # Lat/Lon
    lat = np.linspace(19.875, 44.875, 101)
    lon = np.linspace(109.375, 145.375, 145)
    lon2d, lat2d = np.meshgrid(lon, lat)

    seasons = season_defs()
    ondj = build_composite(data, years, seasons["ONDJ"], start_year=start_year, mode=args.mode, clim=clim)
    ond = build_composite(data, years, seasons["OND"], start_year=start_year, mode=args.mode, clim=clim)
    diff = ondj - ond

    # Common symmetric scale for ONDJ/OND
    vals_ab = np.concatenate([np.abs(ondj[np.isfinite(ondj)]), np.abs(ond[np.isfinite(ond)])])
    vabs = nice(float(np.nanpercentile(vals_ab, float(args.prc))) if vals_ab.size else 1.0)
    lev_ab = np.linspace(-vabs, vabs, 21)

    # Diff scale
    vals_d = np.abs(diff[np.isfinite(diff)])
    vabs_d = nice(float(np.nanpercentile(vals_d, float(args.prc))) if vals_d.size else 1.0)
    lev_d = np.linspace(-vabs_d, vabs_d, 21)

    # Plot 1×3
    proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
    fig = plt.figure(figsize=(12.8, 4.2))
    gs = fig.add_gridspec(1, 3, left=0.05, right=0.995, top=0.92, bottom=0.20, wspace=0.08)
    axes = [fig.add_subplot(gs[0, i], **proj) for i in range(3)]
    titles = ["(a) ONDJ", "(b) OND", "(c) ONDJ − OND"]
    cmap = plt.get_cmap("RdBu_r")
    try:
        cmap = cmap.copy(); cmap.set_bad('lightgrey')
    except Exception:
        pass

    h0 = axes[0].contourf(lon2d, lat2d, ondj, levels=lev_ab, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
    h1 = axes[1].contourf(lon2d, lat2d, ond,  levels=lev_ab, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
    h2 = axes[2].contourf(lon2d, lat2d, diff, levels=lev_d,  cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
    for i, ax in enumerate(axes):
        if ccrs is not None:
            ax.set_extent([float(lon2d.min()), float(lon2d.max()), float(lat2d.min()), float(lat2d.max())], crs=ccrs.PlateCarree())
        add_map(ax, left=(i == 0), bottom=True)
        ax.set_title(titles[i], fontsize=11, loc="left")

    # Two colorbars: one for (a)(b), one for (c)
    pos = [ax.get_position() for ax in axes]
    x0 = min(p.x0 for p in pos); x1 = max(p.x1 for p in pos)
    y0 = max(0.06, min(p.y0 for p in pos) - 0.06)
    # Shared for (a)(b)
    cax_ab = fig.add_axes([pos[0].x0, y0, pos[1].x1 - pos[0].x0, 0.025])
    cb_ab = fig.colorbar(h0, cax=cax_ab, orientation='horizontal')
    cb_ab.set_label('MHW days' + (' (anomaly)' if args.mode == 'anomaly' else ''))
    # For diff
    cax_d = fig.add_axes([pos[2].x0, y0, pos[2].x1 - pos[2].x0, 0.025])
    cb_d = fig.colorbar(h2, cax=cax_d, orientation='horizontal')
    cb_d.set_label('MHW days (ONDJ − OND)')

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + '.tmp' + out.suffix)
    fig.savefig(tmp, dpi=args.dpi)
    plt.close(fig)
    tmp.replace(out)


if __name__ == "__main__":
    main()
