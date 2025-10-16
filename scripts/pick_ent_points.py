#!/usr/bin/env python3
"""Pick grid points with large positive entrainment (ENT>0).

Usage
  python llm-ops/scripts/pick_ent_points.py \
    --mlhb /path/to/ml_budget_YYYY.nc \
    --time-index 1 --min-mld 10 --topk 3

Prints two sections (BEST_HEAT and NEXT_HEAT) with lat,lon,value lines.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import xarray as xr


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mlhb", required=True, help="MLHB daily NetCDF (ml_budget_YYYY.nc)")
    p.add_argument("--time-index", type=int, default=0, help="Time index to use (default: 0)")
    p.add_argument("--min-mld", type=float, default=10.0, help="Minimum MLD to consider (m)")
    p.add_argument("--topk", type=int, default=3, help="Number of hottest ENT points to list")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ds = xr.open_dataset(args.mlhb)
    ent = ds["ENT"].isel(time=args.time_index)  # K/day
    mld = ds["MLD"].isel(time=args.time_index)
    mask = np.isfinite(ent) & np.isfinite(mld) & (mld >= args.min_mld) & (ent > 0)
    vals = ent.where(mask)
    arr = vals.values
    lat = ds["lat"].values
    lon = ds["lon"].values
    inds = np.argwhere(np.isfinite(arr))
    if inds.size == 0:
        print("no_valid_points")
        return 1
    items = [(i, j, float(arr[i, j])) for i, j in inds]
    items.sort(key=lambda t: t[2], reverse=True)
    k = min(args.topk, len(items))
    sel = items[:k]
    print("ENT_POS")
    for i, j, v in sel:
        print(f"{lat[i]:.4f},{lon[j]:.4f},{v:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

