#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_d2nf_main.py — Mainline Mixed-Layer Heat Budget in D2-NF form (daily incremental)

Fixed policy relative to legacy:
  - Horizontal advection scheme: centered (no CLI to change)
  - TEN anchoring: forward (no CLI to change; TEN_cen still computed when possible)

Other options (e.g., we-mode, MLD recompute) remain configurable as in legacy.

TEN = QNET + ADV + ENT + DIFF + DIFFV  (computed in K s^-1; written in K day^-1)
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import xarray as xr
from netCDF4 import Dataset, date2num
import gsw

# ---------- constants ----------
PI = np.pi
RE = 6_378_000.0
RHO = 1026.0
CP = 4000.0
DT = 86400.0
AH_DEF = 100.0  # [m^2/s]
KV_DEF = 1.0e-4  # [m^2/s]
R_SW, GAM1, GAM2 = 0.77, 1.5, 14.0  # shortwave two-band
FLUX_REFERENCE_DATE = dt.date(1993, 1, 1)
TIME_UNITS = "days since 1970-01-01 00:00:00"
TIME_CALENDAR = "standard"
MLD_THRESHOLD_DEF = 0.03  # [kg m^-3]
MLD_REF_DEPTH_DEF = 10.0  # [m]


# ---------- default path helpers ----------
LOCAL_INDIR_CANDIDATES = (
    "/Volumes/HJPARK4/MHW/data/GLORYS/ncfiles",
)

LOCAL_OUTDIR_CANDIDATES = (
    "/Volumes/HJPARK4/Decadal/source/ML_budget/output",
)

LOCAL_FLUXDIR_CANDIDATES = (
    "/Volumes/HJPARK4/MHW/data/ERA5/daily_EA",
    "/Volumes/HJPARK4/MHW/data/GLORYS/flux",
    "/Volumes/HJPARK4/MHW/data/GLORYS/fluxes",
)


def select_default_path(candidates: tuple[str, ...], *, require_exists: bool = True) -> str:
    for option in candidates:
        if not option:
            continue
        path = Path(option)
        if require_exists:
            if path.exists():
                return option
        else:
            if path.exists() or path.parent.exists():
                return option
    return candidates[-1]


# ---------- helpers ----------
def pick_var(ds: xr.Dataset, keys) -> xr.DataArray:
    for k in ds.data_vars:
        if any(s in k.lower() for s in keys):
            return ds[k]
    for k in ds.variables:
        if any(s in k.lower() for s in keys):
            return ds[k]
    raise KeyError(f"Variable not found for keys={keys}")


def find_dim(dims, keys):
    for key in keys:
        for d in dims:
            if key == d.lower() or key in d.lower():
                return d
    return None


def to_zyx(da: xr.DataArray) -> xr.DataArray:
    a = da
    for d in list(a.dims):
        if ("time" in d.lower()) and a.sizes[d] == 1:
            a = a.isel({d: 0}, drop=True)
    dims = list(a.dims)
    zdim = find_dim(dims, ("depth", "deptht", "nav_lev", "lev", "z"))
    ydim = find_dim(dims, ("latitude", "nav_lat", "lat", "y", "j"))
    xdim = find_dim(dims, ("longitude", "nav_lon", "lon", "x", "i"))
    if zdim is None or ydim is None or xdim is None:
        raise ValueError(f"Cannot infer (z,y,x) from dims={dims}")
    return a.transpose(zdim, ydim, xdim)


def to_yx(da: xr.DataArray) -> xr.DataArray:
    a = da
    for d in list(a.dims):
        if ("time" in d.lower()) and a.sizes[d] == 1:
            a = a.isel({d: 0}, drop=True)
    dims = list(a.dims)
    ydim = find_dim(dims, ("latitude", "nav_lat", "lat", "y", "j"))
    xdim = find_dim(dims, ("longitude", "nav_lon", "lon", "x", "i"))
    if ydim is None or xdim is None:
        if len(dims) >= 2:
            ydim, xdim = dims[-2], dims[-1]
        else:
            raise ValueError(f"Cannot infer (y,x) from dims={dims}")
    return a.transpose(ydim, xdim)


def ensure_time_var(nc: Dataset):
    time_var = nc.createVariable("time", "f8", ("time",))
    time_var.units = TIME_UNITS
    time_var.calendar = TIME_CALENDAR
    time_var.long_name = "time"
    return time_var


def create_nc_variable(nc: Dataset, name: str, units: str, long_name: str):
    var = nc.createVariable(name, "f4", ("time", "lat", "lon"), zlib=True, complevel=4, fill_value=np.nan)
    var.units = units
    var.long_name = long_name
    return var


def compute_mld_sigma0_field(
    theta: np.ndarray,
    salinity: np.ndarray,
    depth: np.ndarray,
    lat_grid: np.ndarray,
    lon_grid: np.ndarray,
    *,
    threshold: float,
    ref_depth: float,
) -> np.ndarray:
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

    # Reference density at ref_depth using linear interpolation on the shared depth grid
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
            weight = (ref_depth - z_lo) / (z_hi - z_lo) if z_hi > z_lo else 0.0
        sigma_ref = sig_lo + weight * (sig_hi - sig_lo)
    sigma_ref_3d = sigma_ref[None, :, :]

    diff = sigma0 - sigma_ref_3d
    diff = np.where(valid_mask, diff, np.nan)

    diff_flat = diff.reshape(Nz, -1)
    try:
        k_ref = int(np.searchsorted(depth, float(ref_depth), side="left"))
    except Exception:
        k_ref = 0
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

    no_cross_cols = (~has_cross) & has_valid.flatten()
    if np.any(no_cross_cols):
        idx = np.where(no_cross_cols)[0]
        k_last = (valid_counts.flatten()[idx] - 1).astype(int)
        mld_flat[idx] = depth[k_last]

    mld = mld_flat.reshape(Ny, Nx)
    mld[~has_valid] = np.nan
    mld = np.clip(mld, 0.0, None)

    fully_mixed_flat = np.zeros(ncol, dtype=bool)
    fully_mixed_flat[no_cross_cols] = True
    fully_mixed = fully_mixed_flat.reshape(Ny, Nx)
    fully_mixed[~has_valid] = False

    return mld, fully_mixed


def ddx_c(field, dx_row):
    out = np.full_like(field, np.nan, dtype=np.float64)
    out[:, 1:-1] = (field[:, 2:] - field[:, 0:-2]) / (2.0 * dx_row[:, None])
    return out


def ddy_c(field, dy):
    out = np.full_like(field, np.nan, dtype=np.float64)
    out[1:-1, :] = (field[2:, :] - field[0:-2, :]) / (2.0 * dy)
    return out


def compute_advection_centered(
    T: np.ndarray,
    U: np.ndarray,
    V: np.ndarray,
    dx_row: np.ndarray,
    dy: float,
) -> np.ndarray:
    dTx = ddx_c(T, dx_row)
    dTy = ddy_c(T, dy)
    return -(U * dTx + V * dTy)


def ml_avg_Tb_Tz_sfc(T3d, U3d, V3d, H2d, depth, topo):
    Nz, Ny, Nx = T3d.shape
    Tm = np.full((Ny, Nx), np.nan, dtype=np.float64)
    Um = np.full((Ny, Nx), np.nan, dtype=np.float64)
    Vm = np.full((Ny, Nx), np.nan, dtype=np.float64)
    Tb = np.full((Ny, Nx), np.nan, dtype=np.float64)
    TzH = np.full((Ny, Nx), np.nan, dtype=np.float64)
    T0 = np.full((Ny, Nx), np.nan, dtype=np.float64)

    zhalf = np.empty(Nz + 1, dtype=np.float64)
    zhalf[0] = 0.0
    for k in range(0, Nz - 1):
        zhalf[k + 1] = 0.5 * (depth[k] + depth[k + 1])
    if Nz >= 2:
        zhalf[Nz] = depth[Nz - 1] + 0.5 * (depth[Nz - 1] - depth[Nz - 2])
    else:
        zhalf[Nz] = depth[Nz - 1] + 1.0

    for j in range(Ny):
        for i in range(Nx):
            kbot = topo[j, i]
            if kbot <= 0:
                continue
            h = H2d[j, i]
            if not np.isfinite(h) or h <= 0.0:
                continue
            hmax = depth[kbot - 1]
            if h > hmax:
                h = hmax

            t0 = np.nan
            if kbot >= 2 and np.isfinite(T3d[0, j, i]) and np.isfinite(T3d[1, j, i]):
                z0, z1 = depth[0], depth[1]
                if z1 > z0:
                    m = (T3d[1, j, i] - T3d[0, j, i]) / (z1 - z0)
                    t0 = T3d[0, j, i] - m * z0
            if not np.isfinite(t0):
                t0 = T3d[0, j, i]
            T0[j, i] = t0

            ts = us = vs = 0.0
            for k in range(0, kbot):
                zl, zh = zhalf[k], zhalf[k + 1]
                if h <= zl:
                    break
                w = min(h, zh) - zl
                if w > 0.0:
                    ts += T3d[k, j, i] * w
                    us += U3d[k, j, i] * w
                    vs += V3d[k, j, i] * w
            if h > 0.0:
                Tm[j, i] = ts / h
                Um[j, i] = us / h
                Vm[j, i] = vs / h

            pos = np.searchsorted(depth[:kbot], h, side="right") - 1
            if pos < 0:
                pos = 0
            if pos >= kbot - 1:
                pos = kbot - 2
            zlo, zhi = depth[pos], depth[pos + 1]
            if (zhi > zlo) and np.isfinite(T3d[pos, j, i]) and np.isfinite(T3d[pos + 1, j, i]):
                alpha = (h - zlo) / (zhi - zlo)
                Tb[j, i] = T3d[pos, j, i] + alpha * (T3d[pos + 1, j, i] - T3d[pos, j, i])
                TzH[j, i] = (T3d[pos + 1, j, i] - T3d[pos, j, i]) / (zhi - zlo)
            else:
                Tb[j, i] = Tm[j, i]
                TzH[j, i] = 0.0

    return Tm, Um, Vm, Tb, TzH, T0


def process_year(
    year,
    indir,
    outdir,
    fluxdir,
    ah=AH_DEF,
    kv=KV_DEF,
    use_hbar_denom=False,
    we_mode="deepening",
    we_cap_md=None,
    dT_cap=None,
    ent_cap_kpd=None,
    save_we=False,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
    mld_source: str = "recompute",
    mld_threshold: float = MLD_THRESHOLD_DEF,
    mld_ref_depth: float = MLD_REF_DEPTH_DEF,
):
    default_indir = select_default_path(LOCAL_INDIR_CANDIDATES)
    indir = indir or default_indir
    default_outdir = select_default_path(LOCAL_OUTDIR_CANDIDATES, require_exists=False)
    outdir = outdir or default_outdir
    default_fluxdir = select_default_path(LOCAL_FLUXDIR_CANDIDATES)
    fluxdir = fluxdir or default_fluxdir

    all_files = sorted(glob.glob(os.path.join(indir, f"GLO_PHY_MY_{year}*.nc")))
    if not all_files:
        raise FileNotFoundError(f"No GLORYS daily files for year={year} in {indir}")

    # date filter
    dates = []
    files = []
    for p in all_files:
        base = os.path.basename(p)
        # GLO_PHY_MY_YYYYMMDD_YYYYMMDD.nc
        try:
            tag = base.split("_")[3]
            d = dt.datetime.strptime(tag, "%Y%m%d").date()
        except Exception:
            continue
        if start_date and d < start_date:
            continue
        if end_date and d > end_date:
            continue
        files.append(p)
        dates.append(d)
    if len(files) < 2:
        raise RuntimeError("Need at least two consecutive days for forward TEN anchoring")

    Path(outdir).mkdir(parents=True, exist_ok=True)
    nc_path = os.path.join(outdir, f"ml_budget_{year}.nc")

    ds0 = xr.open_dataset(files[0], decode_cf=True, mask_and_scale=True)
    T_da = pick_var(ds0, ("thetao", "votemper", "temp", "temperature"))
    U_da = pick_var(ds0, ("uo", "vozocrtx", "u"))
    V_da = pick_var(ds0, ("vo", "vomecrty", "v"))
    S_da = pick_var(ds0, ("so", "salinity", "salt"))
    H_da = pick_var(ds0, ("mlotst", "mld", "ml_depth")) if mld_source == "product" else None

    # coords
    depth_coord = None
    for k in ("depth", "deptht", "nav_lev", "lev", "z"):
        if k in ds0.coords or (k in ds0.variables and ds0[k].ndim == 1):
            depth_coord = ds0[k]
            break
    if depth_coord is None:
        T_tmp = to_zyx(T_da)
        depth_coord = (
            ds0[T_tmp.dims[0]]
            if T_tmp.dims[0] in ds0
            else xr.DataArray(np.arange(T_tmp.sizes[0]), dims=(T_tmp.dims[0],))
        )

    lat_coord = None
    for k in ("latitude", "nav_lat", "lat", "y", "j"):
        if k in ds0.coords or (k in ds0.variables and ds0[k].ndim in (1, 2)):
            lat_coord = ds0[k]
            break
    if lat_coord is None:
        raise ValueError("Latitude coordinate not found")

    lon_coord = None
    for k in ("longitude", "nav_lon", "lon", "x", "i"):
        if k in ds0.coords or (k in ds0.variables and ds0[k].ndim in (1, 2)):
            lon_coord = ds0[k]
            break
    if lon_coord is None:
        raise ValueError("Longitude coordinate not found")

    lat_vals = lat_coord.values.astype(np.float64)
    lon_vals = lon_coord.values.astype(np.float64)
    lat1d = lat_vals[:, 0] if lat_vals.ndim == 2 else lat_vals
    if lat_vals.ndim == 1:
        lat_grid = np.repeat(lat_vals[:, None], lon_vals.size if lon_vals.ndim == 1 else lon_vals.shape[1], axis=1)
    else:
        lat_grid = lat_vals
    if lon_vals.ndim == 1:
        lon_grid = np.repeat(lon_vals[None, :], lat_vals.shape[0] if lat_vals.ndim == 2 else lat_vals.size, axis=0)
    else:
        lon_grid = lon_vals

    dy = 2.0 * PI * RE * (1.0 / 12.0) / 360.0
    dx_row = (dy * np.cos(np.deg2rad(lat1d))).astype(np.float64)

    T0 = to_zyx(T_da).values.astype(np.float64)
    U0 = to_zyx(U_da).values.astype(np.float64)
    V0 = to_zyx(V_da).values.astype(np.float64)
    S0 = to_zyx(S_da).values.astype(np.float64)
    depth = depth_coord.values.astype(np.float64)

    Nz, Ny, Nx = T0.shape
    if lat_grid.shape != (Ny, Nx):
        lat_grid = np.broadcast_to(lat_grid, (Ny, Nx))
    if lon_grid.shape != (Ny, Nx):
        lon_grid = np.broadcast_to(lon_grid, (Ny, Nx))

    if mld_source == "product":
        H0 = to_yx(H_da).values.astype(np.float64)
        if H0.shape != (Ny, Nx):
            H0 = to_yx(H_da).values.astype(np.float64)
        fully_mixed0 = np.zeros_like(H0, dtype=bool)
    else:
        H0, fully_mixed0 = compute_mld_sigma0_field(
            T0,
            S0,
            depth,
            lat_grid,
            lon_grid,
            threshold=mld_threshold,
            ref_depth=mld_ref_depth,
        )

    topo = np.full((Ny, Nx), Nz, dtype=np.int32)
    for j in range(Ny):
        for i in range(Nx):
            col = T0[:, j, i]
            m = np.where(~np.isfinite(col))[0]
            if m.size > 0:
                topo[j, i] = m[0]

    # Use classic model to avoid NC_STRING attributes (GrADS compatibility)
    nc_out = Dataset(nc_path, "w", format="NETCDF4_CLASSIC")
    nc_out.createDimension("time", None)
    nc_out.createDimension("lat", Ny)
    nc_out.createDimension("lon", Nx)

    time_var = ensure_time_var(nc_out)

    if lat_vals.ndim == 1:
        lat_var = nc_out.createVariable("lat", "f4", ("lat",))
        lat_var[:] = lat_vals.astype(np.float32)
    else:
        lat_var = nc_out.createVariable("lat", "f4", ("lat", "lon"))
        lat_var[:, :] = lat_vals.astype(np.float32)
    lat_var.long_name = "latitude"
    lat_var.units = "degrees_north"
    lat_var.standard_name = "latitude"

    if lon_vals.ndim == 1:
        lon_var = nc_out.createVariable("lon", "f4", ("lon",))
        lon_var[:] = lon_vals.astype(np.float32)
    else:
        lon_var = nc_out.createVariable("lon", "f4", ("lat", "lon"))
        lon_var[:, :] = lon_vals.astype(np.float32)
    lon_var.long_name = "longitude"
    lon_var.units = "degrees_east"
    lon_var.standard_name = "longitude"

    data_vars = {
        "T_ML": ("K", "Mixed-layer temperature"),
        "Tb": ("K", "Temperature at -h"),
        "T0": ("K", "Sea surface temperature at z=0"),
        "U_ML": ("m s-1", "Mixed-layer zonal velocity"),
        "V_ML": ("m s-1", "Mixed-layer meridional velocity"),
        "MLD": ("m", "Mixed-layer depth"),
        "TEN": ("K day-1", "Forward temperature tendency"),
        "TEN_cen": ("K day-1", "Centered temperature tendency"),
        "ADV": ("K day-1", "Horizontal advection term"),
        "QNET": ("K day-1", "Surface net heat flux / rho Cp h"),
        "ENT": ("K day-1", "Entrainment term"),
        "DIFF": ("K day-1", "Horizontal diffusion term"),
        "DIFFV": ("K day-1", "Vertical diffusion term"),
        "CLOS_d2_ten": ("K day-1", "Closure residual (forward)"),
        "CLOS_d2_ten_cen": ("K day-1", "Closure residual (centered)"),
        # diagnostic masks (0/1 floats)
        "MASK_FULLY_MIXED": ("1", "No Δσ0 crossing before bottom (includes shallow)"),
        "MASK_SHALLOW_LT10": ("1", "Bottom depth < 10 m (shallow shelf)"),
        "MASK_DEEP_NO_CROSS": ("1", "10 m ≤ z; 0 ≤ max(Δσ0) < threshold before bottom"),
        "MASK_INVERSE_GE10": ("1", "10 m ≤ z; max(Δσ0) < 0 before bottom"),
    }

    nc_vars = {
        name: create_nc_variable(nc_out, name, units, long_name)
        for name, (units, long_name) in data_vars.items()
    }

    nc_out.setncattr("title", "Mixed-Layer Heat Budget (D2-NF) — mainline")
    nc_out.setncattr("source", "process_d2nf_main.py")
    nc_out.setncattr("ah", ah)
    nc_out.setncattr("kv", kv)
    nc_out.setncattr("we_mode", we_mode)
    nc_out.setncattr("adv_scheme", "centered")
    nc_out.setncattr("mld_source", mld_source)
    nc_out.setncattr("mld_threshold_dsigma0", mld_threshold)
    nc_out.setncattr("mld_ref_depth_m", mld_ref_depth)
    nc_out.setncattr("ten_anchor", "forward")
    nc_out.setncattr("created", dt.datetime.utcnow().iso8601() if hasattr(dt.datetime, 'iso8601') else dt.datetime.utcnow().isoformat())

    Tm_prev = None
    Tm_prev_prev = None
    H_prev = None
    time_index = 0
    current_date = dates[0]
    fully_mixed_sum = np.zeros((Ny, Nx), dtype=np.int64)

    for ti in range(1, len(files)):
        ds1 = xr.open_dataset(files[ti], decode_cf=True, mask_and_scale=True)
        T1 = to_zyx(pick_var(ds1, ("thetao", "votemper", "temp", "temperature"))).values.astype(np.float64)
        U1 = to_zyx(pick_var(ds1, ("uo", "vozocrtx", "u"))).values.astype(np.float64)
        V1 = to_zyx(pick_var(ds1, ("vo", "vomecrty", "v"))).values.astype(np.float64)
        if mld_source == "product":
            H1 = to_yx(pick_var(ds1, ("mlotst", "mld", "ml_depth"))).values.astype(np.float64)
            fully_mixed1 = np.zeros_like(H1, dtype=bool)
        else:
            S1 = to_zyx(pick_var(ds1, ("so", "salinity", "salt"))).values.astype(np.float64)
            H1, fully_mixed1 = compute_mld_sigma0_field(
                T1,
                S1,
                depth,
                lat_grid,
                lon_grid,
                threshold=mld_threshold,
                ref_depth=mld_ref_depth,
            )

        flux_idx = (current_date - FLUX_REFERENCE_DATE).days
        sw = np.fromfile(os.path.join(fluxdir, "sw_GLORYS.data"), dtype=np.float32, count=Ny*Nx, offset=flux_idx*Ny*Nx*4).reshape(Ny, Nx)
        lw = np.fromfile(os.path.join(fluxdir, "lw_GLORYS.data"), dtype=np.float32, count=Ny*Nx, offset=flux_idx*Ny*Nx*4).reshape(Ny, Nx)
        lhf = np.fromfile(os.path.join(fluxdir, "lhf_GLORYS.data"), dtype=np.float32, count=Ny*Nx, offset=flux_idx*Ny*Nx*4).reshape(Ny, Nx)
        shf = np.fromfile(os.path.join(fluxdir, "shf_GLORYS.data"), dtype=np.float32, count=Ny*Nx, offset=flux_idx*Ny*Nx*4).reshape(Ny, Nx)
        Qnet_sfc = sw + lw + lhf + shf

        Tm, Um, Vm, Tb, Tz_mh, T0z = ml_avg_Tb_Tz_sfc(T0, U0, V0, H0, depth, topo)
        dT = Tm - Tb

        hden = 0.5 * (H0 + H1) if use_hbar_denom else H0
        hden = np.where(hden > 0.0, hden, np.nan)

        qh = sw * (R_SW * np.exp(-H0 / GAM1) + (1.0 - R_SW) * np.exp(-H0 / GAM2))
        QNET = (Qnet_sfc - qh) / (RHO * CP * hden)

        ADV = compute_advection_centered(Tm, Um, Vm, dx_row, dy)

        if (we_mode in ("centered", "centered_deepening")) and (H_prev is not None):
            ht = (H1 - H_prev) / (2.0 * DT)
        else:
            ht = (H1 - H0) / DT
        div_hu = ddx_c(H0 * Um, dx_row)
        div_hv = ddy_c(H0 * Vm, dy)
        we_dhdt = ht
        we_div = div_hu + div_hv
        if we_mode == "dhdt":
            we_use = we_dhdt
        elif we_mode == "deepening":
            we_use = np.where(we_dhdt + we_div > 0.0, we_dhdt + we_div, 0.0)
        elif we_mode == "centered_deepening":
            we_use = np.where(we_dhdt + we_div > 0.0, we_dhdt + we_div, 0.0)
        else:
            we_use = we_dhdt + we_div

        dT_eff = np.clip(dT, -abs(dT_cap), abs(dT_cap)) if dT_cap is not None else dT

        ENT = -(we_use / hden) * dT_eff
        if ent_cap_kpd is not None:
            cap_s = float(ent_cap_kpd) / 86400.0
            ENT = np.clip(ENT, -cap_s, cap_s)

        DIFF = np.full((Ny, Nx), np.nan, dtype=np.float64)
        for j in range(1, Ny - 1):
            dxj = dx_row[j]
            for i in range(1, Nx - 1):
                if not (np.isfinite(Tm[j, i]) and np.isfinite(H0[j, i])):
                    continue
                hTx_ip = H0[j, i + 1] * (Tm[j, i + 1] - Tm[j, i]) / dxj
                hTx_im = H0[j, i] * (Tm[j, i] - Tm[j, i - 1]) / dxj
                dThx_ip = dT[j, i + 1] * (H0[j, i + 1] - H0[j, i]) / dxj
                dThx_im = dT[j, i] * (H0[j, i] - H0[j, i - 1]) / dxj
                hTy_jp = H0[j + 1, i] * (Tm[j + 1, i] - Tm[j, i]) / dy
                hTy_jm = H0[j, i] * (Tm[j, i] - Tm[j - 1, i]) / dy
                dThy_jp = dT[j + 1, i] * (H0[j + 1, i] - H0[j, i]) / dy
                dThy_jm = dT[j, i] * (H0[j, i] - H0[j - 1, i]) / dy
                div1 = (hTx_ip - hTx_im) / dxj + (hTy_jp - hTy_jm) / dy
                div2 = (dThx_ip - dThx_im) / dxj + (dThy_jp - dThy_jm) / dy
                DIFF[j, i] = (ah / hden[j, i]) * (div1 - div2)

        # Vertical diffusion term (z increases downward). In z_down coordinates,
        # the upward diffusive heat flux at the MLD is F_up = Kv * dT/dz_down.
        # The mixed-layer tendency contribution is F_up / hden, i.e., +(Kv/h) * dT/dz_down.
        DIFFV = (kv * Tz_mh) / hden

        if np.any(fully_mixed0):
            mask_fm = fully_mixed0
            ENT = np.where(mask_fm, 0.0, ENT)
            DIFFV = np.where(mask_fm, 0.0, DIFFV)

        if Tm_prev is None:
            TEN_F = np.full_like(Tm, np.nan, dtype=np.float64)
            TEN_C = np.full_like(Tm, np.nan, dtype=np.float64)
        else:
            Tm_next = None
            try:
                Tm_next, _, _, _, _, _ = ml_avg_Tb_Tz_sfc(T1, U1, V1, H1, depth, topo)
            except Exception:
                Tm_next = None

            # forward anchoring as mainline
            TEN_F = (Tm_next - Tm) / DT if Tm_next is not None else np.full_like(Tm, np.nan, dtype=np.float64)

            if Tm_prev_prev is None or Tm_next is None:
                TEN_C = np.full_like(Tm, np.nan, dtype=np.float64)
            else:
                TEN_C = (Tm_next - Tm_prev_prev) / (2.0 * DT)

        RHS = QNET + ADV + ENT + DIFF + DIFFV
        CLOSF = TEN_F - RHS
        CLOSC = TEN_C - RHS

        current_dt = dt.datetime.combine(current_date, dt.time())
        time_var[time_index] = date2num(current_dt, TIME_UNITS, TIME_CALENDAR)

        # diagnostic masks based on T0/S0
        try:
            valid0 = np.isfinite(T0) & np.isfinite(S0)
            vcnt0 = valid0.sum(axis=0)
            bottom_k = np.where(vcnt0 > 0, vcnt0 - 1, -1)
            bottom_depth0 = np.where(bottom_k >= 0, depth[bottom_k], np.nan)
            shallow0 = np.isfinite(bottom_depth0) & (bottom_depth0 < mld_ref_depth)

            z3 = depth[:, None, None]
            p0 = gsw.p_from_z(-z3, lat_grid[None, :, :])
            SA0 = gsw.SA_from_SP(S0, p0, lon_grid[None, :, :], lat_grid[None, :, :])
            CT0 = gsw.CT_from_pt(SA0, T0)
            sigma0 = gsw.sigma0(SA0, CT0)

            if depth[0] >= mld_ref_depth:
                sigma_ref0 = sigma0[0, :, :]
            elif depth[-1] <= mld_ref_depth:
                sigma_ref0 = sigma0[-1, :, :]
            else:
                upper = int(np.searchsorted(depth, mld_ref_depth, side="left"))
                lower = max(upper - 1, 0)
                z_lo = depth[lower]
                z_hi = depth[upper]
                sig_lo = sigma0[lower, :, :]
                sig_hi = sigma0[upper, :, :]
                with np.errstate(invalid="ignore", divide="ignore"):
                    w = (mld_ref_depth - z_lo) / (z_hi - z_lo) if z_hi > z_lo else 0.0
                sigma_ref0 = sig_lo + w * (sig_hi - sig_lo)
            diff0 = sigma0 - sigma_ref0[None, :, :]
            k_ref = int(np.searchsorted(depth, float(mld_ref_depth), side="left"))
            if k_ref > 0:
                diff0[:k_ref, :, :] = np.nan
            maxdiff = np.nanmax(diff0, axis=0)
            any_below = np.isfinite(diff0).any(axis=0)
            inverse0 = any_below & (maxdiff < 0) & (~shallow0)
            deepnocross0 = any_below & (maxdiff >= 0) & (maxdiff < mld_threshold) & (~shallow0)

            nc_vars["MASK_FULLY_MIXED"][time_index, :, :] = fully_mixed0.astype(np.float32)
            nc_vars["MASK_SHALLOW_LT10"][time_index, :, :] = shallow0.astype(np.float32)
            nc_vars["MASK_DEEP_NO_CROSS"][time_index, :, :] = deepnocross0.astype(np.float32)
            nc_vars["MASK_INVERSE_GE10"][time_index, :, :] = inverse0.astype(np.float32)
        except Exception:
            pass

        nc_vars["T_ML"][time_index, :, :] = Tm.astype(np.float32)
        nc_vars["Tb"][time_index, :, :] = Tb.astype(np.float32)
        nc_vars["T0"][time_index, :, :] = T0z.astype(np.float32)
        nc_vars["U_ML"][time_index, :, :] = Um.astype(np.float32)
        nc_vars["V_ML"][time_index, :, :] = Vm.astype(np.float32)
        nc_vars["MLD"][time_index, :, :] = H0.astype(np.float32)

        k_per_day = DT
        nc_vars["TEN"][time_index, :, :] = (TEN_F * k_per_day).astype(np.float32)
        nc_vars["TEN_cen"][time_index, :, :] = (TEN_C * k_per_day).astype(np.float32)
        nc_vars["ADV"][time_index, :, :] = (ADV * k_per_day).astype(np.float32)
        nc_vars["QNET"][time_index, :, :] = (QNET * k_per_day).astype(np.float32)
        nc_vars["ENT"][time_index, :, :] = (ENT * k_per_day).astype(np.float32)
        nc_vars["DIFF"][time_index, :, :] = (DIFF * k_per_day).astype(np.float32)
        nc_vars["DIFFV"][time_index, :, :] = (DIFFV * k_per_day).astype(np.float32)
        nc_vars["CLOS_d2_ten"][time_index, :, :] = (CLOSF * k_per_day).astype(np.float32)
        nc_vars["CLOS_d2_ten_cen"][time_index, :, :] = (CLOSC * k_per_day).astype(np.float32)

        time_index += 1
        if (ti % 10 == 0) or (ti == 1):
            print(f"[{year}] day {ti}/{len(files) - 1} saved")

        fully_mixed_sum += fully_mixed0.astype(np.int64)
        Tm_prev_prev = Tm_prev
        Tm_prev = Tm
        H_prev = H0
        T0, U0, V0, H0 = T1, U1, V1, H1
        if mld_source != "product":
            S0 = S1
        fully_mixed0 = fully_mixed1
        # advance current_date to the day corresponding to this time index
        current_date = dates[ti]

    nc_out.setncattr("fully_mixed_days_sum", int(fully_mixed_sum.sum()))
    nc_out.close()


def parse_years(arg: str) -> list[int]:
    if ":" in arg:
        a, b = arg.split(":", 1)
        return list(range(int(a), int(b) + 1))
    return [int(arg)]


def parse_date_arg(s: str | None) -> dt.date | None:
    if not s:
        return None
    return dt.datetime.strptime(s, "%Y-%m-%d").date()


def main():
    default_indir = select_default_path(LOCAL_INDIR_CANDIDATES)
    default_outdir = select_default_path(LOCAL_OUTDIR_CANDIDATES, require_exists=False)
    default_fluxdir = select_default_path(LOCAL_FLUXDIR_CANDIDATES)

    ap = argparse.ArgumentParser(description="D2-NF ML heat budget — mainline (centered, forward)")
    ap.add_argument("--indir", default=default_indir)
    ap.add_argument("--outdir", default=default_outdir)
    ap.add_argument("--fluxdir", default=default_fluxdir)
    ap.add_argument("--years", default="1993:2022")
    ap.add_argument("--workers", default="auto", help="parallel processes (auto=cores-1)")
    ap.add_argument("--ah", type=float, default=AH_DEF)
    ap.add_argument("--kv", type=float, default=KV_DEF)
    ap.add_argument("--use-hbar-denom", action="store_true")
    ap.add_argument("--we-mode", choices=["full", "deepening", "dhdt", "centered", "centered_deepening"], default="deepening")
    ap.add_argument("--we-cap-md", type=float, default=None)
    ap.add_argument("--dT-cap", type=float, default=None)
    ap.add_argument("--ent-cap-kpd", type=float, default=None)
    ap.add_argument("--start-date")
    ap.add_argument("--end-date")
    ap.add_argument("--mld-source", choices=["recompute", "product"], default="recompute")
    ap.add_argument("--mld-threshold", type=float, default=MLD_THRESHOLD_DEF)
    ap.add_argument("--mld-ref-depth", type=float, default=MLD_REF_DEPTH_DEF)

    args = ap.parse_args()

    years = parse_years(args.years)
    start_date = parse_date_arg(args.start_date)
    end_date = parse_date_arg(args.end_date)

    if args.workers == "auto":
        try:
            import multiprocessing as mp

            n_workers = max(1, mp.cpu_count() - 1)
        except Exception:
            n_workers = 1
    else:
        n_workers = max(1, int(args.workers))

    kwargs = dict(
        ah=args.ah,
        kv=args.kv,
        use_hbar_denom=args.use_hbar_denom,
        we_mode=args.we_mode,
        we_cap_md=args.we_cap_md,
        dT_cap=args.dT_cap,
        ent_cap_kpd=args.ent_cap_kpd,
        save_we=False,
        start_date=start_date,
        end_date=end_date,
        mld_source=args.mld_source,
        mld_threshold=args.mld_threshold,
        mld_ref_depth=args.mld_ref_depth,
    )

    if n_workers == 1 or len(years) == 1:
        for y in years:
            process_year(str(y), args.indir, args.outdir, args.fluxdir, **kwargs)
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            futs = {
                ex.submit(process_year, str(y), args.indir, args.outdir, args.fluxdir, **kwargs): y
                for y in years
            }
            for fut in as_completed(futs):
                y = futs[fut]
                try:
                    fut.result()
                except Exception as exc:
                    print(f"[ERR] year {y}: {exc}")


if __name__ == "__main__":
    main()
