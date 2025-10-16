#!/usr/bin/env python3
"""Plot T/S/σ0 vertical profiles from SODA monthly and highlight MLD (mlp).

Guidelines adhered: docs/guidelines/02_plot_guidelines.md §D (혼합층 프로파일 시각화)
- Overplot potential temperature (°C), salinity (psu), σ0 (kg m^-3)
- Show MLD (mlp) as dashed line; annotate Δσ0 at MLD vs 10 m and ΔT_actual/ΔT_equiv
- Use TEOS-10 (gsw) for σ0 from SP/pt where possible
"""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import xarray as xr
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import gsw


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--file", required=True, help="SODA monthly NetCDF (soda3.4.2_mn_ocean_reg_YYYY.nc)")
    p.add_argument("--month", type=int, default=1, help="Calendar month 1..12")
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--out", required=True, help="Output PNG path")
    p.add_argument("--max-depth", type=float, default=200.0)
    return p.parse_args()


def _fmt(decimals: int) -> FuncFormatter:
    def f(v, _):
        if np.isnan(v):
            return ""
        s = f"{v:.{decimals}f}".rstrip("0").rstrip(".")
        return s
    return FuncFormatter(f)


def interp_at(z: np.ndarray, y: np.ndarray, zt: float) -> float:
    if zt <= z[0]:
        return float(y[0])
    if zt >= z[-1]:
        return float(y[-1])
    return float(np.interp(zt, z, y))


def main() -> int:
    a = parse_args()
    ds = xr.open_dataset(a.file)
    m = int(a.month) - 1
    # nearest grid point
    col_T = ds["temp"].isel(time=m).sel(yt_ocean=a.lat, xt_ocean=a.lon, method="nearest")
    col_S = ds["salt"].isel(time=m).sel(yt_ocean=a.lat, xt_ocean=a.lon, method="nearest")
    lat0 = float(col_T.yt_ocean)
    lon0 = float(col_T.xt_ocean)
    z = ds["st_ocean"].values.astype(float)
    T = col_T.values.astype(float)
    S = col_S.values.astype(float)
    mask = np.isfinite(T) & np.isfinite(S)
    z = z[mask]; T = T[mask]; S = S[mask]
    if T.size < 3:
        raise SystemExit("Insufficient valid levels at this point")
    # TEOS-10
    p = gsw.p_from_z(-z, lat0)
    SA = gsw.SA_from_SP(S, p, lon0, lat0)
    CT = gsw.CT_from_pt(SA, T)
    sigma0 = gsw.sigma0(SA, CT)
    # MLD from file (mlp)
    mlp = float(ds["mlp"].isel(time=m).sel(yt_ocean=lat0, xt_ocean=lon0, method="nearest").values)
    # references at 10 m and MLD
    T10 = interp_at(z, T, 10.0)
    sig10 = interp_at(z, sigma0, 10.0)
    TM = interp_at(z, T, mlp)
    sigM = interp_at(z, sigma0, mlp)
    dT_actual = TM - T10
    # α,ρ at 10m for ΔT_equiv
    SA10 = interp_at(z, SA, 10.0)
    CT10 = interp_at(z, CT, 10.0)
    alpha10 = gsw.alpha(SA10, CT10, 0.0)
    rho10 = gsw.rho(SA10, CT10, 0.0)
    dSigma = sigM - sig10
    dT_equiv = (dSigma / (rho10 * alpha10)) if (rho10 * alpha10) != 0 else np.nan

    # Plot per guidelines
    fig, ax = plt.subplots(figsize=(6.0, 6.0))
    depth_limit = min(a.max_depth, float(z[-1]))
    ylim = (depth_limit, 0.0)
    ax.plot(T, z, color="tab:red", label="Potential Temp (°C)")
    ax.set_xlabel("Temperature (°C)", color="tab:red")
    ax.set_ylabel("Depth (m)")
    ax.tick_params(axis="x", colors="tab:red")
    ax.xaxis.set_major_formatter(_fmt(2))
    ax.set_ylim(*ylim)
    ax.grid(True, alpha=0.2)

    ax2 = ax.twiny()
    ax2.spines["top"].set_position(("axes", 1.05))
    ax2.plot(S, z, color="tab:blue", label="Salinity (psu)")
    ax2.set_xlabel("Salinity (psu)", color="tab:blue")
    ax2.tick_params(axis="x", colors="tab:blue", pad=2)
    ax2.spines["top"].set_color("tab:blue")
    ax2.xaxis.set_major_formatter(_fmt(3))
    ax2.set_ylim(*ylim)

    ax3 = ax.twiny()
    ax3.spines["top"].set_position(("axes", 1.18))
    ax3.plot(sigma0, z, color="tab:green", label="σ₀ (kg m⁻³)")
    ax3.set_xlabel("σ₀ (kg m⁻³)", color="tab:green")
    ax3.tick_params(axis="x", colors="tab:green", pad=2)
    ax3.spines["top"].set_color("tab:green")
    ax3.xaxis.set_major_formatter(_fmt(3))
    ax3.set_ylim(*ylim)
    ax2.xaxis.set_label_coords(0.5, 1.13)
    ax3.xaxis.set_label_coords(0.5, 1.30)

    ax.axhline(mlp, color="black", ls="--", label=f"MLD (mlp) = {mlp:.1f} m")
    ax.axhline(10.0, color="gray", lw=0.8, ls=":")
    ax.axvline(0.0, color="gray", lw=0.6)
    ann = (
        f"ΔT_actual (MLD−10 m) = {dT_actual:+.2f} °C\n"
        f"ΔT_equiv ≈ {dT_equiv:+.2f} °C\n"
        f"Δσ₀ = {dSigma:+.3f} kg m⁻³"
    )
    ax.text(0.02, 0.02, ann, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=9, bbox=dict(facecolor="white", alpha=0.75, edgecolor="none"))
    ax.set_title(f"SODA monthly profile @ ({lat0:.2f}°N, {lon0:.2f}°E), month={a.month}\n{Path(a.file).name}")

    lines, labels = [], []
    for axis in (ax, ax2, ax3):
        l, lab = axis.get_legend_handles_labels()
        lines += l; labels += lab
    ax.legend(lines, labels, loc="upper right", fontsize=9)

    out_path = Path(a.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp.png")
    fig.tight_layout()
    fig.savefig(tmp, dpi=180)
    plt.close(fig)
    tmp.replace(out_path)
    print(f"Saved {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

