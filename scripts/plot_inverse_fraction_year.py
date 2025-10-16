#!/usr/bin/env python3
"""Render a 12-panel map of monthly inverse-fraction (Δσ0 below 10 m < 0).

It expects monthly diagnostics produced by compute_mld_fallback_stats.py,
which contain variables: inverse_fraction, valid_days, lat, lon.

Example
  python llm-ops/scripts/plot_inverse_fraction_year.py \
    --year 1993 \
    --diag-root /Volumes/HJPARK4/Decadal/source/ML_budget/output/diagnostics \
    --out /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/inverse_fraction/1993_inverse_fraction_12panel.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--diag-root", default="/Volumes/HJPARK4/Decadal/source/ML_budget/output/diagnostics")
    p.add_argument("--out", required=True)
    p.add_argument("--cmap", default="viridis")
    p.add_argument("--vmax", type=float, default=None, help="Max for color scale; if unset, determined from data")
    return p.parse_args()


def open_month(diag_root: Path, year: int, month: int) -> xr.Dataset | None:
    f = diag_root / f"mld_masks_{year}{month:02d}.nc"
    if not f.exists():
        return None
    return xr.open_dataset(f)


def main() -> int:
    args = parse_args()
    root = Path(args.diag_root)
    months = list(range(1, 13))

    datasets: list[xr.Dataset | None] = [open_month(root, args.year, m) for m in months]
    if all(ds is None for ds in datasets):
        print("no_months_found")
        return 1

    # Determine vmin/vmax from available data if needed
    vmax = args.vmax
    if vmax is None:
        vmax = 0.0
        for ds in datasets:
            if ds is None:
                continue
            inv = ds.get("inverse_fraction")
            vd = ds.get("valid_days")
            if inv is None or vd is None:
                continue
            data = inv.where(vd > 0)
            m = float(data.max().values)
            if np.isfinite(m):
                vmax = max(vmax, m)
        # sensible cap to avoid single-pixel outliers dominating
        vmax = float(min(max(vmax, 0.05), 0.5))

    # Prepare figure
    fig, axes = plt.subplots(3, 4, figsize=(12, 8), constrained_layout=True)
    axes = axes.ravel()

    common = None
    for i, (m, ax) in enumerate(zip(months, axes)):
        ds = datasets[i]
        ax.set_title(f"{args.year}-{m:02d}")
        if ds is None:
            ax.axis('off')
            continue
        lat = ds["lat"].values
        lon = ds["lon"].values
        inv = ds["inverse_fraction"].values
        vd = ds["valid_days"].values
        data = np.where(vd > 0, inv, np.nan)
        if lat.ndim == 1 and lon.ndim == 1:
            X, Y = np.meshgrid(lon, lat)
            h = ax.pcolormesh(X, Y, data, cmap=args.cmap, vmin=0.0, vmax=vmax, shading="nearest")
        else:
            h = ax.pcolormesh(lon, lat, data, cmap=args.cmap, vmin=0.0, vmax=vmax, shading="nearest")
        ax.set_xlabel("lon")
        ax.set_ylabel("lat")
        ax.set_aspect("equal", adjustable="box")
        if common is None:
            common = h

    # single colorbar
    if common is not None:
        cbar = fig.colorbar(common, ax=axes, fraction=0.03, pad=0.02)
        cbar.set_label("inverse fraction (per grid)")

    outp = Path(args.out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    tmp = outp.with_name(outp.stem + ".tmp" + outp.suffix)
    fig.savefig(tmp, dpi=180)
    Path(tmp).replace(outp)
    print(f"wrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
