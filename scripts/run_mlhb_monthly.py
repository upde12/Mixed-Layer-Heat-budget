#!/usr/bin/env python3
"""Run MLHB monthly pipeline: daily run, monthly mean append, cleanup."""
from __future__ import annotations

import argparse
import calendar
import subprocess
import traceback
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import numpy as np
import xarray as xr

DT = 86400.0


@dataclass
class MonthWindow:
    year: int
    month: int

    @property
    def start(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def end(self) -> date:
        last_day = calendar.monthrange(self.year, self.month)[1]
        return date(self.year, self.month, last_day)

    def label(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


def month_sequence(start: str, end: str) -> Iterable[MonthWindow]:
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    current_y, current_m = sy, sm
    while (current_y, current_m) <= (ey, em):
        yield MonthWindow(current_y, current_m)
        if current_m == 12:
            current_y += 1
            current_m = 1
        else:
            current_m += 1


def check_disk_free(path: Path, min_free_gb: float) -> None:
    usage = subprocess.check_output(["df", "-k", str(path)])
    lines = usage.decode().strip().splitlines()
    if len(lines) >= 2:
        parts = lines[-1].split()
        avail_kb = int(parts[3])
        avail_gb = avail_kb / (1024 * 1024)
        if avail_gb < min_free_gb:
            raise RuntimeError(
                f"Available space {avail_gb:.1f} GB is below threshold {min_free_gb} GB"
            )


def run_daily(window: MonthWindow, args) -> Path:
    scratch_dir = Path(args.temp_root) / f"{window.year:04d}" / f"{window.month:02d}"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    outdir = scratch_dir

    cmd = [
        args.python,
        "src/process_d2nf.py",
        "--indir",
        args.indir,
        "--outdir",
        str(outdir),
        "--fluxdir",
        args.fluxdir,
        "--years",
        f"{window.year}:{window.year}",
        "--workers",
        args.workers,
        "--start-date",
        window.start.isoformat(),
        "--end-date",
        window.end.isoformat(),
        "--ah",
        str(args.ah),
        "--kv",
        str(args.kv),
        "--we-mode",
        args.we_mode,
        "--adv-scheme",
        args.adv_scheme,
    ]
    if args.use_hbar_denom:
        cmd.append("--use-hbar-denom")
    if args.mld_source:
        cmd.extend(["--mld-source", args.mld_source])
    if args.mld_threshold is not None:
        cmd.extend(["--mld-threshold", str(args.mld_threshold)])
    if args.mld_ref_depth is not None:
        cmd.extend(["--mld-ref-depth", str(args.mld_ref_depth)])
    if args.ten_anchor:
        cmd.extend(["--ten-anchor", args.ten_anchor])

    print("[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)

    daily_path = outdir / f"ml_budget_{window.year}.nc"
    if not daily_path.exists():
        raise FileNotFoundError(daily_path)
    return daily_path


def append_monthly(daily_nc: Path, window: MonthWindow, agg_path: Path) -> None:
    ds_daily = xr.open_dataset(daily_nc)
    month_mean = ds_daily.mean(dim="time", skipna=True, keep_attrs=True)
    month_mean.attrs.update(ds_daily.attrs)
    ds_daily.close()

    time_val = np.datetime64(window.start)
    month_mean = month_mean.expand_dims(time=[time_val]).assign_coords(time=("time", [time_val]))

    if agg_path.exists():
        existing = xr.open_dataset(agg_path)
        combined = xr.concat([existing, month_mean], dim="time")
        existing.close()
    else:
        combined = month_mean

    combined = combined.sortby("time")
    # Ensure CF-compliant time axis without conflicting with encoding
    if "time" in combined.coords:
        # keep descriptive attrs only; do not set units/calendar here
        attrs = dict(combined["time"].attrs)
        attrs.pop("units", None)
        attrs.pop("calendar", None)
        attrs["long_name"] = "time"
        combined["time"].attrs = attrs

    encoding = {var: {"zlib": True, "complevel": 4} for var in combined.data_vars}
    encoding.update({coord: {"zlib": False} for coord in combined.coords if coord != "time"})
    encoding["time"] = {
        "dtype": "f8",
        "_FillValue": None,
        "units": "days since 1970-01-01 00:00:00",
        "calendar": "standard",
    }

    tmp_path = agg_path.parent / f"{agg_path.name}.tmp"
    combined.to_netcdf(
        tmp_path,
        mode="w",
        engine="netcdf4",
        format="NETCDF4_CLASSIC",
        unlimited_dims="time",
        encoding=encoding,
    )
    tmp_path.replace(agg_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MLHB monthly pipeline")
    parser.add_argument("--start", default="1993-01")
    parser.add_argument("--end", default="2020-12")
    parser.add_argument("--indir", default="/Volumes/HJPARK4/MHW/data/GLORYS/ncfiles")
    parser.add_argument("--fluxdir", default="/Volumes/HJPARK4/MHW/data/ERA5/daily_EA")
    parser.add_argument("--out", default="/Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly.nc")
    parser.add_argument("--temp-root", default="/Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily")
    parser.add_argument("--python", default=".venv/bin/python")
    parser.add_argument("--workers", default="auto")
    parser.add_argument("--ah", type=float, default=100.0)
    parser.add_argument("--kv", type=float, default=1e-4)
    parser.add_argument("--we-mode", default="deepening")
    parser.add_argument(
        "--adv-scheme",
        choices=["centered", "upwind", "flux"],
        default="centered",
    )
    parser.add_argument("--use-hbar-denom", action="store_true")
    parser.add_argument("--mld-source", default="recompute")
    parser.add_argument("--mld-threshold", type=float, default=0.03)
    parser.add_argument("--mld-ref-depth", type=float, default=10.0)
    parser.add_argument("--min-free-gb", type=float, default=90.0)
    parser.add_argument("--keep-daily", action="store_true", help="Do not delete daily scratch after monthly append")
    parser.add_argument("--ten-anchor", choices=["backward","forward","centered"], default="forward")
    return parser.parse_args()


def cleanup(path: Path) -> None:
    if not path.exists():
        return
    for child in list(path.iterdir()):
        try:
            if child.is_file():
                child.unlink(missing_ok=True)
            else:
                cleanup(child)
                child.rmdir()
        except FileNotFoundError:
            continue
    try:
        path.rmdir()
    except OSError:
        pass


def main():
    args = parse_args()
    print('[notice] This runner has moved to the MLHB project. Please use MLHB/scripts/run_mlhb_monthly.py')
    agg_path = Path(args.out)
    agg_path.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(args.temp_root)
    temp_root.mkdir(parents=True, exist_ok=True)

    check_disk_free(agg_path.parent, args.min_free_gb)

    for window in month_sequence(args.start, args.end):
        label = window.label()
        print(f"===== {label} =====")
        scratch_dir = temp_root / f"{window.year:04d}" / f"{window.month:02d}"
        cleanup(scratch_dir)
        scratch_dir.mkdir(parents=True, exist_ok=True)
        try:
            daily_nc = run_daily(window, args)
            append_monthly(daily_nc, window, agg_path)
        except Exception as exc:
            print(f"[ERR] {label}: {exc}")
            traceback.print_exc()
            raise
        finally:
            if not args.keep_daily:
                cleanup(scratch_dir)
        print(f"[DONE] {label} appended to {agg_path}")


if __name__ == "__main__":
    main()
