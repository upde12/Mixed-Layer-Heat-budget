#!/usr/bin/env python3
"""Build MLHB monthly fields from SODA3.4.2 monthly NetCDF (GLORYS-equivalent).

Inputs
- One SODA monthly-mean file per year: soda3.4.2_mn_ocean_reg_YYYY.nc (time=12)
- Variables used: temp (°C), salt (psu), u (m/s), v (m/s), wt (m/s),
  mlp (m), net_heating (W/m^2), xt_ocean, yt_ocean, st_ocean (positive down)

Outputs
- Per-month NetCDF files with time=1 under --out-root:
  mlhb_monthly_soda_YYYYMM.nc
- Variables and units mirror GLORYS monthly outputs:
  T_ML (K), Tb (K), T0 (K), U_ML (m s-1), V_ML (m s-1), MLD (m),
  TEN, QNET, ADV, ENT, DIFF, DIFFV (all K day-1), CLOS_d2_ten (K day-1)

Notes
- Equations, signs, and units follow repo conventions (z↓; DIFFV>0 for upward flux).
- Monthly cadence: tendencies/divergences use monthly differencing; this yields a
  conservative approximation compared to daily GLORYS.
"""
from __future__ import annotations

import argparse
import calendar
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import xarray as xr


R_EARTH = 6_371_000.0
RHO = 1026.0
CP = 4000.0
SEC_PER_DAY = 86400.0


@dataclass
class Region:
    latmin: float
    latmax: float
    lonmin: float
    lonmax: float

    @classmethod
    def from_arg(cls, s: str | None) -> "Region | None":
        if not s:
            return None
        parts = [p.strip() for p in s.split(",")]
        if len(parts) != 4:
            raise SystemExit("--region must be 'latmin,latmax,lonmin,lonmax'")
        return cls(float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--soda-root", required=True, help="Directory with soda3.4.2_mn_ocean_reg_YYYY.nc files")
    p.add_argument("--years", required=True, help="Year or range A:B (e.g., 1993 or 1993:1993)")
    p.add_argument("--out-root", required=True, help="Output directory for per-month NetCDF files")
    p.add_argument("--region", default=None, help="latmin,latmax,lonmin,lonmax (optional subset)")
    p.add_argument("--ah", type=float, default=100.0, help="Lateral diffusivity A_h [m^2/s]")
    p.add_argument("--kv", type=float, default=1e-4, help="Vertical diffusivity K_v [m^2/s]")
    p.add_argument("--mld-source", choices=["mlp", "mlt", "recompute"], default="mlp")
    p.add_argument("--dsigma", type=float, default=0.03, help="Δσ0 threshold if --mld-source=recompute")
    p.add_argument("--ref-depth", type=float, default=10.0, help="Reference depth for Δσ0 MLD [m]")
    p.add_argument("--dpi", type=int, default=170)
    p.add_argument("--uv-fill-mode", choices=["none","nearest","zero"], default="nearest",
                   help="Fallback when no valid U/V in 0..h: nearest valid along z, zero, or none")
    # Debug / diagnostics
    p.add_argument("--emit-masks", action="store_true", help="Emit per-step boolean masks as separate NetCDFs")
    p.add_argument(
        "--mask-out-root",
        default=None,
        help="Output root for mask NetCDFs (default: <out-root>/debug_masks)",
    )
    return p.parse_args(argv)


def years_from_spec(spec: str) -> list[int]:
    if ":" in spec:
        a, b = spec.split(":", 1)
        return list(range(int(a), int(b) + 1))
    return [int(spec)]


def compute_edges(zc: np.ndarray) -> np.ndarray:
    """Return layer edge depths from center depths (positive down)."""
    zc = np.asarray(zc, dtype=float)
    nz = zc.size
    ze = np.empty(nz + 1, dtype=float)
    ze[0] = 0.0
    if nz > 1:
        ze[1:nz] = 0.5 * (zc[:-1] + zc[1:])
        ze[nz] = zc[-1] + (zc[-1] - zc[-2]) * 0.5
    else:
        ze[1] = zc[0]
    return ze


def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def to_K(c: np.ndarray) -> np.ndarray:
    return np.asarray(c, dtype=np.float64) + 273.15


def spherical_dx_dy(lat: np.ndarray, lon: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return grid spacing in meters for x (per row) and y (per column).

    lat, lon are 1D arrays in degrees (monotonic). Assumes regular spacing.
    """
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    dlat_deg = float(np.mean(np.diff(lat)))
    dlon_deg = float(np.mean(np.diff(lon)))
    dy = (np.pi / 180.0) * R_EARTH * dlat_deg  # constant per row
    dx_row = (np.pi / 180.0) * R_EARTH * dlon_deg * np.cos(np.deg2rad(lat))  # per-lat array
    return dx_row, dy


def central_diff_x(field: np.ndarray, dx_row: np.ndarray) -> np.ndarray:
    """Central difference in x (lon), spacing per latitude row."""
    f = np.asarray(field, dtype=np.float64)
    ny, nx = f.shape
    out = np.empty_like(f)
    # interior
    out[:, 1:-1] = (f[:, 2:] - f[:, :-2]) / (dx_row[:, None] * 2.0)
    # edges
    out[:, 0] = (f[:, 1] - f[:, 0]) / dx_row
    out[:, -1] = (f[:, -1] - f[:, -2]) / dx_row
    return out


def central_diff_y(field: np.ndarray, dy: float) -> np.ndarray:
    f = np.asarray(field, dtype=np.float64)
    ny, nx = f.shape
    out = np.empty_like(f)
    out[1:-1, :] = (f[2:, :] - f[:-2, :]) / (2.0 * dy)
    out[0, :] = (f[1, :] - f[0, :]) / dy
    out[-1, :] = (f[-1, :] - f[-2, :]) / dy
    return out


def layer_mean_t(Tz: np.ndarray, dz: np.ndarray, zc: np.ndarray, ze: np.ndarray, h: np.ndarray) -> np.ndarray:
    """Return thickness-weighted 0→h mean temperature in K.

    Tz: (nz, ny, nx) in °C; dz: (nz,), zc: (nz,), ze: (nz+1,), h: (ny, nx)
    """
    nz, ny, nx = Tz.shape
    hf = h.ravel()
    Kf = np.searchsorted(ze, hf, side="right") - 1
    Kf = np.clip(Kf, 0, nz - 1)
    K = Kf.reshape(h.shape)
    zeK = ze[K]
    part = (h - zeK)
    Tdz = Tz * dz[:, None, None]
    cT = np.cumsum(Tdz, axis=0)
    full = np.zeros((ny, nx), dtype=np.float64)
    mk = (K > 0)
    if np.any(mk):
        jj, ii = np.where(mk)
        full[mk] = cT[K[mk] - 1, jj, ii]
    jj_all = np.arange(ny)[:, None]
    ii_all = np.arange(nx)[None, :]
    TK = Tz[K, jj_all, ii_all]
    num = full + TK * part
    denom = np.where(h > 0, h, np.nan)
    return to_K(num / denom)


def compute_mld_sigma0_from_prho(
    prho_t: np.ndarray,
    zc: np.ndarray,
    ref_depth: float = 10.0,
    dsigma: float = 0.03,
    min_h: float = 5.0,
) -> np.ndarray:
    """Compute MLD from potential density (per time slice).

    prho_t: (nz, ny, nx) potential density [kg/m^3]; zc positive-down centers.
    Returns h (ny, nx) in meters; NaN where insufficient data.
    """
    nz, ny, nx = prho_t.shape
    sigma = prho_t - 1000.0
    h = np.full((ny, nx), np.nan, dtype=np.float64)
    # reference index around ref_depth
    k_ref = int(np.clip(np.searchsorted(zc, ref_depth, side="right") - 1, 0, nz - 2))
    zlo_ref = zc[k_ref]
    zhi_ref = zc[k_ref + 1]
    w_ref = (ref_depth - zlo_ref) / (zhi_ref - zlo_ref + 1e-12)
    # interpolate sigma at ref depth
    sig_ref = sigma[k_ref, :, :] + w_ref * (sigma[k_ref + 1, :, :] - sigma[k_ref, :, :])
    # search crossing from k_ref+1 downward direction (increasing depth)
    for j in range(ny):
        for i in range(nx):
            col = sigma[:, j, i]
            if not np.isfinite(sig_ref[j, i]):
                continue
            found = False
            prev_val = col[k_ref] - sig_ref[j, i]
            for k in range(k_ref + 1, nz):
                val = col[k] - sig_ref[j, i]
                if np.isfinite(val) and np.isfinite(prev_val):
                    if val >= dsigma:
                        # linear interpolation between k-1 and k
                        z0 = zc[k - 1]; z1 = zc[k]
                        d0 = prev_val; d1 = val
                        frac = (dsigma - d0) / (d1 - d0 + 1e-12)
                        zz = z0 + np.clip(frac, 0.0, 1.0) * (z1 - z0)
                        h[j, i] = zz
                        found = True
                        break
                prev_val = val
            if not found:
                # no crossing → keep NaN; caller may fallback
                pass
    # enforce minimum/maximum reasonable bounds
    h = np.where(np.isfinite(h), np.clip(h, min_h, zc[-1] - 1e-6), h)
    return h


def month_time_value(year: int, month: int) -> np.datetime64:
    return np.datetime64(f"{year:04d}-{month:02d}-01")


def subset_to_region(ds: xr.Dataset, reg: Region | None) -> xr.Dataset:
    if reg is None:
        return ds
    # SODA longitudes are 0..360 (degrees_E). ECS is 109..146E → direct slice.
    sel_kwargs = {}
    if "yt_ocean" in ds.coords:
        ysel_t = (ds["yt_ocean"] >= reg.latmin) & (ds["yt_ocean"] <= reg.latmax)
        sel_kwargs["yt_ocean"] = ysel_t
        ny_t = int(ysel_t.sum())
    else:
        ny_t = None
    if "xt_ocean" in ds.coords:
        xsel_t = (ds["xt_ocean"] >= reg.lonmin) & (ds["xt_ocean"] <= reg.lonmax)
        sel_kwargs["xt_ocean"] = xsel_t
        nx_t = int(xsel_t.sum())
    else:
        nx_t = None
    # Also subset staggered U/V grid if present to keep alignment
    if "yu_ocean" in ds.coords:
        ysel_u = (ds["yu_ocean"] >= reg.latmin) & (ds["yu_ocean"] <= reg.latmax)
        if ny_t is not None:
            # Align counts with tracer grid by trimming from edges if needed
            ny_u = int(ysel_u.sum())
            if ny_u != ny_t and ny_u > 0:
                idx = np.where(ysel_u.values)[0]
                if ny_u > ny_t:
                    d = ny_u - ny_t
                    s = d // 2
                    idx = idx[s:s + ny_t]
                else:  # ny_u < ny_t → pad by extending one cell each side if available
                    need = ny_t - ny_u
                    pre = max(idx[0] - (need // 2), 0)
                    post = pre + ny_t
                    idx = np.arange(pre, min(post, ds["yu_ocean"].size))
                ymask = np.zeros(ds["yu_ocean"].size, dtype=bool)
                ymask[idx] = True
                ysel_u = xr.DataArray(ymask, dims=("yu_ocean",))
        sel_kwargs["yu_ocean"] = ysel_u
    if "xu_ocean" in ds.coords:
        xsel_u = (ds["xu_ocean"] >= reg.lonmin) & (ds["xu_ocean"] <= reg.lonmax)
        if nx_t is not None:
            nx_u = int(xsel_u.sum())
            if nx_u != nx_t and nx_u > 0:
                idx = np.where(xsel_u.values)[0]
                if nx_u > nx_t:
                    d = nx_u - nx_t
                    s = d // 2
                    idx = idx[s:s + nx_t]
                else:
                    need = nx_t - nx_u
                    pre = max(idx[0] - (need // 2), 0)
                    post = pre + nx_t
                    idx = np.arange(pre, min(post, ds["xu_ocean"].size))
                xmask = np.zeros(ds["xu_ocean"].size, dtype=bool)
                xmask[idx] = True
                xsel_u = xr.DataArray(xmask, dims=("xu_ocean",))
        sel_kwargs["xu_ocean"] = xsel_u
    return ds.sel(**sel_kwargs)


def write_month_nc(path: Path, lat: np.ndarray, lon: np.ndarray, **vars2d):
    ds = xr.Dataset()
    # 1D CF-compliant coordinate variables
    ds = ds.assign_coords(lat=("lat", lat.astype(np.float32)))
    ds = ds.assign_coords(lon=("lon", lon.astype(np.float32)))
    ds["lat"].attrs = {
        "long_name": "latitude",
        "standard_name": "latitude",
        "units": "degrees_north",
    }
    ds["lon"].attrs = {
        "long_name": "longitude",
        "standard_name": "longitude",
        "units": "degrees_east",
    }
    for name, val in vars2d.items():
        if name == "_time_value":
            continue
        data, units, long_name = val
        da = xr.DataArray(np.asarray(data, dtype=np.float32), dims=("lat", "lon"))
        da.attrs["units"] = units
        da.attrs["long_name"] = long_name
        ds[name] = da
    # time coord (single value)
    t0 = vars2d.get("_time_value")
    if t0 is None:
        raise SystemExit("Internal error: missing _time_value")
    time_val = np.array([t0[0]], dtype="datetime64[ns]")
    ds = ds.expand_dims(time=time_val)
    # Ensure time coordinate exists and only encoding carries CF units/calendar
    ds["time"] = xr.DataArray(time_val, dims=("time",))
    ds["time"].attrs = {"long_name": "time"}
    # Order dimensions as (time, lat, lon) for all variables
    ds = ds.transpose("time", "lat", "lon")
    encoding = {var: {"zlib": True, "complevel": 4} for var in ds.data_vars}
    encoding.update({coord: {"zlib": False} for coord in ds.coords if coord != "time"})
    encoding["time"] = {
        "dtype": "f8",
        "_FillValue": None,
        "units": "days since 1970-01-01 00:00:00",
        "calendar": "standard",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / (path.name + ".tmp")
    ds.to_netcdf(
        tmp,
        mode="w",
        engine="netcdf4",
        format="NETCDF4_CLASSIC",
        encoding=encoding,
        unlimited_dims="time",
    )
    tmp.replace(path)


def build_one_year(
    year: int,
    soda_root: Path,
    out_root: Path,
    region: Region | None,
    ah: float,
    kv: float,
    mld_source: str,
    *,
    emit_masks: bool = False,
    mask_out_root: Path | None = None,
    uv_fill_mode: str = "nearest",
) -> None:
    fn = soda_root / f"soda3.4.2_mn_ocean_reg_{year}.nc"
    if not fn.exists():
        raise FileNotFoundError(fn)
    ds = xr.open_dataset(fn)
    ds = subset_to_region(ds, region)
    # Coordinates
    lat = ds["yt_ocean"].values.astype(np.float64)
    lon = ds["xt_ocean"].values.astype(np.float64)
    zc = ds["st_ocean"].values.astype(np.float64)
    ze = compute_edges(zc)
    dz = ze[1:] - ze[:-1]
    nz = zc.size

    # Metric spacings
    dx_row, dy = spherical_dx_dy(lat, lon)

    # Time count
    nt = int(ds.dims.get("time", ds["time"].size))
    if nt != 12:
        print(f"[WARN] year {year}: time={nt} (expected 12)")

    # Load variables (all as float64)
    temp = ds["temp"].values.astype(np.float64)  # (time, z, y, x) in °C
    salt = ds["salt"].values.astype(np.float64)
    u = ds["u"].values.astype(np.float64)
    v = ds["v"].values.astype(np.float64)
    wt = ds["wt"].values.astype(np.float64) if "wt" in ds else np.zeros_like(temp)
    # MLD with fallbacks (mlp -> mlt -> mls) or recompute from prho
    if mld_source == "recompute":
        if "prho" not in ds:
            raise SystemExit("--mld-source=recompute requires variable 'prho' in SODA file")
        prho = ds["prho"].values.astype(np.float64)  # (time,z,y,x)
        mld = np.empty((nt, lat.size, lon.size), dtype=np.float64)
        for it in range(nt):
            mld[it, :, :] = compute_mld_sigma0_from_prho(prho[it, :, :, :], zc, ref_depth=10.0, dsigma=0.03, min_h=5.0)
        mld_long_name = "Mixed-layer depth (Δσ0 recompute @10 m)"
    elif mld_source == "mlp":
        mlp = ds["mlp"].values.astype(np.float64) if "mlp" in ds else None
        mlt = ds["mlt"].values.astype(np.float64) if "mlt" in ds else None
        mls = ds["mls"].values.astype(np.float64) if "mls" in ds else None
        base = np.full((nt, lat.size, lon.size), np.nan, dtype=np.float64)
        if mlp is not None:
            base = np.where(np.isfinite(mlp), mlp, base)
        if mlt is not None:
            base = np.where(np.isnan(base) & np.isfinite(mlt), mlt, base)
        if mls is not None:
            base = np.where(np.isnan(base) & np.isfinite(mls), mls, base)
        mld = base
        mld_long_name = "Mixed-layer depth (SODA mlp)"
    elif mld_source == "mlt":
        mlt = ds["mlt"].values.astype(np.float64) if "mlt" in ds else None
        mlp = ds["mlp"].values.astype(np.float64) if "mlp" in ds else None
        mls = ds["mls"].values.astype(np.float64) if "mls" in ds else None
        base = np.full((nt, lat.size, lon.size), np.nan, dtype=np.float64)
        if mlt is not None:
            base = np.where(np.isfinite(mlt), mlt, base)
        if mlp is not None:
            base = np.where(np.isnan(base) & np.isfinite(mlp), mlp, base)
        if mls is not None:
            base = np.where(np.isnan(base) & np.isfinite(mls), mls, base)
        mld = base
        mld_long_name = "Mixed-layer depth (SODA mlt)"
    else:
        mld = None
        mld_long_name = "Mixed-layer depth"

    # Surface net heating (common)
    qnet_wm2 = ds["net_heating"].values.astype(np.float64) if "net_heating" in ds else None

    # Helper closures
    def gather_csum(arr_csum: np.ndarray, k_idx: np.ndarray) -> np.ndarray:
        """Gather cumulative sum at (k_idx-1), with 0 where k_idx==0.

        arr_csum shape: (nz, ny, nx); k_idx shape: (ny, nx)
        """
        ny, nx = k_idx.shape
        out = np.zeros((ny, nx), dtype=np.float64)
        # mask where k>0
        mk = k_idx > 0
        if np.any(mk):
            sel = arr_csum[k_idx[mk] - 1, np.where(mk)[0], np.where(mk)[1]]
            out[mk] = sel
        return out

    # Precompute cumulative dz
    csum_dz = np.cumsum(dz)

    # Loop months
    for it in range(nt):
        month = it + 1
        # Per-time slices
        Tz = temp[it, :, :, :]  # z,y,x (°C)
        Sz = salt[it, :, :, :]
        Uz = u[it, :, :, :]
        Vz = v[it, :, :, :]
        # Ocean mask from surface temperature (diagnostic variants captured below)
        mask_surface_T = np.isfinite(Tz[0, :, :])
        mask_any_T = np.isfinite(Tz).any(axis=0)
        mask_ocean = mask_surface_T.copy()
        # MLD for this month with fallback only over ocean
        h_raw = (mld[it, :, :] if mld is not None else np.full(Tz.shape[1:], np.nan))
        mask_h_raw = np.isfinite(h_raw)
        h = h_raw.copy()
        h = np.where(mask_ocean & ~np.isfinite(h), 20.0, h)
        h = np.where(np.isfinite(h), np.clip(h, 0.5, ze[-1] - 1e-6), np.nan)
        mask_h_final = np.isfinite(h)

        # Surface temperature (approx z=0 ⇒ level 0)
        T0 = to_K(Tz[0, :, :])
        T0[~mask_ocean] = np.nan

        # Indices where MLD falls within layer: K s.t. ze[K] < h <= ze[K+1]
        # Using searchsorted on flattened arrays
        hf = h.ravel()
        Kf = np.searchsorted(ze, hf, side="right") - 1  # 0..nz-1
        Kf = np.clip(Kf, 0, nz - 1)
        K = Kf.reshape(h.shape)
        # Partial thickness at K: (h - ze[K])
        zeK = ze[K]
        part = (h - zeK)

        # Thickness-weighted means
        dz3 = dz[:, None, None]

        # T_ML: original thickness-weighted mean (assume near-complete coverage)
        Tdz = Tz * dz3
        cT = np.cumsum(Tdz, axis=0)
        full_T = gather_csum(cT, K)
        TK = Tz[K, np.arange(h.shape[0])[:, None], np.arange(h.shape[1])[None, :]]
        num_T = full_T + TK * part
        denom_T = np.where(h > 0, h, np.nan)
        T_ML = to_K(num_T / denom_T)

        # U_ML: NaN-robust thickness-weighted mean
        mU = np.isfinite(Uz)
        Udz = np.where(mU, Uz * dz3, 0.0)
        cU = np.cumsum(Udz, axis=0)
        full_U = gather_csum(cU, K)
        UK = Uz[K, np.arange(h.shape[0])[:, None], np.arange(h.shape[1])[None, :]]
        UK_part = np.where(np.isfinite(UK) & (part > 0), UK * part, 0.0)
        denU_c = np.cumsum(np.where(mU, dz3, 0.0), axis=0)
        denU_full = gather_csum(denU_c, K)
        denU_part = np.where(np.isfinite(UK) & (part > 0), part, 0.0)
        den_U = denU_full + denU_part
        U_ML = np.where(den_U > 0, (full_U + UK_part) / den_U, np.nan)

        # V_ML: NaN-robust thickness-weighted mean
        mV = np.isfinite(Vz)
        Vdz = np.where(mV, Vz * dz3, 0.0)
        cV = np.cumsum(Vdz, axis=0)
        full_V = gather_csum(cV, K)
        VK = Vz[K, np.arange(h.shape[0])[:, None], np.arange(h.shape[1])[None, :]]
        VK_part = np.where(np.isfinite(VK) & (part > 0), VK * part, 0.0)
        denV_c = np.cumsum(np.where(mV, dz3, 0.0), axis=0)
        denV_full = gather_csum(denV_c, K)
        denV_part = np.where(np.isfinite(VK) & (part > 0), part, 0.0)
        den_V = denV_full + denV_part
        V_ML = np.where(den_V > 0, (full_V + VK_part) / den_V, np.nan)

        # Optional fallback: if no valid U/V in 0..h, fill by nearest valid level or zero
        empty_U = ~(den_U > 0)
        empty_V = ~(den_V > 0)
        if uv_fill_mode != "none":
            rows = np.arange(h.shape[0])[:, None]
            cols = np.arange(h.shape[1])[None, :]
            if uv_fill_mode == "zero":
                U_ML[empty_U] = 0.0
                V_ML[empty_V] = 0.0
            else:  # nearest along z from top
                hasU = mU.any(axis=0)
                fillU = empty_U & hasU
                if np.any(fillU):
                    ktopU = np.argmax(mU, axis=0)
                    U_top = Uz[ktopU, rows, cols]
                    U_ML[fillU] = U_top[fillU]
                hasV = mV.any(axis=0)
                fillV = empty_V & hasV
                if np.any(fillV):
                    ktopV = np.argmax(mV, axis=0)
                    V_top = Vz[ktopV, rows, cols]
                    V_ML[fillV] = V_top[fillV]
        for arr in (T_ML, U_ML, V_ML):
            arr[~mask_ocean] = np.nan

        # Tb: linear interpolation at z=-h between nearest centers
        # Find lower/upper center indices around h
        # Use Kc: index of center just below h
        Kc = np.searchsorted(zc, hf, side="right") - 1
        Kc = np.clip(Kc, 0, nz - 2)  # ensure Kc+1 valid
        Kc = Kc.reshape(h.shape)
        z0 = zc[Kc]
        z1 = zc[Kc + 1]
        T0c = Tz[Kc, np.arange(h.shape[0])[:, None], np.arange(h.shape[1])[None, :]]
        T1c = Tz[Kc + 1, np.arange(h.shape[0])[:, None], np.arange(h.shape[1])[None, :]]
        w = np.where(z1 > z0, (h - z0) / (z1 - z0 + 1e-12), 0.0)
        Tb = to_K(T0c + w * (T1c - T0c))
        Tb[~mask_ocean] = np.nan

        # Horizontal gradients of T_ML
        dTdx = central_diff_x(T_ML, dx_row)
        dTdy = central_diff_y(T_ML, dy)
        ADV = -(U_ML * dTdx + V_ML * dTdy) * SEC_PER_DAY
        ADV[~mask_ocean] = np.nan
        mask_grad = np.isfinite(dTdx) & np.isfinite(dTdy)
        mask_adv = np.isfinite(ADV)

        # w_e = ∂t h + ∇·(hU, hV)
        if it == 0:
            dhdt = ( (mld[it + 1, :, :] if mld is not None else h) - h ) / (days_in_month(year, month) * SEC_PER_DAY)
        elif it == nt - 1:
            dhdt = ( h - (mld[it - 1, :, :] if mld is not None else h) ) / (days_in_month(year, month) * SEC_PER_DAY)
        else:
            dt1 = days_in_month(year, month)
            dt2 = days_in_month(year, month + 1)
            dhf = ( (mld[it + 1, :, :] - mld[it - 1, :, :]) if mld is not None else 0.0 )
            dhdt = dhf / ((dt1 + dt2) * 0.5 * SEC_PER_DAY)
        hU = h * U_ML
        hV = h * V_ML
        div = central_diff_x(hU, dx_row) + central_diff_y(hV, dy)
        we = dhdt + div
        ENT = (we / np.where(h > 0, h, np.nan)) * (Tb - T_ML) * SEC_PER_DAY
        ENT[~mask_ocean] = np.nan
        mask_dhdt = np.isfinite(dhdt)
        mask_div = np.isfinite(div)
        mask_we = np.isfinite(we)
        mask_ent = np.isfinite(ENT)

        # DIFF: (A_h/h) * ∇·(h ∇T)
        gTx = central_diff_x(T_ML, dx_row)
        gTy = central_diff_y(T_ML, dy)
        flux_x = h * gTx
        flux_y = h * gTy
        div_hgT = central_diff_x(flux_x, dx_row) + central_diff_y(flux_y, dy)
        DIFF = (ah / np.where(h > 0, h, np.nan)) * div_hgT * SEC_PER_DAY
        DIFF[~mask_ocean] = np.nan

        # DIFFV: (K_v/h)·(∂T/∂z)|_{-h} (z↓)
        dTdz = (T1c - T0c) / (z1 - z0 + 1e-12)
        DIFFV = (kv / np.where(h > 0, h, np.nan)) * dTdz * SEC_PER_DAY
        DIFFV[~mask_ocean] = np.nan

        # QNET
        if qnet_wm2 is None:
            QNET = np.zeros_like(T_ML)
        else:
            QNET = (qnet_wm2[it, :, :] / (RHO * CP * np.where(h > 0, h, np.nan))) * SEC_PER_DAY
            QNET[~mask_ocean] = np.nan
        mask_qnet = np.isfinite(QNET)

        # TEN: monthly tendency of T_ML using month-specific MLD for next/prev
        if it == 0:
            h_next = (mld[it + 1, :, :] if mld is not None else h)
            T_next = layer_mean_t(temp[it + 1, :, :, :], dz, zc, ze, h_next)
            TEN = (T_next - T_ML) / days_in_month(year, month)
        elif it == nt - 1:
            h_prev = (mld[it - 1, :, :] if mld is not None else h)
            T_prev = layer_mean_t(temp[it - 1, :, :, :], dz, zc, ze, h_prev)
            TEN = (T_ML - T_prev) / days_in_month(year, month)
        else:
            h_next = (mld[it + 1, :, :] if mld is not None else h)
            h_prev = (mld[it - 1, :, :] if mld is not None else h)
            T_next = layer_mean_t(temp[it + 1, :, :, :], dz, zc, ze, h_next)
            T_prev = layer_mean_t(temp[it - 1, :, :, :], dz, zc, ze, h_prev)
            TEN = (T_next - T_prev) / ((days_in_month(year, month) + days_in_month(year, month + 1)) * 0.5)
        TEN[~mask_ocean] = np.nan
        mask_ten = np.isfinite(TEN)

        # Closure residual
        CLOS = TEN - (QNET + ADV + ENT + DIFF + DIFFV)
        CLOS[~mask_ocean] = np.nan
        mask_clos = np.isfinite(CLOS)

        # Compute masks at the end (after any filling and masking)
        mask_tml = np.isfinite(T_ML)
        mask_u_ml = np.isfinite(U_ML)
        mask_v_ml = np.isfinite(V_ML)

        # Write per-month file
        out_path = out_root / f"mlhb_monthly_soda_{year:04d}{month:02d}.nc"
        write_month_nc(
            out_path,
            lat=lat,
            lon=lon,
            _time_value=(month_time_value(year, month), "time value"),
            T_ML=(T_ML, "K", "Mixed-layer temperature"),
            Tb=(Tb, "K", "Temperature at -h"),
            T0=(T0, "K", "Sea surface temperature (z≈0)"),
            U_ML=(U_ML, "m s-1", "Mixed-layer zonal velocity"),
            V_ML=(V_ML, "m s-1", "Mixed-layer meridional velocity"),
            MLD=(h, "m", mld_long_name if 'mld_long_name' in locals() else "Mixed-layer depth"),
            TEN=(TEN, "K day-1", "Monthly tendency of T_ML"),
            QNET=(QNET, "K day-1", "Surface net heat flux / (rho*cp*h)"),
            ADV=(ADV, "K day-1", "Horizontal advection of T_ML"),
            ENT=(ENT, "K day-1", "Entrainment term"),
            DIFF=(DIFF, "K day-1", "Lateral diffusion term"),
            DIFFV=(DIFFV, "K day-1", "Vertical diffusion term"),
            CLOS_d2_ten=(CLOS, "K day-1", "Closure residual: TEN-(QNET+ADV+ENT+DIFF+DIFFV)"),
        )
        print(f"[OK] {year}-{month:02d} → {out_path}")

        # Optional: emit boolean masks for diagnostics
        if emit_masks:
            mroot = mask_out_root if mask_out_root is not None else (out_root / "debug_masks")
            mroot.mkdir(parents=True, exist_ok=True)
            mout = mroot / f"mlhb_monthly_soda_{year:04d}{month:02d}_masks.nc"
            def as_u8(a: np.ndarray) -> np.ndarray:
                return np.asarray(a, dtype=np.uint8)
            write_month_nc(
                mout,
                lat=lat,
                lon=lon,
                _time_value=(month_time_value(year, month), "time value"),
                MASK_SURFACE_T=(as_u8(mask_surface_T), "1", "Finite surface temperature (z≈5 m)"),
                MASK_ANY_T=(as_u8(mask_any_T), "1", "Any finite temperature along column"),
                MASK_OCEAN=(as_u8(mask_ocean), "1", "Ocean mask used in pipeline (surface-based)"),
                MASK_H_RAW=(as_u8(mask_h_raw), "1", "Raw MLD (provided/recomputed) finite"),
                MASK_H_FINAL=(as_u8(mask_h_final), "1", "Final MLD after fallback/clip finite"),
                MASK_T_ML=(as_u8(mask_tml), "1", "Finite mixed-layer temperature"),
                MASK_U_ML=(as_u8(mask_u_ml), "1", "Finite mixed-layer zonal velocity"),
                MASK_V_ML=(as_u8(mask_v_ml), "1", "Finite mixed-layer meridional velocity"),
                MASK_GRAD_T=(as_u8(mask_grad), "1", "Finite horizontal gradients of T_ML"),
                MASK_ADV=(as_u8(mask_adv), "1", "Finite ADV term"),
                MASK_DHDT=(as_u8(mask_dhdt), "1", "Finite dh/dt (time derivative of MLD)"),
                MASK_DIV_HU=(as_u8(mask_div), "1", "Finite divergence of hU,hV"),
                MASK_WE=(as_u8(mask_we), "1", "Finite entrainment velocity w_e"),
                MASK_ENT=(as_u8(mask_ent), "1", "Finite ENT term"),
                MASK_QNET=(as_u8(mask_qnet), "1", "Finite QNET term"),
                MASK_TEN=(as_u8(mask_ten), "1", "Finite TEN term"),
                MASK_CLOS=(as_u8(mask_clos), "1", "Finite closure residual"),
            )
            print(f"[OK] masks → {mout}")

    ds.close()


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    soda_root = Path(args.soda_root)
    out_root = Path(args.out_root)
    region = Region.from_arg(args.region)
    ys = years_from_spec(args.years)
    mask_out_root = Path(args.mask_out_root) if args.mask_out_root else None
    for y in ys:
        build_one_year(
            y,
            soda_root,
            out_root,
            region,
            args.ah,
            args.kv,
            args.mld_source,
            emit_masks=args.emit_masks,
            mask_out_root=mask_out_root,
            uv_fill_mode=args.uv_fill_mode,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
