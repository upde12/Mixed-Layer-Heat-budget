#!/usr/bin/env python3
"""Append a timestamped note to today's temporary journal file."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
TMP_DIR = BASE_DIR / 'docs' / 'journal' / 'tmp'


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Append a note to docs/journal/tmp/<date>_notes.md')
    parser.add_argument('message', help='Text to append')
    parser.add_argument('--date', help='YYYY-MM-DD (default: today)')
    parser.add_argument('--time', help='HH:MM (default: now)')
    parser.add_argument('--workdir', help='Working directory to record (default: current directory relative to repo root)')
    return parser.parse_args(argv)


def resolved_date(date_str: str | None) -> dt.date:
    if date_str:
        return dt.datetime.strptime(date_str, '%Y-%m-%d').date()
    return dt.date.today()


def resolved_time(time_str: str | None) -> str:
    if time_str:
        # Validate format
        dt.datetime.strptime(time_str, '%H:%M')
        return time_str
    return dt.datetime.now().strftime('%H:%M')


def ensure_file(date: dt.date) -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    path = TMP_DIR / f'{date:%Y-%m-%d}_notes.md'
    if not path.exists():
        header = f'# Temporary Notes – {date:%Y-%m-%d}\n\n'
        path.write_text(header, encoding='utf-8')
    return path


def resolved_workdir(workdir: str | None) -> str:
    if workdir:
        return workdir
    try:
        rel = Path.cwd().relative_to(BASE_DIR)
        return '.' if str(rel) == '.' else rel.as_posix()
    except ValueError:
        return str(Path.cwd())


def append_note(path: Path, time_str: str, message: str, workdir: str) -> None:
    with path.open('a', encoding='utf-8') as fh:
        fh.write(f'- {time_str} {message} [dir: {workdir}]\n')


def main(argv=None):
    args = parse_args(argv)
    date = resolved_date(args.date)
    time_str = resolved_time(args.time)
    path = ensure_file(date)
    workdir = resolved_workdir(args.workdir)
    append_note(path, time_str, args.message, workdir)
    print(f'Appended note to {path.relative_to(BASE_DIR)}')


if __name__ == '__main__':
    raise SystemExit(main())
