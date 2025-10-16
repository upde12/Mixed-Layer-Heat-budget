#!/usr/bin/env python3
"""Seasonal composite MLHB anomalies for ELT years (ONDJ, MJJAS).

Builds seasonal composites (ELT-year average minus monthly climatology) and
renders a 3×2 terms panel and a single T_ML map for each requested season.

Inputs: monthly MLHB NetCDF files named like mlhb_monthly_main_YYYYMM.nc
 - Budget terms stored in K day^-1; T_ML in K.
 - Output unit can be K day^-1 (day) or K month^-1 (month).

Seasons supported by default:
 - ONDJ = Oct(prev), Nov(prev), Dec(prev), Jan(curr)
 - MJJAS = May..Sep (curr)
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
except Exception:  # cartopy optional
    ccrs = None
    cfeature = None


Season = Tuple[str, Sequence[Tuple[int, bool]]]


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--monthly-root", required=True, help="Directory containing mlhb_monthly_main_YYYYMM.nc files")
    p.add_argument("--years", required=True, help="Comma-separated ELT years for primary set or grid, e.g., 1998,2010,2016,2020")
    p.add_argument("--years-alt", default=None, help="Optional comma-separated ELT years for alternate set (e.g., 1983,1988)")
    p.add_argument("--out-root", required=True, help="Output directory for PNGs")
    p.add_argument("--seasons", default="ONDJ,MJJAS", help="Comma-separated seasons to render (choices: ONDJ,MJJAS)")
    p.add_argument("--diffv-mode", choices=["native","residual"], default="native")
    p.add_argument("--adv-smooth-iter", type=int, default=2)
    p.add_argument("--rhs-prc", type=float, default=98.0, help="Percentile to set symmetric abs scale for terms")
    p.add_argument("--unit", choices=["day","month"], default="month")
    p.add_argument("--ten-scale", type=float, default=2.0, help="Multiply TEN by this factor for visualization (default 2.0)")
    p.add_argument("--lon-max", type=float, default=None, help="Limit plot to maximum longitude (e.g., 140.0)")
    p.add_argument("--grid", action="store_true", help="Render a single 4×N grid panel (rows: QNET, ocean_total, TEN, T_ML; cols: years)")
    p.add_argument("--dpi", type=int, default=170)
    return p.parse_args(argv)


def default_seasons() -> Dict[str, Sequence[Tuple[int, bool]]]:
    # (month, is_prev_year)
    return {
        "ONDJ": [(10, True), (11, True), (12, True), (1, False)],
        "MJJAS": [(5, False), (6, False), (7, False), (8, False), (9, False)],
    }


def parse_season_spec(spec: str) -> List[Season]:
    defs = default_seasons()
    out: List[Season] = []
    for token in [s.strip().upper() for s in spec.split(',') if s.strip()]:
        if token not in defs:
            raise SystemExit(f"Unknown season '{token}'. Supported: {','.join(defs.keys())}")
        out.append((token, defs[token]))
    return out


def open_month_file(root: Path, year: int, month: int) -> xr.Dataset:
    # Support both 'main' and 'soda' naming
    cand = [
        root / f"mlhb_monthly_main_{year:04d}{month:02d}.nc",
        root / f"mlhb_monthly_soda_{year:04d}{month:02d}.nc",
    ]
    for fn in cand:
        if fn.exists():
            return xr.open_dataset(fn)
    raise FileNotFoundError(cand[0])


def _season_composite(root: Path, years: List[int], months: Sequence[Tuple[int, bool]], diffv_mode: str, adv_smooth_iter: int, unit: str) -> Tuple[Dict[str, xr.DataArray], xr.DataArray, xr.DataArray]:
    """Return seasonal composite anomaly fields and coordinates for given years.

    Returns (fields dict, lat, lon) where fields has keys QNET,SUBS,ADV,ED,DIFFV,TEN,T_ML.
    """
    # Composite over ELT years
    dsets_comp: List[xr.Dataset] = []
    for y in years:
        for m, is_prev in months:
            yy = y - 1 if is_prev else y
            try:
                dsets_comp.append(open_month_file(root, yy, m))
            except FileNotFoundError:
                continue
    if not dsets_comp:
        raise SystemExit("No composite datasets found for provided years")
    comp = mean_stack(dsets_comp).mean(dim='time', skipna=True)

    # Coordinates
    lat = (comp['lat'].values if 'lat' in comp.coords else comp['latitude'].values)
    lon = (comp['lon'].values if 'lon' in comp.coords else comp['longitude'].values)

    # Climatology for the same calendar months
    clim_months: List[xr.Dataset] = []
    for m, _ in months:
        dsets = []
        for yy in range(1980, 2023):
            try:
                dsets.append(open_month_file(root, yy, m))
            except FileNotFoundError:
                continue
        if dsets:
            clim_m = mean_stack(dsets).mean(dim='time', skipna=True)
            clim_months.append(clim_m)
    if not clim_months:
        raise SystemExit("No climatology datasets found")
    clim = xr.concat(clim_months, dim='stack').mean('stack', skipna=True)

    def S(name: str) -> xr.DataArray:
        return (pick_var(comp, name) - pick_var(clim, name)).squeeze(drop=True)

    QNET = S('QNET'); ADV = S('ADV'); ENT = S('ENT'); DIFF = S('DIFF')
    if diffv_mode == 'residual':
        TEN = S('TEN')
        DIFFV = TEN - (QNET + ADV + ENT + DIFF)
    else:
        DIFFV = S('DIFFV'); TEN = S('TEN')
    TML = (pick_var(comp, 'T_ML') - pick_var(clim, 'T_ML')).squeeze(drop=True)

    # Optional smoothing on ADV
    if adv_smooth_iter > 0:
        ADV = maybe_smooth(ADV, adv_smooth_iter)

    # Unit scaling
    scale = 1.0 if unit == 'day' else 30.4375
    QNET *= scale; ADV *= scale; ENT *= scale; DIFF *= scale; DIFFV *= scale; TEN *= scale
    ED = ENT + DIFF
    SUBS = ADV + ENT + DIFF + DIFFV

    fields = {
        'QNET': QNET,
        'SUBS': SUBS,
        'ADV': ADV,
        'ED': ED,
        'DIFFV': DIFFV,
        'TEN': TEN,
        'T_ML': TML,
    }
    return fields, xr.DataArray(lat), xr.DataArray(lon)


def mean_stack(dsets: List[xr.Dataset]) -> xr.Dataset:
    if not dsets:
        raise SystemExit("No datasets to average")
    ds = xr.concat(dsets, dim="stack")
    out = ds.mean("stack", skipna=True, keep_attrs=True)
    for d in dsets:
        try:
            d.close()
        except Exception:
            pass
    return out


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
    if iters <= 0:
        return da
    arr = da.values.copy()
    for _ in range(iters):
        arr = smth9_2d(arr)
    return da.copy(data=arr)


def add_map(ax, left: bool, bottom: bool) -> None:
    if ccrs is None:
        if bottom: ax.set_xlabel("Longitude")
        if left: ax.set_ylabel("Latitude")
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
    if not np.isfinite(v) or v <= 0:
        return 1.0
    mag = 10.0 ** np.floor(np.log10(v))
    base = v / mag
    for s in [1,1.5,2,2.5,3,5,6,8,10]:
        if base <= s + 1e-12:
            return s * mag
    return 10 * mag


def pick_var(ds: xr.Dataset, name: str) -> xr.DataArray:
    for k in ds.data_vars:
        if k.lower() == name.lower():
            return ds[k]
    aliases = {"t_ml": ["t_ml","tml","tmean"]}
    for a in aliases.get(name.lower(), [name]):
        for k in ds.data_vars:
            if k.lower() == a:
                return ds[k]
    raise KeyError(name)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    years = [int(s) for s in args.years.split(',') if s.strip()]
    years_alt = [int(s) for s in args.years_alt.split(',')] if args.years_alt else None
    seasons = parse_season_spec(args.seasons)
    root = Path(args.monthly_root)
    outdir = Path(args.out_root)
    outdir.mkdir(parents=True, exist_ok=True)

    for season_name, months in seasons:
        # Grid mode: one 4×N panel with specified years
        if args.grid:
            year_list = years
            # Collect per-year seasonal anomalies
            per_year_fields: Dict[int, Dict[str, xr.DataArray]] = {}
            lat_da = lon_da = None
            for y in year_list:
                fy, lat_da, lon_da = _season_composite(root, [y], months, args.diffv_mode, args.adv_smooth_iter, args.unit)
                # TEN scaling
                fy['TEN'] = fy['TEN'] * float(args.ten_scale)
                per_year_fields[y] = fy

            # Compute shared levels for terms (QNET, SUBS, TEN) across all years
            def stack_terms() -> np.ndarray:
                vals = []
                for y in year_list:
                    f = per_year_fields[y]
                    for k in ('QNET','SUBS','TEN'):
                        a = np.abs(f[k].values).ravel()
                        a = a[np.isfinite(a)]
                        if a.size:
                            vals.append(a)
                return np.concatenate(vals) if vals else np.array([])
            def stack_tml() -> np.ndarray:
                vals = []
                for y in year_list:
                    a = np.abs(per_year_fields[y]['T_ML'].values).ravel()
                    a = a[np.isfinite(a)]
                    if a.size:
                        vals.append(a)
                return np.concatenate(vals) if vals else np.array([])

            s_terms = stack_terms()
            s_tml = stack_tml()
            vabs_terms = nice(float(np.nanpercentile(s_terms, float(args.rhs_prc))) if s_terms.size else 1.0)
            vabs_tml   = nice(float(np.nanpercentile(s_tml,   float(args.rhs_prc))) if s_tml.size   else 1.0)
            lev_terms = np.linspace(-vabs_terms, vabs_terms, 17)
            lev_tml   = np.linspace(-vabs_tml,   vabs_tml,   21)

            # Prepare grid figure (rows: QNET, ocean_total(SUBS), TEN, T_ML; cols: years)
            ncol = len(year_list)
            proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
            fig = plt.figure(figsize=(2.8*ncol+2.0, 10.0))
            gs = fig.add_gridspec(4, ncol, left=0.06, right=0.99, top=0.94, bottom=0.14, wspace=0.08, hspace=0.08)
            titles_row = ["Surface Heat Flux (Qnet)", "Ocean Total (ADV+ENT+DIFF+V)", f"Tendency (TEN×{args.ten_scale:g})", "T_ML anomaly"]

            lon = lon_da.values; lat = lat_da.values
            lon2d, lat2d = (np.meshgrid(lon, lat) if (lat.ndim==1 and lon.ndim==1) else (lon, lat))
            cmap = plt.get_cmap('RdBu_r')
            try:
                cmap = cmap.copy(); cmap.set_bad('lightgrey')
            except Exception:
                pass

            mapp_terms = []
            mapp_tml = None
            for c, y in enumerate(year_list):
                f = per_year_fields[y]
                fields_arr = [f['QNET'], f['SUBS'], f['TEN'], f['T_ML']]
                for r in range(4):
                    ax = fig.add_subplot(gs[r, c], **proj)
                    da = fields_arr[r]
                    levels = lev_tml if r==3 else lev_terms
                    h = ax.contourf(lon2d, lat2d, da.values, levels=levels, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
                    if ccrs is not None:
                        xmin = float(np.nanmin(lon2d)); xmax = float(np.nanmax(lon2d))
                        if args.lon_max is not None:
                            xmax = min(xmax, float(args.lon_max))
                        ax.set_extent([xmin, xmax, float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
                    add_map(ax, left=(c==0), bottom=(r==3))
                    if c==0:
                        ax.set_ylabel(titles_row[r], fontsize=9)
                    if r==0:
                        ax.set_title(str(y), fontsize=10)
                    if r<3:
                        mapp_terms.append(h)
                    else:
                        mapp_tml = h

            # Colorbars: one for terms (shared), one for T_ML
            poss = [ax.get_position() for ax in fig.axes]
            x0 = min(p.x0 for p in poss); x1 = max(p.x1 for p in poss)
            y0 = max(0.05, min(p.y0 for p in poss) - 0.06)
            # Terms colorbar
            cax1 = fig.add_axes([x0, y0, x1-x0, 0.022])
            cb1 = fig.colorbar(mapp_terms[0], cax=cax1, orientation='horizontal')
            cb1.set_label('K month$^{-1}$' if args.unit=='month' else 'K day$^{-1}$')
            # T_ML colorbar (stack above)
            cax2 = fig.add_axes([x0, y0+0.03, x1-x0, 0.022])
            if mapp_tml is not None:
                cb2 = fig.colorbar(mapp_tml, cax=cax2, orientation='horizontal'); cb2.set_label('K')
            outp = outdir / f"elt_comp_grid_{season_name}.png"
            tmp = outp.with_suffix('.tmp.png')
            fig.savefig(tmp, dpi=args.dpi); plt.close(fig); tmp.replace(outp)
            continue

        # non-grid mode (primary/alt sets, existing behavior)
        # Primary and (optional) alternate composites
        prim_fields, lat_da, lon_da = _season_composite(root, years, months, args.diffv_mode, args.adv_smooth_iter, args.unit)
        alt_fields = None
        if years_alt:
            alt_fields, _, _ = _season_composite(root, years_alt, months, args.diffv_mode, args.adv_smooth_iter, args.unit)

        # Apply TEN scaling
        prim_fields['TEN'] = prim_fields['TEN'] * float(args.ten_scale)
        if alt_fields is not None:
            alt_fields['TEN'] = alt_fields['TEN'] * float(args.ten_scale)

        # Common levels across sets
        def stack_for_levels(fields: Dict[str, xr.DataArray]) -> np.ndarray:
            arrs = [np.abs(fields[k].values).ravel() for k in ('QNET','SUBS','ADV','ED','DIFFV')]
            return np.concatenate(arrs)
        stack = stack_for_levels(prim_fields)
        if alt_fields is not None:
            stack = np.concatenate((stack, stack_for_levels(alt_fields)))
        stack = stack[np.isfinite(stack)]
        vabs = nice(float(np.nanpercentile(stack, float(args.rhs_prc))) if stack.size else 1.0)
        levels = np.linspace(-vabs, vabs, 17)

        # Coordinates
        lon = lon_da.values; lat = lat_da.values
        lon2d, lat2d = (np.meshgrid(lon, lat) if (lat.ndim==1 and lon.ndim==1) else (lon, lat))

        def plot_set(tag: str, fields: Dict[str, xr.DataArray]):
            QNET = fields['QNET']; SUBS = fields['SUBS']; ADV = fields['ADV']; ED = fields['ED']; DIFFV = fields['DIFFV']; TEN = fields['TEN']
            proj = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
            fig = plt.figure(figsize=(8.6, 11.2))
            gs = fig.add_gridspec(3, 2, left=0.08, right=0.985, top=0.97, bottom=0.18, wspace=0.10, hspace=0.12)
            axes = np.array([[fig.add_subplot(gs[r, c], **proj) for c in range(2)] for r in range(3)])
            titles = [
                "Surface Heat Flux (Qnet)",
                "ADV+ENT+DIFF(+V)",
                "Horizontal Advection",
                "Entrainment+Lateral Diffusion",
                "Vertical Diffusion",
                f"Tendency (TEN×{args.ten_scale:g})",
            ]
            fields_arr = [QNET, SUBS, ADV, ED, DIFFV, TEN]
            cmap = plt.get_cmap('RdBu_r')
            try:
                cmap = cmap.copy(); cmap.set_bad('lightgrey')
            except Exception:
                pass
            mapp = []
            for i, (ax, da, tt) in enumerate(zip(axes.ravel(), fields_arr, titles)):
                h = ax.contourf(lon2d, lat2d, da.values, levels=levels, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
                if ccrs is not None:
                    xmin = float(np.nanmin(lon2d)); xmax = float(np.nanmax(lon2d))
                    if args.lon_max is not None:
                        xmax = min(xmax, float(args.lon_max))
                    ax.set_extent([xmin, xmax, float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
                add_map(ax, left=(i % 2 == 0), bottom=(i // 2 == 2))
                ax.set_title(f"({chr(ord('a') + i)}) {tt}", loc='left', pad=6)
                mapp.append(h)
            poss = [ax.get_position() for ax in axes.ravel()]
            x0 = min(p.x0 for p in poss); x1 = max(p.x1 for p in poss); y0 = max(0.06, min(p.y0 for p in poss) - 0.08)
            cax = fig.add_axes([x0, y0, x1 - x0, 0.025])
            cb = fig.colorbar(mapp[0], cax=cax, orientation='horizontal')
            cb.set_label('K month$^{-1}$' if args.unit == 'month' else 'K day$^{-1}$')
            out_terms = outdir / f"elt_comp_terms_{season_name}_{tag}.png"
            tmp = out_terms.with_suffix('.tmp.png')
            fig.savefig(tmp, dpi=args.dpi); plt.close(fig); tmp.replace(out_terms)

            # T_ML
            fig2 = plt.figure(figsize=(4.6, 3.6))
            ax2 = fig2.add_subplot(1, 1, 1, **proj)
            a = np.abs(fields['T_ML'].values); a = a[np.isfinite(a)]
            vabs_t = nice(float(np.nanpercentile(a, float(args.rhs_prc))) if a.size else 1.0)
            lev_t = np.linspace(-vabs_t, vabs_t, 21)
            hc = ax2.contourf(lon2d, lat2d, fields['T_ML'].values, levels=lev_t, cmap=cmap, extend='both', transform=ccrs.PlateCarree() if ccrs is not None else None)
            if ccrs is not None:
                xmin = float(np.nanmin(lon2d)); xmax = float(np.nanmax(lon2d))
                if args.lon_max is not None:
                    xmax = min(xmax, float(args.lon_max))
                ax2.set_extent([xmin, xmax, float(np.nanmin(lat2d)), float(np.nanmax(lat2d))], crs=ccrs.PlateCarree())
            add_map(ax2, left=True, bottom=True)
            cax2 = fig2.add_axes([0.12, 0.08, 0.78, 0.045])
            cb2 = fig2.colorbar(hc, cax=cax2, orientation='horizontal'); cb2.set_label('K')
            out_t = outdir / f"elt_comp_TML_{season_name}_{tag}.png"
            tmp2 = out_t.with_suffix('.tmp.png')
            fig2.savefig(tmp2, dpi=args.dpi); plt.close(fig2); tmp2.replace(out_t)

        plot_set('primary', prim_fields)
        if alt_fields is not None:
            plot_set('alt', alt_fields)


if __name__ == '__main__':
    main()
