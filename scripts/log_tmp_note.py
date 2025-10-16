#!/usr/bin/env python3
"""Append a timestamped note to today's temporary journal file."""
from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
TMP_DIR = BASE_DIR / 'docs' / 'journal' / 'tmp'
# Human-friendly alias for the repository root path
ROOT_ALIAS = 'LLM_OPS'
COMPAT_ALIASES = ('MLHB',)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Append a note to docs/journal/tmp/<date>_notes.md')
    parser.add_argument('message', help='Text to append')
    parser.add_argument('--date', help='YYYY-MM-DD (default: today)')
    parser.add_argument('--time', help='HH:MM (default: now)')
    parser.add_argument('--workdir', help='Working directory to record (default: current directory relative to repo root)')
    parser.add_argument('--tag', action='append', help='Add tag(s) to note; repeatable, or comma-separated')
    parser.add_argument('--proj', help='Project name to tag this note, e.g., EA_warming')
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
        # Always present paths relative to repo root with a concise alias
        if str(rel) == '.':
            script_rel = Path(__file__).resolve().relative_to(BASE_DIR).parent.as_posix()
            return f"{ROOT_ALIAS}/{script_rel}"
        return f"{ROOT_ALIAS}/{rel.as_posix()}"
    except ValueError:
        return str(Path.cwd())


def normalize_tags(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    items: list[str] = []
    for r in raw:
        items.extend([t.strip() for t in r.split(',') if t.strip()])
    # deduplicate preserving order
    seen = set()
    result = []
    for t in items:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _resolve_link_target(note_file: Path, workdir_label: str) -> str:
    """Return a clickable link target for Markdown based on workdir label.
    - If label starts with 'MLHB/', resolve relative to repo root.
    - If label == 'MLHB', target is repo root.
    - Else, if absolute path, return as-is; otherwise keep label.
    """
    base = BASE_DIR
    aliases = (ROOT_ALIAS, *COMPAT_ALIASES)
    if workdir_label in aliases:
        target = base
    elif any(workdir_label.startswith(f"{a}/") for a in aliases):
        for a in aliases:
            prefix = f"{a}/"
            if workdir_label.startswith(prefix):
                target = base / workdir_label[len(prefix):]
                break
    else:
        p = Path(workdir_label)
        return workdir_label if p.is_absolute() else workdir_label
    try:
        rel = os.path.relpath(str(target), start=str(note_file.parent))
        return Path(rel).as_posix()
    except Exception:
        return str(target)


def append_note(path: Path, time_str: str, message: str, workdir: str, proj: str | None = None, tags: list[str] | None = None) -> None:
    suffix = ''
    if tags:
        suffix += f' [tags: {", ".join(tags)}]'
    if proj:
        suffix += f' [proj: {proj}]'
    link = _resolve_link_target(path, workdir)
    with path.open('a', encoding='utf-8') as fh:
        # Record directory in a machine-parseable form and add a clickable Markdown link.
        fh.write(f'- {time_str} {message}{suffix} [dir: {workdir}] [{workdir}]({link})\n')


def main(argv=None):
    args = parse_args(argv)
    date = resolved_date(args.date)
    time_str = resolved_time(args.time)
    path = ensure_file(date)
    workdir = resolved_workdir(args.workdir)
    tags = normalize_tags(args.tag)
    append_note(path, time_str, args.message, workdir, proj=args.proj, tags=tags)
    rel = path.relative_to(BASE_DIR).as_posix()
    print(f'Appended note to {ROOT_ALIAS}/{rel}')


if __name__ == '__main__':
    raise SystemExit(main())
