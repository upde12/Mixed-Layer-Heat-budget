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

Also saves:
  - T0YYYY.data : T(z=0) per day (float32 Ny×Nx)
  - TbYYYY.data : bottom temperature at z=-h
  - T_MLYYYY.data : Tm (as before)
"""

import os, glob, argparse
import numpy as np
import xarray as xr
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

# ---------- constants ----------
PI   = np.pi
RE   = 6_378_000.0
RHO  = 1026.0
CP   = 4000.0
DT   = 86400.0
HMIN_DEF = 10.0           # [m] min thickness for denominators
AH_DEF   = 100.0          # [m^2/s]
KV_DEF   = 1.0e-4         # [m^2/s]
R_SW, GAM1, GAM2 = 0.77, 1.5, 14.0  # shortwave two-band

# ---------- I/O helpers ----------
def write_append(path, arr2d):
    arr = np.asarray(arr2d, dtype=np.float32)
    with open(path, "ab") as f:
        arr.tofile(f)

def read_rec_2d(path, idx, ny, nx, dtype=np.float32):
    item = np.dtype(dtype).itemsize
    off  = idx * ny * nx * item
    with open(path, "rb") as f:
        f.seek(off, 0)
        buf = f.read(ny*nx*item)
        if len(buf) != ny*nx*item:
            raise IOError(f"Cannot read record {idx} from {path}")
        return np.frombuffer(buf, dtype=dtype).reshape(ny, nx)

# ---------- dataset helpers ----------
def pick_var(ds, keys):
    for k in ds.data_vars:
        if any(s in k.lower() for s in keys): return ds[k]
    for k in ds.variables:
        if any(s in k.lower() for s in keys): return ds[k]
    raise KeyError(f"Variable not found for keys={keys}")

def find_dim(dims, keys):
    for key in keys:
        for d in dims:
            if key == d.lower() or key in d.lower(): return d
    return None

def to_zyx(da):
    a = da
    for d in list(a.dims):
        if ("time" in d.lower()) and a.sizes[d] == 1:
            a = a.isel({d:0}, drop=True)
    dims = list(a.dims)
    zdim = find_dim(dims, ("depth","deptht","nav_lev","lev","z"))
    ydim = find_dim(dims, ("latitude","nav_lat","lat","y","j"))
    xdim = find_dim(dims, ("longitude","nav_lon","lon","x","i"))
    if zdim is None or ydim is None or xdim is None:
        raise ValueError(f"Cannot infer (z,y,x) from dims={dims}")
    return a.transpose(zdim, ydim, xdim)

def to_yx(da):
    a = da
    for d in list(a.dims):
        if ("time" in d.lower()) and a.sizes[d] == 1:
            a = a.isel({d:0}, drop=True)
    dims = list(a.dims)
    ydim = find_dim(dims, ("latitude","nav_lat","lat","y","j"))
    xdim = find_dim(dims, ("longitude","nav_lon","lon","x","i"))
    if ydim is None or xdim is None:
        if len(dims) >= 2: ydim, xdim = dims[-2], dims[-1]
        else: raise ValueError(f"Cannot infer (y,x) from dims={dims}")
    return a.transpose(ydim, xdim)

# ---------- finite differences ----------
def ddx_c(field, dx_row):
    out = np.full_like(field, np.nan, dtype=np.float64)
    out[:,1:-1] = (field[:,2:] - field[:,0:-2]) / (2.0*dx_row[:,None])
    return out

def ddy_c(field, dy):
    out = np.full_like(field, np.nan, dtype=np.float64)
    out[1:-1,:] = (field[2:,:] - field[0:-2,:]) / (2.0*dy)
    return out

# ---------- ML means + Tb + (dT/dz)|_-h + T(0) ----------
def ml_avg_Tb_Tz_sfc(T3d, U3d, V3d, H2d, depth, topo):
    """
    Robust mixed-layer diagnostics using half-level overlaps.

    Returns:
      Tm, Um, Vm   : mixed-layer means
      Tb           : temperature at z=-h (linear interp in containing cell)
      Tz_mh        : (∂T/∂z)|_{z=-h} from the same cell (z positive downward)
      T0           : temperature at z=0 (linear extrap from top two levels; fallback k=0)
    """
    Nz, Ny, Nx = T3d.shape
    Tm  = np.full((Ny,Nx), np.nan, dtype=np.float64)
    Um  = np.full((Ny,Nx), np.nan, dtype=np.float64)
    Vm  = np.full((Ny,Nx), np.nan, dtype=np.float64)
    Tb  = np.full((Ny,Nx), np.nan, dtype=np.float64)
    TzH = np.full((Ny,Nx), np.nan, dtype=np.float64)
    T0  = np.full((Ny,Nx), np.nan, dtype=np.float64)

    # half-level boundaries z_{k+1/2}
    zhalf = np.empty(Nz+1, dtype=np.float64)
    zhalf[0] = 0.0
    for k in range(0, Nz-1):
        zhalf[k+1] = 0.5*(depth[k] + depth[k+1])
    # bottom boundary (not used for shallow h but set consistently)
    if Nz >= 2:
        zhalf[Nz] = depth[Nz-1] + 0.5*(depth[Nz-1] - depth[Nz-2])
    else:
        zhalf[Nz] = depth[Nz-1] + 1.0

    for j in range(Ny):
        for i in range(Nx):
            kbot = topo[j,i]
            if kbot <= 0:  # land
                continue
            h = H2d[j,i]
            if not np.isfinite(h) or h <= 0.0:
                continue
            # cap h to last valid center
            hmax = depth[kbot-1]
            if h > hmax: h = hmax

            # T(0) via linear extrapolation from top two levels (fallback: k=0)
            t0 = np.nan
            if kbot >= 2 and np.isfinite(T3d[0,j,i]) and np.isfinite(T3d[1,j,i]):
                z0, z1 = depth[0], depth[1]
                if z1 > z0:
                    m = (T3d[1,j,i] - T3d[0,j,i]) / (z1 - z0)
                    t0 = T3d[0,j,i] - m*z0    # extrapolate to z=0
            if not np.isfinite(t0):
                t0 = T3d[0,j,i]
            T0[j,i] = t0

            # weights by overlap with [0,h]
            ts = us = vs = 0.0
            for k in range(0, kbot):   # only valid part of the column
                zl, zh = zhalf[k], zhalf[k+1]
                if h <= zl: break
                w = min(h, zh) - zl
                if w > 0.0:
                    ts += T3d[k,j,i] * w
                    us += U3d[k,j,i] * w
                    vs += V3d[k,j,i] * w
            if h > 0.0:
                Tm[j,i] = ts / h
                Um[j,i] = us / h
                Vm[j,i] = vs / h

            # containing cell for h  (depth centers)
            # find largest k with depth[k] <= h, within valid range
            pos = np.searchsorted(depth[:kbot], h, side='right') - 1
            if pos < 0: pos = 0
            if pos >= kbot-1: pos = kbot-2
            zlo, zhi = depth[pos], depth[pos+1]
            if (zhi > zlo) and np.isfinite(T3d[pos,j,i]) and np.isfinite(T3d[pos+1,j,i]):
                alpha = (h - zlo) / (zhi - zlo)
                Tb[j,i]  = T3d[pos,j,i] + alpha*(T3d[pos+1,j,i] - T3d[pos,j,i])
                TzH[j,i] = (T3d[pos+1,j,i] - T3d[pos,j,i]) / (zhi - zlo)
            else:
                # very shallow or degenerate → set neutral
                Tb[j,i]  = Tm[j,i]
                TzH[j,i] = 0.0

    return Tm, Um, Vm, Tb, TzH, T0

# ---------- yearly processor ----------
def process_year(year, indir, outdir, fluxdir,
                 ah=AH_DEF, kv=KV_DEF, use_hbar_denom=False, hmin=HMIN_DEF,
                 we_mode="dhdt", we_cap_md=None,
                 ent_only_cooling=True, dT_cap=None, ent_cap_kpd=None,
                 save_we=False):
    print(f"[INFO] year {year}  (Ah={ah}, Kv={kv}, denom={'hbar' if use_hbar_denom else 'h'}, "
          f"hmin={hmin}, we_mode={we_mode}, cap={we_cap_md} m/day)")
    Path(outdir).mkdir(parents=True, exist_ok=True)

    files = sorted(glob.glob(os.path.join(indir, f"GLO_PHY_MY_{year}*.nc")))
    if len(files) < 3:
        raise RuntimeError(f"Need ≥3 daily files for centered tendency in {year}")

    # day-0
    ds0 = xr.open_dataset(files[0], decode_cf=True, mask_and_scale=True)
    T_da = pick_var(ds0, ("thetao","votemper","temp","temperature"))
    U_da = pick_var(ds0, ("uo","vozocrtx","u"))
    V_da = pick_var(ds0, ("vo","vomecrty","v"))
    H_da = pick_var(ds0, ("mlotst","mld","ml_depth"))

    # coords
    depth_coord = None
    for k in ("depth","deptht","nav_lev","lev","z"):
        if k in ds0.coords or (k in ds0.variables and ds0[k].ndim==1):
            depth_coord = ds0[k]; break
    if depth_coord is None:
        T_tmp = to_zyx(T_da)
        depth_coord = ds0[T_tmp.dims[0]] if T_tmp.dims[0] in ds0 else xr.DataArray(np.arange(T_tmp.sizes[0]), dims=(T_tmp.dims[0],))
    lat_coord = None
    for k in ("latitude","nav_lat","lat","y","j"):
        if k in ds0.coords or (k in ds0.variables and ds0[k].ndim in (1,2)):
            lat_coord = ds0[k]; break
    if lat_coord is None:
        raise ValueError("Latitude coordinate not found")
    lat1d = lat_coord.values[:,0].astype(np.float64) if lat_coord.ndim==2 else lat_coord.values.astype(np.float64)

    # metrics (≈1/12°)
    dy = 2.0*PI*RE*(1.0/12.0)/360.0
    dx_row = (dy*np.cos(np.deg2rad(lat1d))).astype(np.float64)

    # arrays day-0
    T0 = to_zyx(T_da).values.astype(np.float64)
    U0 = to_zyx(U_da).values.astype(np.float64)
    V0 = to_zyx(V_da).values.astype(np.float64)
    H0 = to_yx(H_da).values.astype(np.float64)
    depth = depth_coord.values.astype(np.float64)

    Nz, Ny, Nx = T0.shape
    if H0.shape != (Ny, Nx):
        H0 = to_yx(H_da).values.astype(np.float64)

    # topo: first missing level index (bottom)
    topo = np.full((Ny,Nx), Nz, dtype=np.int32)
    for j in range(Ny):
        for i in range(Nx):
            col = T0[:,j,i]
            m = np.where(~np.isfinite(col))[0]
            if m.size>0: topo[j,i] = m[0]

    # outputs
    p_TML = os.path.join(outdir, f"T_ML{year}.data")   # Tm
    p_TB  = os.path.join(outdir, f"Tb{year}.data")     # Tb
    p_T0  = os.path.join(outdir, f"T0{year}.data")     # T(z=0)

    p_UML = os.path.join(outdir, f"U_ML{year}.data")
    p_VML = os.path.join(outdir, f"V_ML{year}.data")
    p_MLD = os.path.join(outdir, f"MLD{year}.data")

    p_TEN_F = os.path.join(outdir, f"ten{year}.data")          # forward
    p_TEN_C = os.path.join(outdir, f"ten_cen{year}.data")      # centered
    p_ADV   = os.path.join(outdir, f"advNF{year}.data")
    p_QNET  = os.path.join(outdir, f"qnet{year}.data")
    p_ENT   = os.path.join(outdir, f"ent{year}.data")
    p_DIFF  = os.path.join(outdir, f"diff{year}.data")
    p_DIFFV = os.path.join(outdir, f"diffv{year}.data")
    p_CLOSF = os.path.join(outdir, f"clos_d2_ten{year}.data")
    p_CLOSC = os.path.join(outdir, f"clos_d2_ten_cen{year}.data")

    # clean old
    for p in [p_TML,p_TB,p_T0,p_UML,p_VML,p_MLD,p_TEN_F,p_TEN_C,p_ADV,p_QNET,p_ENT,p_DIFF,p_DIFFV,p_CLOSF,p_CLOSC]:
        if os.path.exists(p): os.remove(p)

    # optional diagnostics (not changed here)
    base = (int(year) - 1993) * 365
    Tm_prev = None
    Tm_prev_prev = None
    H_prev = None

    # ===== daily loop =====
    for ti in range(1, len(files)):
        ds1 = xr.open_dataset(files[ti], decode_cf=True, mask_and_scale=True)
        T1 = to_zyx(pick_var(ds1, ("thetao","votemper","temp","temperature"))).values.astype(np.float64)
        U1 = to_zyx(pick_var(ds1, ("uo","vozocrtx","u"))).values.astype(np.float64)
        V1 = to_zyx(pick_var(ds1, ("vo","vomecrty","v"))).values.astype(np.float64)
        H1 = to_yx(pick_var(ds1, ("mlotst","mld","ml_depth"))).values.astype(np.float64)

        # surface fluxes (into-ocean +)
        sw  = read_rec_2d(os.path.join(fluxdir, "sw_GLORYS.data"),  base+ti-1, Ny, Nx)
        lw  = read_rec_2d(os.path.join(fluxdir, "lw_GLORYS.data"),  base+ti-1, Ny, Nx)
        lhf = read_rec_2d(os.path.join(fluxdir, "lhf_GLORYS.data"), base+ti-1, Ny, Nx)
        shf = read_rec_2d(os.path.join(fluxdir, "shf_GLORYS.data"), base+ti-1, Ny, Nx)
        Qnet_sfc = sw + lw + lhf + shf

        # ML diagnostics at day-0 thickness H0
        Tm, Um, Vm, Tb, Tz_mh, T0z = ml_avg_Tb_Tz_sfc(T0, U0, V0, H0, depth, topo)
        dT = Tm - Tb

        # denominators
        Hc = np.where(H0 < hmin, hmin, H0)
        if use_hbar_denom:
            Hn   = np.where(H1 < hmin, hmin, H1)
            hden = 0.5*(Hc + Hn)
        else:
            hden = Hc

        # QNET with shortwave penetration
        qh   = sw * ( R_SW*np.exp(-H0/GAM1) + (1.0-R_SW)*np.exp(-H0/GAM2) )
        QNET = (Qnet_sfc - qh) / (RHO * CP * hden)

        # Non-flux advection
        Tmx = ddx_c(Tm, dx_row); Tmy = ddy_c(Tm, dy)
        ADV = -(Um*Tmx + Vm*Tmy)

        # Entrainment speed (conservative defaults)
        if (we_mode == "centered") and (H_prev is not None):
            ht = (H1 - H_prev) / (2.0*DT)
        else:
            ht = (H1 - H0) / DT
        div_hu = ddx_c(H0*Um, dx_row); div_hv = ddy_c(H0*Vm, dy)
        we_dhdt = ht
        we_div  = div_hu + div_hv
        if we_mode == "dhdt":      we_use = we_dhdt
        elif we_mode == "deepening": we_use = np.where(we_dhdt+we_div > 0.0, we_dhdt+we_div, 0.0)
        else:                       we_use = we_dhdt + we_div
        if we_cap_md is not None:
            cap = float(we_cap_md)/86400.0
            we_use = np.clip(we_use, -cap, cap)

        # ΔT cap only for ENT (optional)
        if dT_cap is not None:
            dT_eff = np.clip(dT, -abs(dT_cap), abs(dT_cap))
        else:
            dT_eff = dT

        ENT = -(we_use / hden) * dT_eff
        if ent_only_cooling:
            ENT = np.where(ENT < 0.0, ENT, 0.0)
        if ent_cap_kpd is not None:
            cap_s = float(ent_cap_kpd)/86400.0
            ENT = np.clip(ENT, -cap_s, 0.0 if ent_only_cooling else cap_s)

        # Horizontal diffusion (conservative discretization)
        DIFF = np.full((Ny,Nx), np.nan, dtype=np.float64)
        for j in range(1, Ny-1):
            dxj = dx_row[j]
            for i in range(1, Nx-1):
                if not (np.isfinite(Tm[j,i]) and np.isfinite(H0[j,i])): continue
                hTx_ip  = H0[j,i+1]*(Tm[j,i+1]-Tm[j,i])   / dxj
                hTx_im  = H0[j,i]  *(Tm[j,i]  -Tm[j,i-1]) / dxj
                dThx_ip = dT[j,i+1]*(H0[j,i+1]-H0[j,i])   / dxj
                dThx_im = dT[j,i]  *(H0[j,i]  -H0[j,i-1]) / dxj
                hTy_jp  = H0[j+1,i]*(Tm[j+1,i]-Tm[j,i])   / dy
                hTy_jm  = H0[j,i]  *(Tm[j,i]  -Tm[j-1,i]) / dy
                dThy_jp = dT[j+1,i]*(H0[j+1,i]-H0[j,i])   / dy
                dThy_jm = dT[j,i]  *(H0[j,i]  -H0[j-1,i]) / dy
                div1 = (hTx_ip - hTx_im)/dxj + (hTy_jp - hTy_jm)/dy
                div2 = (dThx_ip - dThx_im)/dxj + (dThy_jp - dThy_jm)/dy
                DIFF[j,i] = (ah / hden[j,i]) * (div1 - div2)

        # Vertical diffusion
        DIFFV = -(kv * Tz_mh) / hden

        # Tendencies
        if Tm_prev is None:
            TEN_F = np.full_like(Tm, np.nan, dtype=np.float64)
            TEN_C = np.full_like(Tm, np.nan, dtype=np.float64)
        else:
            TEN_F = (Tm - Tm_prev) / DT
            if Tm_prev_prev is None:
                TEN_C = np.full_like(Tm, np.nan, dtype=np.float64)
            else:
                # need Tm_next: compute once here
                Tm_next, _, _, _, _, _ = ml_avg_Tb_Tz_sfc(T1, U1, V1, H1, depth, topo)
                TEN_C = (Tm_next - Tm_prev_prev) / (2.0*DT)

        RHS  = QNET + ADV + ENT + DIFF + DIFFV
        CLOSF = TEN_F - RHS
        CLOSC = TEN_C - RHS

        # ---- save daily fields
        write_append(p_TML, Tm)
        write_append(p_TB,  Tb)
        write_append(p_T0,  T0z)

        write_append(p_UML, Um)
        write_append(p_VML, Vm)
        write_append(p_MLD, H0)

        write_append(p_TEN_F, TEN_F)
        write_append(p_TEN_C, TEN_C)
        write_append(p_ADV,   ADV)
        write_append(p_QNET,  QNET)
        write_append(p_ENT,   ENT)
        write_append(p_DIFF,  DIFF)
        write_append(p_DIFFV, DIFFV)
        write_append(p_CLOSF, CLOSF)
        write_append(p_CLOSC, CLOSC)

        if (ti % 10 == 0) or (ti == 1):
            print(f"[{year}] day {ti}/{len(files)-1} saved")

        # roll
        Tm_prev_prev = Tm_prev
        Tm_prev = Tm
        H_prev  = H0
        T0, U0, V0, H0 = T1, U1, V1, H1

    print(f"[OK] {year} done → {outdir}")

# ---------- driver ----------
def parse_years(s):
    if ":" in s:
        a,b = s.split(":")
        return list(range(int(a), int(b)+1))
    return [int(x) for x in s.split(",")]

def main():
    ap = argparse.ArgumentParser(description="D2-NF ML heat budget (Tm/Tb robust, daily incremental)")
    ap.add_argument("--indir",  default="/data3/GLORYS/Daily_93_21/glorys_subset")
    ap.add_argument("--outdir", default="/data3/GLORYS/ML_budget/output_gpt")
    ap.add_argument("--fluxdir",default="/data3/GLORYS/ML_budget/data")
    ap.add_argument("--years",  default="1993:2022")
    ap.add_argument("--workers",default="auto", help="parallel processes (auto=cores-1)")
    ap.add_argument("--ah", type=float, default=AH_DEF)
    ap.add_argument("--kv", type=float, default=KV_DEF)
    ap.add_argument("--hmin", type=float, default=HMIN_DEF, help="min thickness for denominators (m)")
    ap.add_argument("--use-hbar-denom", action="store_true", help="use hbar=(h_t+h_{t+Δt})/2 for denominators")

    # entrainment options (kept; defaults are conservative)
    ap.add_argument("--we-mode", choices=["full","deepening","dhdt","centered"], default="dhdt")
    ap.add_argument("--we-cap-md", type=float, default=None, help="cap |w_e| in m/day")
    ap.add_argument("--ent-only-cooling", action="store_true", default=True, help="force ENT ≤ 0")
    ap.add_argument("--dT-cap", type=float, default=None, help="cap |ΔT| used in ENT (K)")
    ap.add_argument("--ent-cap-kpd", type=float, default=None, help="cap |ENT| in K/day (guard)")

    args = ap.parse_args()

    years = parse_years(args.years)
    if args.workers == "auto":
        try:
            import multiprocessing as mp
            n_workers = max(1, mp.cpu_count()-1)
        except Exception:
            n_workers = 1
    else:
        n_workers = max(1, int(args.workers))

    if n_workers == 1 or len(years) == 1:
        for y in years:
            process_year(str(y), args.indir, args.outdir, args.fluxdir,
                         ah=args.ah, kv=args.kv, use_hbar_denom=args.use_hbar_denom,
                         hmin=args.hmin, we_mode=args.we_mode, we_cap_md=args.we_cap_md,
                         ent_only_cooling=args.ent_only_cooling, dT_cap=args.dT_cap,
                         ent_cap_kpd=args.ent_cap_kpd, save_we=False)
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as ex:
            futs = {
                ex.submit(process_year, str(y), args.indir, args.outdir, args.fluxdir,
                          args.ah, args.kv, args.use_hbar_denom, args.hmin,
                          args.we_mode, args.we_cap_md, args.ent_only_cooling,
                          args.dT_cap, args.ent_cap_kpd, False): y
            for y in years}
            for fut in as_completed(futs):
                y = futs[fut]
                try:
                    fut.result()
                except Exception as e:
                    print(f"[ERR] year {y}: {e}")

if __name__ == "__main__":
    main()

