#!/usr/bin/env python3
"""Select representative grid points for multiple categories on a given day.

Categories
 - ENTPOS: ENT > 0 (K/day)
 - ENTNEG: ENT < 0
 - CLOS_GOOD: |CLOS_d2_ten| minimal
 - CLOS_BAD: |CLOS_d2_ten| maximal
 - SHALLOW_LT10: water column shallower than 10 m (based on GLORYS valid depth)
 - FALLBACK: depth >= 10 m but Δσ0(z) relative to 10 m never reaches 0.03 before bottom (fully-mixed fallback)
 - MLD_GE10: MLD >= 10 m

The script prints lat,lon,value per category for quick plotting.

Example
  python llm-ops/scripts/pick_profile_points_multi.py \
    --mlhb /Volumes/HJPARK4/Decadal/source/ML_budget/output/daily/1993/01/ml_budget_1993.nc \
    --glorys /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles/GLO_PHY_MY_19930102_19930102.nc \
    --time-index 1 --topk 1
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import xarray as xr
import gsw


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mlhb", required=True, help="MLHB daily NetCDF (ml_budget_YYYY.nc)")
    p.add_argument("--glorys", required=True, help="GLORYS daily NetCDF for the same date")
    p.add_argument("--time-index", type=int, default=0)
    p.add_argument("--topk", type=int, default=1)
    p.add_argument("--mld-threshold", type=float, default=0.03, help="Δσ0 threshold (kg m^-3)")
    return p.parse_args()


@dataclass
class Grid:
    lat: np.ndarray  # (lat,) or (lat,lon)
    lon: np.ndarray  # (lon,) or (lat,lon)

    def to_2d(self) -> tuple[np.ndarray, np.ndarray]:
        lat, lon = self.lat, self.lon
        if lat.ndim == 1 and lon.ndim == 1:
            lat2 = np.repeat(lat[:, None], lon.size, axis=1)
            lon2 = np.repeat(lon[None, :], lat.size, axis=0)
            return lat2, lon2
        if lat.ndim == 2 and lon.ndim == 2:
            return lat, lon
        # fallback broadcast
        lat2 = np.broadcast_to(lat, (lat.shape[0], lon.shape[-1]))
        lon2 = np.broadcast_to(lon, lat2.shape)
        return lat2, lon2


def select_indices_by_mask(mask: np.ndarray, weights: np.ndarray | None, topk: int, reverse: bool = False) -> list[tuple[int, int, float]]:
    inds = np.argwhere(mask)
    if inds.size == 0:
        return []
    if weights is None:
        vals = np.zeros(inds.shape[0], dtype=float)
    else:
        vals = np.array([float(weights[i, j]) for i, j in inds])
    order = np.argsort(vals)
    if reverse:
        order = order[::-1]
    sel = []
    for order_idx in order[:topk]:
        i, j = inds[order_idx]
        sel.append((int(i), int(j), float(vals[order_idx])))
    return sel


def main() -> int:
    args = parse_args()
    ds = xr.open_dataset(args.mlhb)
    ti = int(args.time_index)

    # Coordinates from MLHB
    lat = ds["lat"].values
    lon = ds["lon"].values
    grid = Grid(lat=lat, lon=lon)

    # Data layers (2D)
    ENT = ds["ENT"].isel(time=ti).values
    MLD = ds["MLD"].isel(time=ti).values
    CLOS = ds["CLOS_d2_ten"].isel(time=ti).values

    Ny, Nx = MLD.shape

    # Categories from MLHB
    entpos_inds = select_indices_by_mask(np.isfinite(ENT) & (ENT > 0), ENT, args.topk, reverse=True)
    entneg_inds = select_indices_by_mask(np.isfinite(ENT) & (ENT < 0), -ENT, args.topk, reverse=True)

    absC = np.abs(CLOS)
    clos_good_inds = select_indices_by_mask(np.isfinite(absC), -absC, args.topk, reverse=True)  # smallest |C|
    clos_bad_inds = select_indices_by_mask(np.isfinite(absC), absC, args.topk, reverse=True)   # largest |C|

    mld_ge10_inds = select_indices_by_mask(np.isfinite(MLD) & (MLD >= 10.0), MLD, args.topk, reverse=True)
    mld_lt10_inds = select_indices_by_mask(np.isfinite(MLD) & (MLD < 10.0), -MLD, args.topk, reverse=True)

    # GLORYS-based diagnostics for shallow and fallback
    dg = xr.open_dataset(args.glorys, decode_times=False)
    theta = dg["thetao"].isel(time=0).values  # (z,y,x)
    so = dg["so"].isel(time=0).values        # (z,y,x)
    depth = dg["depth"].values.astype(float) # (z,)
    lat_g = dg["latitude"].values
    lon_g = dg["longitude"].values

    # align shapes
    lat2, lon2 = Grid(lat_g, lon_g).to_2d()

    valid = np.isfinite(theta) & np.isfinite(so)
    valid_counts = valid.sum(axis=0)
    # bottom depth (last valid level)
    bottom_k = np.where(valid_counts > 0, valid_counts - 1, -1)
    bottom_depth = np.where(bottom_k >= 0, depth[bottom_k], np.nan)
    shallow_mask = np.isfinite(bottom_depth) & (bottom_depth < 10.0)

    # Fallback (no threshold crossing before bottom), only where depth >= 10 m
    # TEOS-10 properties
    z3 = depth[:, None, None]
    p = gsw.p_from_z(-z3, lat2[None, :, :])
    SA = gsw.SA_from_SP(so, p, lon2[None, :, :], lat2[None, :, :])
    CT = gsw.CT_from_pt(SA, theta)
    sigma0 = gsw.sigma0(SA, CT)

    # sigma at 10 m
    if depth[0] >= 10.0:
        sigma_ref = sigma0[0, :, :]
    elif depth[-1] <= 10.0:
        sigma_ref = sigma0[-1, :, :]
    else:
        upper = int(np.searchsorted(depth, 10.0, side="left"))
        lower = max(upper - 1, 0)
        z_lo = depth[lower]
        z_hi = depth[upper]
        sig_lo = sigma0[lower, :, :]
        sig_hi = sigma0[upper, :, :]
        w = (10.0 - z_lo) / (z_hi - z_lo) if z_hi > z_lo else 0.0
        sigma_ref = sig_lo + w * (sig_hi - sig_lo)
    diff = sigma0 - sigma_ref[None, :, :]

    # ignore depths shallower than 10 m
    k_ref = int(np.searchsorted(depth, 10.0, side="left"))
    if k_ref > 0:
        diff[:k_ref, :, :] = np.nan
    maxdiff = np.nanmax(diff, axis=0)
    fallback_mask = (np.isfinite(bottom_depth) & (bottom_depth >= 10.0) & (~np.isfinite(maxdiff) | (maxdiff < args.mld_threshold)))

    shallow_inds = select_indices_by_mask(shallow_mask, bottom_depth, args.topk, reverse=False)
    fallback_inds = select_indices_by_mask(fallback_mask, bottom_depth, args.topk, reverse=True)

    # helper to emit
    def emit(section: str, inds: list[tuple[int, int, float]]):
        print(section)
        if not inds:
            print("none")
            return
        # derive MLHB coords (assume same indexing order as GLORYS; if not, nearest match)
        # We will use MLHB lat/lon to print exact coordinates
        lat_arr = ds["lat"].values
        lon_arr = ds["lon"].values
        # support 1D lat/lon variables
        if lat_arr.ndim == 1:
            for i, j, v in inds:
                print(f"{float(lat_arr[i]):.4f},{float(lon_arr[j]):.4f},{v:.6f}")
        else:
            for i, j, v in inds:
                print(f"{float(lat_arr[i,j]):.4f},{float(lon_arr[i,j]):.4f},{v:.6f}")

    emit("ENT_POS", entpos_inds)
    emit("ENT_NEG", entneg_inds)
    emit("CLOS_GOOD", clos_good_inds)
    emit("CLOS_BAD", clos_bad_inds)
    emit("SHALLOW_LT10", shallow_inds)
    emit("FALLBACK", fallback_inds)
    emit("MLD_GE10", mld_ge10_inds)
    emit("MLD_LT10", mld_lt10_inds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
