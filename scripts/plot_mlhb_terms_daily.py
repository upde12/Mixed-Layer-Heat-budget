#!/usr/bin/env python3
"""Plot MLHB daily terms for a selected day, with TEN and TOTAL side-by-side.

Reads a daily MLHB NetCDF (time × lat × lon) and renders a multi-panel figure
including:
  - TEN (K day^-1)
  - TOTAL = QNET + ADV + ENT + DIFF + DIFFV (K day^-1)
  - QNET, ADV, ENT, DIFF, DIFFV
  - (optional) CLOS_d2_ten if requested via --vars

By default, plots TEN,TOTAL,QNET,ADV,ENT,DIFF,DIFFV with a shared symmetric
color scale (abs percentile) for easy comparison.

Examples
  # Select by index (0-based; 1993-01-02 is typically index=1)
  python llm-ops/scripts/plot_mlhb_terms_daily.py \
    --file /Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily/1993/01/ml_budget_1993.nc \
    --time-index 1 \
    --out  /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/mlhb_terms_daily/mlhb_terms_19930102.png

  # Or select by date (YYYY-MM-DD)
  python llm-ops/scripts/plot_mlhb_terms_daily.py \
    --file /.../ml_budget_1993.nc --date 1993-01-02 --out /.../mlhb_terms_19930102.png
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence
import matplotlib as mpl

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt


DEFAULT_VARS = (
    "TEN",
    "TOTAL",
    "QNET",
    "ADV",
    "MIX",  # ENT+DIFF+DIFFV
    # "CLOS_d2_ten",  # include by adding to --vars if desired
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", required=True, help="Daily MLHB NetCDF (time×lat×lon)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--time-index", type=int, help="0-based time index to plot")
    g.add_argument("--date", help="YYYY-MM-DD date selector")
    p.add_argument("--out", required=True, help="Output PNG path")
    p.add_argument("--vars", default=",".join(DEFAULT_VARS), help="Comma-separated variables to plot (use 'TOTAL' to include the sum)")
    p.add_argument("--cmap", default="RdBu_r")
    p.add_argument("--vclip", type=float, default=None, help="Fixed abs max for symmetric scale (e.g., 1.5)")
    p.add_argument("--prc", type=float, default=98.0, help="Percentile for auto scale (sym abs from selected vars)")
    p.add_argument("--dpi", type=int, default=180)
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


def pick_time_index(ds: xr.Dataset, idx: int | None, date: str | None) -> int:
    if idx is not None:
        return int(idx)
    # select by date
    tt = ds["time"].values
    target = np.datetime64(date)
    # exact match if possible, else nearest
    try:
        pos = int(np.where(tt == target)[0][0])
    except Exception:
        # nearest by absolute difference
        pos = int(np.argmin(np.abs(tt - target)))
    return pos


def compute_total(day: xr.Dataset) -> xr.DataArray:
    required = ("QNET", "ADV", "ENT", "DIFF", "DIFFV")
    missing = [v for v in required if v not in day]
    if missing:
        raise KeyError(f"missing variables for TOTAL: {', '.join(missing)}")
    tot = day["QNET"] + day["ADV"] + day["ENT"] + day["DIFF"] + day["DIFFV"]
    tot.name = "TOTAL"
    tot.attrs["units"] = "K day-1"
    tot.attrs["long_name"] = "Sum of QNET+ADV+ENT+DIFF+DIFFV"
    return tot


def compute_mix(day: xr.Dataset) -> xr.DataArray:
    required = ("ENT", "DIFF", "DIFFV")
    missing = [v for v in required if v not in day]
    if missing:
        raise KeyError(f"missing variables for MIX: {', '.join(missing)}")
    mix = day["ENT"] + day["DIFF"] + day["DIFFV"]
    mix.name = "MIX"
    mix.attrs["units"] = "K day-1"
    mix.attrs["long_name"] = "ENT+DIFF+DIFFV"
    return mix


def compute_symmetric_scale(data: dict[str, np.ndarray], prc: float, vfix: float | None) -> float:
    if vfix is not None and vfix > 0:
        return float(vfix)
    vals = []
    for k, a in data.items():
        if a is None:
            continue
        aa = a[np.isfinite(a)]
        if aa.size:
            vals.append(np.nanpercentile(np.abs(aa), prc))
    vmax = float(np.nanmax(vals)) if vals else 1.0
    return max(1e-3, min(vmax, 10.0))


def main() -> int:
    args = parse_args()
    ds = xr.open_dataset(Path(args.file))
    ti = pick_time_index(ds, args.time_index, args.date)
    day = ds.isel(time=ti)

    # Optional regional subset (1D lat/lon assumed)
    if all(v is not None for v in (args.lat_min, args.lat_max, args.lon_min, args.lon_max)):
        try:
            day = day.sel(lat=slice(float(args.lat_min), float(args.lat_max)),
                          lon=slice(float(args.lon_min), float(args.lon_max)))
        except Exception:
            pass

    # Build plotting list and compute TOTAL if requested
    req_vars = [v.strip() for v in args.vars.split(",") if v.strip()]
    arrays: dict[str, np.ndarray] = {}
    for v in req_vars:
        if v.upper() == "TOTAL":
            arrays[v] = compute_total(day).values
        elif v.upper() == "MIX":
            arrays[v] = compute_mix(day).values
        else:
            if v not in day:
                arrays[v] = None
            else:
                arrays[v] = day[v].values

    lat = day["lat"].values
    lon = day["lon"].values
    X, Y = to_mesh(lat if lat.ndim == 2 else lat, lon if lon.ndim == 2 else lon)

    n = len(req_vars)
    ncols = min(4, n)
    nrows = int(np.ceil(n / ncols))

    vmax = compute_symmetric_scale({k: a for k, a in arrays.items() if a is not None}, args.prc, args.vclip)
    vmin, vmax = -vmax, vmax

    fig, axes = plt.subplots(nrows, ncols, figsize=(3.6 * ncols, 3.0 * nrows), constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()
    cm = None
    for i, v in enumerate(req_vars):
        ax = axes[i]
        A = arrays.get(v)
        if A is None:
            ax.axis("off")
            ax.set_title(f"{v} (missing)")
            continue
        try:
            cmap = mpl.cm.get_cmap(args.cmap).copy(); cmap.set_bad('lightgrey')
        except Exception:
            cmap = mpl.cm.get_cmap(args.cmap)
            try: cmap.set_bad('lightgrey')
            except Exception: pass
        h = ax.pcolormesh(X, Y, A, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest")
        ax.set_title(v)
        ax.set_xlabel("lon")
        ax.set_ylabel("lat")
        ax.set_aspect("equal", adjustable="box")
        if cm is None:
            cm = h
    for j in range(n, len(axes)):
        axes[j].axis("off")
    if cm is not None:
        cbar = fig.colorbar(cm, ax=axes.tolist(), fraction=0.03, pad=0.02)
        cbar.set_label("K day$^{-1}$")

    # Title with date if available
    try:
        tval = np.datetime_as_string(day["time"].values, unit="D")
        fig.suptitle(f"MLHB terms — {tval}", fontsize=10)
    except Exception:
        pass

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
