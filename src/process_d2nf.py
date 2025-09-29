#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_d2nf.py — Mixed-Layer Heat Budget in D2-NF form (daily incremental)

TEN = QNET + ADV_NF + ENT + DIFF + DIFFV  (all terms in K s^-1)

This version fixes Tm/Tb by:
  * half-level overlap weighting for mixed-layer averages
  * trapezoidal treatment of the last fractional slab (implicit via overlaps)
  * linear interpolation for Tb at z=-h
  * linear extrapolation for T(0) from the top two levels (fallback: k=0)

Outputs are stored as NetCDF files containing time × lat × lon fields.
"""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import xarray as xr
from netCDF4 import Dataset, date2num

# ---------- constants ----------
PI = np.pi
RE = 6_378_000.0
RHO = 1026.0
CP = 4000.0
DT = 86400.0
HMIN_DEF = 10.0  # [m] min thickness for denominators
AH_DEF = 100.0  # [m^2/s]
KV_DEF = 1.0e-4  # [m^2/s]
R_SW, GAM1, GAM2 = 0.77, 1.5, 14.0  # shortwave two-band
FLUX_REFERENCE_DATE = dt.date(1993, 1, 1)
TIME_UNITS = "seconds since 1970-01-01 00:00:00"
TIME_CALENDAR = "standard"


# ---------- default path helpers ----------
LOCAL_INDIR_CANDIDATES = (
    "/Volumes/HJPARK4/MHW/data/GLORYS/ncfiles",
    "/data3/GLORYS/Daily_93_21/glorys_subset",
)

LOCAL_OUTDIR_CANDIDATES = (
    "/Volumes/HJPARK4/Decadal/source/ML_budget/output",
    "/data3/GLORYS/ML_budget/output_gpt",
)

LOCAL_FLUXDIR_CANDIDATES = (
    "/Volumes/HJPARK4/MHW/data/ERA5/daily_EA",
    "/Volumes/HJPARK4/MHW/data/GLORYS/flux",
    "/Volumes/HJPARK4/MHW/data/GLORYS/fluxes",
    "/data3/GLORYS/ML_budget/data",
)


def select_default_path(candidates: tuple[str, ...], *, require_exists: bool = True) -> str:
    """Return the first usable path from *candidates*."""

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
def read_rec_2d(path: str, idx: int, ny: int, nx: int, dtype=np.float32) -> np.ndarray:
    item = np.dtype(dtype).itemsize
    off = idx * ny * nx * item
    with open(path, "rb") as f:
        f.seek(off, 0)
        buf = f.read(ny * nx * item)
        if len(buf) != ny * nx * item:
            raise IOError(f"Cannot read record {idx} from {path}")
        return np.frombuffer(buf, dtype=dtype).reshape(ny, nx)


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


def parse_file_date(path: str) -> dt.date:
    name = os.path.basename(path)
    match = re.search(r"(\d{8})_(\d{8})", name)
    if not match:
        raise ValueError(f"Cannot parse date from filename: {name}")
    return dt.datetime.strptime(match.group(1), "%Y%m%d").date()


def filter_files_by_date(files: list[str], start_date: dt.date | None, end_date: dt.date | None) -> list[tuple[str, dt.date]]:
    items = [(f, parse_file_date(f)) for f in files]
    if start_date:
        items = [item for item in items if item[1] >= start_date]
    if end_date:
        items = [item for item in items if item[1] <= end_date]
    return items


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


def ddx_c(field, dx_row):
    out = np.full_like(field, np.nan, dtype=np.float64)
    out[:, 1:-1] = (field[:, 2:] - field[:, 0:-2]) / (2.0 * dx_row[:, None])
    return out


def ddy_c(field, dy):
    out = np.full_like(field, np.nan, dtype=np.float64)
    out[1:-1, :] = (field[2:, :] - field[0:-2, :]) / (2.0 * dy)
    return out


def ml_avg_Tb_Tz_sfc(T3d, U3d, V3d, H2d, depth, topo):
    """Return mixed-layer means and boundary diagnostics."""

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


# ---------- yearly processor ----------
def process_year(
    year,
    indir,
    outdir,
    fluxdir,
    ah=AH_DEF,
    kv=KV_DEF,
    use_hbar_denom=False,
    hmin=HMIN_DEF,
    we_mode="dhdt",
    we_cap_md=None,
    ent_only_cooling=True,
    dT_cap=None,
    ent_cap_kpd=None,
    save_we=False,
    start_date: dt.date | None = None,
    end_date: dt.date | None = None,
):
    print(
        f"[INFO] year {year}  (Ah={ah}, Kv={kv}, denom={'hbar' if use_hbar_denom else 'h'}, "
        f"hmin={hmin}, we_mode={we_mode}, cap={we_cap_md} m/day)"
    )

    all_files = sorted(glob.glob(os.path.join(indir, f"GLO_PHY_MY_{year}*.nc")))
    filtered = filter_files_by_date(all_files, start_date, end_date)
    if len(filtered) < 2:
        raise RuntimeError(f"Need ≥2 daily files after filtering for year {year}")

    files = [item[0] for item in filtered]
    dates = [item[1] for item in filtered]

    Path(outdir).mkdir(parents=True, exist_ok=True)
    nc_path = os.path.join(outdir, f"ml_budget_{year}.nc")

    ds0 = xr.open_dataset(files[0], decode_cf=True, mask_and_scale=True)
    T_da = pick_var(ds0, ("thetao", "votemper", "temp", "temperature"))
    U_da = pick_var(ds0, ("uo", "vozocrtx", "u"))
    V_da = pick_var(ds0, ("vo", "vomecrty", "v"))
    H_da = pick_var(ds0, ("mlotst", "mld", "ml_depth"))

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

    dy = 2.0 * PI * RE * (1.0 / 12.0) / 360.0
    dx_row = (dy * np.cos(np.deg2rad(lat1d))).astype(np.float64)

    T0 = to_zyx(T_da).values.astype(np.float64)
    U0 = to_zyx(U_da).values.astype(np.float64)
    V0 = to_zyx(V_da).values.astype(np.float64)
    H0 = to_yx(H_da).values.astype(np.float64)
    depth = depth_coord.values.astype(np.float64)

    Nz, Ny, Nx = T0.shape
    if H0.shape != (Ny, Nx):
        H0 = to_yx(H_da).values.astype(np.float64)

    topo = np.full((Ny, Nx), Nz, dtype=np.int32)
    for j in range(Ny):
        for i in range(Nx):
            col = T0[:, j, i]
            m = np.where(~np.isfinite(col))[0]
            if m.size > 0:
                topo[j, i] = m[0]

    nc_out = Dataset(nc_path, "w")
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
        "TEN": ("K s-1", "Forward temperature tendency"),
        "TEN_cen": ("K s-1", "Centered temperature tendency"),
        "ADV_NF": ("K s-1", "Non-flux horizontal advection"),
        "QNET": ("K s-1", "Surface net heat flux / rho Cp h"),
        "ENT": ("K s-1", "Entrainment term"),
        "DIFF": ("K s-1", "Horizontal diffusion term"),
        "DIFFV": ("K s-1", "Vertical diffusion term"),
        "CLOS_d2_ten": ("K s-1", "Closure residual (forward)"),
        "CLOS_d2_ten_cen": ("K s-1", "Closure residual (centered)"),
    }

    nc_vars = {
        name: create_nc_variable(nc_out, name, units, long_name)
        for name, (units, long_name) in data_vars.items()
    }

    nc_out.setncattr("title", "Mixed-Layer Heat Budget (D2-NF)")
    nc_out.setncattr("source", "process_d2nf.py")
    nc_out.setncattr("ah", ah)
    nc_out.setncattr("kv", kv)
    nc_out.setncattr("hmin", hmin)
    nc_out.setncattr("we_mode", we_mode)
    nc_out.setncattr("created", dt.datetime.utcnow().isoformat())

    Tm_prev = None
    Tm_prev_prev = None
    H_prev = None
    time_index = 0
    current_date = dates[0]

    for ti in range(1, len(files)):
        ds1 = xr.open_dataset(files[ti], decode_cf=True, mask_and_scale=True)
        T1 = to_zyx(pick_var(ds1, ("thetao", "votemper", "temp", "temperature"))).values.astype(np.float64)
        U1 = to_zyx(pick_var(ds1, ("uo", "vozocrtx", "u"))).values.astype(np.float64)
        V1 = to_zyx(pick_var(ds1, ("vo", "vomecrty", "v"))).values.astype(np.float64)
        H1 = to_yx(pick_var(ds1, ("mlotst", "mld", "ml_depth"))).values.astype(np.float64)

        flux_idx = (current_date - FLUX_REFERENCE_DATE).days
        sw = read_rec_2d(os.path.join(fluxdir, "sw_GLORYS.data"), flux_idx, Ny, Nx)
        lw = read_rec_2d(os.path.join(fluxdir, "lw_GLORYS.data"), flux_idx, Ny, Nx)
        lhf = read_rec_2d(os.path.join(fluxdir, "lhf_GLORYS.data"), flux_idx, Ny, Nx)
        shf = read_rec_2d(os.path.join(fluxdir, "shf_GLORYS.data"), flux_idx, Ny, Nx)
        Qnet_sfc = sw + lw + lhf + shf

        Tm, Um, Vm, Tb, Tz_mh, T0z = ml_avg_Tb_Tz_sfc(T0, U0, V0, H0, depth, topo)
        dT = Tm - Tb

        Hc = np.where(H0 < hmin, hmin, H0)
        if use_hbar_denom:
            Hn = np.where(H1 < hmin, hmin, H1)
            hden = 0.5 * (Hc + Hn)
        else:
            hden = Hc

        qh = sw * (R_SW * np.exp(-H0 / GAM1) + (1.0 - R_SW) * np.exp(-H0 / GAM2))
        QNET = (Qnet_sfc - qh) / (RHO * CP * hden)

        Tmx = ddx_c(Tm, dx_row)
        Tmy = ddy_c(Tm, dy)
        ADV = -(Um * Tmx + Vm * Tmy)

        if (we_mode == "centered") and (H_prev is not None):
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
        else:
            we_use = we_dhdt + we_div
        if we_cap_md is not None:
            cap = float(we_cap_md) / 86400.0
            we_use = np.clip(we_use, -cap, cap)

        if dT_cap is not None:
            dT_eff = np.clip(dT, -abs(dT_cap), abs(dT_cap))
        else:
            dT_eff = dT

        ENT = -(we_use / hden) * dT_eff
        if ent_only_cooling:
            ENT = np.where(ENT < 0.0, ENT, 0.0)
        if ent_cap_kpd is not None:
            cap_s = float(ent_cap_kpd) / 86400.0
            ENT = np.clip(ENT, -cap_s, 0.0 if ent_only_cooling else cap_s)

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

        DIFFV = -(kv * Tz_mh) / hden

        if Tm_prev is None:
            TEN_F = np.full_like(Tm, np.nan, dtype=np.float64)
            TEN_C = np.full_like(Tm, np.nan, dtype=np.float64)
        else:
            TEN_F = (Tm - Tm_prev) / DT
            if Tm_prev_prev is None:
                TEN_C = np.full_like(Tm, np.nan, dtype=np.float64)
            else:
                Tm_next, _, _, _, _, _ = ml_avg_Tb_Tz_sfc(T1, U1, V1, H1, depth, topo)
                TEN_C = (Tm_next - Tm_prev_prev) / (2.0 * DT)

        RHS = QNET + ADV + ENT + DIFF + DIFFV
        CLOSF = TEN_F - RHS
        CLOSC = TEN_C - RHS

        current_dt = dt.datetime.combine(current_date, dt.time())
        time_var[time_index] = date2num(current_dt, TIME_UNITS, TIME_CALENDAR)

        nc_vars["T_ML"][time_index, :, :] = Tm.astype(np.float32)
        nc_vars["Tb"][time_index, :, :] = Tb.astype(np.float32)
        nc_vars["T0"][time_index, :, :] = T0z.astype(np.float32)
        nc_vars["U_ML"][time_index, :, :] = Um.astype(np.float32)
        nc_vars["V_ML"][time_index, :, :] = Vm.astype(np.float32)
        nc_vars["MLD"][time_index, :, :] = H0.astype(np.float32)
        nc_vars["TEN"][time_index, :, :] = TEN_F.astype(np.float32)
        nc_vars["TEN_cen"][time_index, :, :] = TEN_C.astype(np.float32)
        nc_vars["ADV_NF"][time_index, :, :] = ADV.astype(np.float32)
        nc_vars["QNET"][time_index, :, :] = QNET.astype(np.float32)
        nc_vars["ENT"][time_index, :, :] = ENT.astype(np.float32)
        nc_vars["DIFF"][time_index, :, :] = DIFF.astype(np.float32)
        nc_vars["DIFFV"][time_index, :, :] = DIFFV.astype(np.float32)
        nc_vars["CLOS_d2_ten"][time_index, :, :] = CLOSF.astype(np.float32)
        nc_vars["CLOS_d2_ten_cen"][time_index, :, :] = CLOSC.astype(np.float32)

        time_index += 1
        if (ti % 10 == 0) or (ti == 1):
            print(f"[{year}] day {ti}/{len(files) - 1} saved")

        Tm_prev_prev = Tm_prev
        Tm_prev = Tm
        H_prev = H0
        T0, U0, V0, H0 = T1, U1, V1, H1
        current_date = dates[ti]

        ds1.close()

    ds0.close()
    nc_out.close()
    print(f"[OK] {year} done → {nc_path}")


# ---------- driver ----------
def parse_years(s: str) -> list[int]:
    if ":" in s:
        a, b = s.split(":")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def parse_date_arg(value: str | None) -> dt.date | None:
    if not value:
        return None
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def main():
    default_indir = select_default_path(LOCAL_INDIR_CANDIDATES)
    default_outdir = select_default_path(LOCAL_OUTDIR_CANDIDATES, require_exists=False)
    default_fluxdir = select_default_path(LOCAL_FLUXDIR_CANDIDATES)

    ap = argparse.ArgumentParser(
        description="D2-NF ML heat budget (Tm/Tb robust, daily incremental)"
    )
    ap.add_argument("--indir", default=default_indir)
    ap.add_argument("--outdir", default=default_outdir)
    ap.add_argument("--fluxdir", default=default_fluxdir)
    ap.add_argument("--years", default="1993:2022")
    ap.add_argument("--workers", default="auto", help="parallel processes (auto=cores-1)")
    ap.add_argument("--ah", type=float, default=AH_DEF)
    ap.add_argument("--kv", type=float, default=KV_DEF)
    ap.add_argument("--hmin", type=float, default=HMIN_DEF, help="min thickness for denominators (m)")
    ap.add_argument("--use-hbar-denom", action="store_true", help="use hbar=(h_t+h_{t+Δt})/2 for denominators")

    ap.add_argument("--we-mode", choices=["full", "deepening", "dhdt", "centered"], default="dhdt")
    ap.add_argument("--we-cap-md", type=float, default=None, help="cap |w_e| in m/day")
    ap.add_argument("--ent-only-cooling", action="store_true", default=True, help="force ENT ≤ 0")
    ap.add_argument("--dT-cap", type=float, default=None, help="cap |ΔT| used in ENT (K)")
    ap.add_argument("--ent-cap-kpd", type=float, default=None, help="cap |ENT| in K/day (guard)")
    ap.add_argument("--start-date", help="YYYY-MM-DD inclusive")
    ap.add_argument("--end-date", help="YYYY-MM-DD inclusive")

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
    )
    kwargs.update(
        use_hbar_denom=args.use_hbar_denom,
        hmin=args.hmin,
        we_mode=args.we_mode,
        we_cap_md=args.we_cap_md,
        ent_only_cooling=args.ent_only_cooling,
        dT_cap=args.dT_cap,
        ent_cap_kpd=args.ent_cap_kpd,
        save_we=False,
        start_date=start_date,
        end_date=end_date,
    )

    if n_workers == 1 or len(years) == 1:
        for y in years:
            process_year(str(y), args.indir, args.outdir, args.fluxdir, **kwargs)
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            futs = {
                ex.submit(
                    process_year,
                    str(y),
                    args.indir,
                    args.outdir,
                    args.fluxdir,
                    **kwargs,
                ): y
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
