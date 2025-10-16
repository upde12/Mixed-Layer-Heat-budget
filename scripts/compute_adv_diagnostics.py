#!/usr/bin/env python3
"""Build Kuroshio-region diagnostics for multiple advection schemes."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Kuroshio diagnostics for MLHB advection runs")
    parser.add_argument("--schemes", default="centered,upwind,flux")
    parser.add_argument("--root", default="/Volumes/HJPARK4/Decadal/source/ML_budget/output/adv_schemes")
    parser.add_argument("--lat-min", type=float, default=28.0)
    parser.add_argument("--lat-max", type=float, default=36.0)
    parser.add_argument("--lon-min", type=float, default=128.0)
    parser.add_argument("--lon-max", type=float, default=145.0)
    parser.add_argument("--out-path", default="/Volumes/HJPARK4/Decadal/source/ML_budget/output/adv_schemes/kuroshio/adv_kuroshio_diagnostics.nc")
    return parser.parse_args()


def _phase_array(lat: xr.DataArray, lon: xr.DataArray) -> xr.DataArray:
    i = xr.DataArray(np.arange(lat.size), dims=("lat",), coords={"lat": lat})
    j = xr.DataArray(np.arange(lon.size), dims=("lon",), coords={"lon": lon})
    phase = ((i + j) % 2) * 2 - 1
    return phase.astype(np.float32)


def _weights(lat: xr.DataArray, template: xr.DataArray) -> xr.DataArray:
    lat_weights = xr.DataArray(np.cos(np.deg2rad(lat)), dims=("lat",), coords={"lat": lat})
    reference = template.isel(time=0)
    weights = lat_weights.broadcast_like(reference)
    return weights.astype(np.float32)


def load_scheme_data(path_root: Path, scheme: str, lat_slice: slice, lon_slice: slice) -> tuple[xr.DataArray, xr.DataArray]:
    daily_path = path_root / scheme / "daily" / "ml_budget_1993.nc"
    monthly_dir = path_root / scheme / "monthly"
    monthly_files = sorted(monthly_dir.glob("adv_monthly_*.nc"))
    if not daily_path.exists():
        raise FileNotFoundError(daily_path)
    if not monthly_files:
        raise FileNotFoundError(f"No monthly files in {monthly_dir}")

    daily_ds = xr.open_dataset(daily_path)
    daily = daily_ds["ADV"].sel(lat=lat_slice, lon=lon_slice).astype(np.float32).load()
    daily_ds.close()

    monthly_ds = xr.open_mfdataset(monthly_files, combine="by_coords")
    monthly = monthly_ds["ADV"].sel(lat=lat_slice, lon=lon_slice).astype(np.float32).load()
    monthly = monthly.rename(time="time_monthly")
    monthly_ds.close()

    return daily, monthly


def compute_metrics(data: xr.DataArray, weights: xr.DataArray, phase: xr.DataArray) -> tuple[xr.DataArray, xr.DataArray]:
    mask = xr.where(np.isfinite(data), 1.0, 0.0)
    effective_weights = weights * mask
    weight_sum = effective_weights.sum(dim=("lat", "lon"))
    area_mean = (data * effective_weights).sum(dim=("lat", "lon")) / weight_sum

    checker = data * phase
    checker_rms = np.sqrt(((checker ** 2) * effective_weights).sum(dim=("lat", "lon")) / weight_sum)
    return area_mean.astype(np.float32), checker_rms.astype(np.float32)


def main() -> None:
    args = parse_args()
    schemes = [s.strip() for s in args.schemes.split(",") if s.strip()]
    path_root = Path(args.root)
    lat_slice = slice(args.lat_min, args.lat_max)
    lon_slice = slice(args.lon_min, args.lon_max)

    daily_list = []
    monthly_list = []
    area_daily = []
    area_monthly = []
    checker_daily = []
    checker_monthly = []

    for scheme in schemes:
        daily, monthly = load_scheme_data(path_root, scheme, lat_slice, lon_slice)
        phase = _phase_array(daily["lat"], daily["lon"])
        weights = _weights(daily["lat"], daily)

        area_mean_d, checker_d = compute_metrics(daily, weights, phase)
        area_mean_m, checker_m = compute_metrics(monthly, weights, phase)

        daily_list.append(daily.expand_dims(scheme=[scheme]))
        monthly_list.append(monthly.expand_dims(scheme=[scheme]))
        area_daily.append(area_mean_d.expand_dims(scheme=[scheme]))
        area_monthly.append(area_mean_m.expand_dims(scheme=[scheme]))
        checker_daily.append(checker_d.expand_dims(scheme=[scheme]))
        checker_monthly.append(checker_m.expand_dims(scheme=[scheme]))

    adv_daily = xr.concat(daily_list, dim="scheme")
    adv_monthly = xr.concat(monthly_list, dim="scheme")
    area_daily = xr.concat(area_daily, dim="scheme")
    area_monthly = xr.concat(area_monthly, dim="scheme")
    checker_daily = xr.concat(checker_daily, dim="scheme")
    checker_monthly = xr.concat(checker_monthly, dim="scheme")

    ds_out = xr.Dataset(
        {
            "adv_daily": adv_daily,
            "adv_monthly": adv_monthly,
            "adv_daily_area_mean": area_daily,
            "adv_monthly_area_mean": area_monthly,
            "adv_daily_checker_rms": checker_daily,
            "adv_monthly_checker_rms": checker_monthly,
        }
    )
    out_path = Path(args.out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    encoding = {var: {"zlib": True, "complevel": 4} for var in ds_out.data_vars}
    ds_out.to_netcdf(out_path, encoding=encoding)
    ds_out.close()


if __name__ == "__main__":
    print('[notice] This script has moved to the MLHB project. Please use MLHB/scripts/compute_adv_diagnostics.py')
    raise SystemExit(0)
