#!/usr/bin/env python3
"""Daily journal end helper."""
from __future__ import annotations

import argparse
import datetime as dt
from collections import defaultdict
from pathlib import Path
import os
import re

BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_ALIAS = 'LLM_OPS'
JOURNAL_DIR = BASE_DIR / 'docs' / 'journal'
TEMPLATE_PATH = JOURNAL_DIR / 'templates' / 'daily_template.md'
TMP_DIR = JOURNAL_DIR / 'tmp'
PROJECT_PRIORITY = ['DEC', 'MHW_JC', 'TCPI', '137E', 'MLHB_OPS', 'GENERAL']
TAGS_PATTERN = re.compile(r'\[tags:\s*([^\]]+)\]')
PROJ_PATTERN = re.compile(r'\[proj:\s*([^\]]+)\]')
TOPIC_LABELS = {
    'run': '실행',
    'result': '결과',
    'decision': '결정',
    'viz': '시각화',
    'doc': '문서',
    'ops': '운영',
    'issue': '이슈',
    'plan': '계획',
    'misc': '기타',
}
TOPIC_KEYWORDS = {
    'run': ['실행', '재가동', '배치', 'run', 'resample'],
    'result': ['닫힘', '통계', '결과', 'diagnostic', 'RMS', 'trend'],
    'decision': ['결정', '정책', '옵션', '방침'],
    'viz': ['그림', '프로파일', '색상바', 'plot', 'figure', '시각화'],
    'doc': ['지침', '문서', 'README', 'manual', '문구', '가이드'],
    'ops': ['경로', '별칭', '링크', '구조', 'rename', 'alias'],
    'issue': ['오류', '에러', '이슈', '실패', 'error', 'bug'],
    'plan': ['계획', 'plan', '로드맵'],
}


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


def _is_placeholder_focus_task(text: str) -> bool:
    """Heuristic to detect template placeholder tasks that shouldn't be carried."""
    placeholders = (
        '<주요 목표',
        'PPT 도입부 핵심 메시지 정리',
        '슬라이드-대본 정합성 점검 및 수정',
    )
    return any(p in text for p in placeholders)


def _split_metadata_items(raw: str) -> list[str]:
    parts: list[str] = []
    for token in re.split(r'[,+/&]', raw):
        token = token.strip()
        if token:
            parts.append(token)
    return parts


def _strip_time_prefix(text: str) -> str:
    return re.sub(r'^\d{2}:\d{2}–\d{2}:\d{2}\s*\|\s*', '', text).strip()


def _remove_link_suffix(text: str) -> str:
    if ' | ' in text:
        return text.split(' | ', 1)[0].strip()
    return text


def _extract_metadata(text: str) -> tuple[str, list[str], list[str]]:
    projects: list[str] = []
    tags: list[str] = []

    proj_match = PROJ_PATTERN.search(text)
    if proj_match:
        raw = proj_match.group(1)
        projects = [p.upper() for p in _split_metadata_items(raw)]
        text = PROJ_PATTERN.sub('', text)
    tag_match = TAGS_PATTERN.search(text)
    if tag_match:
        raw = tag_match.group(1)
        tags = [t.strip().lower() for t in _split_metadata_items(raw)]
        text = TAGS_PATTERN.sub('', text)

    text = _remove_link_suffix(text)
    text = _strip_time_prefix(text)
    cleaned = re.sub(r'\s{2,}', ' ', re.sub(r'\[[^\]]+\]', '', text)).strip()
    return cleaned, projects, tags


def _project_order_key(code: str) -> tuple[int, str]:
    try:
        idx = PROJECT_PRIORITY.index(code)
    except ValueError:
        idx = len(PROJECT_PRIORITY)
    return idx, code


def _summarize_project(project: str, entries: list[dict], limit: int = 2) -> str | None:
    if not entries:
        return None
    mlhb_flag = any(('mlhb' in (e.get('tags') or []) or 'mlhb' in e.get('text', '').lower()) for e in entries)
    # Prepare candidates by topic with original order preserved
    priority = ('decision', 'run', 'result', 'viz', 'doc', 'ops', 'issue', 'plan', 'misc')
    by_topic: dict[str, list[str]] = defaultdict(list)
    seen: set[str] = set()
    def detect_topic(text: str, tags: list[str]) -> str:
        tagset = {t.lower() for t in (tags or [])}
        for t in priority:
            if t in tagset:
                return t
        low = text.lower()
        # ops priority
        for w in TOPIC_KEYWORDS['ops']:
            if w.lower() in low:
                return 'ops'
        for t in ('decision', 'result', 'run', 'viz', 'doc', 'issue', 'plan'):
            if any(w.lower() in low for w in TOPIC_KEYWORDS.get(t, [])):
                return t
        return 'misc'
    for e in entries:
        txt = (e.get('text') or '').strip()
        if not txt:
            continue
        topic = detect_topic(txt, e.get('tags', []))
        if txt not in seen:
            by_topic[topic].append(txt)
            seen.add(txt)
    # Choose up to `limit` representative phrases
    chosen: list[tuple[str, str]] = []
    for topic in priority:
        if len(chosen) >= limit:
            break
        items = by_topic.get(topic)
        if items:
            label = TOPIC_LABELS.get(topic, topic)
            phrase = items[-1] if limit == 1 else items[0]
            if topic == 'ops':
                low = phrase.lower()
                if '링크' in phrase or 'link' in low:
                    phrase = '링크 검증'
                elif '레포' in phrase or 'alias' in low or '경로' in phrase or '구조' in phrase or 'repo' in low or 'refactor' in low:
                    phrase = '레포 구조 정비'
                elif 'start' in low or 'journal_start' in low or '루틴' in phrase or 'routine' in low:
                    phrase = '시작 루틴 개선'
                else:
                    phrase = '운영 개선'
            # remove duplicated leading labels like '결정:' if present
            for token in ('결정:', '실행:', '문서:', '시각화:', '이슈:', '계획:', '결과:', 'decision:', 'run:', 'result:'):
                if phrase.lower().startswith(token.lower()):
                    phrase = phrase[len(token):].lstrip()
            if len(phrase) > 110:
                phrase = phrase[:109].rstrip() + '…'
            chosen.append((label, phrase))
    if not chosen and entries:
        phrase = (entries[-1].get('text') or '').strip()
        if phrase:
            chosen.append((TOPIC_LABELS.get('misc', '기타'), phrase))
    if not chosen:
        return None
    parts = [f"{label} — {phrase}" for label, phrase in chosen]
    prefix = 'MLHB — ' if mlhb_flag else ''
    body = f"{prefix}{'; '.join(parts)}"
    if project == 'GENERAL':
        return body
    return f"{project}: {body}"


def _generate_focus_lines(entries: list[dict], fallback_notes: list[str] | None = None) -> list[str]:
    """Generate human-friendly focus lines grouped by project code, summarised by topic."""
    parsed: list[dict] = []
    for entry in entries:
        text = entry.get('text', '').strip()
        if not text:
            continue
        cleaned, projects, tags = _extract_metadata(text)
        if not cleaned:
            continue
        parsed.append({'text': cleaned, 'projects': [p for p in projects if p], 'tags': tags})

    if fallback_notes and not parsed:
        for chunk in fallback_notes:
            for raw_line in chunk.splitlines():
                cleaned, projects, tags = _extract_metadata(raw_line)
                if cleaned:
                    parsed.append({'text': cleaned, 'projects': [p for p in projects if p], 'tags': tags})

    if not parsed:
        return []

    grouped: dict[str, list[dict]] = defaultdict(list)
    for entry in parsed:
        projects = entry.get('projects') or []
        if not projects:
            grouped['GENERAL'].append(entry)
        else:
            for proj in projects:
                grouped[proj].append(entry)

    lines: list[str] = []
    for proj, proj_entries in sorted(grouped.items(), key=lambda kv: _project_order_key(kv[0])):
        line = _summarize_project(proj, proj_entries, limit=1)
        if line:
            lines.append(line)
    return lines


def load_tmp_entries(date: dt.date):
    path = TMP_DIR / f'{date:%Y-%m-%d}_notes.md'
    if not path.exists():
        return []

    # Accept lines of the form:
    # - HH:MM message [dir: PATH]
    # - HH:MM message [dir: PATH] [TEXT](PATH)
    # The trailing Markdown link is optional and ignored during parsing.
    pattern = re.compile(r'- (\d{2}:\d{2})\s+(.*?)(?:\s+\[dir: ([^\]]+)\])?(?:\s+\[[^\]]+\]\([^)]+\))?\s*$')
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


def _resolve_note_link_target(journal_file: Path, workdir_label: str) -> str:
    """Return a clickable link target for Markdown based on workdir label.
    Mirrors log_tmp_note._resolve_link_target behavior, but resolves relative to the
    daily journal file location instead of the tmp note file.

    Rules:
    - If label starts with 'MLHB/', resolve relative to repo root.
    - If label == 'MLHB', target is repo root.
    - Else, if absolute path, return as-is; otherwise keep label.
    """
    base_dir = BASE_DIR
    root_alias = ROOT_ALIAS
    compat_aliases = ("MLHB",)
    if workdir_label == root_alias or workdir_label in compat_aliases:
        target = base_dir
    elif workdir_label.startswith(f"{root_alias}/"):
        target = base_dir / workdir_label[len(f"{root_alias}/"):]
    elif any(workdir_label.startswith(f"{a}/") for a in compat_aliases):
        for a in compat_aliases:
            prefix = f"{a}/"
            if workdir_label.startswith(prefix):
                target = base_dir / workdir_label[len(prefix):]
                break
    else:
        p = Path(workdir_label)
        return workdir_label if p.is_absolute() else workdir_label
    try:
        rel = os.path.relpath(str(target), start=str(journal_file.parent))
        return Path(rel).as_posix()
    except Exception:
        return str(target)


def summarize_tmp_entries(
    entries: list[dict],
    end_time: dt.datetime | None = None,
    journal_file: Path | None = None,
) -> list[str]:
    if not entries:
        return []

    summary: list[str] = []
    now = end_time or dt.datetime.now()
    for idx, entry in enumerate(entries):
        start = entry['timestamp']
        end = entries[idx + 1]['timestamp'] if idx + 1 < len(entries) else now
        if end < start:
            end = start
        dirs = entry['dirs']
        if dirs and dirs != '.':
            # Support multiple paths separated by ';'
            parts = [p.strip() for p in re.split(r'[;,]', dirs) if p.strip()]
            if journal_file is not None:
                link_items = []
                for label in parts:
                    target = _resolve_note_link_target(journal_file, label)
                    link_items.append(f'[{label}]({target})')
                link_str = ' · '.join(link_items) if link_items else '.'
            else:
                link_str = ' · '.join(f'[{p}]({p})' for p in parts)
        else:
            link_str = '.'
        line = f"{start:%H:%M}–{end:%H:%M} | {entry['text']} | {link_str}"
        summary.append(line)
    return summary


_TIME_PREFIX_RE = re.compile(r'^\d{2}:\d{2}–\d{2}:\d{2}\s*\|\s*')


def _normalize_progress_line(text: str) -> str:
    """Normalize a progress note for deduplication.

    - Strip time range prefix (HH:MM–HH:MM | )
    - Drop trailing link column ( | ...)
    - Collapse spaces
    """
    s = _TIME_PREFIX_RE.sub('', text).strip()
    if ' | ' in s:
        s = s.split(' | ', 1)[0].strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def _is_nonwork_progress(text: str) -> bool:
    """Return True if the normalized text is routine/housekeeping, not scientific work."""
    lower = text.lower()
    # Korean/English routine patterns
    nonwork_starts = (
        '시작:',
        '참고:',
        '재작성:',
    )
    if text.startswith(nonwork_starts):
        return True
    keywords = (
        'journal_start.py 실행',
        '7일 요약',
        '요약 적용',
        'recommendation',
        '추천할 보류 작업',
    )
    return any(k in text or k in lower for k in keywords)


_TIME_RANGE_EXTRACT_RE = re.compile(r'^(\d{2}:\d{2})\s*–\s*(\d{2}:\d{2})\s*\|\s*(.*)$')


def _coalesce_progress_time(existing_line: str, new_line: str) -> str | None:
    """If existing/new progress notes normalize to the same text, update the time range.

    Strategy:
    - Parse both lines as "HH:MM–HH:MM | BODY".
    - Keep the existing BODY (to avoid jitter in links/formatting) and START time.
    - Replace only the END time with the newer END from new_line.
    - Return the updated full line (including leading bullet and spaces) or None if parse fails.
    """
    # Strip leading bullet for parsing, but remember indentation
    prefix = ''
    raw_existing = existing_line
    if raw_existing.startswith('  - '):
        prefix = '  - '
        raw_existing = raw_existing[4:]
    m_old = _TIME_RANGE_EXTRACT_RE.match(raw_existing.strip())
    m_new = _TIME_RANGE_EXTRACT_RE.match(new_line.strip())
    if not (m_old and m_new):
        return None
    start_old, end_old, body_old = m_old.groups()
    start_new, end_new, _body_new = m_new.groups()
    # Only coalesce when start time matches (same task interval continuing)
    if start_old != start_new:
        return None
    # Construct merged line using existing body and new end time
    merged = f"{prefix}{start_old}–{end_new} | {body_old}"
    return merged


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
        if status == ' ' and not _is_placeholder_focus_task(task):
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

    tmp_summaries = summarize_tmp_entries(entries, end_time=until_dt, journal_file=path)
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
            existing_norm = set()
            existing_index_by_norm: dict[str, int] = {}
            while insert_idx < len(lines) and lines[insert_idx].startswith('  - '):
                raw = lines[insert_idx].strip()[2:].strip()
                existing.append(raw)
                norm_key = _normalize_progress_line(raw)
                existing_norm.add(norm_key)
                # Record the first occurrence index for potential in-place coalesce
                if norm_key not in existing_index_by_norm:
                    existing_index_by_norm[norm_key] = insert_idx
                insert_idx += 1

            additions = []
            for chunk in notes_payload:
                for note in (line.strip() for line in chunk.splitlines() if line.strip()):
                    norm = _normalize_progress_line(note)
                    if _is_nonwork_progress(norm):
                        continue
                    if norm in existing_norm:
                        # Try to coalesce time range of the existing line instead of appending
                        idx = existing_index_by_norm.get(norm)
                        if idx is not None:
                            updated = _coalesce_progress_time(lines[idx], note)
                            if updated:
                                lines[idx] = updated
                        # Regardless of coalescing, skip appending duplicate
                        continue
                    additions.append(f'  - {note}')
                    existing.append(note)
                    existing_norm.add(norm)
                    # Track newly added index for potential further coalescing in same run
                    existing_index_by_norm[norm] = insert_idx
                    insert_idx += 1

            if additions:
                lines = lines[:insert_idx] + additions + lines[insert_idx:]
                new_work_block = '\n'.join(lines)
                new_text = new_text[:work_start] + new_work_block + new_text[work_end:]

    # Generate/update Focus for Today at save time (project-aware summary)
    try:
        focus_lines = _generate_focus_lines(entries, fallback_notes=notes_payload)
    except Exception:
        focus_lines = []
    if focus_start != -1:
        new_focus_block = ''.join(f'- {line}\n' for line in focus_lines)
        new_text = new_text[:focus_start] + new_focus_block + new_text[focus_end:]

    # Update last_saved checkpoint only if we added new tmp summaries
    if tmp_summaries:
        new_text = set_meta(new_text, last_saved=until_dt.isoformat(timespec='minutes'))

    if new_text != text:
        path.write_text(new_text, encoding='utf-8')

    if created:
        print(f"Journal created: {ROOT_ALIAS}/{path.relative_to(BASE_DIR).as_posix()}")
    else:
        print(f"Journal updated: {ROOT_ALIAS}/{path.relative_to(BASE_DIR).as_posix()}")
    if carried:
        print('Moved to Next Steps:')
        for item in carried:
            print(f' - {item}')
    else:
        print('No incomplete items to carry over.')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
