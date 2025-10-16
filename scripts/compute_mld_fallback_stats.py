#!/usr/bin/env python3
"""Compute Δσ0-threshold MLD fallback statistics for a month without full MLHB.

This script scans GLORYS daily files for a given month, recomputes the mixed
layer depth (MLD) using the Δσ0=0.03 (ref 10 m) criterion via TEOS-10, and
counts columns where the threshold is never reached before the bottom
("fallback"; fully mixed) as well as shallow columns (<10 m).

Outputs summary counts to stdout and, optionally, a small NetCDF with per-grid
fallback counts and fractions.

Example
  python llm-ops/scripts/compute_mld_fallback_stats.py \
    --month 1993-01 \
    --indir /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
    --out \
      /Volumes/HJPARK4/Decadal/source/ML_budget/output/diagnostics/mld_fallback_199301.nc
"""
from __future__ import annotations

import argparse
import glob
import os
from pathlib import Path
from datetime import datetime

import numpy as np
import xarray as xr
import gsw


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--month", required=True, help="Target month YYYY-MM")
    p.add_argument("--indir", default="/Volumes/HJPARK4/MHW/data/GLORYS/ncfiles")
    p.add_argument("--threshold", type=float, default=0.03, help="Δσ0 threshold (kg m^-3)")
    p.add_argument("--ref-depth", type=float, default=10.0, help="Reference depth for Δσ0 (m)")
    p.add_argument("--out", help="Optional NetCDF output path")
    p.add_argument("--max-days", type=int, default=None, help="Optional limit of days to process")
    return p.parse_args()


def list_glorys_daily(indir: str, month: str) -> list[str]:
    pattern = os.path.join(indir, f"GLO_PHY_MY_{month.replace('-', '')[:6]}*.nc")
    files = sorted(glob.glob(pattern))
    # Keep only files whose first date belongs to the month
    out = []
    for f in files:
        base = os.path.basename(f)
        # name like GLO_PHY_MY_YYYYMMDD_YYYYMMDD.nc
        try:
            ymd = base.split("_")[3]  # YYYYMMDD
            y, m = int(ymd[:4]), int(ymd[4:6])
            ym = f"{y:04d}-{m:02d}"
            if ym == month:
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
    # broadcast fallback
    lat2 = np.broadcast_to(lat, (lat.shape[0], lon.shape[-1]))
    lon2 = np.broadcast_to(lon, lat2.shape)
    return lat2, lon2


def compute_mld_sigma0_field(theta: np.ndarray, salinity: np.ndarray, depth: np.ndarray,
                              lat_grid: np.ndarray, lon_grid: np.ndarray,
                              *, threshold: float, ref_depth: float) -> tuple[np.ndarray, np.ndarray]:
    """Simplified copy of the recomputed MLD via Δσ0 threshold.

    Returns (MLD[m], fully_mixed[bool]). fully_mixed is True where no crossing.
    """
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

    # sigma at reference depth
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
    # ignore shallower than ref_depth
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


def main() -> int:
    args = parse_args()
    files = list_glorys_daily(args.indir, args.month)
    if not files:
        print("no_files")
        return 1
    if args.max_days:
        files = files[: args.max_days]

    # Open one file to get grid size/coords
    ds0 = xr.open_dataset(files[0], decode_times=False)
    lat = ds0["latitude"].values
    lon = ds0["longitude"].values
    depth = ds0["depth"].values.astype(float)
    Ny = lat.shape[0] if lat.ndim == 1 else lat.shape[0]
    Nx = lon.shape[-1] if lon.ndim == 1 else lon.shape[1]
    lat2, lon2 = to_2d(lat if lat.ndim==1 else lat, lon if lon.ndim==1 else lon)

    fallback_days = np.zeros((Ny, Nx), dtype=np.int32)      # all no-cross
    shallow_days = np.zeros((Ny, Nx), dtype=np.int32)       # bottom depth < ref
    inverse_days = np.zeros((Ny, Nx), dtype=np.int32)       # max Δσ0 below ref < 0
    deepnocross_days = np.zeros((Ny, Nx), dtype=np.int32)   # 0 <= max Δσ0 < thr
    valid_days = np.zeros((Ny, Nx), dtype=np.int32)

    for idx, f in enumerate(files, 1):
        dsg = xr.open_dataset(f, decode_times=False)
        theta = dsg["thetao"].isel(time=0).values.astype(float)  # (z,y,x)
        sal = dsg["so"].isel(time=0).values.astype(float)
        # compute MLD/fallback
        mld, fully_mixed = compute_mld_sigma0_field(theta, sal, depth, lat2, lon2,
                                                    threshold=args.threshold,
                                                    ref_depth=args.ref_depth)
        valid = np.isfinite(mld)
        valid_days[valid] += 1
        # shallow < 10 m using bottom level from valid counts
        vmask = np.isfinite(theta) & np.isfinite(sal)
        vcnt = vmask.sum(axis=0)
        bottom_depth = depth[np.maximum(vcnt - 1, 0)]
        shallow = (vcnt > 0) & (bottom_depth < args.ref_depth)
        shallow_days[shallow] += 1

        # classify inverse vs deep-no-cross using Δσ0 below ref
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
        inv_mask = any_below & (maxdiff < 0) & (~shallow)
        dnc_mask = any_below & (maxdiff >= 0) & (maxdiff < args.threshold) & (~shallow)
        inverse_days[inv_mask] += 1
        deepnocross_days[dnc_mask] += 1
        fallback_days[(inv_mask | dnc_mask) & valid] += 1
        print(f"processed {idx}/{len(files)}: {os.path.basename(f)}")

    # Summary
    tot_valid = int(valid_days.sum())
    tot_fallback = int(fallback_days.sum())
    tot_inverse = int(inverse_days.sum())
    tot_deepnocross = int(deepnocross_days.sum())
    tot_shallow = int(shallow_days.sum())
    frac_fb = (tot_fallback / tot_valid) if tot_valid > 0 else float('nan')
    frac_inv = (tot_inverse / tot_valid) if tot_valid > 0 else float('nan')
    frac_sh = (tot_shallow / tot_valid) if tot_valid > 0 else float('nan')
    print(
        f"days={len(files)} valid_cells={tot_valid} fallback={tot_fallback} (frac={frac_fb:.4f}); "
        f"inverse={tot_inverse} (frac={frac_inv:.4f}); deep_no_cross={tot_deepnocross}; shallow={tot_shallow} (frac={frac_sh:.4f})"
    )

    if args.out:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        ds_out = xr.Dataset(
            {
                "fallback_days": (("lat", "lon"), fallback_days),
                "deepnocross_days": (("lat", "lon"), deepnocross_days),
                "inverse_days": (("lat", "lon"), inverse_days),
                "shallow_days": (("lat", "lon"), shallow_days),
                "valid_days": (("lat", "lon"), valid_days),
                "fallback_fraction": (("lat", "lon"), np.where(valid_days>0, fallback_days/valid_days, np.nan)),
                "inverse_fraction": (("lat", "lon"), np.where(valid_days>0, inverse_days/valid_days, np.nan)),
                "shallow_fraction": (("lat", "lon"), np.where(valid_days>0, shallow_days/valid_days, np.nan)),
            },
            coords={
                "lat": ("lat", lat if lat.ndim==1 else lat[:,0]),
                "lon": ("lon", lon if lon.ndim==1 else lon[0,:]),
            },
            attrs={
                "created": datetime.utcnow().isoformat(),
                "threshold_dsigma0": args.threshold,
                "ref_depth_m": args.ref_depth,
                "inverse_definition": "max(Δσ0(z)=σ0(z)-σ0(10m), z>=ref_depth) < 0",
                "month": args.month,
                "source": "compute_mld_fallback_stats.py",
            },
        )
        tmp = outp.with_suffix(outp.suffix + ".tmp")
        ds_out.to_netcdf(tmp)
        tmp.replace(outp)
        print(f"wrote {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
