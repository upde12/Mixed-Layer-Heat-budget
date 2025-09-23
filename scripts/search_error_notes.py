#!/usr/bin/env python3
"""Search utility for error notes."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
NOTES_DIR = BASE_DIR / "docs" / "error_notes"
IGNORES = {NOTES_DIR / "README.md", NOTES_DIR / "_categories.yml"}


def iter_note_files(category: str | None = None):
    base = NOTES_DIR / category if category else NOTES_DIR
    if not base.exists():
        return
    for path in base.rglob('*.md'):
        if path in IGNORES:
            continue
        if path.name == 'note_template.md':
            continue
        yield path


def normalise(text: str) -> str:
    return text.lower().replace('_', '').replace('-', ' ')


def search_notes(keywords: list[str], category: str | None = None):
    keywords = [normalise(k) for k in keywords if k]
    results = []
    for path in iter_note_files(category):
        raw = path.read_text(encoding='utf-8')
        text = normalise(raw)
        if all(k in text for k in keywords):
            title = ""
            for line in raw.splitlines():
                if line.lower().startswith('title:'):
                    title = line.split(':', 1)[1].strip()
                    break
            results.append((path, title))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description='오답노트 검색기')
    parser.add_argument('query', nargs='+', help='검색 키워드 (공백 구분)')
    parser.add_argument('--category', help='특정 카테고리만 검색 (data_io 등)')
    args = parser.parse_args(argv)

    matches = search_notes(args.query, args.category)
    if not matches:
        print('일치하는 오답노트가 없습니다.', file=sys.stderr)
        return 1
    for path, title in matches:
        rel = path.relative_to(BASE_DIR)
        print(f"- {rel}: {title}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
