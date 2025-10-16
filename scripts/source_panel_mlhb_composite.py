#!/usr/bin/env python3
"""Composite MLHB anomalies for ELT years by month.

For a list of ELT years (e.g., 1998,2010,2016,2020), compute monthly composite
anomalies (target month across ELT years minus climatological monthly mean over
all available years). Renders a 3×2 terms panel and a separate T_ML map for
each requested month.

Inputs are monthly MLHB NetCDF files named like .../mlhb_monthly_main_YYYYMM.nc
(time=1 per file) containing variables in K day^-1 for budget terms and K for
T_ML.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
except Exception:
    ccrs = None
    cfeature = None


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--monthly-root", required=True, help="Directory that contains monthly files mlhb_monthly_main_YYYYMM.nc")
    p.add_argument("--years", required=True, help="Comma-separated ELT years, e.g., 1998,2010,2016,2020")
    p.add_argument("--out-root", required=True, help="Output directory for PNGs")
    p.add_argument("--months", default="prev11,prev12,1-12", help="Months to render: use 'prev11,prev12,1-12' or explicit list like 1,2,3")
    p.add_argument(
        "--grid-tml-years",
        default=None,
        help="Comma-separated years to render as a single T_ML grid",
    )
    p.add_argument(
        "--grid-tml-rows",
        choices=["months","years"],
        default="months",
        help="Grid orientation for T_ML grid: rows are 'months' (12×N) or 'years' (N×12)",
    )
    p.add_argument(
        "--grid-tml-aggregate",
        choices=["none","3mo-prev10"],
        default="none",
        help="Aggregate T_ML grid over 3‑month windows starting at prev Oct (prevOND, JFM, AMJ, JAS, OND)",
    )
    p.add_argument(
        "--grid-include-mean",
        action="store_true",
        help="In grid mode with rows=years, add a top row with the mean across the selected years (per month/window)",
    )
    p.add_argument(
        "--grid-mean-scale",
        type=float,
        default=1.0,
        help="Scale factor applied only to the MEAN row (visual exaggeration)",
    )
    p.add_argument(
        "--grid-mean-sig",
        choices=["off","hatch","mask"],
        default="hatch",
        help="Significance marking for MEAN row (two-sided t-test vs 0 at 95%%): 'hatch' (default) or 'off'",
    )
    p.add_argument(
        "--overlay-source",
        choices=["none","qnet","soda-net"],
        default="qnet",
        help="Contour overlay: 'none' (off), 'qnet' from monthly outputs, or 'soda-net' from raw SODA net_heating (W m^-2)",
    )
    p.add_argument("--overlay-pos-color", default="#b2182b",
                   help="Overlay color for positive heating contours (default: deep red)")
    p.add_argument("--overlay-neg-color", default="#2166ac",
                   help="Overlay color for negative cooling contours (default: deep blue)")
    p.add_argument("--overlay-zero-color", default="#000000",
                   help="Overlay color for zero contour (default: black)")
    p.add_argument("--overlay-lw", type=float, default=0.9,
                   help="Line width for positive/negative overlay contours (default: 0.9)")
    p.add_argument("--overlay-zero-lw", type=float, default=0.8,
                   help="Line width for zero overlay contour (default: 0.8)")
    p.add_argument("--overlay-alpha", type=float, default=0.9,
                   help="Alpha for all overlay contours (default: 0.9)")
    p.add_argument("--overlay-nlevels", type=int, default=3,
                   help="Number of positive/negative contour levels per side (default: 4)")
    p.add_argument(
        "--soda-root",
        default="/Volumes/HJPARK4/soda",
        help="Root directory for SODA monthly files (soda3.4.2_mn_ocean_reg_YYYY.nc) when overlay-source=soda-net",
    )
    p.add_argument("--lon-max", type=float, default=None, help="Optional max longitude for map extent (e.g., 140.0)")
    p.add_argument("--aggregate-season", choices=["none","MJJAS","ONDJ"], default="none", help="If set, average the specified season into a single panel")
    p.add_argument("--diffv-mode", choices=["native","residual"], default="native")
    p.add_argument("--adv-smooth-iter", type=int, default=0)
    p.add_argument("--rhs-prc", type=float, default=98.0)
    p.add_argument("--unit", choices=["day","month"], default="day")
    p.add_argument("--dpi", type=int, default=180)
    p.add_argument("--twelve-vars", default="T_ML", help="Comma-separated variables to assemble into a 12-month 6×2 panel (choices: T_ML,TEN,QNET,ADV,ENT,DIFF,DIFFV,SUBS)")
    return p.parse_args(argv)


def month_list(spec: str) -> List[Tuple[int,bool]]:
    """Return list of (month, is_prev_year) from spec.

    Example: 'prev11,prev12,1-12' -> [(11,True),(12,True),(1,False)...(12,False)]
    """
    out: List[Tuple[int,bool]] = []
    parts = [s.strip() for s in spec.split(',') if s.strip()]
    for token in parts:
        if token.startswith('prev'):
            m = int(token.replace('prev',''))
            out.append((m, True))
        elif '-' in token:
            a,b = token.split('-',1)
            for m in range(int(a), int(b)+1):
                out.append((m, False))
        else:
            out.append((int(token), False))
    return out


def open_month_file(root: Path, year: int, month: int) -> xr.Dataset:
    """Open a monthly MLHB file. Supports 'main' and 'soda' naming."""
    cand = [
        root / f"mlhb_monthly_main_{year:04d}{month:02d}.nc",
        root / f"mlhb_monthly_soda_{year:04d}{month:02d}.nc",
    ]
    for fn in cand:
        if fn.exists():
            return xr.open_dataset(fn)
    raise FileNotFoundError(cand[0])

def month_abbrev(idx: int) -> str:
    names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    return names[idx-1] if 1 <= idx <= 12 else str(idx)

def months_for_season(name: str) -> List[Tuple[int,bool]]:
    if name == "MJJAS":
        return [(5, False),(6, False),(7, False),(8, False),(9, False)]
    if name == "ONDJ":
        return [(10, True),(11, True),(12, True),(1, False)]
    return []


def mean_stack(dsets: List[xr.Dataset]) -> xr.Dataset:
    if not dsets:
        raise SystemExit("No datasets to average")
    ds = xr.concat(dsets, dim="stack")
    out = ds.mean("stack", skipna=True, keep_attrs=True)
    for d in dsets:
        try: d.close()
        except Exception: pass
    return out


def lighten_cmap(base: str = 'RdBu_r', lighten: float = 0.25) -> mcolors.Colormap:
    """Return a lightened version of a base colormap by blending towards white.

    lighten in [0,1]: 0=no change, 0.25=25% towards white.
    """
    base_cmap = plt.get_cmap(base)
    N = 256
    cols = base_cmap(np.linspace(0, 1, N))
    cols[:, :3] = cols[:, :3] * (1.0 - lighten) + lighten
    return mcolors.ListedColormap(cols)


def smth9_2d(a: np.ndarray, p: float = 0.50, q: float = 0.25) -> np.ndarray:
    ny, nx = a.shape
    def shift(di, dj):
        out = np.full_like(a, np.nan)
        si0, si1 = (0, ny-di) if di>=0 else (-di, ny)
        di0, di1 = (di, ny) if di>=0 else (0, ny+di)
        sj0, sj1 = (0, nx-dj) if dj>=0 else (-dj, nx)
        dj0, dj1 = (dj, nx) if dj>=0 else (0, nx+dj)
        if si1>si0 and sj1>sj0:
            out[di0:di1, dj0:dj1] = a[si0:si1, sj0:sj1]
        return out
    c = a
    n = shift(-1,0); s = shift(1,0); w = shift(0,-1); e = shift(0,1)
    nw = shift(-1,-1); ne = shift(-1,1); sw = shift(1,-1); se = shift(1,1)
    valid = np.isfinite(c)&np.isfinite(n)&np.isfinite(s)&np.isfinite(w)&np.isfinite(e)&np.isfinite(nw)&np.isfinite(ne)&np.isfinite(sw)&np.isfinite(se)
    out = c.copy()
    if np.any(valid):
        sides = w + e + n + s
        corners = nw + ne + sw + se
        out[valid] = c[valid] + (p/4.0)*(sides[valid]-4.0*c[valid]) + (q/4.0)*(corners[valid]-4.0*c[valid])
    out[~np.isfinite(c)] = np.nan
    return out


def maybe_smooth(da: xr.DataArray, iters: int) -> xr.DataArray:
    if iters<=0: return da
    arr = da.values.copy()
    for _ in range(iters): arr = smth9_2d(arr)
    return da.copy(data=arr)


def add_map(ax, left: bool, bottom: bool) -> None:
    if ccrs is None:
        if bottom: ax.set_xlabel("Longitude")
        if left:   ax.set_ylabel("Latitude")
        return
    try:
        land50 = cfeature.NaturalEarthFeature('physical','land','50m', edgecolor='black', facecolor='lightgrey', linewidth=0.6)
        ax.add_feature(land50, zorder=0)
    except Exception:
        ax.add_feature(cfeature.LAND, facecolor='lightgrey', edgecolor='black', linewidth=0.6, zorder=0)
    ax.coastlines(resolution='50m', color='black', linewidth=0.8)
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.4, linestyle=':')
    gl.xlocator = mticker.MultipleLocator(5); gl.ylocator = mticker.MultipleLocator(5)
    try:
        gl.xformatter = LongitudeFormatter(number_format='.0f', degree_symbol='°')
        gl.yformatter = LatitudeFormatter(number_format='.0f', degree_symbol='°')
    except Exception:
        pass
    try:
        gl.top_labels=False; gl.right_labels=False; gl.left_labels=bool(left); gl.bottom_labels=bool(bottom)
    except Exception:
        gl.xlabels_top=False; gl.ylabels_right=False; gl.ylabels_left=bool(left); gl.xlabels_bottom=bool(bottom)
    gl.xlabel_style={"size":10,"rotation":0}; gl.ylabel_style={"size":10}


def nice(v: float) -> float:
    if not np.isfinite(v) or v<=0: return 1.0
    mag = 10.0**np.floor(np.log10(v)); base=v/mag
    for s in [1,1.5,2,2.5,3,5,6,8,10]:
        if base<=s+1e-12: return s*mag
    return 10*mag


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    years = [int(s) for s in args.years.split(',') if s.strip()]
    # Grid T_ML mode: render a single 12×N panel of T_ML anomalies for specific years
    grid_years = [int(s) for s in args.grid_tml_years.split(',')] if args.grid_tml_years else None
    months = month_list(args.months)
    root = Path(args.monthly_root)
    outdir = Path(args.out_root)
    outdir.mkdir(parents=True, exist_ok=True)

    # Gather coordinates from a sample file
    sample = open_month_file(root, years[0], 1)
    lat = (sample['lat'].values if 'lat' in sample.coords else sample['latitude'].values)
    lon = (sample['lon'].values if 'lon' in sample.coords else sample['longitude'].values)
    sample.close()

    if grid_years:
        # Build climatology for each calendar month
        clim_by_month: dict[int, xr.Dataset] = {}
        for m in range(1, 13):
            dsets = []
            for yy in range(1980, 2023):
                try:
                    dsets.append(open_month_file(root, yy, m))
                except FileNotFoundError:
                    continue
            if dsets:
                clim_by_month[m] = mean_stack(dsets).mean(dim='time', skipna=True)

        # If using raw SODA net_heating overlay, prepare its monthly climatology on the target grid
        soda_clim_by_month: dict[int, xr.DataArray] = {}
        if args.overlay_source == 'soda-net':
            # Target grid coordinates from monthly product
            lat_t = lat; lon_t = lon
            # Load SODA coords from a sample file
            import xarray as _xr
            from pathlib import Path as _P
            sample_soda = _xr.open_dataset(_P(args.soda_root) / f"soda3.4.2_mn_ocean_reg_1993.nc")
            yt = sample_soda['yt_ocean'].values; xt = sample_soda['xt_ocean'].values
            # Build nearest index mapping
            import numpy as _np
            Jmap = _np.array([int(_np.argmin(_np.abs(yt - v))) for v in lat_t], dtype=int)
            Imap = _np.array([int(_np.argmin(_np.abs(xt - v))) for v in lon_t], dtype=int)
            sample_soda.close()
            # Monthly climatology: average over available years
            for m in range(1,13):
                acc = []
                for yy in range(1980, 2021):
                    fp = _P(args.soda_root) / f"soda3.4.2_mn_ocean_reg_{yy}.nc"
                    if not fp.exists():
                        continue
                    dsr = xr.open_dataset(fp)
                    if 'net_heating' not in dsr:
                        dsr.close(); continue
                    da = dsr['net_heating'].isel(time=m-1, yt_ocean=Jmap, xt_ocean=Imap)
                    acc.append(da)
                    dsr.close()
                if acc:
                    soda_clim_by_month[m] = xr.concat(acc, dim='stack').mean('stack', skipna=True)
        # Helper to compute monthly anomaly for a given (year, month)
        def monthly_anom(y: int, m: int) -> tuple[xr.DataArray | None, xr.DataArray | None]:
            try:
                ds = open_month_file(root, y, m)
            except FileNotFoundError:
                return None, None
            if m not in clim_by_month:
                ds.close(); return None, None
            comp = ds.mean(dim='time', skipna=True)
            tml = comp['T_ML'] if 'T_ML' in comp.data_vars else comp[[k for k in comp.data_vars if k.lower()=='t_ml'][0]]
            Cl = clim_by_month[m]
            tmlc = Cl['T_ML'] if 'T_ML' in Cl.data_vars else Cl[[k for k in Cl.data_vars if k.lower()=='t_ml'][0]]
            da_tml = (tml - tmlc).squeeze(drop=True)
            da_q = None
            if args.overlay_source == 'qnet':
                if 'QNET' in comp.data_vars and 'QNET' in Cl.data_vars:
                    q = (comp['QNET'] - Cl['QNET']).squeeze(drop=True)
                    if args.unit == 'month':
                        q = q * 30.4375
                    da_q = q
            elif args.overlay_source == 'soda-net':
                # Read raw SODA net_heating and map to target grid
                import xarray as _xr
                from pathlib import Path as _P
                fp = _P(args.soda_root) / f"soda3.4.2_mn_ocean_reg_{y}.nc"
                if fp.exists() and m in soda_clim_by_month:
                    dsr = _xr.open_dataset(fp)
                    if 'net_heating' in dsr:
                        # Reuse mapping built earlier
                        yt = dsr['yt_ocean'].values; xt = dsr['xt_ocean'].values
                        import numpy as _np
                        Jmap = _np.array([int(_np.argmin(_np.abs(yt - v))) for v in lat], dtype=int)
                        Imap = _np.array([int(_np.argmin(_np.abs(xt - v))) for v in lon], dtype=int)
                        da = dsr['net_heating'].isel(time=m-1, yt_ocean=Jmap, xt_ocean=Imap)
                        clim = soda_clim_by_month[m]
                        # Ensure same mapping on clim (already mapped when built)
                        da_q = (da - clim)
                    dsr.close()
            else:
                da_q = None
            ds.close()
            return da_tml, da_q

        # Collect monthly anomalies into dicts
        tml_grid: dict[tuple[int,int], xr.DataArray] = {}
        qnet_grid: dict[tuple[int,int], xr.DataArray] = {}
        for y in grid_years:
            for m in range(1,13):
                da_tml, da_q = monthly_anom(y, m)
                if da_tml is not None:
                    tml_grid[(y,m)] = da_tml
                if da_q is not None:
                    qnet_grid[(y,m)] = da_q
        # Common symmetric color level across all cells
        vals = []
        for key, da in tml_grid.items():
            a = np.abs(da.values).ravel(); a = a[np.isfinite(a)]
            if a.size: vals.append(a)
        stack = np.concatenate(vals) if vals else np.array([1.0])
        vabs = nice(float(np.nanpercentile(stack, float(args.rhs_prc)))) if stack.size else 1.0
        lev = np.linspace(-vabs, vabs, 21)
        # Prepare 3-month aggregation windows if requested
        use_3mo = (args.grid_tml_aggregate == '3mo-prev10')
        if use_3mo:
            # Define windows: prevOND (prev Oct–Dec), JFM, AMJ, JAS, OND
            windows = [
                ("prevOND", [(10, True),(11, True),(12, True)]),
                ("JFM",     [(1, False),(2, False),(3, False)]),
                ("AMJ",     [(4, False),(5, False),(6, False)]),
                ("JAS",     [(7, False),(8, False),(9, False)]),
                ("OND",     [(10, False),(11, False),(12, False)]),
            ]
            # Aggregate per year × window
            agg_tml: dict[tuple[int,str], xr.DataArray] = {}
            agg_qnet: dict[tuple[int,str], xr.DataArray] = {}
            for y in grid_years:
                for wname, spec in windows:
                    cells_t = []
                    cells_q = []
                    for m, is_prev in spec:
                        yy = y-1 if is_prev else y
                        # fetch or compute if missing
                        key = (yy, m)
                        if key not in tml_grid:
                            da_tml, da_q = monthly_anom(yy, m)
                            if da_tml is not None:
                                tml_grid[key] = da_tml
                            if da_q is not None:
                                qnet_grid[key] = da_q
                        if key in tml_grid:
                            cells_t.append(tml_grid[key])
                        if key in qnet_grid:
                            cells_q.append(qnet_grid[key])
                    if cells_t:
                        agg_tml[(y,wname)] = xr.concat(cells_t, dim='stack').mean('stack', skipna=True)
                    if cells_q:
                        agg_qnet[(y,wname)] = xr.concat(cells_q, dim='stack').mean('stack', skipna=True)

            # Optional: mean across selected years per window
            mean_tml_by_window: dict[str, xr.DataArray] = {}
            mean_qnet_by_window: dict[str, xr.DataArray] = {}
            mean_sig_by_window: dict[str, np.ndarray] = {}
            if args.grid_include_mean:
                for wname, spec_w in windows:
                    # Build monthly-level stack across all selected years and months in this window
                    arr_mt: list[xr.DataArray] = []  # T_ML monthly anomalies
                    arr_mq: list[xr.DataArray] = []  # QNET/net_heating monthly anomalies
                    for y in grid_years:
                        for m, is_prev in spec_w:
                            yy = y-1 if is_prev else y
                            key = (yy, m)
                            if key not in tml_grid:
                                da_tml, da_q = monthly_anom(yy, m)
                                if da_tml is not None:
                                    tml_grid[key] = da_tml
                                if da_q is not None:
                                    qnet_grid[key] = da_q
                            if key in tml_grid:
                                arr_mt.append(tml_grid[key])
                            if key in qnet_grid:
                                arr_mq.append(qnet_grid[key])
                    if arr_mt:
                        # samples = months × years (NaN‑robust)
                        stk = xr.concat(arr_mt, dim='stack')
                        mean_tml_by_window[wname] = stk.mean('stack', skipna=True)
                        # Two-sided t-test for mean=0 at 95% with N_eff via lag-1 autocorr
                        n = stk.count('stack').values.astype(np.int32)  # total valid samples per grid
                        std = stk.std('stack', skipna=True, ddof=1).values
                        mu = mean_tml_by_window[wname].values
                        # Estimate r1 (lag-1 autocorrelation) along 'stack' per grid
                        vals = stk.values.astype(np.float64)  # (S, Y, X)
                        S, NY, NX = vals.shape
                        r1 = np.zeros((NY, NX), dtype=np.float64)
                        r1[:] = 0.0
                        if S >= 3:
                            for j in range(NY):
                                a = vals[:-1, j, :]
                                b = vals[1:, j, :]
                                for i in range(NX):
                                    aa = a[:, i]
                                    bb = b[:, i]
                                    mask = np.isfinite(aa) & np.isfinite(bb)
                                    if np.count_nonzero(mask) >= 2:
                                        x = aa[mask]; y = bb[mask]
                                        xm = x.mean(); ym = y.mean()
                                        xv = x - xm; yv = y - ym
                                        denom = np.sqrt(np.sum(xv*xv) * np.sum(yv*yv))
                                        r1[j, i] = (np.sum(xv*yv)/denom) if denom > 0 else 0.0
                                    else:
                                        r1[j, i] = 0.0
                        # N_eff = N * (1-r1)/(1+r1), clipped to [2, N]
                        with np.errstate(invalid='ignore', divide='ignore'):
                            ratio = (1.0 - r1) / (1.0 + r1)
                        neff = np.where(n > 0, n * ratio, 0.0)
                        neff = np.where(np.isfinite(neff), neff, 0.0)
                        neff = np.clip(neff, 0.0, n.astype(np.float64))
                        # We need integer df; require at least 2 for t-test
                        neff_int = neff.astype(np.int32)
                        # t-value using N_eff
                        with np.errstate(invalid='ignore', divide='ignore'):
                            tval = mu / (std / np.sqrt(np.where(neff_int > 0, neff_int, 1)))
                        # df = N_eff-1; use t-critical table up to 30 (0.975 two-sided)
                        tcrit_tbl = np.array([
                            np.nan, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262,
                            2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093,
                            2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045,
                            2.042
                        ], dtype=float)
                        df = np.clip(neff_int - 1, 1, len(tcrit_tbl) - 1)
                        tcrit = tcrit_tbl[df]
                        sig = (neff_int >= 2) & np.isfinite(tval) & (np.abs(tval) > tcrit)
                        mean_sig_by_window[wname] = sig
                    if arr_mq:
                        mean_qnet_by_window[wname] = xr.concat(arr_mq, dim='stack').mean('stack', skipna=True)

        # Grid orientation and size
        rows_years = (args.grid_tml_rows == 'years')
        if use_3mo:
            ncols_windows = 5
            if rows_years:
                base_rows = len(grid_years)
                nrow = base_rows + (1 if args.grid_include_mean else 0)
                ncol = ncols_windows
            else:
                nrow = ncols_windows; ncol = len(grid_years)
        else:
            if rows_years:
                base_rows = len(grid_years)
                nrow = base_rows + (1 if args.grid_include_mean else 0)
                ncol = 12
            else:
                nrow = 12; ncol = len(grid_years)
        proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
        # Compact layout to minimize whitespace
        width = 2.2*ncol + 1.6
        height = 1.9*nrow + 1.6
        fig = plt.figure(figsize=(width, height))
        gs = fig.add_gridspec(nrow, ncol, left=0.05, right=0.995, top=0.96, bottom=0.10, wspace=0.03, hspace=0.03)
        lon2d, lat2d = (np.meshgrid(lon,lat) if (lat.ndim==1 and lon.ndim==1) else (lon,lat))
        cmap = lighten_cmap('RdBu_r', 0.25)
        try:
            cmap = cmap.copy(); cmap.set_bad('lightgrey')
        except Exception:
            pass
        mapp = None
        # Prepare symmetric contour levels for overlay across all cells (if enabled)
        qvals = []
        if args.overlay_source != 'none':
            for key in qnet_grid:
                da = qnet_grid[key]
                a = np.abs(da.values).ravel()
                a = a[np.isfinite(a)]
                if a.size:
                    qvals.append(a)
        qstack = np.concatenate(qvals) if qvals else np.array([])
        qabs = nice(float(np.nanpercentile(qstack, float(args.rhs_prc)))) if qstack.size else (vabs/5.0)
        # Symmetric levels including zero; default to ~9 levels (±overlay_nlevels + 0)
        nposneg = max(1, int(args.overlay_nlevels))
        clevs = np.linspace(-qabs, qabs, 2 * nposneg + 1)  # includes zero
        zero_level = np.array([0.0])
        neg_levels = clevs[clevs < -1e-12]
        pos_levels = clevs[clevs > 1e-12]
        # Overlay colors (colorblind-safe by default): positive=orange, negative=green, zero=black
        pos_color = str(args.overlay_pos_color)
        neg_color = str(args.overlay_neg_color)
        zero_color = str(args.overlay_zero_color)
        lw_negpos = float(args.overlay_lw)
        lw_zero = float(args.overlay_zero_lw)
        alpha = float(args.overlay_alpha)
        if rows_years:
            # rows = years, cols = months or 3‑month windows
            row_labels: list[object] = ([] if not args.grid_include_mean else ["MEAN"]) + grid_years
            cols_iter = (range(1,13) if not use_3mo else ["prevOND","JFM","AMJ","JAS","OND"])
            for ri, rlab in enumerate(row_labels):
                for ci, col in enumerate(cols_iter):
                    ax = fig.add_subplot(gs[ri, ci], **proj)
                    if use_3mo:
                        if rlab == "MEAN":
                            da = mean_tml_by_window.get(col)
                            q = mean_qnet_by_window.get(col)
                            if da is not None and args.grid_mean_scale != 1.0:
                                da = da * float(args.grid_mean_scale)
                            if q is not None and args.grid_mean_scale != 1.0:
                                q = q * float(args.grid_mean_scale)
                        else:
                            y = int(rlab)
                            da = agg_tml.get((y, col))
                            q = agg_qnet.get((y, col))
                    else:
                        m = int(col)
                        if rlab == "MEAN":
                            # Monthly mean across years (if needed in future)
                            arr_t = [tml_grid.get((y, m)) for y in grid_years if (y, m) in tml_grid]
                            arr_t = [a for a in arr_t if a is not None]
                            da = xr.concat(arr_t, dim='stack').mean('stack', skipna=True) if arr_t else None
                            arr_q = [qnet_grid.get((y, m)) for y in grid_years if (y, m) in qnet_grid]
                            arr_q = [a for a in arr_q if a is not None]
                            q = xr.concat(arr_q, dim='stack').mean('stack', skipna=True) if arr_q else None
                            if da is not None and args.grid_mean_scale != 1.0:
                                da = da * float(args.grid_mean_scale)
                            if q is not None and args.grid_mean_scale != 1.0:
                                q = q * float(args.grid_mean_scale)
                        else:
                            y = int(rlab)
                            da = tml_grid.get((y,m))
                            q = qnet_grid.get((y,m))
                    if da is not None:
                        h = ax.contourf(lon2d, lat2d, da.values, levels=lev, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
                        if mapp is None: mapp = h
                        # Significance hatching for MEAN row (after base shading)
                        if (rlab == "MEAN") and use_3mo and (args.grid_mean_sig != "off"):
                            sig = mean_sig_by_window.get(col)
                            if sig is not None and np.isfinite(sig).any():
                                # hatch where significant
                                try:
                                    ax.contourf(
                                        lon2d, lat2d, sig.astype(float),
                                        levels=[0.5, 1.5], hatches=['..'], colors='none',
                                        transform=ccrs.PlateCarree() if ccrs is not None else None,
                                    )
                                except Exception:
                                    pass
                    # Overlay contours if enabled: positive(heating) solid, negative(cooling) dashed, zero solid black
                    if (args.overlay_source != 'none') and (q is not None):
                        if neg_levels.size:
                            ax.contour(
                                lon2d, lat2d, q.values,
                                levels=neg_levels,
                                colors=[neg_color],
                                linestyles='dashed',
                                linewidths=lw_negpos,
                                alpha=alpha,
                                transform=ccrs.PlateCarree() if ccrs is not None else None,
                            )
                        if pos_levels.size:
                            ax.contour(
                                lon2d, lat2d, q.values,
                                levels=pos_levels,
                                colors=[pos_color],
                                linestyles='solid',
                                linewidths=lw_negpos,
                                alpha=alpha,
                                transform=ccrs.PlateCarree() if ccrs is not None else None,
                            )
                        ax.contour(
                            lon2d, lat2d, q.values,
                            levels=zero_level,
                            colors=[zero_color],
                            linestyles='solid',
                            linewidths=lw_zero,
                            alpha=alpha,
                            transform=ccrs.PlateCarree() if ccrs is not None else None,
                        )
                    if ccrs is not None:
                        xmin = float(np.nanmin(lon2d)); xmax = float(np.nanmax(lon2d))
                        if args.lon_max is not None:
                            xmax = min(xmax, float(args.lon_max))
                        ax.set_extent([xmin, xmax, float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
                    add_map(ax, left=(ci==0), bottom=(ri==nrow-1))
                    if ci == 0:
                        ax.set_ylabel("MEAN" if rlab == "MEAN" else str(rlab), fontsize=9)
                    if ri == 0:
                        title = (month_abbrev(m) if not use_3mo else str(col))
                        ax.set_title(title, fontsize=9)
        else:
            # rows = months, cols = years (default)
            for ci, y in enumerate(grid_years):
                rows_iter = (range(1,13) if not use_3mo else ["prevOND","JFM","AMJ","JAS","OND"])
                for ri, row in enumerate(rows_iter):
                    ax = fig.add_subplot(gs[ri, ci], **proj)
                    if use_3mo:
                        da = agg_tml.get((y, row))
                        q = agg_qnet.get((y, row))
                    else:
                        m = int(row)
                        da = tml_grid.get((y,m))
                        q = qnet_grid.get((y,m))
                    if da is not None:
                        h = ax.contourf(lon2d, lat2d, da.values, levels=lev, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
                        if mapp is None: mapp = h
                    if (args.overlay_source != 'none') and (q is not None):
                        if neg_levels.size:
                            ax.contour(
                                lon2d, lat2d, q.values,
                                levels=neg_levels,
                                colors=[neg_color],
                                linestyles='dashed',
                                linewidths=lw_negpos,
                                alpha=alpha,
                                transform=ccrs.PlateCarree() if ccrs is not None else None,
                            )
                        if pos_levels.size:
                            ax.contour(
                                lon2d, lat2d, q.values,
                                levels=pos_levels,
                                colors=[pos_color],
                                linestyles='solid',
                                linewidths=lw_negpos,
                                alpha=alpha,
                                transform=ccrs.PlateCarree() if ccrs is not None else None,
                            )
                        ax.contour(
                            lon2d, lat2d, q.values,
                            levels=zero_level,
                            colors=[zero_color],
                            linestyles='solid',
                            linewidths=lw_zero,
                            alpha=alpha,
                            transform=ccrs.PlateCarree() if ccrs is not None else None,
                        )
                    if ccrs is not None:
                        xmin = float(np.nanmin(lon2d)); xmax = float(np.nanmax(lon2d))
                        if args.lon_max is not None:
                            xmax = min(xmax, float(args.lon_max))
                        ax.set_extent([xmin, xmax, float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
                    add_map(ax, left=(ci==0), bottom=(ri==nrow-1))
                    if ci == 0:
                        lab = (month_abbrev(m) if not use_3mo else str(row))
                        ax.set_ylabel(lab, fontsize=9)
                    if ri == 0:
                        ax.set_title(str(y), fontsize=10)
        # Colorbar shared
        poss = [ax.get_position() for ax in fig.axes]
        x0=min(p.x0 for p in poss); x1=max(p.x1 for p in poss); y0=max(0.03, min(p.y0 for p in poss)-0.06)
        cax = fig.add_axes([x0, y0, x1-x0, 0.018])
        cb = fig.colorbar(mapp, cax=cax, orientation='horizontal'); cb.set_label('K', labelpad=4)
        tag = 'rows-years' if rows_years else 'rows-months'
        outp = outdir / f"elt_TML_grid_{tag}.png"
        tmp = outp.with_suffix('.tmp.png')
        fig.savefig(tmp, dpi=args.dpi); plt.close(fig); tmp.replace(outp)
        return

    # Iterate months
    tml_by_month: dict[int, xr.DataArray] = {}
    var12_by_month: dict[str, dict[int, xr.DataArray]] = {k: {} for k in [
        "T_ML","TEN","QNET","ADV","ENT","DIFF","DIFFV","SUBS"
    ]}
    for month, is_prev in months:
        # Composite over ELT years
        dsets_comp = []
        for y in years:
            yy = y-1 if is_prev else y
            try:
                dsets_comp.append(open_month_file(root, yy, month))
            except FileNotFoundError:
                continue
        if not dsets_comp:
            print(f"Skip month {month} prev={is_prev}: no files")
            continue
        comp = mean_stack(dsets_comp).mean(dim='time', skipna=True)

        # Climatology for this calendar month across all available years
        dsets_clim = []
        for yy in range(1980, 2023):
            try:
                dsets_clim.append(open_month_file(root, yy, month))
            except FileNotFoundError:
                continue
        clim = mean_stack(dsets_clim).mean(dim='time', skipna=True)

        def pick(ds: xr.Dataset, name: str) -> xr.DataArray:
            for k in ds.data_vars:
                if k.lower()==name.lower(): return ds[k]
            aliases = {"t_ml":["t_ml","tml","tmean"]}
            for a in aliases.get(name.lower(), [name]):
                for k in ds.data_vars:
                    if k.lower()==a: return ds[k]
            raise KeyError(name)

        # Budget terms anomalies (K day^-1)
        squeeze = lambda da: da.squeeze(drop=True)
        QNET = squeeze(pick(comp,'QNET') - pick(clim,'QNET'))
        ADV  = squeeze(pick(comp,'ADV')  - pick(clim,'ADV'))
        ENT  = squeeze(pick(comp,'ENT')  - pick(clim,'ENT'))
        DIFF = squeeze(pick(comp,'DIFF') - pick(clim,'DIFF'))
        TEN  = squeeze(pick(comp,'TEN')  - pick(clim,'TEN'))
        if args.diffv_mode=='residual':
            DIFFV = TEN - (QNET+ADV+ENT+DIFF)
        else:
            DIFFV = squeeze(pick(comp,'DIFFV') - pick(clim,'DIFFV'))
        # Temperature anomaly (K)
        TML = squeeze(pick(comp,'T_ML') - pick(clim,'T_ML'))

        # Optional ADV smoothing
        ADV = maybe_smooth(ADV, args.adv_smooth_iter)

        # Unit scaling for terms
        scale = 1.0 if args.unit=='day' else 30.4375
        QNET*=scale; ADV*=scale; ENT*=scale; DIFF*=scale; DIFFV*=scale; TEN*=scale
        SUBS = ADV+ENT+DIFF+DIFFV

        # Scale from percentile across all terms
        stack = np.concatenate([np.abs(x.values).ravel() for x in (QNET,SUBS,ADV,ENT,DIFF,DIFFV)])
        stack = stack[np.isfinite(stack)]
        vabs = nice(float(np.nanpercentile(stack, float(args.rhs_prc))) if stack.size else 1.0)
        levels = np.linspace(-vabs, vabs, 17)

        # Plot terms panel
        proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
        fig = plt.figure(figsize=(8.6, 11.2))
        gs = fig.add_gridspec(3,2,left=0.08,right=0.985,top=0.97,bottom=0.18,wspace=0.10,hspace=0.12)
        axes = np.array([[fig.add_subplot(gs[r,c], **proj) for c in range(2)] for r in range(3)])
        titles = ["Surface Heat Flux (Qnet)","ADV+ENT+DIFF(+V)","Horizontal Advection","Entrainment","Lateral Diffusion","Vertical Diffusion"]
        fields = [QNET,SUBS,ADV,ENT,DIFF,DIFFV]
        lon2d, lat2d = (np.meshgrid(lon,lat) if (lat.ndim==1 and lon.ndim==1) else (lon,lat))
        cmap = lighten_cmap('RdBu_r', 0.25)
        try: cmap = cmap.copy(); cmap.set_bad('lightgrey')
        except Exception: pass
        mapp=[]
        for i,(ax,da,tt) in enumerate(zip(axes.ravel(), fields, titles)):
            h = ax.contourf(lon2d, lat2d, da.values, levels=levels, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
            if ccrs is not None:
                ax.set_extent([float(np.nanmin(lon2d)), float(np.nanmax(lon2d)), float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
            add_map(ax, left=(i%2==0), bottom=(i//2==2))
            ax.set_title(f"({chr(ord('a')+i)}) {tt}", loc='left', pad=6)
            mapp.append(h)
        # colorbar
        poss=[ax.get_position() for ax in axes.ravel()]
        x0=min(p.x0 for p in poss); x1=max(p.x1 for p in poss); y0=max(0.03, min(p.y0 for p in poss)-0.10)
        cax=fig.add_axes([x0,y0,x1-x0,0.025])
        cb=fig.colorbar(mapp[0], cax=cax, orientation='horizontal')
        cb.set_label('K month$^{-1}$' if args.unit=='month' else 'K day$^{-1}$', labelpad=4)
        # save
        tag = f"prev{month:02d}" if is_prev else f"{month:02d}"
        out_terms = outdir / f"elt_comp_terms_{tag}.png"
        tmp = out_terms.with_suffix('.tmp.png')
        fig.savefig(tmp, dpi=args.dpi); plt.close(fig); tmp.replace(out_terms)

        # Plot T_ML anomaly
        fig2 = plt.figure(figsize=(4.6,3.6))
        ax2 = fig2.add_subplot(1,1,1, **proj)
        vabs_t = nice(float(np.nanpercentile(np.abs(TML.values[np.isfinite(TML.values)]), 98.0)) if np.isfinite(TML.values).any() else 1.0)
        lev_t = np.linspace(-vabs_t, vabs_t, 21)
        hc = ax2.contourf(lon2d, lat2d, TML.values, levels=lev_t, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
        if ccrs is not None:
            ax2.set_extent([float(np.nanmin(lon2d)), float(np.nanmax(lon2d)), float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
        add_map(ax2, left=True, bottom=True)
        cax2 = fig2.add_axes([0.12, 0.05, 0.78, 0.045])
        cb2 = fig2.colorbar(hc, cax=cax2, orientation='horizontal'); cb2.set_label('K', labelpad=4)
        out_t = outdir / f"elt_comp_TML_{tag}.png"
        tmp2 = out_t.with_suffix('.tmp.png')
        fig2.savefig(tmp2, dpi=args.dpi); plt.close(fig2); tmp2.replace(out_t)

        # collect for 12-month panel
        if not is_prev and 1 <= month <= 12:
            tml_by_month[month] = TML
            var12_by_month["T_ML"][month] = TML
            var12_by_month["TEN"][month] = TEN
            var12_by_month["QNET"][month] = QNET
            var12_by_month["ADV"][month]  = ADV
            var12_by_month["ENT"][month]  = ENT
            var12_by_month["DIFF"][month] = DIFF
            var12_by_month["DIFFV"][month]= DIFFV
            var12_by_month["SUBS"][month] = SUBS

    # 12-month T_ML panel (6×2) if all months available
    if len([m for m in tml_by_month if 1 <= m <= 12]) >= 12:
        proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
        # 6 columns × 2 rows
        fig = plt.figure(figsize=(14.0, 5.8))
        gs = fig.add_gridspec(2, 6, left=0.05, right=0.995, top=0.95, bottom=0.14, wspace=0.06, hspace=0.10)
        # common scale across months
        vals = []
        for m in range(1,13):
            da = tml_by_month[m]
            a = np.abs(da.values)
            a = a[np.isfinite(a)]
            if a.size: vals.append(np.nanpercentile(a, float(args.rhs_prc)))
        vabs = nice(float(np.nanmax(vals))) if vals else 1.0
        lev = np.linspace(-vabs, vabs, 21)
        cmap = plt.get_cmap('RdBu_r')
        try: cmap = cmap.copy(); cmap.set_bad('lightgrey')
        except Exception: pass
        lon = (sample['lon'].values if 'lon' in sample.coords else sample['longitude'].values)
        lat = (sample['lat'].values if 'lat' in sample.coords else sample['latitude'].values)
        lon2d, lat2d = (np.meshgrid(lon, lat) if (lat.ndim==1 and lon.ndim==1) else (lon, lat))
        month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        # arrange Jan–Jun (row0), Jul–Dec (row1)
        mapp = []
        for idx, m in enumerate(range(1,13)):
            r = 0 if idx < 6 else 1
            c = idx if idx < 6 else idx-6
            ax = fig.add_subplot(gs[r, c], **proj)
            da = tml_by_month[m]
            h = ax.contourf(lon2d, lat2d, da.values, levels=lev, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
            if ccrs is not None:
                ax.set_extent([float(np.nanmin(lon2d)), float(np.nanmax(lon2d)), float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
            add_map(ax, left=(c==0), bottom=(r==1))
            ax.set_title(month_names[m-1], fontsize=10)
            if idx == 0:
                mapp.append(h)
        # colorbar
        poss=[ax.get_position() for ax in fig.axes]
        x0=min(p.x0 for p in poss); x1=max(p.x1 for p in poss); y0=max(0.035, min(p.y0 for p in poss)-0.06)
        cax = fig.add_axes([x0, y0, x1-x0, 0.022])
        cb = fig.colorbar(mapp[0], cax=cax, orientation='horizontal'); cb.set_label('K', labelpad=4)
        outp = outdir / "elt_comp_TML_12months_6x2.png"
        tmp = outp.with_suffix('.tmp.png')
        fig.savefig(tmp, dpi=args.dpi); plt.close(fig); tmp.replace(outp)


    # 12-month panel(s) for requested variables
    wanted = [s.strip().upper() for s in args.twelve_vars.split(',') if s.strip()]
    for varname in wanted:
        if varname not in var12_by_month:
            continue
        if len([m for m in var12_by_month[varname] if 1 <= m <= 12]) < 12:
            continue
        proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
        fig = plt.figure(figsize=(14.0, 5.8))
        gs = fig.add_gridspec(2, 6, left=0.05, right=0.995, top=0.95, bottom=0.14, wspace=0.06, hspace=0.10)
        # determine common symmetric scale across months
        vals = []
        for m in range(1,13):
            da = var12_by_month[varname][m]
            a = np.abs(da.values)
            a = a[np.isfinite(a)]
            if a.size:
                vals.append(np.nanpercentile(a, float(args.rhs_prc)))
        vabs = nice(float(np.nanmax(vals))) if vals else 1.0
        lev = np.linspace(-vabs, vabs, 21)
        cmap = lighten_cmap('RdBu_r', 0.25)
        try:
            cmap = cmap.copy(); cmap.set_bad('lightgrey')
        except Exception:
            pass
        lon2d, lat2d = (np.meshgrid(lon, lat) if (lat.ndim==1 and lon.ndim==1) else (lon, lat))
        month_names = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        mapp = []
        for idx, m in enumerate(range(1,13)):
            r = 0 if idx < 6 else 1
            c = idx if idx < 6 else idx-6
            ax = fig.add_subplot(gs[r, c], **proj)
            da = var12_by_month[varname][m]
            h = ax.contourf(lon2d, lat2d, da.values, levels=lev, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
            if ccrs is not None:
                ax.set_extent([float(np.nanmin(lon2d)), float(np.nanmax(lon2d)), float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
            add_map(ax, left=(c==0), bottom=(r==1))
            ax.set_title(month_names[m-1], fontsize=10)
            if idx == 0:
                mapp.append(h)
        poss=[ax.get_position() for ax in fig.axes]
        x0=min(p.x0 for p in poss); x1=max(p.x1 for p in poss); y0=max(0.035, min(p.y0 for p in poss)-0.06)
        cax = fig.add_axes([x0, y0, x1-x0, 0.022])
        unit_label = 'K' if varname == 'T_ML' else ('K month$^{-1}$' if args.unit=='month' else 'K day$^{-1}$')
        cb = fig.colorbar(mapp[0], cax=cax, orientation='horizontal'); cb.set_label(unit_label, labelpad=4)
        outp = outdir / f"elt_comp_{varname}_12months_6x2.png"
        tmp = outp.with_suffix('.tmp.png')
        fig.savefig(tmp, dpi=args.dpi); plt.close(fig); tmp.replace(outp)


if __name__ == '__main__':
    main()
