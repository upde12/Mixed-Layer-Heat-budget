#!/usr/bin/env python3
"""Plot temperature/salinity/density profiles and highlight MLD.

Usage example:
    python scripts/plot_mld_profile.py \
        --file /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles/GLO_PHY_MY_19930101_19930101.nc \
        --lat 30.0 --lon 138.0 --region WNP --out figures/mld_profile_wnp_19930101.png \
        --max-depth 200
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import xarray as xr
import gsw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", required=True, help="GLORYS daily NetCDF file")
    parser.add_argument("--lat", type=float, required=True, help="Target latitude (deg N)")
    parser.add_argument("--lon", type=float, required=True, help="Target longitude (deg E)")
    parser.add_argument("--region", default="region", help="Region label for title/filename")
    parser.add_argument("--out", required=True, help="Output image path")
    parser.add_argument("--max-depth", type=float, default=200.0, help="Depth limit in plot (m)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    nc_path = Path(args.file)
    if not nc_path.exists():
        raise FileNotFoundError(nc_path)

    ds = xr.open_dataset(nc_path, decode_times=False)

    theta = ds["thetao"].isel(time=0).sel(latitude=args.lat, longitude=args.lon, method="nearest")
    so = ds["so"].isel(time=0).sel(latitude=args.lat, longitude=args.lon, method="nearest")
    mld = ds["mlotst"].isel(time=0).sel(latitude=args.lat, longitude=args.lon, method="nearest")

    depth = ds["depth"].values.astype(float)

    lat_actual = float(theta.latitude)
    lon_actual = float(theta.longitude)
    temp_profile = theta.values.astype(float)
    sal_profile = so.values.astype(float)
    mask = np.isfinite(temp_profile) & np.isfinite(sal_profile)
    if not np.any(mask):
        raise ValueError("No finite temperature/salinity values at this location.")
    temp_profile = temp_profile[mask]
    sal_profile = sal_profile[mask]
    depth = depth[mask]
    mld_value = float(mld.values)

    p = gsw.p_from_z(-depth, lat_actual)
    SA = gsw.SA_from_SP(sal_profile, p, lon_actual, lat_actual)
    CT = gsw.CT_from_pt(SA, temp_profile)
    sigma0 = gsw.sigma0(SA, CT)
    mask_sigma = np.isfinite(sigma0)
    temp_profile = temp_profile[mask_sigma]
    sal_profile = sal_profile[mask_sigma]
    sigma0 = sigma0[mask_sigma]
    depth = depth[mask_sigma]
    p = p[mask_sigma]
    SA = SA[mask_sigma]
    CT = CT[mask_sigma]
    if temp_profile.size == 0:
        raise ValueError("Density profile contains no finite values.")

    def value_at(target: float, depths: np.ndarray, values: np.ndarray) -> float:
        if target <= depths[0]:
            return float(values[0])
        if target >= depths[-1]:
            return float(values[-1])
        return float(np.interp(target, depths, values))

    # basic sanity checks before plotting
    if np.any((temp_profile < -5) | (temp_profile > 40)):
        raise ValueError("Temperature profile outside expected oceanic range (-5 to 40 °C).")
    if np.any((sal_profile < 0) | (sal_profile > 40)):
        raise ValueError("Salinity profile outside expected range (0 to 40 psu).")
    if np.any((sigma0 < 20) | (sigma0 > 30)):
        raise ValueError("Sigma0 profile outside expected range (20 to 30 kg m^-3).")

    # reference depths
    temp_ref = value_at(10.0, depth, temp_profile)
    sigma_ref = value_at(10.0, depth, sigma0)
    depth_ref = value_at(10.0, depth, depth)

    temp_mld = value_at(mld_value, depth, temp_profile)
    sigma_mld = value_at(mld_value, depth, sigma0)
    depth_mld = value_at(mld_value, depth, depth)

    SA_ref = value_at(10.0, depth, SA)
    CT_ref = value_at(10.0, depth, CT)
    # TEOS-10: use rho(SA, CT, p) for conservative temperature; do not use rho_t_exact with CT
    alpha_ref = gsw.alpha(SA_ref, CT_ref, 0.0)
    rho_ref = gsw.rho(SA_ref, CT_ref, 0.0)
    delta_sigma = sigma_mld - sigma_ref
    delta_t_actual = temp_mld - temp_ref
    delta_t_equiv = delta_sigma / (rho_ref * alpha_ref) if rho_ref * alpha_ref != 0 else float('nan')

    fig, ax = plt.subplots(figsize=(6, 6))
    y = depth

    color_temp = "tab:red"
    color_sal = "tab:blue"
    color_sig = "tab:green"

    def make_formatter(decimals: int) -> FuncFormatter:
        def _fmt(value, _):
            if np.isnan(value):
                return ""
            formatted = f"{value:.{decimals}f}"
            formatted = formatted.rstrip('0').rstrip('.')
            return formatted
        return FuncFormatter(_fmt)

    def compute_limits(values: np.ndarray, mask: np.ndarray | None = None, pad_fraction: float = 0.1) -> tuple[float, float]:
        if mask is not None:
            data = values[mask]
        else:
            data = values
        data = data[np.isfinite(data)]
        if data.size == 0:
            return (-1, 1)
        vmin = float(np.nanmin(data))
        vmax = float(np.nanmax(data))
        if vmax <= vmin:
            pad = 0.05 * (abs(vmax) if vmax != 0 else 1.0)
            return vmin - pad, vmax + pad
        span = vmax - vmin
        pad = span * pad_fraction
        if pad == 0:
            ref = max(abs(vmin), abs(vmax), 1.0)
            pad = ref * pad_fraction
        return vmin - pad, vmax + pad

    depth_limit = min(args.max_depth, float(depth[-1]))
    upper_mask = depth <= depth_limit

    ax.plot(temp_profile, y, label="Potential Temp (°C)", color=color_temp)
    ax.set_xlabel("Temperature (°C)", color=color_temp)
    ax.set_ylabel("Depth (m)")
    ax.tick_params(axis="x", colors=color_temp)
    ax.xaxis.set_major_formatter(make_formatter(2))
    ax.set_xlim(compute_limits(temp_profile, upper_mask))

    ax2 = ax.twiny()
    ax2.spines["top"].set_position(("axes", 1.05))
    ax2.plot(sal_profile, y, label="Salinity (psu)", color=color_sal)
    ax2.set_xlabel("Salinity (psu)", color=color_sal)
    ax2.tick_params(axis="x", colors=color_sal, pad=2)
    ax2.spines["top"].set_color(color_sal)
    ax2.xaxis.set_major_formatter(make_formatter(3))
    ax2.set_xlim(compute_limits(sal_profile, upper_mask))

    ax3 = ax.twiny()
    ax3.spines["top"].set_position(("axes", 1.18))
    ax3.plot(sigma0, y, label="σ₀ (kg m⁻³)", color=color_sig)
    ax3.set_xlabel("σ₀ (kg m⁻³)", color=color_sig)
    ax3.tick_params(axis="x", colors=color_sig, pad=2)
    ax3.spines["top"].set_color(color_sig)
    ax3.xaxis.set_major_formatter(make_formatter(3))
    ax3.set_xlim(compute_limits(sigma0, upper_mask))

    # ensure label positions are staggered further to avoid overlap
    ax2.xaxis.set_label_coords(0.5, 1.13)
    ax3.xaxis.set_label_coords(0.5, 1.30)

    for axis in (ax, ax2, ax3):
        axis.set_ylim(depth_limit, 0)
        axis.grid(True, alpha=0.2)

    ax.axhline(mld_value, color="black", linestyle="--", label=f"MLD = {mld_value:.1f} m")

    annotation = (
        f"ΔT_actual (MLD - {depth_ref:.1f} m) = {delta_t_actual:+.2f} °C\n"
        f"ΔT_equiv ≈ {delta_t_equiv:+.2f} °C\n"
        f"Δσ₀ = {delta_sigma:+.3f} kg m⁻³"
    )
    ax.text(
        0.02,
        0.02,
        annotation,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        bbox=dict(facecolor="white", alpha=0.75, edgecolor="none"),
    )

    ax.set_title(
        f"GLORYS profile @ ({lat_actual:.2f}°N, {lon_actual:.2f}°E) | {args.region}\n{nc_path.name}"
    )

    lines, labels = [], []
    for axis in (ax, ax2, ax3):
        line, label = axis.get_legend_handles_labels()
        lines.extend(line)
        labels.extend(label)
    ax.legend(lines, labels, loc="upper right")

    fig.tight_layout(rect=[0, 0, 1, 0.9])
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    print(f"Saved figure to {out_path}")
    return 0


if __name__ == "__main__":
    print('[notice] This script has moved to the MLHB project. Please use MLHB/scripts/plot_mld_profile.py')
    raise SystemExit(0)
