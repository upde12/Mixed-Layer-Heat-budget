#!/usr/bin/env python3
"""Normalize broken MLHB links in journal Markdown files.

This tool scans docs/journal/**/*.md and fixes Markdown links whose targets
use the MLHB alias incorrectly (e.g., [MLHB/scripts](MLHB/scripts)). It also
converts absolute paths under the repository root to relative paths from the
journal file location.

Rules:
 - target == 'MLHB' -> link to repo root relative to the journal file
 - target startswith 'MLHB/' -> resolve to repo root + subpath, then relativize
 - target absolute path under BASE_DIR -> relativize to the journal file

It leaves labels unchanged.
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
JOURNAL_DIR = BASE_DIR / 'docs' / 'journal'
ROOT_ALIAS = 'MLHB'


LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def resolve_target(md_file: Path, target: str) -> str:
    # Keep web URLs untouched
    if re.match(r"^[a-zA-Z]+://", target):
        return target

    # Normalize whitespace
    t = target.strip()

    # Case 1: alias only
    if t == ROOT_ALIAS:
        try:
            rel = os.path.relpath(str(BASE_DIR), start=str(md_file.parent))
            return Path(rel).as_posix()
        except Exception:
            return t

    # Case 2: alias with subpath
    if t.startswith(f"{ROOT_ALIAS}/"):
        sub = t[len(f"{ROOT_ALIAS}/"):]
        dest = (BASE_DIR / sub)
        try:
            rel = os.path.relpath(str(dest), start=str(md_file.parent))
            return Path(rel).as_posix()
        except Exception:
            return dest.as_posix()

    # Case 3: absolute path under repo root
    try:
        p = Path(t)
        if p.is_absolute():
            try:
                # Check if the path is within the repo root
                rel_to_root = p.relative_to(BASE_DIR)
            except Exception:
                return t  # outside repo; keep as-is
            dest = BASE_DIR / rel_to_root
            rel = os.path.relpath(str(dest), start=str(md_file.parent))
            return Path(rel).as_posix()
    except Exception:
        pass

    # Default: keep original
    return t


def fix_links_in_text(md_file: Path, text: str) -> tuple[str, int]:
    changes = 0

    def _sub(m: re.Match) -> str:
        nonlocal changes
        label, target = m.group(1), m.group(2)
        new_target = resolve_target(md_file, target)
        if new_target != target:
            changes += 1
        return f"[{label}]({new_target})"

    return LINK_RE.sub(_sub, text), changes


def iter_md_files(root: Path):
    for path in root.rglob('*.md'):
        yield path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Normalize MLHB links in journal markdowns')
    ap.add_argument('--root', default=str(JOURNAL_DIR), help='Root directory to scan (default: docs/journal)')
    ap.add_argument('--dry-run', action='store_true', help='Do not write changes; only report')
    args = ap.parse_args(argv)

    root = Path(args.root)
    if not root.exists():
        print(f"Target root not found: {root}")
        return 1

    total_files = 0
    total_changes = 0
    for md in iter_md_files(root):
        text = md.read_text(encoding='utf-8')
        new_text, n = fix_links_in_text(md, text)
        if n > 0:
            total_files += 1
            total_changes += n
            if not args.dry_run:
                md.write_text(new_text, encoding='utf-8')
            rel = md.relative_to(BASE_DIR).as_posix()
            print(f"Fixed {n:>3} links in {ROOT_ALIAS}/{rel}")

    if total_changes == 0:
        print("No links needed fixing.")
    else:
        print(f"Total: {total_changes} links fixed across {total_files} files.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

