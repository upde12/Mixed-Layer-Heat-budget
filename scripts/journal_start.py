#!/usr/bin/env python3
"""Daily journal start helper."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
JOURNAL_DIR = BASE_DIR / 'docs' / 'journal'
TEMPLATE_PATH = JOURNAL_DIR / 'templates' / 'daily_template.md'


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Create/update daily journal at start of day')
    parser.add_argument('--date', help='YYYY-MM-DD (default: today)')
    parser.add_argument('--no-carry', action='store_true', help='Do not carry over previous Next Steps')
    return parser.parse_args(argv)


def resolved_date(date_str: str | None) -> dt.date:
    if date_str:
        return dt.datetime.strptime(date_str, '%Y-%m-%d').date()
    return dt.date.today()


def journal_path_for(date: dt.date) -> Path:
    year_dir = JOURNAL_DIR / f'{date.year}'
    year_dir.mkdir(parents=True, exist_ok=True)
    return year_dir / f'{date:%Y-%m-%d}.md'


def read_template(date: dt.date) -> str:
    text = TEMPLATE_PATH.read_text(encoding='utf-8')
    return text.replace('<YYYY-MM-DD>', f'{date:%Y-%m-%d}')


def get_previous_journal(target_date: dt.date) -> Path | None:
    candidates = sorted(JOURNAL_DIR.rglob('20??-??-??.md'))
    for path in reversed(candidates):
        try:
            journal_date = dt.datetime.strptime(path.stem, '%Y-%m-%d').date()
        except ValueError:
            continue
        if journal_date < target_date:
            return path
    return None


def extract_section(text: str, title: str) -> tuple[str, int, int]:
    marker = f'## {title}'
    idx = text.find(marker)
    if idx == -1:
        return '', -1, -1
    start = text.find('\n', idx) + 1
    nxt = text.find('\n## ', start)
    if nxt == -1:
        nxt = len(text)
    return text[start:nxt], start, nxt


def extract_next_steps(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8')
    block, *_ = extract_section(text, 'Next Steps (for tomorrow)')
    steps = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith('- [') and '<TODO' not in stripped:
            steps.append(stripped.split(']', 1)[1].strip())
    return steps


def extract_completed_focus(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8')
    block, *_ = extract_section(text, 'Focus for Today')
    completed = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith('- [x'):
            completed.append(stripped.split(']', 1)[1].strip())
    return completed


def replace_section(text: str, title: str, lines: list[str]) -> str:
    _, start, end = extract_section(text, title)
    if start == -1:
        return text
    new_block = ''.join(f'- [ ] {line}\n' for line in lines) if lines else ''
    return text[:start] + new_block + text[end:]


def set_yesterday_recap(text: str, recap_lines: list[str]) -> str:
    _, start, end = extract_section(text, 'Yesterday Recap')
    if start == -1:
        return text
    if recap_lines:
        new_block = ''.join(f'- {line}\n' for line in recap_lines)
    else:
        new_block = '- 전날 일지가 없거나 완료 항목이 없습니다.\n'
    return text[:start] + new_block + text[end:]


def reset_next_steps(previous_path: Path):
    text = previous_path.read_text(encoding='utf-8')
    _, start, end = extract_section(text, 'Next Steps (for tomorrow)')
    if start == -1:
        return
    placeholder = '- [ ] <TODO 1>\n- [ ] <TODO 2>\n'
    previous_path.write_text(text[:start] + placeholder + text[end:], encoding='utf-8')


def main(argv=None):
    args = parse_args(argv)
    date = resolved_date(args.date)
    path = journal_path_for(date)
    created = False
    if not path.exists():
        path.write_text(read_template(date), encoding='utf-8')
        created = True

    prev_path = None
    carried_steps: list[str] = []
    recap_lines: list[str] = []
    if not args.no_carry:
        prev_path = get_previous_journal(date)
        if prev_path:
            carried_steps = extract_next_steps(prev_path)
            recap_lines = extract_completed_focus(prev_path)

    text = path.read_text(encoding='utf-8')
    if carried_steps:
        text = replace_section(text, 'Focus for Today', carried_steps)
        if prev_path:
            reset_next_steps(prev_path)
    if prev_path:
        text = set_yesterday_recap(text, recap_lines)
    else:
        text = set_yesterday_recap(text, [])
    path.write_text(text, encoding='utf-8')

    status = 'created' if created else 'updated'
    print(f'Journal {status}: {path.relative_to(BASE_DIR)}')
    if carried_steps:
        print('Carried over tasks:')
        for item in carried_steps:
            print(f' - {item}')
    if recap_lines:
        print('Yesterday recap items:')
        for item in recap_lines:
            print(f' - {item}')


if __name__ == '__main__':
    raise SystemExit(main())
