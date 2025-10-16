#!/usr/bin/env python3
"""Plot daily fallback masks (1=fallback, 0=else) for a given month.

Computes Δσ0(10 m) threshold crossings from GLORYS daily files using
TEOS‑10 (SA, CT) and saves one PNG per day showing fallback columns
(never reach threshold before bottom) as value 1 and others 0.

Example
  python llm-ops/scripts/plot_mld_fallback_daily_maps.py \
    --month 1993-01 \
    --indir /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
    --outdir /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/mld_fallback_maps/1993-01
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm

# reuse helpers by importing functions from the stats script
import glob
import gsw

def list_glorys_daily(indir: str, month: str) -> list[str]:
    pattern = os.path.join(indir, f"GLO_PHY_MY_{month.replace('-', '')[:6]}*.nc")
    files = sorted(glob.glob(pattern))
    out = []
    for f in files:
        base = os.path.basename(f)
        try:
            ymd = base.split("_")[3]
            y, m = int(ymd[:4]), int(ymd[4:6])
            if f"{y:04d}-{m:02d}" == month:
                out.append(f)
        except Exception:
            continue
    return out

def to_2d(lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if lat.ndim == 1 and lon.ndim == 1:
        return (np.repeat(lat[:, None], lon.size, axis=1),
                np.repeat(lon[None, :], lat.size, axis=0))
    if lat.ndim == 2 and lon.ndim == 2:
        return lat, lon
    lat2 = np.broadcast_to(lat, (lat.shape[0], lon.shape[-1]))
    lon2 = np.broadcast_to(lon, lat2.shape)
    return lat2, lon2

def compute_mld_sigma0_field(theta: np.ndarray, salinity: np.ndarray, depth: np.ndarray,
                              lat_grid: np.ndarray, lon_grid: np.ndarray,
                              *, threshold: float, ref_depth: float) -> tuple[np.ndarray, np.ndarray]:
    theta = theta.astype(np.float64, copy=False)
    salinity = salinity.astype(np.float64, copy=False)
    depth = depth.astype(np.float64, copy=False)
    Nz, Ny, Nx = theta.shape
    depth_3d = depth[:, None, None]
    lat3 = lat_grid[None, :, :].astype(np.float64, copy=False)
    lon3 = lon_grid[None, :, :].astype(np.float64, copy=False)

    pressure = gsw.p_from_z(-depth_3d, lat3)
    SA = gsw.SA_from_SP(salinity, pressure, lon3, lat3)
    CT = gsw.CT_from_pt(SA, theta)
    sigma0 = gsw.sigma0(SA, CT)

    valid_mask = np.isfinite(theta) & np.isfinite(salinity) & np.isfinite(sigma0)
    valid_counts = valid_mask.sum(axis=0)
    has_valid = valid_counts > 0

    if depth[0] >= ref_depth:
        sigma_ref = sigma0[0, :, :]
    elif depth[-1] <= ref_depth:
        sigma_ref = sigma0[-1, :, :]
    else:
        upper = int(np.searchsorted(depth, ref_depth, side="left"))
        lower = max(upper - 1, 0)
        z_lo = depth[lower]
        z_hi = depth[upper]
        sig_lo = sigma0[lower, :, :]
        sig_hi = sigma0[upper, :, :]
        with np.errstate(invalid="ignore", divide="ignore"):
            w = (ref_depth - z_lo) / (z_hi - z_lo) if z_hi > z_lo else 0.0
        sigma_ref = sig_lo + w * (sig_hi - sig_lo)
    diff = np.where(valid_mask, sigma0 - sigma_ref[None, :, :], np.nan)

    diff_flat = diff.reshape(Nz, -1)
    k_ref = int(np.searchsorted(depth, float(ref_depth), side="left"))
    if k_ref > 0:
        diff_flat[:k_ref, :] = np.nan
    valid_flat = np.isfinite(diff_flat)
    mask = valid_flat & (diff_flat >= threshold)
    has_cross = mask.any(axis=0)
    first_idx = np.argmax(mask, axis=0)

    ncol = diff_flat.shape[1]
    mld_flat = np.full(ncol, np.nan, dtype=np.float64)
    valid_cols = np.where(has_cross)[0]
    if valid_cols.size > 0:
        k_valid = first_idx[valid_cols]
        mld_flat[valid_cols] = depth[k_valid]
        interp_mask = k_valid > 0
        if np.any(interp_mask):
            interp_cols = valid_cols[interp_mask]
            k_interp = k_valid[interp_mask]
            k_prev = k_interp - 1
            z1 = depth[k_prev]
            z2 = depth[k_interp]
            d1 = diff_flat[k_prev, interp_cols]
            d2 = diff_flat[k_interp, interp_cols]
            finite_mask = np.isfinite(d1) & np.isfinite(d2)
            denom = d2 - d1
            slope_mask = np.abs(denom) > 1e-12
            usable = finite_mask & slope_mask
            if np.any(usable):
                w = np.zeros_like(d1)
                w[usable] = (threshold - d1[usable]) / denom[usable]
                w = np.clip(w, 0.0, 1.0, out=w)
                mld_flat[interp_cols[usable]] = z1[usable] + w[usable] * (z2[usable] - z1[usable])
            if np.any(finite_mask & ~slope_mask):
                same = finite_mask & ~slope_mask
                mld_flat[interp_cols[same]] = z2[same]

    no_cross_cols = (~has_cross) & (has_valid.reshape(-1))
    if np.any(no_cross_cols):
        idx = np.where(no_cross_cols)[0]
        k_last = (valid_counts.reshape(-1)[idx] - 1).astype(int)
        mld_flat[idx] = depth[k_last]

    mld = mld_flat.reshape(has_valid.shape)
    mld[~has_valid] = np.nan
    fully_mixed_flat = np.zeros(ncol, dtype=bool)
    fully_mixed_flat[no_cross_cols] = True
    fully_mixed = fully_mixed_flat.reshape(has_valid.shape)
    fully_mixed[~has_valid] = False
    return mld, fully_mixed


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--month", required=True, help="Target month YYYY-MM")
    p.add_argument("--indir", default="/Volumes/HJPARK4/MHW/data/GLORYS/ncfiles")
    p.add_argument("--threshold", type=float, default=0.03)
    p.add_argument("--ref-depth", type=float, default=10.0)
    p.add_argument("--outdir", required=True, help="Directory to write PNG maps")
    p.add_argument("--dpi", type=int, default=150)
    return p.parse_args()


def simple_map(ax, data: np.ndarray, lat: np.ndarray, lon: np.ndarray):
    """Render a quick lat-lon image without cartopy (diagnostic).

    - Land is masked (NaN) and shown as blank.
    - Discrete 0/1 colormap with high-visibility colors; colorbar matches bins.
    """
    # discrete classes: 0=normal, 1=fallback(deep-no-cross), 2=shallow<10m, 3=inverse
    cmap = ListedColormap(["lightgrey", "crimson", "gold", "royalblue"])  # avoid black for visibility
    cmap.set_bad(color="lightgrey")  # land/NaN
    bounds = [-0.5, 0.5, 1.5, 2.5, 3.5]
    norm = BoundaryNorm(bounds, cmap.N)

    if lat.ndim == 1 and lon.ndim == 1:
        X, Y = np.meshgrid(lon, lat)
        h = ax.pcolormesh(X, Y, data, cmap=cmap, norm=norm, shading="nearest")
    else:
        h = ax.pcolormesh(lon, lat, data, cmap=cmap, norm=norm, shading="nearest")
    ax.set_xlabel("Longitude (degE)")
    ax.set_ylabel("Latitude (degN)")
    ax.set_aspect("equal", adjustable="box")
    cb = plt.colorbar(h, ax=ax, fraction=0.046, pad=0.04, ticks=[0, 1, 2, 3])
    cb.set_label("class: 0=normal,1=fallback,2=shallow,3=inverse_ge10")


def main() -> int:
    args = parse_args()
    files = list_glorys_daily(args.indir, args.month)
    if not files:
        print("no_files")
        return 1
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # grid from first file
    ds0 = xr.open_dataset(files[0], decode_times=False)
    lat = ds0["latitude"].values
    lon = ds0["longitude"].values
    depth = ds0["depth"].values.astype(float)
    lat2, lon2 = to_2d(lat if lat.ndim==1 else lat, lon if lon.ndim==1 else lon)

    for f in files:
        base = os.path.basename(f)
        day = base.split("_")[3]  # YYYYMMDD
        tag = f"{day[:4]}-{day[4:6]}-{day[6:8]}"

        ds = xr.open_dataset(f, decode_times=False)
        theta = ds["thetao"].isel(time=0).values.astype(float)
        sal = ds["so"].isel(time=0).values.astype(float)
        mld, fully_mixed = compute_mld_sigma0_field(
            theta, sal, depth, lat2, lon2, threshold=args.threshold, ref_depth=args.ref_depth
        )
        # Land mask: where no valid ocean sample exists at any depth
        ocean = np.isfinite(theta) & np.isfinite(sal)
        vcnt = ocean.sum(axis=0)
        ocean2d = vcnt > 0
        bottom_depth = depth[np.maximum(vcnt - 1, 0)]
        shallow = (vcnt > 0) & (bottom_depth < args.ref_depth)

        # classify using Δσ0 below ref
        z3 = depth[:, None, None]
        p = gsw.p_from_z(-z3, lat2[None, :, :])
        SA = gsw.SA_from_SP(sal, p, lon2[None, :, :], lat2[None, :, :])
        CT = gsw.CT_from_pt(SA, theta)
        sigma0 = gsw.sigma0(SA, CT)
        if depth[0] >= args.ref_depth:
            sigma_ref = sigma0[0, :, :]
        elif depth[-1] <= args.ref_depth:
            sigma_ref = sigma0[-1, :, :]
        else:
            upper = int(np.searchsorted(depth, args.ref_depth, side="left"))
            lower = max(upper - 1, 0)
            z_lo = depth[lower]
            z_hi = depth[upper]
            sig_lo = sigma0[lower, :, :]
            sig_hi = sigma0[upper, :, :]
            w = (args.ref_depth - z_lo) / (z_hi - z_lo) if z_hi > z_lo else 0.0
            sigma_ref = sig_lo + w * (sig_hi - sig_lo)
        diff = sigma0 - sigma_ref[None, :, :]
        k_ref = int(np.searchsorted(depth, float(args.ref_depth), side="left"))
        if k_ref > 0:
            diff[:k_ref, :, :] = np.nan
        maxdiff = np.nanmax(diff, axis=0)
        any_below = np.isfinite(diff).any(axis=0)
        inverse = any_below & (maxdiff < 0) & (~shallow)
        deepnocross = any_below & (maxdiff >= 0) & (maxdiff < args.threshold) & (~shallow)

        # class map
        cls = np.full_like(mld, np.nan, dtype=float)
        cls[ocean2d] = 0.0
        cls[deepnocross] = 1.0
        cls[shallow] = 2.0
        cls[inverse] = 3.0

        fig, ax = plt.subplots(figsize=(6.5, 5))
        simple_map(ax, cls, lat, lon)
        ax.set_title(f"Δσ0 class map — {tag}")
        out = outdir / f"fallback_{day}.png"
        tmp = outdir / f"fallback_{day}.tmp.png"
        plt.tight_layout()
        fig.savefig(tmp, dpi=args.dpi)
        plt.close(fig)
        tmp.replace(out)
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
