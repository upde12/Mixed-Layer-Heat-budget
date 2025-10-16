#!/usr/bin/env python3
"""Compute correlation map between TEN and TOTAL over a time window.

TOTAL = QNET + ADV + ENT + DIFF + DIFFV

Example
  python llm-ops/scripts/compute_corr_ten_total.py \
    --daily /Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily/1993/01/ml_budget_1993.nc \
    --start 1993-01-02 --end 1993-01-31 \
    --out-nc /Volumes/HJPARK4/Decadal/source/ML_budget/output/diagnostics/corr_ten_total_199301.nc \
    --out-png /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/corr/ten_total/corr_ten_total_199301.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--daily", required=True, help="Daily MLHB NetCDF (time×lat×lon)")
    p.add_argument("--start", required=True, help="Start date YYYY-MM-DD (inclusive)")
    p.add_argument("--end", required=True, help="End date YYYY-MM-DD (inclusive)")
    p.add_argument("--out-nc", required=True, help="Output NetCDF path for correlation map")
    p.add_argument("--out-png", required=True, help="Output PNG path for correlation map")
    p.add_argument("--dpi", type=int, default=180)
    p.add_argument("--cmap", default="RdBu_r", help="Colormap (default: RdBu_r; land masked light grey)")
    p.add_argument("--vmin", type=float, default=None, help="Color scale min (optional)")
    p.add_argument("--vmax", type=float, default=None, help="Color scale max (optional)")
    return p.parse_args()


def to_mesh(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if lat.ndim == 1 and lon.ndim == 1:
        X, Y = np.meshgrid(lon, lat)
        return X, Y
    return lon, lat


def main() -> int:
    args = parse_args()
    ds = xr.open_dataset(args.daily)
    # Select time window
    win = ds.sel(time=slice(args.start, args.end))
    # Build TOTAL
    TOTAL = win["QNET"] + win["ADV"] + win["ENT"] + win["DIFF"] + win["DIFFV"]
    TEN = win["TEN"]

    # Correlation along time with skipna
    # xr.corr aligns along the dim; for older versions, implement manually
    try:
        corr = xr.corr(TEN, TOTAL, dim="time")
    except Exception:
        # manual correlation
        t0 = TEN - TEN.mean(dim="time", skipna=True)
        t1 = TOTAL - TOTAL.mean(dim="time", skipna=True)
        num = (t0 * t1).sum(dim="time", skipna=True)
        den = np.sqrt((t0 ** 2).sum(dim="time", skipna=True) * (t1 ** 2).sum(dim="time", skipna=True))
        corr = num / den

    # Count of valid time pairs per grid
    valid = np.isfinite(TEN) & np.isfinite(TOTAL)
    n_valid = valid.sum(dim="time")

    # Output dataset
    out_nc = Path(args.out_nc)
    out_nc.parent.mkdir(parents=True, exist_ok=True)
    ds_out = xr.Dataset(
        {
            "corr_ten_total": corr,
            "n_valid": n_valid,
        },
        coords={"lat": ds["lat"], "lon": ds["lon"]},
        attrs={
            "source": "compute_corr_ten_total.py",
            "daily": str(Path(args.daily)),
            "start": args.start,
            "end": args.end,
        },
    )
    tmp = out_nc.with_suffix(out_nc.suffix + ".tmp")
    ds_out.to_netcdf(tmp)
    tmp.replace(out_nc)

    # Plot
    lat = ds_out["lat"].values
    lon = ds_out["lon"].values
    X, Y = to_mesh(lat if lat.ndim == 2 else lat, lon if lon.ndim == 2 else lon)
    fig, ax = plt.subplots(figsize=(8, 4.5), constrained_layout=True)
    vmin = -1.0 if args.vmin is None else float(args.vmin)
    vmax = 1.0 if args.vmax is None else float(args.vmax)
    import matplotlib as mpl
    try:
        cmap = mpl.cm.get_cmap(args.cmap).copy(); cmap.set_bad('lightgrey')
    except Exception:
        cmap = mpl.cm.get_cmap(args.cmap)
        try: cmap.set_bad('lightgrey')
        except Exception: pass
    h = ax.pcolormesh(X, Y, ds_out["corr_ten_total"].values, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest")
    rng = f" [{vmin},{vmax}]" if (args.vmin is not None or args.vmax is not None) else ""
    ax.set_title(f"corr(TEN, TOTAL) over {args.start}..{args.end}{rng}")
    ax.set_xlabel("lon"); ax.set_ylabel("lat"); ax.set_aspect("equal", adjustable="box")
    cb = fig.colorbar(h, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("correlation")
    out_png = Path(args.out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    tmp_png = out_png.with_name(out_png.stem + ".tmp" + out_png.suffix)
    fig.savefig(tmp_png, dpi=args.dpi)
    plt.close(fig)
    tmp_png.replace(out_png)
    print(f"wrote {out_nc}\nwrote {out_png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
