#!/usr/bin/env python3
"""Daily journal end helper."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parents[1]
JOURNAL_DIR = BASE_DIR / 'docs' / 'journal'
TEMPLATE_PATH = JOURNAL_DIR / 'templates' / 'daily_template.md'
TMP_DIR = JOURNAL_DIR / 'tmp'


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Wrap up daily journal at end of day')
    parser.add_argument('--date', help='YYYY-MM-DD (default: today)')
    parser.add_argument('--since', help='Start time HH:MM or ISO datetime; default: last saved time in journal')
    parser.add_argument('--until', help='End time HH:MM or ISO datetime; default: now')
    parser.add_argument('--force', action='store_true', help='Bypass ~1h minimum interval guard for saving')
    parser.add_argument('--full', action='store_true', help='Ignore last-saved checkpoint and summarize the whole day')
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


META_RE = re.compile(r"<!--\s*journal-meta:\s*([^>]*)-->")


def parse_meta(text: str) -> dict:
    meta = {}
    m = META_RE.search(text)
    if not m:
        return meta
    body = m.group(1)
    for part in body.split(','):
        if '=' in part:
            k, v = part.split('=', 1)
            meta[k.strip()] = v.strip()
    return meta


def set_meta(text: str, **updates) -> str:
    meta = parse_meta(text)
    meta.update({k: v for k, v in updates.items() if v is not None})
    body = ', '.join(f'{k}={v}' for k, v in meta.items())
    new_line = f'<!-- journal-meta: {body} -->'
    if META_RE.search(text):
        return META_RE.sub(new_line, text)
    # insert after first title line
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith('# '):
            lines.insert(i + 1, new_line)
            return '\n'.join(lines)
    # fallback: prepend
    return new_line + '\n' + text


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


def load_tmp_entries(date: dt.date):
    path = TMP_DIR / f'{date:%Y-%m-%d}_notes.md'
    if not path.exists():
        return []

    pattern = re.compile(r'- (\d{2}:\d{2})\s+(.*?)(?:\s+\[dir: ([^\]]+)\])?$')
    entries = []
    for line in path.read_text(encoding='utf-8').splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        time_str, text, dirs = match.groups()
        try:
            timestamp = dt.datetime.strptime(f'{date:%Y-%m-%d} {time_str}', '%Y-%m-%d %H:%M')
        except ValueError:
            continue
        entries.append({
            'timestamp': timestamp,
            'text': text.strip(),
            'dirs': dirs.strip() if dirs else '.',
        })

    entries.sort(key=lambda item: item['timestamp'])
    return entries


def summarize_tmp_entries(entries: list[dict], end_time: dt.datetime | None = None) -> list[str]:
    if not entries:
        return []

    summary: list[str] = []
    now = end_time or dt.datetime.now()
    for idx, entry in enumerate(entries):
        start = entry['timestamp']
        end = entries[idx + 1]['timestamp'] if idx + 1 < len(entries) else now
        if end < start:
            end = start
        line = f"{start:%H:%M}–{end:%H:%M} | {entry['text']} | {entry['dirs']}"
        summary.append(line)
    return summary


def main(argv=None):
    args = parse_args(argv)
    date = resolved_date(args.date)
    path, created = ensure_journal(date)

    text = path.read_text(encoding='utf-8')
    meta = parse_meta(text)
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

    # Determine time window for summarization
    def parse_dt(s: str | None, default: dt.datetime | None) -> dt.datetime:
        if not s:
            return default if default else dt.datetime.now()
        s = s.strip()
        # Try HH:MM for the given date
        try:
            return dt.datetime.strptime(f'{date:%Y-%m-%d} {s}', '%Y-%m-%d %H:%M')
        except ValueError:
            pass
        # Try ISO datetime
        try:
            return dt.datetime.fromisoformat(s)
        except ValueError:
            raise SystemExit(f'Invalid time/datetime: {s}')

    last_saved_iso = meta.get('last_saved')
    last_saved_dt = None
    if last_saved_iso and not args.full and not args.since:
        try:
            last_saved_dt = dt.datetime.fromisoformat(last_saved_iso)
        except ValueError:
            last_saved_dt = None

    until_dt = parse_dt(args.until, dt.datetime.now())
    since_dt = parse_dt(args.since, last_saved_dt) if (args.since or last_saved_dt) else None

    # Load and filter tmp entries for the window
    entries = load_tmp_entries(date)
    if since_dt:
        entries = [e for e in entries if e['timestamp'] > since_dt]
    if entries and until_dt:
        entries = [e for e in entries if e['timestamp'] <= until_dt]

    # Enforce ~1h minimum interval unless overridden
    if since_dt and not args.force:
        delta_min = int((until_dt - since_dt).total_seconds() // 60)
        if delta_min < 50:
            print(f'Skip: interval {delta_min} min < ~60 min; use --force to override.')
            entries = []

    notes_payload = []
    if args.notes:
        notes_payload.append(args.notes.strip())
    if args.notes_file:
        file_text = args.notes_file.read_text(encoding='utf-8').strip()
        if file_text:
            notes_payload.append(file_text)

    tmp_summaries = summarize_tmp_entries(entries, end_time=until_dt)
    if tmp_summaries:
        notes_payload.append('\n'.join(tmp_summaries))

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

    # Update last_saved checkpoint only if we added new tmp summaries
    if tmp_summaries:
        new_text = set_meta(new_text, last_saved=until_dt.isoformat(timespec='minutes'))

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
