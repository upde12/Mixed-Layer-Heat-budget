#!/usr/bin/env python3
"""Run MLHB daily outputs for multiple advection schemes and form monthly means.

The script wraps ``process_d2nf.py`` so we can compare ``ADV`` computed with
different horizontal advection discretisations (centered, upwind, flux). It
also produces per-scheme monthly-mean NetCDF files derived from the daily
output so downstream diagnostics can focus on the Kuroshio region.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
from pathlib import Path

import xarray as xr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MLHB for multiple advection schemes")
    parser.add_argument("--schemes", default="centered,upwind,flux", help="Comma-separated list of advection schemes")
    parser.add_argument("--start-date", default="1993-01-01")
    parser.add_argument("--end-date", default="1993-04-30")
    parser.add_argument("--we-mode", default="centered_deepening")
    parser.add_argument("--workers", default="auto")
    parser.add_argument("--indir", default="/Volumes/HJPARK4/MHW/data/GLORYS/ncfiles")
    parser.add_argument("--fluxdir", default="/Volumes/HJPARK4/MHW/data/ERA5/daily_EA")
    parser.add_argument("--out-root", default="/Volumes/HJPARK4/Decadal/source/ML_budget/output/adv_schemes")
    parser.add_argument("--python", default=".venv/bin/python")
    parser.add_argument("--use-hbar-denom", action="store_true")
    parser.add_argument("--skip-run", action="store_true", help="Skip process_d2nf runs and only build monthly means")
    return parser.parse_args()


def _years_arg(start: dt.date, end: dt.date) -> str:
    if start.year == end.year:
        return str(start.year)
    return f"{start.year}:{end.year}"


def run_scheme(args: argparse.Namespace, scheme: str, start: dt.date, end: dt.date) -> Path:
    years_arg = _years_arg(start, end)
    daily_out = Path(args.out_root) / scheme / "daily"
    daily_out.mkdir(parents=True, exist_ok=True)

    cmd = [
        args.python,
        "src/process_d2nf.py",
        "--indir",
        args.indir,
        "--outdir",
        str(daily_out),
        "--fluxdir",
        args.fluxdir,
        "--years",
        years_arg,
        "--start-date",
        start.isoformat(),
        "--end-date",
        end.isoformat(),
        "--workers",
        args.workers,
        "--we-mode",
        args.we_mode,
        "--adv-scheme",
        scheme,
    ]
    if args.use_hbar_denom:
        cmd.append("--use-hbar-denom")

    print("[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return daily_out


def build_monthly(daily_out: Path, start: dt.date, end: dt.date) -> Path:
    monthly_out = daily_out.parent / "monthly"
    monthly_out.mkdir(parents=True, exist_ok=True)

    daily_files = sorted(daily_out.glob("ml_budget_*.nc"))
    if not daily_files:
        raise FileNotFoundError(f"No daily outputs in {daily_out}")

    ds = xr.open_mfdataset(daily_files, combine="by_coords")
    ds_adv = ds[["ADV"]]
    monthly = ds_adv.resample(time="MS").mean(skipna=True)
    # CF-compliant time coordinate via encoding (avoid overwriting attrs keys)
    if "time" in monthly.coords:
        attrs = dict(monthly["time"].attrs)
        attrs.pop("units", None)
        attrs.pop("calendar", None)
        attrs["long_name"] = "time"
        monthly["time"].attrs = attrs
        monthly["time"].encoding.update({
            "units": "days since 1970-01-01 00:00:00",
            "calendar": "standard",
        })

    tag = f"{start.year}{start.month:02d}_{end.year}{end.month:02d}"
    monthly_path = monthly_out / f"adv_monthly_{tag}.nc"
    monthly.to_netcdf(monthly_path)

    ds.close()
    return monthly_path


def main() -> None:
    args = parse_args()
    schemes = [s.strip() for s in args.schemes.split(",") if s.strip()]
    start = dt.datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end = dt.datetime.strptime(args.end_date, "%Y-%m-%d").date()

    for scheme in schemes:
        if not args.skip_run:
            daily_out = run_scheme(args, scheme, start, end)
        else:
            daily_out = Path(args.out_root) / scheme / "daily"
            if not daily_out.exists():
                raise FileNotFoundError(f"Missing daily output directory: {daily_out}")
        monthly_path = build_monthly(daily_out, start, end)
        print(f"[DONE] scheme={scheme} monthly={monthly_path}")


if __name__ == "__main__":
    print('[notice] This runner has moved to the MLHB project. Please use MLHB/scripts/run_adv_schemes.py')
    raise SystemExit(0)
