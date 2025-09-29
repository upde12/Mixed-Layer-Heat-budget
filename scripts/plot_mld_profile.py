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
    mld_value = float(mld.values)

    p = gsw.p_from_z(-depth, lat_actual)
    SA = gsw.SA_from_SP(sal_profile, p, lon_actual, lat_actual)
    CT = gsw.CT_from_pt(SA, temp_profile)
    sigma0 = gsw.sigma0(SA, CT)

    fig, ax = plt.subplots(figsize=(6, 6))
    y = depth

    color_temp = "tab:red"
    color_sal = "tab:blue"
    color_sig = "tab:green"

    ax.plot(temp_profile, y, label="Potential Temp (°C)", color=color_temp)
    ax.set_xlabel("Temperature (°C)", color=color_temp)
    ax.set_ylabel("Depth (m)")
    ax.tick_params(axis="x", colors=color_temp)

    ax2 = ax.twiny()
    ax2.spines["top"].set_position(("axes", 1.05))
    ax2.plot(sal_profile, y, label="Salinity (psu)", color=color_sal)
    ax2.set_xlabel("Salinity (psu)", color=color_sal)
    ax2.tick_params(axis="x", colors=color_sal)
    ax2.spines["top"].set_color(color_sal)

    ax3 = ax.twiny()
    ax3.spines["top"].set_position(("axes", 1.15))
    ax3.plot(sigma0, y, label="σ₀ (kg m⁻³)", color=color_sig)
    ax3.set_xlabel("σ₀ (kg m⁻³)", color=color_sig)
    ax3.tick_params(axis="x", colors=color_sig)
    ax3.spines["top"].set_color(color_sig)

    max_depth = min(args.max_depth, float(depth[-1]))
    for axis in (ax, ax2, ax3):
        axis.set_ylim(max_depth, 0)
        axis.grid(True, alpha=0.2)

    ax.axhline(mld_value, color="black", linestyle="--", label=f"MLD = {mld_value:.1f} m")

    ax.set_title(
        f"GLORYS profile @ ({lat_actual:.2f}°N, {lon_actual:.2f}°E) | {args.region}\n{nc_path.name}"
    )

    lines, labels = [], []
    for axis in (ax, ax2, ax3):
        line, label = axis.get_legend_handles_labels()
        lines.extend(line)
        labels.extend(label)
    ax.legend(lines, labels, loc="upper right")

    fig.tight_layout()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200)
    print(f"Saved figure to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

