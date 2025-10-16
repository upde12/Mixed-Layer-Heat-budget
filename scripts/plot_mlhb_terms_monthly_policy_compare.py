#!/usr/bin/env python3
"""Compare MLHB monthly terms with policy toggle (e.g., I=0 vs I=1).

Reads two monthly NetCDF files (time=1) and renders a panel with either:
 - wide (default): 2 × N, top=row0 (file0), bottom=row1 (file1)
 - tall: N × 2, left=file0, right=file1

Variables are plotted with a shared symmetric color scale computed across both
files and all requested variables. Supports derived variables:
 - MIX = ENT + DIFF + DIFFV
 - TOTAL = QNET + ADV + ENT + DIFF + DIFFV

Example
  python llm-ops/scripts/plot_mlhb_terms_monthly_policy_compare.py \
    --file0 /path/to/monthly_S1D1I0.nc \
    --file1 /path/to/monthly_S1D1I1.nc \
    --out   /path/to/fig.png \
    --vars TEN,TOTAL,QNET,ADV,MIX,CLOS_d2_ten --layout wide
"""
from __future__ import annotations

import argparse
from pathlib import Path
import matplotlib as mpl
from typing import Sequence

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt


DEFAULT_VARS = ("TEN", "TOTAL", "QNET", "ADV", "MIX", "CLOS_d2_ten")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file0", required=True, help="Monthly NetCDF for policy A (time=1)")
    p.add_argument("--file1", required=True, help="Monthly NetCDF for policy B (time=1)")
    p.add_argument("--out", required=True, help="Output PNG path")
    p.add_argument("--vars", default=",".join(DEFAULT_VARS), help="Comma-separated variables to plot (supports MIX,TOTAL)")
    p.add_argument("--cmap", default="RdBu_r")
    p.add_argument("--vclip", type=float, default=None, help="Fixed abs max for symmetric scale (overrides percentile)")
    p.add_argument("--prc", type=float, default=98.0, help="Percentile for symmetric scale if --vclip is unset")
    p.add_argument("--dpi", type=int, default=170)
    p.add_argument("--layout", choices=["wide", "tall"], default="wide")
    # optional regional subset (assumes 1D lat/lon)
    p.add_argument("--lat-min", type=float)
    p.add_argument("--lat-max", type=float)
    p.add_argument("--lon-min", type=float)
    p.add_argument("--lon-max", type=float)
    return p.parse_args()


def to_mesh(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if lat.ndim == 1 and lon.ndim == 1:
        X, Y = np.meshgrid(lon, lat)
        return X, Y
    return lon, lat


def get_var(ds: xr.Dataset, name: str) -> np.ndarray | None:
    if name.upper() == "MIX":
        if all(v in ds for v in ("ENT", "DIFF", "DIFFV")):
            return (ds["ENT"].isel(time=0).values + ds["DIFF"].isel(time=0).values + ds["DIFFV"].isel(time=0).values)
        return None
    if name.upper() == "TOTAL":
        req = ("QNET", "ADV", "ENT", "DIFF", "DIFFV")
        if all(v in ds for v in req):
            a = 0.0
            for v in req:
                a = a + ds[v].isel(time=0).values
            return a
        return None
    return None if name not in ds else ds[name].isel(time=0).values


def compute_symmetric_scale(arrs: list[np.ndarray], prc: float, vclip: float | None) -> float:
    if vclip is not None and vclip > 0:
        return float(vclip)
    vals = []
    for a in arrs:
        if a is None:
            continue
        aa = a[np.isfinite(a)]
        if aa.size:
            vals.append(np.nanpercentile(np.abs(aa), prc))
    vmax = float(np.nanmax(vals)) if vals else 1.0
    return max(1e-3, min(vmax, 10.0))


def subset(ds: xr.Dataset, args: argparse.Namespace) -> xr.Dataset:
    if all(v is not None for v in (args.lat_min, args.lat_max, args.lon_min, args.lon_max)):
        try:
            return ds.sel(lat=slice(float(args.lat_min), float(args.lat_max)),
                          lon=slice(float(args.lon_min), float(args.lon_max)))
        except Exception:
            return ds
    return ds


def main() -> int:
    args = parse_args()
    ds0 = subset(xr.open_dataset(Path(args.file0)), args)
    ds1 = subset(xr.open_dataset(Path(args.file1)), args)

    lat = (ds0["lat"].values if "lat" in ds0 else ds1["lat"].values)
    lon = (ds0["lon"].values if "lon" in ds0 else ds1["lon"].values)
    X, Y = to_mesh(lat if lat.ndim == 2 else lat, lon if lon.ndim == 2 else lon)

    vars_ = [v.strip() for v in args.vars.split(",") if v.strip()]
    # collect arrays and scale
    arr0, arr1 = {}, {}
    pool: list[np.ndarray] = []
    for v in vars_:
        a0 = get_var(ds0, v)
        a1 = get_var(ds1, v)
        arr0[v], arr1[v] = a0, a1
        if a0 is not None:
            pool.append(a0)
        if a1 is not None:
            pool.append(a1)
    vmax = compute_symmetric_scale(pool, args.prc, args.vclip)
    vmin, vmax = -vmax, vmax

    n = len(vars_)
    if args.layout == "wide":
        fig, axes = plt.subplots(2, n, figsize=(3.2 * n, 6.0), constrained_layout=True)
    else:
        fig, axes = plt.subplots(n, 2, figsize=(8.4, 2.6 * n), constrained_layout=True)
    cm = None
    for i, v in enumerate(vars_):
        if args.layout == "wide":
            ax0, ax1 = axes[0, i], axes[1, i]
        else:
            ax0, ax1 = axes[i, 0], axes[i, 1]
        try:
            cmap = mpl.cm.get_cmap(args.cmap).copy(); cmap.set_bad('lightgrey')
        except Exception:
            cmap = mpl.cm.get_cmap(args.cmap)
            try: cmap.set_bad('lightgrey')
            except Exception: pass
        for ax, a in ((ax0, arr0.get(v)), (ax1, arr1.get(v))):
            if a is None:
                ax.axis('off'); ax.set_title(f"{v} (missing)")
                continue
            h = ax.pcolormesh(X, Y, a, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest")
            ax.set_xlabel("lon"); ax.set_ylabel("lat"); ax.set_aspect("equal", adjustable="box")
            if cm is None:
                cm = h
        if args.layout == "wide":
            axes[0, i].set_title(v)
            axes[1, i].set_title(v)
        else:
            axes[i, 0].set_ylabel(v)
            axes[i, 0].set_title("file0")
            axes[i, 1].set_title("file1")

    if cm is not None:
        cbar = fig.colorbar(cm, ax=axes.ravel().tolist(), fraction=0.02, pad=0.02)
        cbar.set_label("K day$^{-1}$")

    # annotate time if available
    try:
        t0 = np.datetime_as_string(ds0["time"].values[0], unit="D")
        t1 = np.datetime_as_string(ds1["time"].values[0], unit="D")
        title = f"Monthly MLHB terms — {t0} vs {t1}"
    except Exception:
        title = "Monthly MLHB terms"
    fig.suptitle(title, fontsize=11)

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    tmp = outp.with_name(outp.stem + ".tmp" + outp.suffix)
    fig.savefig(tmp, dpi=args.dpi)
    plt.close(fig)
    tmp.replace(outp)
    print(f"wrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
