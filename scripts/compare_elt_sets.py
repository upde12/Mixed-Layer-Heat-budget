#!/usr/bin/env python3
"""Compare ELT-year composite anomalies between two year sets.

Computes composites for two ELT year lists and reports pattern similarity
(pattern correlation r, RMS ratio, sign agreement) for selected months or
seasons and variables (QNET, ADV, ENT, DIFF, DIFFV, SUBS, TEN, T_ML).

Inputs are monthly files: mlhb_monthly_main_YYYYMM.nc (time=1 per file).
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np
import xarray as xr


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--monthly-root", required=True)
    p.add_argument("--years-a", required=True, help="Comma-separated ELT years (set A)")
    p.add_argument("--years-b", required=True, help="Comma-separated ELT years (set B)")
    p.add_argument("--months", default="1-12", help="Months to include, e.g., 1-12 or 1,2,3 or prev11,prev12")
    p.add_argument("--adv-smooth-iter", type=int, default=2)
    p.add_argument("--diffv-mode", choices=["native","residual"], default="native")
    p.add_argument("--unit", choices=["day","month"], default="month")
    p.add_argument("--region", default=None, help="latmin,latmax,lonmin,lonmax (optional subset for metrics)")
    p.add_argument("--out", default=None, help="Optional Markdown summary output path")
    return p.parse_args(argv)


def parse_years(s: str) -> List[int]:
    return [int(t) for t in s.split(',') if t.strip()]


def parse_months(spec: str) -> List[Tuple[int, bool]]:
    out: List[Tuple[int, bool]] = []
    for token in [t.strip() for t in spec.split(',') if t.strip()]:
        if '-' in token and not token.startswith('prev'):
            a, b = token.split('-', 1)
            for m in range(int(a), int(b) + 1):
                out.append((m, False))
        elif token.startswith('prev'):
            m = int(token.replace('prev', ''))
            out.append((m, True))
        else:
            out.append((int(token), False))
    return out


def open_month(root: Path, year: int, month: int) -> xr.Dataset:
    fn = root / f"mlhb_monthly_main_{year:04d}{month:02d}.nc"
    if not fn.exists():
        raise FileNotFoundError(fn)
    return xr.open_dataset(fn)


def mean_stack(dsets: List[xr.Dataset]) -> xr.Dataset:
    ds = xr.concat(dsets, dim='stack')
    out = ds.mean('stack', skipna=True, keep_attrs=True)
    for d in dsets:
        try:
            d.close()
        except Exception:
            pass
    return out


def pick(ds: xr.Dataset, name: str) -> xr.DataArray:
    lower = name.lower()
    for k in ds.data_vars:
        if k.lower() == lower:
            return ds[k]
    if lower == 't_ml':
        for a in ('t_ml','tml','tmean'):
            for k in ds.data_vars:
                if k.lower() == a:
                    return ds[k]
    raise KeyError(name)


def smth9_2d(a: np.ndarray, p: float = 0.50, q: float = 0.25) -> np.ndarray:
    ny, nx = a.shape
    def shift(di, dj):
        out = np.full_like(a, np.nan)
        si0, si1 = (0, ny-di) if di>=0 else (-di, ny)
        di0, di1 = (di, ny) if di>=0 else (0, ny+di)
        sj0, sj1 = (0, nx-dj) if dj>=0 else (-dj, nx)
        dj0, dj1 = (dj, nx) if dj>=0 else (0, nx+dj)
        if si1>si0 and sj1>sj0:
            out[di0:di1, dj0:dj1] = a[si0:si1, sj0:si1]
        return out
    c = a
    n = np.roll(c, -1, axis=0); s = np.roll(c, 1, axis=0); w = np.roll(c, -1, axis=1); e = np.roll(c, 1, axis=1)
    nw = np.roll(n, -1, axis=1); ne = np.roll(n, 1, axis=1); sw = np.roll(s, -1, axis=1); se = np.roll(s, 1, axis=1)
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


def composite(root: Path, years: Sequence[int], months: Sequence[Tuple[int, bool]]) -> xr.Dataset:
    dsets: List[xr.Dataset] = []
    for y in years:
        for m, is_prev in months:
            yy = y - 1 if is_prev else y
            fn = root / f"mlhb_monthly_main_{yy:04d}{m:02d}.nc"
            if fn.exists():
                dsets.append(xr.open_dataset(fn))
    return mean_stack(dsets).mean('time', skipna=True)


def clim(root: Path, months: Sequence[Tuple[int, bool]]) -> xr.Dataset:
    dsets: List[xr.Dataset] = []
    months_only = sorted({m for m, _ in months})
    for m in months_only:
        mm: List[xr.Dataset] = []
        for yy in range(1993, 2023):
            fn = root / f"mlhb_monthly_main_{yy:04d}{m:02d}.nc"
            if fn.exists():
                mm.append(xr.open_dataset(fn))
        if mm:
            dsets.append(mean_stack(mm).mean('time', skipna=True))
    return mean_stack(dsets) if dsets else None


def metrics(a: np.ndarray, b: np.ndarray) -> Tuple[float, float, float]:
    mask = np.isfinite(a) & np.isfinite(b)
    if not np.any(mask):
        return np.nan, np.nan, np.nan
    va = a[mask].ravel(); vb = b[mask].ravel()
    va = va - np.nanmean(va); vb = vb - np.nanmean(vb)
    r = float(np.dot(va, vb) / (np.sqrt(np.dot(va, va)) * np.sqrt(np.dot(vb, vb)) + 1e-12))
    rms_ratio = float(np.sqrt(np.nanmean(va**2)) / (np.sqrt(np.nanmean(vb**2)) + 1e-12))
    sign_agree = float(np.mean(np.sign(va) == np.sign(vb)))
    return r, rms_ratio, sign_agree


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.monthly_root)
    years_a = parse_years(args.years_a)
    years_b = parse_years(args.years_b)
    months = parse_months(args.months)

    comp_a = composite(root, years_a, months)
    comp_b = composite(root, years_b, months)
    cl = clim(root, months)

    def diff(name: str) -> Tuple[xr.DataArray, xr.DataArray]:
        A = (comp_a[name] - cl[name]).squeeze(drop=True)
        B = (comp_b[name] - cl[name]).squeeze(drop=True)
        return A, B

    names = ['QNET','ADV','ENT','DIFF','DIFFV','TEN','T_ML']
    scale = 1.0 if args.unit == 'day' else 30.4375
    lines = []
    for nm in names:
        A, B = diff(nm)
        if nm == 'ADV':
            A = maybe_smooth(A, args.adv_smooth_iter)
            B = maybe_smooth(B, args.adv_smooth_iter)
        if nm in {'QNET','ADV','ENT','DIFF','DIFFV','TEN'}:
            A = A * scale; B = B * scale
        r, ratio, signp = metrics(A.values, B.values)
        lines.append((nm, r, ratio, signp))

    out_text = [
        f"Comparison months={args.months} unit={args.unit} adv_smooth_iter={args.adv_smooth_iter}",
        f"Years A: {years_a}",
        f"Years B: {years_b}",
        "",
        "Variable | pattern_r | RMS_ratio(A/B) | sign_agreement",
    ]
    for nm, r, ratio, signp in lines:
        out_text.append(f"{nm} | {r:.3f} | {ratio:.3f} | {signp:.3f}")

    text = "\n".join(out_text) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

