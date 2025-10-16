#!/usr/bin/env python3
"""Compare daily MLHB terms with policy I toggled (S=1, D=1 fixed).

For a selected day from a daily MLHB NetCDF (time×lat×lon), renders a panel with
two columns:
  - Left: I=0 (exclude INVERSE_GE10), S=1, D=1
  - Right: I=1 (include INVERSE_GE10), S=1, D=1

Rows correspond to variables (default: TEN, TOTAL, QNET, ADV, ENT, DIFF, DIFFV).
Each subplot shares a single symmetric color scale computed from both columns.

Example
  python llm-ops/scripts/plot_mlhb_terms_daily_policy_compare.py \
    --file /Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily/1993/01/ml_budget_1993.nc \
    --date 1993-01-02 \
    --out  /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/mlhb_terms_daily/mlhb_terms_compare_I_19930102.png
"""
from __future__ import annotations

import argparse
from pathlib import Path
import matplotlib as mpl
from typing import Sequence

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt


DEFAULT_VARS = ("TEN", "TOTAL", "QNET", "ADV", "MIX")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", required=True, help="Daily MLHB NetCDF (time×lat×lon)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--time-index", type=int)
    g.add_argument("--date")
    p.add_argument("--out", required=True, help="Output PNG path")
    p.add_argument("--vars", default=",".join(DEFAULT_VARS), help="Comma-separated variables to plot (use 'TOTAL' to include the sum)")
    p.add_argument("--cmap", default="RdBu_r")
    p.add_argument("--prc", type=float, default=98.0, help="Percentile for symmetric scale from both columns")
    p.add_argument("--vclip", type=float, default=None, help="Fixed abs max for symmetric scale (overrides --prc)")
    p.add_argument("--dpi", type=int, default=170)
    p.add_argument("--layout", choices=["tall", "wide"], default="tall", help="Panel layout: tall=n×2, wide=2×n")
    # optional regional subset (1D lat/lon assumed)
    p.add_argument("--lat-min", type=float)
    p.add_argument("--lat-max", type=float)
    p.add_argument("--lon-min", type=float)
    p.add_argument("--lon-max", type=float)
    p.add_argument("--mask-shallow", action="store_true", help="Exclude SHALLOW_LT10 pixels (MASK_SHALLOW_LT10==1)")
    return p.parse_args()


def pick_time_index(ds: xr.Dataset, idx: int | None, date: str | None) -> int:
    if idx is not None:
        return int(idx)
    tt = ds["time"].values
    target = np.datetime64(date)
    try:
        pos = int(np.where(tt == target)[0][0])
    except Exception:
        pos = int(np.argmin(np.abs(tt - target)))
    return pos


def base_allowed(day: xr.Dataset) -> xr.DataArray:
    # S=1 and D=1 (include shallow and deep-no-cross): allowed everywhere by default
    return xr.ones_like(day["MLD"], dtype=bool)


def allowed_I(day: xr.Dataset, include_inverse: bool) -> xr.DataArray:
    allow = base_allowed(day)
    if "MASK_INVERSE_GE10" in day and not include_inverse:
        allow = allow & (~day["MASK_INVERSE_GE10"].astype(bool))
    return allow


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


def to_mesh(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if lat.ndim == 1 and lon.ndim == 1:
        X, Y = np.meshgrid(lon, lat)
        return X, Y
    return lon, lat


def compute_global_scale(values: list[np.ndarray], prc: float, vclip: float | None) -> float:
    if vclip is not None and vclip > 0:
        return float(vclip)
    arr = []
    for v in values:
        if v is None:
            continue
        a = v[np.isfinite(v)]
        if a.size:
            arr.append(np.nanpercentile(np.abs(a), prc))
    vmax = float(np.nanmax(arr)) if arr else 1.0
    return max(1e-3, min(vmax, 10.0))


def main() -> int:
    args = parse_args()
    ds = xr.open_dataset(Path(args.file))
    ti = pick_time_index(ds, args.time_index, args.date)
    day = ds.isel(time=ti)
    # regional subset if bounds provided
    if all(v is not None for v in (args.lat_min, args.lat_max, args.lon_min, args.lon_max)):
        try:
            day = day.sel(lat=slice(float(args.lat_min), float(args.lat_max)),
                          lon=slice(float(args.lon_min), float(args.lon_max)))
        except Exception:
            pass

    # Dataset must contain inverse mask
    if "MASK_INVERSE_GE10" not in day:
        raise SystemExit("daily dataset missing MASK_INVERSE_GE10; rerun process_d2nf.py with mask support")

    vars_ = [v.strip() for v in args.vars.split(",") if v.strip()]
    allow0 = allowed_I(day, include_inverse=False)
    allow1 = allowed_I(day, include_inverse=True)
    if args.mask_shallow and "MASK_SHALLOW_LT10" in day:
        sh = day["MASK_SHALLOW_LT10"].astype(bool)
        allow0 = allow0 & (~sh)
        allow1 = allow1 & (~sh)

    arrays0, arrays1 = {}, {}
    for v in vars_:
        if v.upper() == "TOTAL":
            a = compute_total(day)
            arrays0[v] = a.where(allow0).values
            arrays1[v] = a.where(allow1).values
        elif v.upper() == "MIX":
            a = compute_mix(day)
            arrays0[v] = a.where(allow0).values
            arrays1[v] = a.where(allow1).values
        else:
            if v not in day:
                arrays0[v] = None
                arrays1[v] = None
            else:
                arrays0[v] = day[v].where(allow0).values
                arrays1[v] = day[v].where(allow1).values

    lat = day["lat"].values
    lon = day["lon"].values
    X, Y = to_mesh(lat if lat.ndim == 2 else lat, lon if lon.ndim == 2 else lon)

    # global symmetric color scale across both columns and all vars
    vmax = compute_global_scale(list(arrays0.values()) + list(arrays1.values()), args.prc, args.vclip)
    vmin, vmax = -vmax, vmax

    n = len(vars_)
    if args.layout == "wide":
        fig, axes = plt.subplots(2, n, figsize=(3.2 * n, 6.0), constrained_layout=True)
        if n == 1:
            axes = np.array([[axes[0]], [axes[1]]])
    else:
        fig, axes = plt.subplots(n, 2, figsize=(8.4, 2.6 * n), constrained_layout=True)
        if n == 1:
            axes = np.array([[axes[0], axes[1]]]) if isinstance(axes, np.ndarray) else np.array([[axes]])
    cm = None
    for i, v in enumerate(vars_):
        A0 = arrays0.get(v)
        A1 = arrays1.get(v)
        if args.layout == "wide":
            ax0 = axes[0, i]
            ax1 = axes[1, i]
        else:
            ax0 = axes[i, 0]
            ax1 = axes[i, 1]
        if A0 is None or A1 is None:
            ax0.axis("off"); ax1.axis("off")
            ax0.set_title(f"{v} (missing)"); ax1.set_title(f"{v} (missing)")
            continue
        try:
            cmap = mpl.cm.get_cmap(args.cmap).copy(); cmap.set_bad('lightgrey')
        except Exception:
            cmap = mpl.cm.get_cmap(args.cmap)
            try: cmap.set_bad('lightgrey')
            except Exception: pass
        h0 = ax0.pcolormesh(X, Y, A0, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest")
        h1 = ax1.pcolormesh(X, Y, A1, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest")
        if args.layout == "wide":
            ax0.set_title(v)
            ax1.set_title(v)
        else:
            ax0.set_ylabel(v)
            ax0.set_title("I=0 (exclude)")
            ax1.set_title("I=1 (include)")
        for ax in (ax0, ax1):
            ax.set_xlabel("lon"); ax.set_aspect("equal", adjustable="box")
        if cm is None:
            cm = h1

    if cm is not None:
        cbar = fig.colorbar(cm, ax=axes.ravel().tolist(), fraction=0.02, pad=0.02)
        cbar.set_label("K day$^{-1}$")

    # Title with date
    try:
        tval = np.datetime_as_string(day["time"].values, unit="D")
        if args.layout == "wide":
            fig.suptitle(f"MLHB terms (I=0 top, I=1 bottom; S=1,D=1) — {tval}", fontsize=11)
        else:
            fig.suptitle(f"MLHB terms (S=1, D=1) — {tval}", fontsize=11)
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
