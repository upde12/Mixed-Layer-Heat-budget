#!/usr/bin/env python3
"""Daily journal start helper."""
from __future__ import annotations

import argparse
import datetime as dt
import os
from collections import defaultdict
from pathlib import Path
import re
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]
ROOT_ALIAS = 'LLM_OPS'
JOURNAL_DIR = BASE_DIR / 'docs' / 'journal'
TEMPLATE_PATH = JOURNAL_DIR / 'templates' / 'daily_template.md'
TMP_DIR = JOURNAL_DIR / 'tmp'
RECAP_TITLE = '최근 7일 요약'
OLD_RECAP_TITLES = ('Yesterday Recap',)
RECAP_TITLES = (RECAP_TITLE, *OLD_RECAP_TITLES)
PROJECT_PRIORITY = ['DEC', 'MHW_JC', 'TCPI', '137E', 'MLHB_OPS', 'GENERAL']
TAGS_PATTERN = re.compile(r'\[tags:\s*([^\]]+)\]')
PROJ_PATTERN = re.compile(r'\[proj:\s*([^\]]+)\]')
# Topic detection (tags first, then keywords)
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
    'ops': ['경로', '별칭', '링크', '구조', 'rename', 'alias', '레포', 'repo', 'refactor', '구조 정리', '분리', '루틴', 'routine', 'journal_start', 'start'],
    'issue': ['오류', '에러', '이슈', '실패', 'error', 'bug'],
    'plan': ['계획', 'plan', '로드맵'],
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Create/update daily journal at start of day')
    parser.add_argument('--date', help='YYYY-MM-DD (default: today)')
    parser.add_argument('--no-carry', action='store_true', help='Do not carry over previous Next Steps')
    parser.add_argument('--rebuild-recap', action='store_true', help='Rebuild the last-7-days recap from scratch')
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


def collect_recent_record_days(target_date: dt.date, limit: int = 7) -> list[tuple[dt.date, Path]]:
    """Return the latest 'limit' existing journal days before or equal to target_date.

    This scans existing journal files (not absolute day windows) and selects the most
    recent days that actually have a file, excluding future dates.
    """
    entries: list[tuple[dt.date, Path]] = []
    for path in JOURNAL_DIR.rglob('20??-??-??.md'):
        journal_date = parse_journal_date(path)
        if not journal_date:
            continue
        if journal_date <= target_date:
            entries.append((journal_date, path))
    # Sort by date descending, take last N (excluding the target if needed later)
    entries.sort(key=lambda t: t[0], reverse=True)
    selected = entries[:limit]
    # Return ascending for nicer display
    return sorted(selected, key=lambda t: t[0])


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


def _strip_bullets(text: str) -> str:
    t = text.strip()
    if not t:
        return ''
    t = re.sub(r'^(?:[-*]\s+)+', '', t)
    return t.strip()


def _strip_time_prefix(text: str) -> str:
    return re.sub(r'^\d{2}:\d{2}–\d{2}:\d{2}\s*\|\s*', '', text).strip()


def _remove_link_suffix(text: str) -> str:
    if ' | ' in text:
        return text.split(' | ', 1)[0].strip()
    return text


def _split_metadata_items(raw: str) -> list[str]:
    parts = []
    for token in re.split(r'[,+/&]', raw):
        token = token.strip()
        if token:
            parts.append(token)
    return parts


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

    cleaned = _remove_link_suffix(_strip_time_prefix(_strip_bullets(text))).strip()
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    if '<시간대별 주요 작업>' in cleaned:
        cleaned = ''
    return cleaned, projects, tags


def extract_progress_entries(path: Path) -> list[dict]:
    """Extract structured progress entries from a journal file."""
    text = path.read_text(encoding='utf-8')
    block, *_ = extract_section(text, 'Work Log')
    if not block:
        return []
    lines = block.splitlines()
    in_progress = False
    collected: list[dict] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- **Progress Notes:**'):
            in_progress = True
            continue
        if stripped.startswith('- **End:**'):
            in_progress = False
        if not in_progress:
            continue
        if stripped.startswith('- ') or stripped.startswith('  - '):
            cleaned, projects, tags = _extract_metadata(stripped)
            if cleaned:
                collected.append({'text': cleaned, 'projects': projects, 'tags': tags})
    return collected


def _detect_topic(text: str, tags: list[str]) -> str:
    # tag-based detection
    tagset = {t.lower() for t in (tags or [])}
    for t in ('decision', 'run', 'result', 'viz', 'doc', 'ops', 'issue', 'plan'):
        if t in tagset:
            return t
    # keyword-based detection with ops priority
    low = text.lower()
    # prioritize ops triggers first
    for w in TOPIC_KEYWORDS['ops']:
        if w.lower() in low:
            return 'ops'
    # then other topics by preferred scientific order
    for t in ('decision', 'result', 'run', 'viz', 'doc', 'issue', 'plan'):
        for w in TOPIC_KEYWORDS.get(t, []):
            if w.lower() in low:
                return t
    return 'misc'


def _trim_phrase(text: str, max_len: int = 110) -> str:
    t = text.strip()
    if len(t) <= max_len:
        return t
    cand = t[:max_len]
    # Prefer sentence boundaries within limit
    ends = ['다.', '요.', '. ', '! ', '? ', '…', ').', '.)', '; ']
    cut = -1
    for end in ends:
        idx = cand.rfind(end)
        if idx != -1:
            cut = max(cut, idx + len(end))
    if cut != -1:
        return cand[:cut].rstrip()
    # Fallback to last whitespace
    ws = cand.rfind(' ')
    if ws != -1 and ws > max_len * 0.6:
        return cand[:ws].rstrip()
    return cand.rstrip()


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
    # Build ordered candidates by topic priority
    priority = ('decision', 'run', 'result', 'viz', 'doc', 'ops', 'issue', 'plan', 'misc')
    by_topic: dict[str, list[str]] = defaultdict(list)
    seen: set[str] = set()
    for e in entries:
        txt = e.get('text', '').strip()
        if not txt:
            continue
        topic = _detect_topic(txt, e.get('tags', []))
        if txt not in seen:
            by_topic[topic].append(txt)
            seen.add(txt)
    # Choose up to limit representative phrases
    chosen: list[tuple[str, str]] = []  # (label, phrase)
    for topic in priority:
        if len(chosen) >= limit:
            break
        items = by_topic.get(topic)
        if items:
            label = TOPIC_LABELS.get(topic, topic)
            phrase = items[0]
            # Simplify ops phrasing aggressively
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
            # Remove duplicated leading labels if any
            phrase = _trim_phrase(phrase)
            chosen.append((label, phrase))
    # If still short, backfill with last distinct entry
    if len(chosen) < limit:
        for e in reversed(entries):
            txt = e.get('text', '').strip()
            if not txt:
                continue
            phrase = _trim_phrase(txt)
            if all(phrase != c for _, c in chosen):
                # simplify ops if needed (rare in backfill)
                chosen.append((TOPIC_LABELS.get('misc', '기타'), phrase))
                if len(chosen) >= limit:
                    break
    if not chosen:
        return None
    parts = [f"{label} — {phrase}" for label, phrase in chosen]
    prefix = 'MLHB — ' if mlhb_flag else ''
    return f"{project}: {prefix}{'; '.join(parts)}"


def build_recent_activity_lines(entries: list[tuple[dt.date, Path]], per_day_items: int = 2) -> list[str]:
    """Build activity recap lines like "YYYY-MM-DD: CODE: summary; ..."."""
    lines: list[str] = []
    for day, path in entries:
        progress_entries = extract_progress_entries(path)
        if not progress_entries:
            continue
        grouped: dict[str, list[dict]] = defaultdict(list)
        for item in progress_entries:
            projects = item.get('projects') or []
            if not projects:
                grouped['GENERAL'].append(item)
            else:
                for proj in projects:
                    grouped[proj].append(item)
        segments: list[str] = []
        for proj, proj_entries in sorted(grouped.items(), key=lambda kv: _project_order_key(kv[0])):
            segment = _summarize_project(proj, proj_entries, limit=per_day_items)
            if segment:
                segments.append(segment)
        if not segments:
            continue
        day_line = f"{day:%Y-%m-%d}: {'; '.join(segments)}"
        lines.append(day_line)
    return lines


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


def _read_recap_lines(text: str) -> list[str]:
    """Return existing recap lines (without leading '-') from the recap section."""
    block, *_ = extract_section(text, RECAP_TITLES)
    lines: list[str] = []
    for ln in block.splitlines():
        s = ln.strip()
        if s.startswith('- '):
            lines.append(s[2:])
    return lines


def _parse_recap_date(line: str) -> dt.date | None:
    """Extract YYYY-MM-DD date from a recap line 'YYYY-MM-DD: ...'."""
    try:
        head = line.split(':', 1)[0].strip()
        return dt.datetime.strptime(head, '%Y-%m-%d').date()
    except Exception:
        return None


def find_previous_record_day(target_date: dt.date) -> tuple[dt.date, Path] | None:
    """Find the most recent journal day strictly before target_date."""
    candidates: list[tuple[dt.date, Path]] = []
    for path in JOURNAL_DIR.rglob('20??-??-??.md'):
        d = parse_journal_date(path)
        if d and d < target_date:
            candidates.append((d, path))
    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0]


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


def summarize_recent_activity(activity_lines: list[str], limit: int = 3) -> str:
    """Return a compact summary string from recent per-day activity lines.

    Uses the part after the date to compose a short preview for tmp notes.
    """
    if not activity_lines:
        return '최근 7일 활동 요약이 없습니다.'
    previews: list[str] = []
    for line in activity_lines[::-1]:  # prefer most recent first
        _, _, detail = line.partition(': ')
        if detail and detail not in previews:
            previews.append(detail)
        if len(previews) >= limit:
            break
    return ' · '.join(previews) if previews else '최근 7일 활동 요약이 없습니다.'


def summarize_next_steps(steps: list[str], limit: int = 3) -> str:
    """Return a compact recommendation text for next steps."""
    if not steps:
        return '추천할 보류 작업이 없습니다.'

    preview = steps[:limit]
    if len(steps) <= limit:
        return ' · '.join(preview)

    remaining = len(steps) - limit
    return ' · '.join(preview) + f' 외 {remaining}건'


def ensure_tmp_note(date: dt.date, recap_summary: str, next_steps_summary: str) -> Path:
    """Ensure that the daily temporary note file exists with an initial entry."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    path = TMP_DIR / f'{date:%Y-%m-%d}_notes.md'
    if path.exists():
        return path

    now = dt.datetime.now().strftime('%H:%M')
    workdir = f"{ROOT_ALIAS}/scripts"
    header = f'# Temporary Notes – {date:%Y-%m-%d}\n\n'
    # Link target should be relative to the tmp note file directory
    link_target = os.path.relpath(str(BASE_DIR / 'scripts'), start=str(path.parent))
    link_target = Path(link_target).as_posix()
    body = [
        '- 작업 메모를 추가하려면 `python3 scripts/log_tmp_note.py "<요약>"`를 사용하세요.\n\n',
        f'- {now} 시작: journal_start.py 실행, 최근 7일 요약 준비 → {recap_summary} [dir: {workdir}] [{workdir}]({link_target})\n',
        f'- {now} 참고: 이월 작업 → {next_steps_summary} [dir: {workdir}] [{workdir}]({link_target})\n',
    ]
    path.write_text(header + ''.join(body) + '\n', encoding='utf-8')
    return path


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
        new_block = '- 최근 7일 활동 요약이 없습니다.\n'
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
    # Do not pre-populate Focus for Today — it will be generated during save.
    # We also avoid resetting previous days' Next Steps here to preserve their context.
    # Incremental update for recent activity recap:
    existing_recap = _read_recap_lines(text)
    if created or not existing_recap:
        # Bootstrap: fill up to 7 most recent recorded days (excluding today)
        recent_days = collect_recent_record_days(date - dt.timedelta(days=1), limit=7)
        activity_lines = build_recent_activity_lines(recent_days)
        text = set_yesterday_recap(text, activity_lines)
    else:
        prev = find_previous_record_day(date)
        if prev is not None:
            prev_date, prev_path = prev
            newest_date = _parse_recap_date(existing_recap[-1]) if existing_recap else None
            if newest_date != prev_date:
                # Build one line for the previous recorded day and append; keep last 7
                new_line = build_recent_activity_lines([(prev_date, prev_path)], per_day_items=2)
                if new_line:
                    updated = existing_recap[-6:] + [new_line[0]] if len(existing_recap) >= 6 else existing_recap + [new_line[0]]
                    text = set_yesterday_recap(text, updated)
        # else: no earlier records; leave as-is
    path.write_text(text, encoding='utf-8')

    status = 'created' if created else 'updated'
    print(f'Journal {status}: {ROOT_ALIAS}/{path.relative_to(BASE_DIR).as_posix()}')
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

    # For tmp note: summarize using the recap currently in file (after update)
    recap_current = _read_recap_lines(text)
    recap_summary = summarize_recent_activity(recap_current)
    next_steps_summary = summarize_next_steps(carried_steps)
    print('요약:', recap_summary)
    print('추천 다음 단계:', next_steps_summary)
    tmp_path = ensure_tmp_note(date, recap_summary, next_steps_summary)
    print(f'임시 메모 파일: {ROOT_ALIAS}/{tmp_path.relative_to(BASE_DIR).as_posix()}')


if __name__ == '__main__':
    raise SystemExit(main())
