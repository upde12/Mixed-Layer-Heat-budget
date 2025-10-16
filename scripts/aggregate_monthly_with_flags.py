#!/usr/bin/env python3
"""Aggregate daily MLHB to monthly means under flag on/off policies (8 combos).

Reads a daily MLHB NetCDF (time × lat × lon) that includes diagnostic mask
variables written by src/process_d2nf.py:
  - MASK_SHALLOW_LT10 (0/1)
  - MASK_DEEP_NO_CROSS (0/1)
  - MASK_INVERSE_GE10 (0/1)
  - MASK_FULLY_MIXED (0/1)

For each policy bit S/D/I (include=1, exclude=0), it masks daily fields where
the corresponding mask is 1 and the policy bit is 0, then computes a monthly
mean with skipna=True. Writes 8 monthly files with suffix _S{0/1}D{0/1}I{0/1}.nc

Example
  python llm-ops/scripts/aggregate_monthly_with_flags.py \
    --daily /Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily/1993/01/ml_budget_1993.nc \
    --out-root /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_199301_flags
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import numpy as np
import xarray as xr


MASK_VARS = (
    "MASK_SHALLOW_LT10",
    "MASK_DEEP_NO_CROSS",
    "MASK_INVERSE_GE10",
    "MASK_FULLY_MIXED",
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--daily", required=True, help="Daily MLHB NetCDF (time×lat×lon)")
    p.add_argument("--out-root", required=True, help="Output root path (prefix for files)")
    return p.parse_args()


def policy_allowed(ds: xr.Dataset, s_inc: int, d_inc: int, i_inc: int) -> xr.DataArray:
    """Return a boolean DataArray(time,lat,lon) where samples are included.

    - s_inc: include shallow (<10 m)
    - d_inc: include deep-no-cross
    - i_inc: include inverse_ge10
    """
    allowed = xr.ones_like(ds["MLD"], dtype=bool)
    if "MASK_SHALLOW_LT10" in ds:
        if int(s_inc) == 0:
            allowed = allowed & (~ds["MASK_SHALLOW_LT10"].astype(bool))
    if "MASK_DEEP_NO_CROSS" in ds:
        if int(d_inc) == 0:
            allowed = allowed & (~ds["MASK_DEEP_NO_CROSS"].astype(bool))
    if "MASK_INVERSE_GE10" in ds:
        if int(i_inc) == 0:
            allowed = allowed & (~ds["MASK_INVERSE_GE10"].astype(bool))
    return allowed


def aggregate_one(ds: xr.Dataset, allowed: xr.DataArray) -> xr.Dataset:
    # apply mask per-variable (exclude mask variables themselves)
    data_vars = [v for v in ds.data_vars if v not in MASK_VARS]
    out_vars: Dict[str, xr.DataArray] = {}
    for v in data_vars:
        da = ds[v]
        if {"time", "lat", "lon"}.issubset(set(da.dims)):
            masked = da.where(allowed)
            out_vars[v] = masked.mean(dim="time", skipna=True, keep_attrs=True)
        else:
            # keep non-(time,lat,lon) variables as-is where sensible
            out_vars[v] = da
    # Build output dataset with 1-length time dimension
    month_start = np.array([np.datetime64(str(ds["time"].values[0])[:10])], dtype="datetime64[ns]")
    result = xr.Dataset(
        {k: v.expand_dims(time=month_start, axis=0) if ("lat" in v.dims and "lon" in v.dims) else v for k, v in out_vars.items()},
        coords={
            "time": ("time", month_start),
            "lat": ds["lat"],
            "lon": ds["lon"],
        },
        attrs=dict(ds.attrs),
    )
    # CF-compliant time encoding
    if "time" in result.coords:
        attrs = dict(result["time"].attrs)
        attrs.pop("units", None)
        attrs.pop("calendar", None)
        attrs["long_name"] = "time"
        result["time"].attrs = attrs
    enc = {var: {"zlib": True, "complevel": 4} for var in result.data_vars}
    enc.update({coord: {"zlib": False} for coord in result.coords if coord != "time"})
    enc["time"] = {"dtype": "f8", "_FillValue": None, "units": "days since 1970-01-01 00:00:00", "calendar": "standard"}
    result.encoding = {}
    return result, enc


def write_nc(ds: xr.Dataset, enc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    ds.to_netcdf(tmp, mode="w", engine="netcdf4", format="NETCDF4", encoding=enc, unlimited_dims="time")
    tmp.replace(path)


def main() -> int:
    args = parse_args()
    daily_path = Path(args.daily)
    out_root = Path(args.out_root)

    ds = xr.open_dataset(daily_path)
    # ensure masks exist
    missing = [m for m in ("MASK_SHALLOW_LT10", "MASK_DEEP_NO_CROSS", "MASK_INVERSE_GE10") if m not in ds]
    if missing:
        raise SystemExit(f"missing required mask variables: {', '.join(missing)}")

    for s in (0, 1):
        for d in (0, 1):
            for i in (0, 1):
                allowed = policy_allowed(ds, s, d, i)
                out, enc = aggregate_one(ds, allowed)
                # annotate policy in attrs
                out.attrs.update({
                    "policy_shallow_included": int(s),
                    "policy_deepnocross_included": int(d),
                    "policy_inverse_included": int(i),
                    "aggregation_source": "aggregate_monthly_with_flags.py",
                })
                out_path = out_root.with_name(out_root.name + f"_S{s}D{d}I{i}").with_suffix(".nc")
                write_nc(out, enc, out_path)
                print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

