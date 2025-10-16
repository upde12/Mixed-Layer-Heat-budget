#!/usr/bin/env python3
"""CLI helper to scaffold raw chat transcript files."""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
TRANSCRIPT_DIR = BASE_DIR / "docs" / "discussions" / "transcripts"
ROOT_ALIAS = "MLHB"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a timestamped transcript stub under docs/discussions/transcripts"
    )
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--time",
        help="HH:MM (default: now)",
    )
    parser.add_argument(
        "--suffix",
        help="Optional short label appended to filename, e.g., mlhb",
    )
    parser.add_argument(
        "--note",
        help="Optional guidance text to include below the header",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing file instead of creating an incremented copy",
    )
    return parser.parse_args(argv)


def resolved_date(date_str: str | None) -> dt.date:
    if date_str:
        return dt.datetime.strptime(date_str, "%Y-%m-%d").date()
    return dt.date.today()


def resolved_time(time_str: str | None) -> str:
    if time_str:
        dt.datetime.strptime(time_str, "%H:%M")
        return time_str
    return dt.datetime.now().strftime("%H:%M")


def slugify(value: str) -> str:
    keep = [c.lower() for c in value if c.isalnum() or c in {"-", "_"}]
    slug = "".join(keep).strip("-")
    return slug or "session"


def build_path(date_val: dt.date, suffix: str | None, force: bool) -> Path:
    base_name = f"{date_val:%Y-%m-%d}_session_raw"
    if suffix:
        base_name = f"{date_val:%Y-%m-%d}_{slugify(suffix)}_session_raw"
    candidate = TRANSCRIPT_DIR / f"{base_name}.txt"
    if force or not candidate.exists():
        return candidate
    index = 2
    while True:
        numbered = TRANSCRIPT_DIR / f"{base_name}_{index}.txt"
        if not numbered.exists():
            return numbered
        index += 1


def write_stub(path: Path, date_val: dt.date, time_str: str, note: str | None) -> None:
    created = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"Transcript: {date_val:%Y-%m-%d} session (raw)",
        "",
        f"(Created {created}; session marker ~{time_str}. Paste conversation below using 'User:'/'Assistant:' format.)",
        "",
    ]
    if note:
        lines.extend([note, ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    date_val = resolved_date(args.date)
    time_str = resolved_time(args.time)
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    target = build_path(date_val, args.suffix, args.force)
    if target.exists() and not args.force:
        print(f"Refusing to overwrite existing file: {target.relative_to(BASE_DIR)}", file=sys.stderr)
        return 1
    write_stub(target, date_val, time_str, args.note)
    rel = target.relative_to(BASE_DIR).as_posix()
    print(f"Created transcript stub: {ROOT_ALIAS}/{rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
