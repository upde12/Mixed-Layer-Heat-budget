#!/usr/bin/env python3
"""Validate Markdown links under given roots.

- Resolves `MLHB/` alias to repo root for existence checks.
- Resolves relative paths from each Markdown file directory.
- Skips http(s), mailto:, and in-page anchors(#...).

Outputs a text summary by default, or JSON with --json.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]
PRIMARY_ALIAS = 'LLM_OPS'
COMPAT_ALIASES = ('MLHB',)


LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


@dataclass
class BrokenLink:
    file: str
    line: int
    label: str
    target: str
    resolved: str | None
    reason: str


def is_web_or_anchor(target: str) -> bool:
    t = target.strip()
    if t.startswith('#'):
        return True
    if re.match(r'^[a-zA-Z]+://', t):
        return True
    if t.startswith('mailto:'):
        return True
    return False


def resolve_target_for_check(md_file: Path, target: str) -> Path | None:
    t = target.strip()
    # Drop in-file fragment
    t, *_ = t.split('#', 1)
    if not t:
        return None
    # Repo root alias (primary + compat)
    aliases = (PRIMARY_ALIAS, *COMPAT_ALIASES)
    if t in aliases:
        return BASE_DIR
    for a in aliases:
        prefix = f"{a}/"
        if t.startswith(prefix):
            sub = t[len(prefix):]
            return BASE_DIR / sub
    # Absolute path
    p = Path(t)
    if p.is_absolute():
        try:
            rel = p.relative_to(BASE_DIR)
        except Exception:
            return None  # outside repo; treat as non-checkable
        return BASE_DIR / rel
    # Relative to file
    return (md_file.parent / t).resolve()


def iter_md_files(roots: Iterable[Path]) -> Iterable[Path]:
    seen = set()
    for r in roots:
        if not r.exists():
            continue
        for p in r.rglob('*.md'):
            if p not in seen:
                seen.add(p)
                yield p


def validate_links(roots: list[Path]) -> dict:
    broken: list[BrokenLink] = []
    scanned = 0
    for md in iter_md_files(roots):
        scanned += 1
        for lineno, line in enumerate(md.read_text(encoding='utf-8').splitlines(), start=1):
            for m in LINK_RE.finditer(line):
                label, target = m.group(1), m.group(2)
                if is_web_or_anchor(target):
                    continue
                resolved = resolve_target_for_check(md, target)
                if resolved is None:
                    broken.append(BrokenLink(
                        file=md.relative_to(BASE_DIR).as_posix(),
                        line=lineno,
                        label=label,
                        target=target,
                        resolved=None,
                        reason='external-or-uncheckable',
                    ))
                    continue
                if not resolved.exists():
                    broken.append(BrokenLink(
                        file=md.relative_to(BASE_DIR).as_posix(),
                        line=lineno,
                        label=label,
                        target=target,
                        resolved=resolved.relative_to(BASE_DIR).as_posix(),
                        reason='not-found',
                    ))
    # Aggregate files affected
    files = sorted({b.file for b in broken})
    return {
        'scanned_files': scanned,
        'broken_count': len(broken),
        'files_affected': len(files),
        'broken': [b.__dict__ for b in broken],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Validate Markdown links under roots')
    ap.add_argument('--root', action='append', default=['docs'], help='Root directory to scan (repeatable). Default: docs')
    ap.add_argument('--json', action='store_true', help='Print JSON result')
    args = ap.parse_args(argv)

    roots = [BASE_DIR / r for r in args.root]
    result = validate_links(roots)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    # Text summary
    print(f"Scanned MD files: {result['scanned_files']}")
    print(f"Broken links: {result['broken_count']} (files: {result['files_affected']})")
    for item in result['broken'][:10]:
        print(f" - {item['file']}:{item['line']} — '{item['label']}' -> {item['target']} ({item.get('resolved') or item['reason']})")
    if result['broken_count'] > 10:
        print(f" ... and {result['broken_count'] - 10} more")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
