#!/usr/bin/env python3
"""Daily journal end helper."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
JOURNAL_DIR = BASE_DIR / 'docs' / 'journal'
TEMPLATE_PATH = JOURNAL_DIR / 'templates' / 'daily_template.md'


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Wrap up daily journal at end of day')
    parser.add_argument('--date', help='YYYY-MM-DD (default: today)')
    parser.add_argument(
        '--notes',
        help='Free-form text to append under Work Log > Progress Notes.',
    )
    parser.add_argument(
        '--notes-file',
        type=Path,
        help='File containing text to append under Work Log > Progress Notes.',
    )
    return parser.parse_args(argv)


def resolved_date(date_str: str | None) -> dt.date:
    if date_str:
        return dt.datetime.strptime(date_str, '%Y-%m-%d').date()
    return dt.date.today()


def journal_path_for(date: dt.date) -> Path:
    year_dir = JOURNAL_DIR / f'{date.year}'
    year_dir.mkdir(parents=True, exist_ok=True)
    return year_dir / f'{date:%Y-%m-%d}.md'


def ensure_journal(date: dt.date) -> tuple[Path, bool]:
    path = journal_path_for(date)
    if path.exists():
        return path, False
    template = TEMPLATE_PATH.read_text(encoding='utf-8')
    template = template.replace('<YYYY-MM-DD>', f'{date:%Y-%m-%d}')
    path.write_text(template, encoding='utf-8')
    return path, True


def extract_section(text: str, title: str):
    marker = f'## {title}'
    idx = text.find(marker)
    if idx == -1:
        return '', idx, idx
    start = text.find('\n', idx) + 1
    next_header = text.find('\n## ', start)
    if next_header == -1:
        next_header = len(text)
    return text[start:next_header], start, next_header


def parse_tasks(block: str):
    tasks = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith('- ['):
            status = stripped[3]
            text = stripped.split(']', 1)[1].strip()
            tasks.append((status, text, line))
    return tasks


def main(argv=None):
    args = parse_args(argv)
    date = resolved_date(args.date)
    path, created = ensure_journal(date)

    text = path.read_text(encoding='utf-8')
    focus_block, focus_start, focus_end = extract_section(text, 'Focus for Today')
    next_block, next_start, next_end = extract_section(text, 'Next Steps (for tomorrow)')
    work_block, work_start, work_end = extract_section(text, 'Work Log')

    focus_tasks = parse_tasks(focus_block)
    next_tasks = [t for t in parse_tasks(next_block) if '<TODO' not in t[1]]

    next_texts = {t[1] for t in next_tasks}
    carried = []
    for status, task, line in focus_tasks:
        if status == ' ':
            if task not in next_texts:
                next_tasks.append((' ', task, line))
                next_texts.add(task)
                carried.append(task)

    if next_tasks:
        new_next = ''.join(f'- [ ] {task}\n' for _, task, _ in next_tasks)
    else:
        new_next = '- [ ] <TODO 1>\n- [ ] <TODO 2>\n'

    new_text = text[:next_start] + new_next + text[next_end:]

    notes_payload = []
    if args.notes:
        notes_payload.append(args.notes.strip())
    if args.notes_file:
        file_text = args.notes_file.read_text(encoding='utf-8').strip()
        if file_text:
            notes_payload.append(file_text)

    if notes_payload and work_block:
        lines = work_block.splitlines()
        progress_idx = None
        for idx, line in enumerate(lines):
            if line.strip().startswith('- **Progress Notes:**'):
                progress_idx = idx
                break

        if progress_idx is not None:
            insert_idx = progress_idx + 1
            existing = []
            while insert_idx < len(lines) and lines[insert_idx].startswith('  - '):
                existing.append(lines[insert_idx].strip()[2:].strip())
                insert_idx += 1

            additions = []
            for chunk in notes_payload:
                for note in (line.strip() for line in chunk.splitlines() if line.strip()):
                    if note not in existing:
                        additions.append(f'  - {note}')
                        existing.append(note)

            if additions:
                lines = lines[:insert_idx] + additions + lines[insert_idx:]
                new_work_block = '\n'.join(lines)
                new_text = new_text[:work_start] + new_work_block + new_text[work_end:]

    if new_text != text:
        path.write_text(new_text, encoding='utf-8')

    if created:
        print(f'Journal created: {path.relative_to(BASE_DIR)}')
    else:
        print(f'Journal updated: {path.relative_to(BASE_DIR)}')
    if carried:
        print('Moved to Next Steps:')
        for item in carried:
            print(f' - {item}')
    else:
        print('No incomplete items to carry over.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
