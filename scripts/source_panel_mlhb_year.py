#!/usr/bin/env python3
"""ELT-year style MLHB panels from monthly NetCDF (annual anomalies).

Loads MLHB monthly outputs (time×lat×lon, units K day^-1) and renders a 3×2
panel for a target year. Each panel shows the annual-mean anomaly (year minus
multi-year mean) for:
 (a) QNET, (b) ADV+ENT+DIFF(+V), (c) ADV, (d) ENT, (e) DIFF, (f) DIFFV

Notes
- Uses the same layout/legend conventions as source_panel_mlhb.py with Cartopy
  map styling (coastlines, land outline, 5° grid, ° labels), if available.
- Advection optional 9-point smoothing (--adv-smooth-iter=N).
- DIFFV can be native from file or residual (=TEN-(QNET+ADV+ENT+DIFF)).
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
except Exception:
    ccrs = None
    cfeature = None


def to_mesh(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if lat.ndim == 1 and lon.ndim == 1:
        X, Y = np.meshgrid(lon, lat)
        return X, Y
    return lon, lat


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--monthly", required=True, help="Glob or file pointing to monthly MLHB NetCDFs (time×lat×lon)")
    p.add_argument("--year", type=int, required=True, help="Target year, e.g., 1998")
    p.add_argument("--out", required=True, help="Output PNG path")
    p.add_argument("--diffv-mode", choices=["native", "residual"], default="native")
    p.add_argument("--adv-smooth-iter", type=int, default=0)
    p.add_argument("--rhs-prc", type=float, default=98.0, help="Percentile for symmetric scale")
    p.add_argument("--unit", choices=["day","month"], default="day", help="Output unit for anomalies: K day^-1 or K month^-1")
    p.add_argument("--dpi", type=int, default=180)
    p.add_argument("--strict-cartopy", action="store_true", help="Fail if Cartopy is unavailable (report mode)")
    return p.parse_args(argv)


def _open_seq(glob_or_path: str) -> xr.Dataset:
    p = Path(glob_or_path)
    if any(ch in str(p) for ch in "*?["):
        files = sorted([str(x) for x in p.parent.glob(p.name)])
        if not files:
            raise SystemExit(f"No files matched: {p}")
        dsets = [xr.open_dataset(f) for f in files]
        try:
            ds = xr.concat(dsets, dim="time")
        finally:
            for d in dsets:
                try: d.close()
                except Exception: pass
        return ds
    if p.is_dir():
        files = sorted([str(x) for x in p.glob("*.nc")])
        if not files:
            raise SystemExit(f"No NetCDF in dir: {p}")
        dsets = [xr.open_dataset(f) for f in files]
        try:
            ds = xr.concat(dsets, dim="time")
        finally:
            for d in dsets:
                try: d.close()
                except Exception: pass
        return ds
    return xr.open_dataset(str(p))


def smth9_2d(data: np.ndarray, p: float = 0.50, q: float = 0.25) -> np.ndarray:
    ny, nx = data.shape
    centre = data
    def shift(a, di, dj):
        out = np.full_like(a, np.nan)
        # vertical shift di (>0 down)
        if di >= 0:
            src_i0, src_i1 = 0, ny - di
            dst_i0, dst_i1 = di, ny
        else:
            src_i0, src_i1 = -di, ny
            dst_i0, dst_i1 = 0, ny + di
        # horizontal shift dj (>0 right)
        if dj >= 0:
            src_j0, src_j1 = 0, nx - dj
            dst_j0, dst_j1 = dj, nx
        else:
            src_j0, src_j1 = -dj, nx
            dst_j0, dst_j1 = 0, nx + dj
        if src_i1 > src_i0 and src_j1 > src_j0:
            out[dst_i0:dst_i1, dst_j0:dst_j1] = a[src_i0:src_i1, src_j0:src_j1]
        return out
    north = shift(centre, -1, 0)
    south = shift(centre, 1, 0)
    west  = shift(centre, 0, -1)
    east  = shift(centre, 0, 1)
    nw = shift(north, 0, -1); ne = shift(north, 0, 1)
    sw = shift(south, 0, -1); se = shift(south, 0, 1)
    valid = np.isfinite(centre) & np.isfinite(north) & np.isfinite(south) & np.isfinite(east) & np.isfinite(west) & np.isfinite(nw) & np.isfinite(ne) & np.isfinite(sw) & np.isfinite(se)
    out = centre.copy()
    if np.any(valid):
        sides = west + east + north + south
        corners = nw + ne + sw + se
        out[valid] = centre[valid] + (p/4.0) * (sides[valid] - 4.0*centre[valid]) + (q/4.0) * (corners[valid] - 4.0*centre[valid])
    out[~np.isfinite(centre)] = np.nan
    return out


def maybe_smooth(da: xr.DataArray, iters: int) -> xr.DataArray:
    if iters <= 0: return da
    arr = da.values.copy()
    for _ in range(iters):
        arr = smth9_2d(arr)
    out = da.copy(data=arr)
    return out


def add_map(ax, left: bool, bottom: bool) -> None:
    if ccrs is None:
        if bottom: ax.set_xlabel("Longitude")
        if left: ax.set_ylabel("Latitude")
        return
    try:
        land50 = cfeature.NaturalEarthFeature("physical","land","50m", edgecolor="black", facecolor="lightgrey", linewidth=0.6)
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
        gl.top_labels=False; gl.right_labels=False; gl.left_labels=bool(left); gl.bottom_labels=bool(bottom)
    except Exception:
        gl.xlabels_top=False; gl.ylabels_right=False; gl.ylabels_left=bool(left); gl.xlabels_bottom=bool(bottom)
    gl.xlabel_style={"size":10,"rotation":0}; gl.ylabel_style={"size":10}


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    if args.strict_cartopy and (ccrs is None):
        raise SystemExit("Cartopy is required (--strict-cartopy) but not available. Install cartopy/shapely/pyproj.")
    ds = _open_seq(args.monthly)
    year = int(args.year)
    ds_year = ds.sel(time=slice(f"{year}-01-01", f"{year}-12-31"))
    if ds_year.dims.get("time", 0) == 0:
        raise SystemExit(f"No data for year {year} in {args.monthly}")
    annual = ds_year.mean(dim="time", skipna=True, keep_attrs=True)
    clim = ds.mean(dim="time", skipna=True, keep_attrs=True)

    def pick(d: xr.Dataset, name: str) -> xr.DataArray:
        for k in d.data_vars:
            if k.lower()==name.lower(): return d[k]
        aliases = {"diffv":["diffv","diff_v","vertical_diff"], "diff":["diff","diffh"], "t_ml":["t_ml","tml","tmean"]}
        keys = aliases.get(name.lower(), [name])
        for a in keys:
            for k in d.data_vars:
                if k.lower()==a: return d[k]
        raise KeyError(name)

    QNET = (pick(annual, "QNET") - pick(clim, "QNET"))
    ADV  = (pick(annual, "ADV")  - pick(clim, "ADV"))
    ENT  = (pick(annual, "ENT")  - pick(clim, "ENT"))
    DIFF = (pick(annual, "DIFF") - pick(clim, "DIFF"))
    if args.diffv_mode == "residual":
        TEN = (pick(annual, "TEN") - pick(clim, "TEN"))
        DIFFV = TEN - (QNET + ADV + ENT + DIFF)
    else:
        DIFFV = (pick(annual, "DIFFV") - pick(clim, "DIFFV"))

    # Optional adv smoothing
    ADV = maybe_smooth(ADV, args.adv_smooth_iter)

    # Unit scaling: files are K day^-1; for month scale multiply by ~30.44
    scale = 1.0 if args.unit == "day" else 30.4375
    QNET *= scale; ADV *= scale; ENT *= scale; DIFF *= scale; DIFFV *= scale
    SUBS = ADV + ENT + DIFF + DIFFV
    lat = (annual["lat"].values if "lat" in annual.coords else annual["latitude"].values)
    lon = (annual["lon"].values if "lon" in annual.coords else annual["longitude"].values)

    # Determine symmetric scale from percentile
    stack = np.concatenate([np.abs(QNET.values.ravel()), np.abs(SUBS.values.ravel()),
                            np.abs(ADV.values.ravel()),  np.abs(ENT.values.ravel()),
                            np.abs(DIFF.values.ravel()), np.abs(DIFFV.values.ravel())])
    stack = stack[np.isfinite(stack)]
    vabs = float(np.nanpercentile(stack, float(args.rhs_prc))) if stack.size else 1.0
    # snap to nice values
    def nice(v: float) -> float:
        if not np.isfinite(v) or v<=0: return 1.0
        mag = 10.0**np.floor(np.log10(v)); base=v/mag
        for s in [1,1.5,2,2.5,3,5,6,8,10]:
            if base<=s+1e-12: return s*mag
        return 10*mag
    vabs = nice(vabs)
    levels = np.linspace(-vabs, vabs, 17)

    # Plot
    proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
    fig = plt.figure(figsize=(8.6, 11.2))
    gs = fig.add_gridspec(3,2, left=0.08, right=0.985, top=0.97, bottom=0.18, wspace=0.10, hspace=0.12)
    axes = np.array([[fig.add_subplot(gs[r,c], **proj) for c in range(2)] for r in range(3)])
    titles = ["Surface Heat Flux (Qnet)", "ADV+ENT+DIFF(+V)", "Horizontal Advection", "Entrainment", "Lateral Diffusion", "Vertical Diffusion"]
    fields = [QNET, SUBS, ADV, ENT, DIFF, DIFFV]
    lon2d, lat2d = (np.meshgrid(lon, lat) if (lat.ndim==1 and lon.ndim==1) else (lon, lat))
    try:
        cmap = plt.get_cmap("RdBu_r").copy(); cmap.set_bad('lightgrey')
    except Exception:
        cmap = plt.get_cmap("RdBu_r")
        try: cmap.set_bad('lightgrey')
        except Exception: pass

    mappables = []
    for i,(ax,da,tt) in enumerate(zip(axes.ravel(), fields, titles)):
        h = ax.contourf(lon2d, lat2d, da.values, levels=levels, cmap=cmap, extend="both", transform=ccrs.PlateCarree() if ccrs is not None else None)
        if ccrs is not None:
            ax.set_extent([float(np.nanmin(lon2d)), float(np.nanmax(lon2d)), float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
        add_map(ax, left=(i%2==0), bottom=(i//2==2))
        ax.set_title(f"({chr(ord('a')+i)}) {tt}", loc="left", pad=6)
        mappables.append(h)

    # Colorbar
    poss = [ax.get_position() for ax in axes.ravel()]
    x0 = min(p.x0 for p in poss); x1 = max(p.x1 for p in poss)
    y0 = max(0.06, min(p.y0 for p in poss) - 0.08)
    cax = fig.add_axes([x0, y0, x1-x0, 0.025])
    cb = fig.colorbar(mappables[0], cax=cax, orientation="horizontal")
    cb.set_label("K month$^{-1}$" if args.unit=="month" else "K day$^{-1}$")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(args.out).with_name(Path(args.out).stem + ".tmp" + Path(args.out).suffix)
    fig.savefig(tmp, dpi=args.dpi)
    plt.close(fig)
    tmp.replace(Path(args.out))


if __name__ == "__main__":
    main()
