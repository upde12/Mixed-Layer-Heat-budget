#!/usr/bin/env python3
"""Seasonal composite of MHW Days (duration) for selected ELT years.

Reads monthly MHW duration from a raw float32 file (time×lat×lon) on the ECS
grid (101×145; lat 19.875–44.875, lon 109.375–145.375). Supports seasons:
 - ONDJ = Oct(prev), Nov(prev), Dec(prev), Jan(curr)
 - MJJAS = May..Sep (curr)

Outputs one PNG per season.
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
    p.add_argument("--seasons", default="ONDJ,MJJAS", help="Comma-separated seasons to render (ONDJ,MJJAS)")
    p.add_argument("--clim-start", type=int, default=1993, help="Climatology start year")
    p.add_argument("--clim-end", type=int, default=2021, help="Climatology end year")
    p.add_argument("--mode", choices=["anomaly","absolute"], default="anomaly", help="Plot anomaly or absolute days")
    p.add_argument("--prc", type=float, default=98.0, help="Percentile for color scale (symmetric for anomaly; upper for absolute)")
    p.add_argument("--cmap", default=None, help="Colormap override (default: RdBu_r for anomaly, YlOrRd for absolute)")
    p.add_argument("--out-root", default="/Volumes/HJPARK4/Decadal/Figure/elt_composite", help="Output directory")
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


def seasons_def() -> Dict[str, List[Tuple[int, bool]]]:
    # Note: ONDJ is previous-year Oct–Dec plus current-year Jan.
    # ONDJ_NEXT is current-year Oct–Dec plus next-year Jan (for comparison).
    return {
        "ONDJ": [(10, True), (11, True), (12, True), (1, False)],
        "ONDJ_NEXT": [(10, False), (11, False), (12, False), (1, False)],
        "MJJAS": [(5, False), (6, False), (7, False), (8, False), (9, False)],
    }


def nice(v: float) -> float:
    if not np.isfinite(v) or v <= 0:
        return 1.0
    mag = 10.0 ** np.floor(np.log10(v))
    base = v / mag
    for s in [1,1.5,2,2.5,3,5,6,8,10]:
        if base <= s + 1e-12:
            return s * mag
    return 10.0 * mag


def add_map(ax, left: bool, bottom: bool) -> None:
    if ccrs is None:
        if bottom: ax.set_xlabel("Longitude")
        if left:   ax.set_ylabel("Latitude")
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


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    years = [int(s) for s in args.years.split(',') if s.strip()]
    seas_list = [s.strip().upper() for s in args.seasons.split(',') if s.strip()]
    seas_map = seasons_def()

    dur = load_monthly(Path(args.dur_file))  # T×101×145
    if dur.shape[0] % 12 != 0:
        raise SystemExit("Time length must be years×12")
    n_years = dur.shape[0] // 12
    data = dur.reshape(n_years, 12, 101, 145)

    # Year axis mapping using provided last year
    last_year = int(args.last_year)
    start_year = last_year - (n_years - 1)
    year_axis = np.arange(start_year, start_year + n_years)

    # Climatology baseline
    mask_clim = (year_axis >= args.clim_start) & (year_axis <= args.clim_end)
    if not np.any(mask_clim):
        raise SystemExit(f"No years within climatology window {args.clim_start}-{args.clim_end}")
    clim = np.nanmean(data[mask_clim, ...], axis=0)  # 12×101×145

    # Coordinates
    lat = np.linspace(19.875, 44.875, 101)
    lon = np.linspace(109.375, 145.375, 145)
    lon2d, lat2d = np.meshgrid(lon, lat)

    comps: Dict[str, np.ndarray] = {}
    for sname in seas_list:
        if sname not in seas_map:
            print(f"Skip unknown season {sname}")
            continue
        months = seas_map[sname]
        # Collect season slices across ELT years
        acc = []
        for y in years:
            yi = y - start_year
            for m, prev in months:
                # Year selection: prev -> y-1; for ONDJ_NEXT Jan uses next year
                if prev:
                    ysel = yi - 1
                else:
                    if sname == 'ONDJ_NEXT' and m == 1:
                        ysel = yi + 1
                    else:
                        ysel = yi
                if ysel < 0 or ysel >= n_years:
                    continue
                mi = m - 1
                if args.mode == 'anomaly':
                    acc.append(data[ysel, mi, ...] - clim[mi, ...])
                else:
                    acc.append(data[ysel, mi, ...])
        if not acc:
            print(f"No samples for {sname}")
            continue
        comp = np.nanmean(np.stack(acc, axis=0), axis=0)  # 101×145

        # Cache for potential diff later
        comps[sname] = comp

        # Levels & cmap
        if args.mode == 'anomaly':
            vals = np.abs(comp[np.isfinite(comp)])
            vabs = nice(float(np.nanpercentile(vals, float(args.prc))) if vals.size else 1.0)
            levels = np.linspace(-vabs, vabs, 21)
            default_cmap = 'RdBu_r'
            cbar_label = 'MHW days (anomaly)'
        else:
            vals = comp[np.isfinite(comp)]
            vmax = float(np.nanpercentile(vals, float(args.prc))) if vals.size else 20.0
            if vmax <= 0:
                vmax = 1.0
            levels = np.linspace(0.0, vmax, 17)
            default_cmap = 'YlOrRd'
            cbar_label = 'MHW days'
        cmap = plt.get_cmap(args.cmap or default_cmap)
        try:
            cmap = cmap.copy(); cmap.set_bad('lightgrey')
        except Exception:
            pass

        proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
        fig = plt.figure(figsize=(5.6, 4.2))
        ax = fig.add_subplot(1,1,1, **proj)
        h = ax.contourf(lon2d, lat2d, comp, levels=levels, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
        if ccrs is not None:
            ax.set_extent([float(np.nanmin(lon2d)), float(np.nanmax(lon2d)), float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
        add_map(ax, left=True, bottom=True)
        cax = fig.add_axes([0.12, 0.08, 0.78, 0.045])
        cb = fig.colorbar(h, cax=cax, orientation='horizontal'); cb.set_label(cbar_label)
        out = Path(args.out_root) / f"elt_comp_MHW_DAYS_{sname}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.stem + '.tmp' + out.suffix)
        fig.savefig(tmp, dpi=args.dpi)
        plt.close(fig)
        tmp.replace(out)

    # Optional: if both ONDJ and ONDJ_NEXT requested, write a diff map
    if 'ONDJ' in comps and 'ONDJ_NEXT' in comps:
        diff = comps['ONDJ'] - comps['ONDJ_NEXT']
        vals = np.abs(diff[np.isfinite(diff)])
        vabs = nice(float(np.nanpercentile(vals, float(args.prc))) if vals.size else 1.0)
        levels = np.linspace(-vabs, vabs, 21)
        cmap = plt.get_cmap(args.cmap or 'RdBu_r')
        try:
            cmap = cmap.copy(); cmap.set_bad('lightgrey')
        except Exception:
            pass
        proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
        fig = plt.figure(figsize=(5.6, 4.2))
        ax = fig.add_subplot(1,1,1, **proj)
        h = ax.contourf(lon2d, lat2d, diff, levels=levels, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
        if ccrs is not None:
            ax.set_extent([float(np.nanmin(lon2d)), float(np.nanmax(lon2d)), float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
        add_map(ax, left=True, bottom=True)
        cax = fig.add_axes([0.12, 0.08, 0.78, 0.045])
        cb = fig.colorbar(h, cax=cax, orientation='horizontal'); cb.set_label('MHW days (ONDJ − ONDJ_NEXT)')
        out = Path(args.out_root) / "elt_comp_MHW_DAYS_ONDJ_DIFF.png"
        tmp = out.with_name(out.stem + '.tmp' + out.suffix)
        fig.savefig(tmp, dpi=args.dpi)
        plt.close(fig)
        tmp.replace(out)


if __name__ == "__main__":
    main()
