#!/usr/bin/env python3
"""Daily journal start helper."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]
JOURNAL_DIR = BASE_DIR / 'docs' / 'journal'
TEMPLATE_PATH = JOURNAL_DIR / 'templates' / 'daily_template.md'
RECAP_TITLE = '최근 7일 요약'
OLD_RECAP_TITLES = ('Yesterday Recap',)
RECAP_TITLES = (RECAP_TITLE, *OLD_RECAP_TITLES)


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


def parse_journal_date(path: Path) -> dt.date | None:
    try:
        return dt.datetime.strptime(path.stem, '%Y-%m-%d').date()
    except ValueError:
        return None


def collect_recent_journals(target_date: dt.date, window_days: int = 7) -> list[tuple[dt.date, Path]]:
    if window_days < 1:
        return []
    start_date = target_date - dt.timedelta(days=window_days - 1)
    entries: list[tuple[dt.date, Path]] = []
    for path in JOURNAL_DIR.rglob('20??-??-??.md'):
        journal_date = parse_journal_date(path)
        if not journal_date:
            continue
        if start_date <= journal_date <= target_date:
            entries.append((journal_date, path))
    entries.sort()
    return entries


def extract_section(text: str, title: str | Iterable[str]) -> tuple[str, int, int]:
    titles = (title,) if isinstance(title, str) else tuple(title)
    for current in titles:
        marker = f'## {current}'
        idx = text.find(marker)
        if idx == -1:
            continue
        start = text.find('\n', idx) + 1
        nxt = text.find('\n## ', start)
        if nxt == -1:
            nxt = len(text)
        return text[start:nxt], start, nxt
    return '', -1, -1


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


def aggregate_next_steps(entries: list[tuple[dt.date, Path]]) -> tuple[list[str], dict[str, dt.date], list[Path]]:
    aggregated: list[str] = []
    step_dates: dict[str, dt.date] = {}
    contributing_paths: list[Path] = []
    seen: set[str] = set()
    for journal_date, path in entries:
        steps = extract_next_steps(path)
        added = False
        for step in steps:
            if step not in seen:
                seen.add(step)
                aggregated.append(step)
                step_dates[step] = journal_date
                added = True
        if added:
            contributing_paths.append(path)
    return aggregated, step_dates, contributing_paths


def aggregate_completed_focus(entries: list[tuple[dt.date, Path]]) -> list[str]:
    recap: list[str] = []
    for journal_date, path in entries:
        completed = extract_completed_focus(path)
        for item in completed:
            recap.append(f'{journal_date:%Y-%m-%d}: {item}')
    return recap


def summarize_recent_completions(recap_lines: list[str], limit: int = 3) -> str:
    """Return a compact summary of recent completed focus items."""
    if not recap_lines:
        return '최근 7일 완료 항목이 없습니다.'

    unique_items: list[str] = []
    for line in recap_lines:
        _, _, detail = line.partition(': ')
        text = detail.strip() if detail else line.strip()
        if text and text not in unique_items:
            unique_items.append(text)

    if not unique_items:
        return '최근 7일 완료 항목이 없습니다.'

    if len(unique_items) <= limit:
        return ' · '.join(unique_items)

    remaining = len(unique_items) - limit
    return ' · '.join(unique_items[:limit]) + f' 외 {remaining}건'


def summarize_next_steps(steps: list[str], limit: int = 3) -> str:
    """Return a compact recommendation text for next steps."""
    if not steps:
        return '추천할 보류 작업이 없습니다.'

    preview = steps[:limit]
    if len(steps) <= limit:
        return ' · '.join(preview)

    remaining = len(steps) - limit
    return ' · '.join(preview) + f' 외 {remaining}건'


def replace_section(text: str, title: str, lines: list[str]) -> str:
    _, start, end = extract_section(text, title)
    if start == -1:
        return text
    new_block = ''.join(f'- [ ] {line}\n' for line in lines) if lines else ''
    return text[:start] + new_block + text[end:]


def ensure_recap_heading(text: str) -> str:
    new_marker = f'## {RECAP_TITLE}'
    if new_marker in text:
        return text
    for old in OLD_RECAP_TITLES:
        old_marker = f'## {old}'
        idx = text.find(old_marker)
        if idx != -1:
            return text[:idx] + new_marker + text[idx + len(old_marker):]
    return text


def set_yesterday_recap(text: str, recap_lines: list[str]) -> str:
    text = ensure_recap_heading(text)
    _, start, end = extract_section(text, RECAP_TITLES)
    if start == -1:
        return text
    if recap_lines:
        new_block = ''.join(f'- {line}\n' for line in recap_lines)
    else:
        new_block = '- 최근 7일간 완료 항목이 없습니다.\n'
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

    carried_steps: list[str] = []
    step_dates: dict[str, dt.date] = {}
    contributing_paths: list[Path] = []
    recap_lines: list[str] = []
    previous_entries: list[tuple[dt.date, Path]] = []
    if not args.no_carry:
        recent_entries = collect_recent_journals(date)
        previous_entries = [(entry_date, entry_path) for entry_date, entry_path in recent_entries if entry_date < date]
        if previous_entries:
            carried_steps, step_dates, contributing_paths = aggregate_next_steps(previous_entries)
            recap_lines = aggregate_completed_focus(previous_entries)

    text = path.read_text(encoding='utf-8')
    if carried_steps:
        text = replace_section(text, 'Focus for Today', carried_steps)
        for prev_path in contributing_paths:
            reset_next_steps(prev_path)
    if not args.no_carry and previous_entries:
        text = set_yesterday_recap(text, recap_lines)
    else:
        text = set_yesterday_recap(text, [])
    path.write_text(text, encoding='utf-8')

    status = 'created' if created else 'updated'
    print(f'Journal {status}: {path.relative_to(BASE_DIR)}')
    if carried_steps:
        print('최근 7일 이월 작업:')
        for item in carried_steps:
            origin = step_dates.get(item)
            prefix = f'{origin:%Y-%m-%d}: ' if origin else ''
            print(f' - {prefix}{item}')
    else:
        print('최근 7일 이월 작업: 없음')

    if recap_lines:
        print('최근 7일 완료 항목:')
        for item in recap_lines:
            print(f' - {item}')
    else:
        print('최근 7일 완료 항목: 없음')

    recap_summary = summarize_recent_completions(recap_lines)
    next_steps_summary = summarize_next_steps(carried_steps)
    print('요약:', recap_summary)
    print('추천 다음 단계:', next_steps_summary)


if __name__ == '__main__':
    raise SystemExit(main())
