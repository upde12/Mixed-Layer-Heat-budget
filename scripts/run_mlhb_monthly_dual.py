#!/usr/bin/env python3
"""Run MLHB monthly twice for comparison: centered vs centered_deepening.

This is a thin orchestrator around scripts/run_mlhb_monthly.py that:
 - runs Jan–Apr 1993 (or a user-specified window) twice
 - once with we-mode=centered (entrainment+detrainment)
 - once with we-mode=centered_deepening (entrainment-only; w_e>0)
 - writes two separate monthly NetCDF outputs

It forwards most arguments to the underlying monthly runner so paths and
parameters remain consistent.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dual monthly MLHB run: centered and centered_deepening")
    p.add_argument("--start", default="1993-01")
    p.add_argument("--end", default="1993-04")
    p.add_argument("--indir", default="/Volumes/HJPARK4/MHW/data/GLORYS/ncfiles")
    p.add_argument("--fluxdir", default="/Volumes/HJPARK4/MHW/data/ERA5/daily_EA")
    p.add_argument(
        "--out-root",
        default="/Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly_centered",
        help="Root path for outputs; suffixes _full.nc and _entrain.nc will be added.",
    )
    p.add_argument("--temp-root", default="/Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily")
    p.add_argument("--python", default=".venv/bin/python")
    p.add_argument("--workers", default="auto")
    p.add_argument("--ah", type=float, default=100.0)
    p.add_argument("--kv", type=float, default=1e-4)
    p.add_argument("--use-hbar-denom", action="store_true")
    p.add_argument("--mld-source", default="recompute")
    p.add_argument("--mld-threshold", type=float, default=0.03)
    p.add_argument("--mld-ref-depth", type=float, default=10.0)
    p.add_argument("--min-free-gb", type=float, default=90.0)
    return p.parse_args()


def run_monthly_once(args: argparse.Namespace, we_mode: str, out_path: Path) -> None:
    cmd = [
        args.python,
        "scripts/run_mlhb_monthly.py",
        "--start", args.start,
        "--end", args.end,
        "--indir", args.indir,
        "--fluxdir", args.fluxdir,
        "--out", str(out_path),
        "--temp-root", args.temp_root,
        "--python", args.python,
        "--workers", args.workers,
        "--ah", str(args.ah),
        "--kv", str(args.kv),
        "--we-mode", we_mode,
        "--mld-source", args.mld_source,
        "--mld-threshold", str(args.mld_threshold),
        "--mld-ref-depth", str(args.mld_ref_depth),
        "--min-free-gb", str(args.min_free_gb),
    ]
    if args.use_hbar_denom:
        cmd.append("--use-hbar-denom")
    print("[DUAL-RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)
    out_full = out_root.with_name(out_root.name + "_full").with_suffix(".nc")
    out_entrain = out_root.with_name(out_root.name + "_entrain").with_suffix(".nc")

    # 1) centered (entrainment+detrainment)
    run_monthly_once(args, we_mode="centered", out_path=out_full)
    # 2) centered_deepening (entrainment-only)
    run_monthly_once(args, we_mode="centered_deepening", out_path=out_entrain)
    print(f"[DONE] Wrote: {out_full}\n[DONE] Wrote: {out_entrain}")


if __name__ == "__main__":
    print('[notice] This runner has moved to the MLHB project. Please use MLHB/scripts/run_mlhb_monthly_dual.py')
    raise SystemExit(0)
