#!/usr/bin/env python3
"""Plot MLHB monthly terms as comparable panels.

Reads a monthly MLHB NetCDF (time=1) and renders a multi-panel figure of
selected terms with a shared symmetric color scale for easy comparison.

Defaults target the main budget terms in K day^-1: TEN, QNET, ADV, ENT, DIFF, DIFFV
plus the closure residual CLOS_d2_ten.

Example
  python llm-ops/scripts/plot_mlhb_terms_monthly.py \
    --file /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly_recompute_199301.nc \
    --out  /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/mlhb_terms/mlhb_terms_199301.png
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
    "QNET",
    "ADV",
    "MIX",  # ENT+DIFF+DIFFV
    "CLOS_d2_ten",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", required=True, help="Monthly MLHB NetCDF (time=1)")
    p.add_argument("--out", required=True, help="Output PNG path")
    p.add_argument("--vars", default=",".join(DEFAULT_VARS), help="Comma-separated variables to plot")
    p.add_argument("--cmap", default="RdBu_r")
    p.add_argument("--vclip", type=float, default=None, help="Fixed abs max for symmetric scale (e.g., 1.5)")
    p.add_argument("--prc", type=float, default=98.0, help="Percentile for auto scale (sym abs from selected vars)")
    p.add_argument("--dpi", type=int, default=180)
    return p.parse_args()


def to_2d(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if lat.ndim == 1 and lon.ndim == 1:
        X, Y = np.meshgrid(lon, lat)
        return X, Y
    return lon, lat


def compute_symmetric_scale(arrays: dict[str, np.ndarray], prc: float, fixed: float | None) -> float:
    if fixed is not None and fixed > 0:
        return float(fixed)
    vals = []
    for a in arrays.values():
        if a is None:
            continue
        aa = a[np.isfinite(a)]
        if aa.size:
            vals.append(np.nanpercentile(np.abs(aa), prc))
    vmax = float(np.nanmax(vals)) if vals else 1.0
    return max(1e-3, min(vmax, 10.0))


def main() -> int:
    args = parse_args()
    path = Path(args.file)
    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)

    ds = xr.open_dataset(path)
    # basic coords
    lat = ds["lat"].values
    lon = ds["lon"].values
    X, Y = to_2d(lat if lat.ndim == 2 else lat, lon if lon.ndim == 2 else lon)

    # variables to plot
    vars_ = [v.strip() for v in args.vars.split(",") if v.strip()]
    n = len(vars_)
    ncols = min(4, n)
    nrows = int(np.ceil(n / ncols))

    # prepare arrays (support derived 'MIX')
    arrays: dict[str, np.ndarray] = {}
    for v in vars_:
        if v.upper() == "MIX":
            missing = [k for k in ("ENT", "DIFF", "DIFFV") if k not in ds]
            arrays[v] = None if missing else (ds["ENT"].isel(time=0).values + ds["DIFF"].isel(time=0).values + ds["DIFFV"].isel(time=0).values)
        else:
            arrays[v] = None if v not in ds else ds[v].isel(time=0).values

    vmax = compute_symmetric_scale(arrays, args.prc, args.vclip)
    vmin, vmax = -vmax, vmax

    fig, axes = plt.subplots(nrows, ncols, figsize=(3.6 * ncols, 3.0 * nrows), constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()
    cm = None

    for i, v in enumerate(vars_):
        ax = axes[i]
        if v not in ds and v.upper() != "MIX":
            ax.axis("off")
            ax.set_title(f"{v} (missing)")
            continue
        if v.upper() == "MIX":
            a = arrays[v]
            if a is None:
                ax.axis("off"); ax.set_title(f"{v} (missing)"); continue
        else:
            a = ds[v].isel(time=0).values
        try:
            cmap = mpl.cm.get_cmap(args.cmap).copy(); cmap.set_bad('lightgrey')
        except Exception:
            cmap = mpl.cm.get_cmap(args.cmap)
            try: cmap.set_bad('lightgrey')
            except Exception: pass
        h = ax.pcolormesh(X, Y, a, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest")
        ax.set_title(v)
        ax.set_xlabel("lon")
        ax.set_ylabel("lat")
        ax.set_aspect("equal", adjustable="box")
        if cm is None:
            cm = h

    # turn off unused axes
    for j in range(n, len(axes)):
        axes[j].axis("off")

    if cm is not None:
        cbar = fig.colorbar(cm, ax=axes.tolist(), fraction=0.03, pad=0.02)
        cbar.set_label("K day$^{-1}$")

    # annotate policy if present
    pol = []
    for k in ("policy_shallow_included", "policy_deepnocross_included", "policy_inverse_included"):
        if k in ds.attrs:
            pol.append(f"{k.split('_')[1][0].upper()}={ds.attrs[k]}")
    if pol:
        fig.suptitle("Policy: " + ", ".join(pol), fontsize=10)

    tmp = outp.with_name(outp.stem + ".tmp" + outp.suffix)
    fig.savefig(tmp, dpi=args.dpi)
    plt.close(fig)
    tmp.replace(outp)
    print(f"wrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
