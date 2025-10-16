#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import xarray as xr


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Pick best/worst closure points for a given day")
    p.add_argument("--mlhb", required=True, help="MLHB daily NetCDF (ml_budget_YYYY.nc)")
    p.add_argument("--time-index", type=int, default=0, help="Time index to use (default: 0)")
    p.add_argument("--min-mld", type=float, default=0.0, help="Minimum MLD to consider (m)")
    p.add_argument("--max-mld", type=float, default=None, help="Maximum MLD to consider (m); if unset, no upper limit")
    p.add_argument("--topk", type=int, default=3, help="Number of points to report for best/worst")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    ds = xr.open_dataset(args.mlhb)
    clos = ds["CLOS_d2_ten"].isel(time=args.time_index)
    mld = ds["MLD"].isel(time=args.time_index)
    mask = np.isfinite(clos) & np.isfinite(mld) & (mld >= args.min_mld)
    if args.max_mld is not None:
        mask = mask & (mld <= args.max_mld)
    vals = abs(clos.where(mask))
    arr = vals.values
    lat = ds["lat"].values
    lon = ds["lon"].values
    inds = np.argwhere(np.isfinite(arr))
    if inds.size == 0:
        print("no_valid_points")
        return 1
    items = [(i, j, float(arr[i, j])) for i, j in inds]
    items.sort(key=lambda t: t[2])
    k = min(args.topk, len(items))
    best = items[:k]
    worst = sorted(items[-k:], key=lambda t: t[2], reverse=True)
    print("BEST")
    for i, j, v in best:
        print(f"{lat[i]:.4f},{lon[j]:.4f},{v:.6f}")
    print("WORST")
    for i, j, v in worst:
        print(f"{lat[i]:.4f},{lon[j]:.4f},{v:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
