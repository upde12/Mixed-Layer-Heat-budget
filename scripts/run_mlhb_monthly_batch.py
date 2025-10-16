#!/usr/bin/env python3
"""Run MLHB monthly mainline in parallel across months.

Spawns multiple instances of scripts/run_mlhb_monthly_main.py, each for a
single month, so that daily scratch is preserved (--keep-daily) and a per-month
NetCDF file is written (one time step per file). Concurrency is limited by
--parallel.
"""
from __future__ import annotations

import argparse
import calendar
import os
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class MonthWindow:
    year: int
    month: int

    @property
    def label(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def yyyymm(self) -> str:
        return f"{self.year:04d}{self.month:02d}"


def month_sequence(start: str, end: str) -> Iterable[MonthWindow]:
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    y, m = sy, sm
    while (y, m) <= (ey, em):
        yield MonthWindow(y, m)
        if m == 12:
            y += 1
            m = 1
        else:
            m += 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Parallel monthly MLHB runner")
    p.add_argument("--start", default="1993-01")
    p.add_argument("--end", default="2022-12")
    p.add_argument("--indir", required=True)
    p.add_argument("--fluxdir", required=True)
    p.add_argument("--out-root", required=True, help="Directory for per-month NetCDF outputs")
    p.add_argument("--temp-root", required=True, help="Root for daily scratch")
    p.add_argument("--python", default=".venv/bin/python")
    p.add_argument("--parallel", type=int, default=6)
    p.add_argument("--workers", default="auto")
    p.add_argument("--ah", type=float, default=100.0)
    p.add_argument("--kv", type=float, default=1e-4)
    p.add_argument("--we-mode", default="deepening")
    p.add_argument("--mld-source", default="recompute")
    p.add_argument("--mld-threshold", type=float, default=0.03)
    p.add_argument("--mld-ref-depth", type=float, default=10.0)
    p.add_argument("--min-free-gb", type=float, default=90.0)
    p.add_argument("--log-dir", default="logs/monthly", help="Relative log dir (under repo)")
    return p.parse_args()


def run_one_month(win: MonthWindow, args: argparse.Namespace, repo: Path) -> tuple[str, int]:
    out_dir = Path(args.out_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = (repo / args.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"mlhb_monthly_main_{win.yyyymm}.nc"
    log_file = log_dir / f"mlhb_main_{win.yyyymm}.log"

    cmd = [
        args.python,
        str(repo / "scripts/run_mlhb_monthly_main.py"),
        "--start", win.label, "--end", win.label,
        "--indir", args.indir,
        "--fluxdir", args.fluxdir,
        "--out", str(out_file),
        "--temp-root", args.temp_root,
        "--python", args.python,
        "--workers", args.workers,
        "--ah", str(args.ah),
        "--kv", str(args.kv),
        "--we-mode", args.we_mode,
        "--mld-source", args.mld_source,
        "--mld-threshold", str(args.mld_threshold),
        "--mld-ref-depth", str(args.mld_ref_depth),
        "--min-free-gb", str(args.min_free_gb),
        "--keep-daily",
    ]

    with open(log_file, "w") as lf:
        lf.write("[RUN] " + " ".join(cmd) + "\n")
        lf.flush()
        proc = subprocess.run(cmd, stdout=lf, stderr=lf)
        return (win.label, proc.returncode)


def main() -> int:
    args = parse_args()
    repo = Path(__file__).resolve().parents[1]

    months = list(month_sequence(args.start, args.end))
    statuses: list[tuple[str, int]] = []
    with ThreadPoolExecutor(max_workers=max(1, int(args.parallel))) as ex:
        futs = [ex.submit(run_one_month, win, args, repo) for win in months]
        for fut in as_completed(futs):
            label, rc = fut.result()
            statuses.append((label, rc))
            print(f"[DONE] {label} rc={rc}")

    failed = [lab for lab, rc in sorted(statuses) if rc != 0]
    if failed:
        print("[SUMMARY] Failed months:", ", ".join(failed))
        return 1
    print("[SUMMARY] All months completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

