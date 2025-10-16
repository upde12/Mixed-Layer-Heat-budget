#!/usr/bin/env python3
"""Plot vertical profiles (T/S/sigma0) from GLORYS and overlay recomputed MLD from MLHB daily file.

Example
  python llm-ops/scripts/plot_mld_profile_recomputed.py \
    --glorys /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles/GLO_PHY_MY_19930101_19930101.nc \
    --mlhb   /Volumes/HJPARK4/Decadal/source/ML_budget/output/daily/1993/01/ml_budget_1993.nc \
    --lat 30.0 --lon 138.0 --region WNP \
    --out llm-ops/figures/mld_profile_wnp_19930101_recomputed.png --max-depth 200
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import xarray as xr
import gsw


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--glorys", required=True, help="GLORYS daily NetCDF file (e.g., GLO_PHY_MY_YYYYMMDD_YYYYMMDD.nc)")
    p.add_argument("--mlhb", required=True, help="MLHB daily output NetCDF (ml_budget_YYYY.nc) for the same month")
    p.add_argument("--lat", type=float, required=True, help="Target latitude (deg N)")
    p.add_argument("--lon", type=float, required=True, help="Target longitude (deg E)")
    p.add_argument("--region", default="region", help="Region label for title/filename")
    p.add_argument("--out", help="Output image path (optional; default saves to MLHB/figures)")
    p.add_argument("--fig-root", help="Figure root directory (default: MLHB/figures)")
    p.add_argument("--max-depth", type=float, default=200.0, help="Absolute cap for depth limit (m)")
    p.add_argument("--depth-mode", choices=["auto", "fixed"], default="auto", help="Depth selection: auto=1.2*MLD, fixed=use --fixed-depth")
    p.add_argument("--fixed-depth", type=float, default=100.0, help="Depth limit when --depth-mode=fixed (m)")
    p.add_argument("--density", choices=["sigma0", "insitu"], default="sigma0", help="Density curve to plot: σ0 at 0 dbar (default) or in-situ ρ(SA,CT,p)")
    return p.parse_args()


def parse_date_from_name(path: Path) -> np.datetime64:
    m = re.search(r"(\d{8})_(\d{8})", path.name)
    if not m:
        raise ValueError(f"Cannot parse date from GLORYS filename: {path.name}")
    ymd = m.group(1)
    return np.datetime64(f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}")


def nearest_time_index(tvals: np.ndarray, target: np.datetime64) -> int:
    # robust cast to datetime64[s] for subtraction
    t_ref = tvals.astype("datetime64[s]")
    tar = target.astype("datetime64[s]")
    idx = int(np.argmin(np.abs(t_ref - tar)))
    return idx


def main() -> int:
    args = parse_args()
    gpath = Path(args.glorys)
    mpath = Path(args.mlhb)
    if not gpath.exists():
        raise FileNotFoundError(gpath)
    if not mpath.exists():
        raise FileNotFoundError(mpath)

    date0 = parse_date_from_name(gpath)

    # 1) GLORYS raw profiles (T/S) and product coords
    dsg = xr.open_dataset(gpath, decode_times=False)
    theta = dsg["thetao"].isel(time=0).sel(latitude=args.lat, longitude=args.lon, method="nearest")
    so = dsg["so"].isel(time=0).sel(latitude=args.lat, longitude=args.lon, method="nearest")
    depth = dsg["depth"].values.astype(float)
    lat_actual = float(theta.latitude)
    lon_actual = float(theta.longitude)
    tprof = theta.values.astype(float)
    sprof = so.values.astype(float)
    mask = np.isfinite(tprof) & np.isfinite(sprof)
    if not np.any(mask):
        raise ValueError("No finite T/S values at this location.")
    tprof = tprof[mask]
    sprof = sprof[mask]
    depth = depth[mask]

    # 2) Recomputed MLD from MLHB daily file (nearest time/lat/lon)
    dsm = xr.open_dataset(mpath)
    # nearest grid point
    mld_point = dsm["MLD"].sel(lat=lat_actual, lon=lon_actual, method="nearest")
    # find time index matching GLORYS date
    if "time" in mld_point.coords:
        tvals = mld_point["time"].values
        tidx = nearest_time_index(tvals, date0)
        mld_val = float(mld_point.isel(time=tidx).values)
    else:
        mld_val = float(mld_point.values)

    # 3) Compute sigma0 profile via TEOS-10 at GLORYS point
    p = gsw.p_from_z(-depth, lat_actual)
    SA = gsw.SA_from_SP(sprof, p, lon_actual, lat_actual)
    CT = gsw.CT_from_pt(SA, tprof)
    sigma0 = gsw.sigma0(SA, CT)
    rho_insitu = gsw.rho(SA, CT, p)  # kg/m^3
    ok = np.isfinite(sigma0)
    tprof, sprof, sigma0, depth = tprof[ok], sprof[ok], sigma0[ok], depth[ok]

    def value_at(target: float, depths: np.ndarray, values: np.ndarray) -> float:
        if target <= depths[0]:
            return float(values[0])
        if target >= depths[-1]:
            return float(values[-1])
        return float(np.interp(target, depths, values))

    # Basic sanity
    if np.any((tprof < -5) | (tprof > 40)):
        raise ValueError("Temperature out of range (-5..40 °C)")
    if np.any((sprof < 0) | (sprof > 40)):
        raise ValueError("Salinity out of range (0..40 psu)")
    if np.any((sigma0 < 20) | (sigma0 > 30)):
        raise ValueError("Sigma0 out of range (20..30 kg m^-3)")

    # 10 m / MLD references
    temp_ref = value_at(10.0, depth, tprof)
    sigma_ref = value_at(10.0, depth, sigma0)
    temp_mld = value_at(mld_val, depth, tprof)
    sigma_mld = value_at(mld_val, depth, sigma0)

    SA_ref = value_at(10.0, depth, SA)
    CT_ref = value_at(10.0, depth, CT)
    # TEOS-10: use rho(SA, CT, p) for conservative temperature; do not use rho_t_exact with CT
    alpha_ref = gsw.alpha(SA_ref, CT_ref, 0.0)
    rho_ref = gsw.rho(SA_ref, CT_ref, 0.0)
    delta_sigma = sigma_mld - sigma_ref
    delta_t_actual = temp_mld - temp_ref
    # ΔT_equiv: temperature-only change that would yield the same Δσ0
    # δσ0_T = -ρ·α·ΔT  ⇒  ΔT ≈ -Δσ0 / (ρ·α)
    delta_t_equiv = (-delta_sigma / (rho_ref * alpha_ref)) if (rho_ref * alpha_ref) != 0 else float('nan')

    # 4) Plot
    # Two-row figure: top=T/S/σ0, bottom=N^2 (s^-2)
    fig, axes = plt.subplots(
        nrows=2, ncols=1, sharey=True,
        gridspec_kw=dict(height_ratios=[3, 1]), figsize=(6, 7.2)
    )
    ax = axes[0]
    y = depth
    color_temp, color_sal, color_sig = "tab:red", "tab:blue", "tab:green"

    def fmt(decimals: int) -> FuncFormatter:
        def _f(val, _):
            if np.isnan(val):
                return ""
            s = f"{val:.{decimals}f}".rstrip('0').rstrip('.')
            return s
        return FuncFormatter(_f)

    def limits(values: np.ndarray, mask: np.ndarray | None = None, pad: float = 0.1):
        data = values[np.isfinite(values)] if mask is None else values[mask]
        data = data[np.isfinite(data)]
        if data.size == 0:
            return (-1, 1)
        vmin, vmax = float(np.nanmin(data)), float(np.nanmax(data))
        if vmax <= vmin:
            p = 0.05 * (abs(vmax) if vmax != 0 else 1.0)
            return vmin - p, vmax + p
        span = vmax - vmin
        return vmin - span * pad, vmax + span * pad

    # Depth limit selection
    # - auto: 1.2*MLD (if available), capped by --max-depth
    # - fixed: use --fixed-depth, capped by --max-depth
    if args.depth_mode == "fixed":
        dlim = float(min(float(args.fixed_depth), float(args.max_depth)))
    else:
        if np.isfinite(mld_val):
            dlim_mld = float(mld_val) * 1.2
            dlim = float(min(dlim_mld, float(args.max_depth)))
        else:
            dlim = float(args.max_depth)
    umask = depth <= dlim

    ax.plot(tprof, y, label="Potential Temp (°C)", color=color_temp)
    ax.set_xlabel("Temperature (°C)", color=color_temp)
    ax.set_ylabel("Depth (m)")
    ax.tick_params(axis="x", colors=color_temp)
    ax.xaxis.set_major_formatter(fmt(2))
    ax.set_xlim(limits(tprof, umask))

    ax2 = ax.twiny()
    ax2.spines["top"].set_position(("axes", 1.05))
    ax2.plot(sprof, y, label="Salinity (psu)", color=color_sal)
    ax2.set_xlabel("Salinity (psu)", color=color_sal)
    ax2.tick_params(axis="x", colors=color_sal, pad=2)
    ax2.spines["top"].set_color(color_sal)
    ax2.xaxis.set_major_formatter(fmt(3))
    ax2.set_xlim(limits(sprof, umask))

    ax3 = ax.twiny()
    ax3.spines["top"].set_position(("axes", 1.18))
    if args.density == "insitu":
        dens_curve = rho_insitu
        dens_label = "ρ (kg m⁻³)"
    else:
        dens_curve = sigma0
        dens_label = "σ₀ (kg m⁻³)"
    ax3.plot(dens_curve, y, label=dens_label, color=color_sig)
    ax3.set_xlabel(dens_label, color=color_sig)
    ax3.tick_params(axis="x", colors=color_sig, pad=2)
    ax3.spines["top"].set_color(color_sig)
    ax3.xaxis.set_major_formatter(fmt(3))
    ax3.set_xlim(limits(dens_curve, umask))
    ax2.xaxis.set_label_coords(0.5, 1.13)
    ax3.xaxis.set_label_coords(0.5, 1.30)

    for axis in (ax, ax2, ax3):
        axis.set_ylim(dlim, 0)
        axis.grid(True, alpha=0.2)

    ax.axhline(mld_val, color="black", linestyle="--", label=f"MLD (recomputed) = {mld_val:.1f} m")

    note = (
        f"ΔT_actual (MLD-10 m) = {delta_t_actual:+.2f} °C\n"
        f"ΔT_equiv ≈ {delta_t_equiv:+.2f} °C\n"
        f"Δσ₀ = {delta_sigma:+.3f} kg m⁻³"
    )
    ax.text(0.02, 0.02, note, transform=ax.transAxes, ha="left", va="bottom", fontsize=9,
            bbox=dict(facecolor="white", alpha=0.75, edgecolor="none"))

    ax.set_title(
        f"GLORYS profile @ ({lat_actual:.2f}°N, {lon_actual:.2f}°E) | {args.region}\n"
        f"{gpath.name} (MLD from {mpath.name}, {str(date0)[:10]})"
    )

    lines, labels = [], []
    for axis in (ax, ax2, ax3):
        lns, lbs = axis.get_legend_handles_labels()
        lines.extend(lns); labels.extend(lbs)
    ax.legend(lines, labels, loc="upper right")

    # Bottom panel: N^2 (buoyancy frequency squared)
    # TEOS-10: N2 from SA, CT, p
    try:
        N2, p_mid = gsw.Nsquared(SA, CT, p, lat_actual)
        z_mid = 0.5 * (depth[:-1] + depth[1:])
        N2_pos = np.where(N2 > 0, N2, np.nan)
        axn = axes[1]
        axn.plot(N2_pos, z_mid, color="purple", label=r"N$^2$ (s$^{-2}$)")
        # log-scale for positive values
        axn.set_xscale("log")
        # x-limits: robust defaults if empty
        if np.isfinite(N2_pos).any():
            xmin = float(np.nanmin(N2_pos))
            xmax = float(np.nanmax(N2_pos))
            if xmin <= 0 or not np.isfinite(xmin):
                xmin = 1e-7
            if not np.isfinite(xmax):
                xmax = 1e-3
        else:
            xmin, xmax = 1e-7, 1e-3
        axn.set_xlim(xmin, xmax)
        axn.set_xlabel(r"N$^2$ (s$^{-2}$)")
        axn.set_ylim(dlim, 0)
        axn.grid(True, alpha=0.2)
    except Exception as _:
        # If Nsquared fails, leave panel blank with note
        axn = axes[1]
        axn.text(0.5, 0.5, "N^2 unavailable", transform=axn.transAxes, ha="center", va="center")
        axn.set_ylim(dlim, 0)
        axn.set_xlabel(r"N$^2$ (s$^{-2}$)")

    # Resolve output path
    out_path: Path
    if args.out:
        out_path = Path(args.out)
    else:
        # default MLHB figures directory
        # try common locations
        candidates = [
            Path("/Users/hjpark/Desktop/GPT/MLHB/figures"),
            Path(__file__).resolve().parents[3] / "MLHB" / "figures",
            Path(__file__).resolve().parents[2] / "MLHB" / "figures",
        ]
        fig_root = None
        if args.fig_root:
            fig_root = Path(args.fig_root)
        else:
            for c in candidates:
                if c.parent.exists():
                    fig_root = c
                    break
        if fig_root is None:
            fig_root = Path("figures")  # fallback to local
        # construct filename
        date_str = str(date0)[:10].replace("-", "")
        fname = f"mld_profile_recomputed_{args.region}_{date_str}_{lat_actual:.2f}_{lon_actual:.2f}.png"
        out_path = fig_root / fname

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(rect=[0, 0, 1, 0.9])
    plt.savefig(out_path, dpi=200)
    print(f"Saved figure to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
