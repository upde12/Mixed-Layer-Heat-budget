#!/usr/bin/env python3
"""Diagnose SODA monthly MLD (mlp) definition at a point by vertical profiles.

Loads a SODA3.4.2 monthly file (time=12), extracts a (lon,lat) profile for a
given month, and compares the provided `mlp` to two candidate criteria:

  A) Fixed density threshold:    Δσθ = 0.03 kg m^-3 at 10 m
  B) Temperature-equivalent:     Δσθ = |∂σ/∂T|_(~10 m) * 0.2 °C at 10 m

For each, we linearly interpolate σ_ref at 10 m from the two bracketing layers
and search downward for the first depth where (σ(z) - σ_ref) >= threshold.
The script renders a quick-look figure and prints the depths for comparison.

Outputs a PNG under `--out` (defaults to workspace diagnostics).
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", required=True, help="SODA monthly NetCDF (soda3.4.2_mn_ocean_reg_YYYY.nc)")
    p.add_argument("--month", type=int, default=1, help="Calendar month 1..12")
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--out", default="llm-ops/docs/diagnostics/mlp_diagnosis.png", help="Output PNG path")
    return p.parse_args(argv)


def nearest_index(arr: np.ndarray, value: float) -> int:
    return int(np.nanargmin(np.abs(arr - value)))


def sigma_at_ref(sigma: np.ndarray, zc: np.ndarray, ref_depth: float = 10.0) -> Tuple[np.ndarray, int]:
    """Return σ_ref at ref_depth via linear interpolation; also k_ref index below ref.

    sigma: (nz,) at a single column; zc: (nz,) positive-down centres.
    """
    k_ref = int(np.clip(np.searchsorted(zc, ref_depth, side="right") - 1, 0, len(zc) - 2))
    z0, z1 = float(zc[k_ref]), float(zc[k_ref + 1])
    s0, s1 = float(sigma[k_ref]), float(sigma[k_ref + 1])
    w = (ref_depth - z0) / (z1 - z0 + 1e-12)
    sref = s0 + w * (s1 - s0)
    return sref, k_ref


def crossing_depth_fixed(sigma: np.ndarray, zc: np.ndarray, sref: float, k_ref: int, d_sigma: float) -> float | np.nan:
    prev = sigma[k_ref] - sref
    for k in range(k_ref + 1, len(zc)):
        cur = sigma[k] - sref
        if np.isfinite(prev) and np.isfinite(cur) and (cur >= d_sigma):
            z0, z1 = float(zc[k - 1]), float(zc[k])
            d0, d1 = float(prev), float(cur)
            frac = (d_sigma - d0) / (d1 - d0 + 1e-12)
            return z0 + np.clip(frac, 0.0, 1.0) * (z1 - z0)
        prev = cur
    return np.nan


def crossing_depth_varsigma(sigma: np.ndarray, temp: np.ndarray, zc: np.ndarray, sref: float, k_ref: int, dT: float = 0.2) -> float | np.nan:
    # local slope ∂σ/∂T around 10 m using k_ref..k_ref+1
    d_sig = sigma[k_ref + 1] - sigma[k_ref]
    d_tmp = temp[k_ref + 1] - temp[k_ref]
    if not (np.isfinite(d_sig) and np.isfinite(d_tmp) and (abs(d_tmp) > 1e-6)):
        return np.nan
    d_sigma_eq = abs(float(d_sig / d_tmp)) * float(dT)
    return crossing_depth_fixed(sigma, zc, sref, k_ref, d_sigma_eq)


def plot_profile(zc: np.ndarray, sigma: np.ndarray, sref: float, mlp: float, zA: float, zB: float, out: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(4.2, 6.0))
    d = sigma - sref
    ax.plot(d, zc, color="k", lw=1.2, label=r"σ(z)−σ(10 m)")
    ax.axvline(0.0, color="gray", lw=0.8)
    ax.axhline(10.0, color="gray", lw=0.8, ls=":")
    if np.isfinite(zA):
        ax.axhline(zA, color="tab:blue", lw=1.2, ls="--", label=r"A: Δσ=0.03")
    if np.isfinite(zB):
        ax.axhline(zB, color="tab:orange", lw=1.2, ls="--", label=r"B: Δσ=|∂σ/∂T|·0.2°C")
    if np.isfinite(mlp):
        ax.axhline(mlp, color="tab:green", lw=1.2, ls="-.", label="mlp (SODA)")
    ax.set_ylim(max(50.0, float(np.nanmax(zc))), 0.0)
    ax.set_xlabel(r"Δσ (kg m$^{-3}$)")
    ax.set_ylabel("Depth (m)")
    ax.grid(True, ls=":", alpha=0.4)
    ax.legend(fontsize=8, loc="lower right")
    ax.set_title(title, fontsize=10)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    tmp = out.with_suffix(".tmp.png")
    fig.savefig(tmp, dpi=170)
    plt.close(fig)
    tmp.replace(out)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    ds = xr.open_dataset(args.file)
    m = int(args.month) - 1
    lat = ds["yt_ocean"].values
    lon = ds["xt_ocean"].values
    j = nearest_index(lat, float(args.lat))
    i = nearest_index(lon, float(args.lon))
    zc = ds["st_ocean"].values.astype(np.float64)
    # extract monthly column
    prho = ds["prho"].isel(time=m, yt_ocean=j, xt_ocean=i).values.astype(np.float64)
    temp = ds["temp"].isel(time=m, yt_ocean=j, xt_ocean=i).values.astype(np.float64)
    sigma = prho - 1000.0
    mlp = float(ds["mlp"].isel(time=m, yt_ocean=j, xt_ocean=i).values) if "mlp" in ds else np.nan
    sref, kref = sigma_at_ref(sigma, zc, 10.0)
    zA = crossing_depth_fixed(sigma, zc, sref, kref, 0.03)
    zB = crossing_depth_varsigma(sigma, temp, zc, sref, kref, 0.2)
    title = f"SODA MLD diagnosis @ ({float(lat[j]):.2f}N, {float(lon[i]):.2f}E), month={m+1}"
    plot_profile(zc, sigma, sref, mlp, zA, zB, Path(args.out), title)
    print(f"Nearest grid: lat={float(lat[j]):.3f}, lon={float(lon[i]):.3f}")
    print(f"Depths (m): mlp={mlp:.2f}, A(Δσ=0.03)={zA:.2f}, B(|∂σ/∂T|·0.2)={zB:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

