#!/usr/bin/env python3
"""Generate a weekly journal from daily logs.

Creates docs/journal/<YYYY>/weekly/<YYYY-Www>.md using daily files and tmp notes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

BASE_DIR = Path(__file__).resolve().parents[1]
JOURNAL_DIR = BASE_DIR / 'docs' / 'journal'
TEMPLATES_DIR = JOURNAL_DIR / 'templates'
WEEKLY_TEMPLATE = TEMPLATES_DIR / 'weekly_template.md'


@dataclass
class Note:
    day: dt.date
    start: dt.datetime
    end: dt.datetime
    text: str
    dirs: list[str]
    duration_min: int
    proj: str | None
    tags: list[str]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description='Build weekly journal from daily entries')
    p.add_argument('--date', help='Any date within target week (YYYY-MM-DD). Default: today')
    p.add_argument('--week', help='ISO week like 2025-W39 (overrides --date)')
    p.add_argument('--prev', action='store_true', help='Use previous ISO week from today')
    p.add_argument('--dry', action='store_true', help='Do not write file, just print summary')
    return p.parse_args(argv)


def iso_week_from_date(d: dt.date) -> tuple[int, int]:
    ic = d.isocalendar()
    return ic.year, ic.week


def date_range_for_iso_week(year: int, week: int) -> tuple[dt.date, dt.date]:
    # ISO week: Monday is 1
    first_thu = dt.date(year, 1, 4)
    # Monday of week 1
    week1_mon = first_thu - dt.timedelta(days=first_thu.isoweekday() - 1)
    start = week1_mon + dt.timedelta(weeks=week - 1)
    end = start + dt.timedelta(days=6)
    return start, end


def journal_path_for(d: dt.date) -> Path:
    return JOURNAL_DIR / f'{d.year}' / f'{d:%Y-%m-%d}.md'


def extract_section(text: str, title: str) -> str:
    marker = f'## {title}'
    idx = text.find(marker)
    if idx == -1:
        return ''
    start = text.find('\n', idx) + 1
    next_header = text.find('\n## ', start)
    if next_header == -1:
        next_header = len(text)
    return text[start:next_header]


TASK_RE = re.compile(r'^- \[( |x)\] (.+)$')
NOTE_RE = re.compile(r'^(\d{2}:\d{2})–(\d{2}:\d{2}) \| (.*?) \| (.+)$')


def parse_tasks(block: str) -> tuple[list[str], list[str]]:
    done, todo = [], []
    for line in block.splitlines():
        m = TASK_RE.match(line.strip())
        if not m:
            continue
        checked, text = m.groups()
        if '<TODO' in text:
            continue
        (done if checked == 'x' else todo).append(text)
    return done, todo


def parse_proj_and_tags(message: str) -> tuple[str | None, list[str]]:
    proj = None
    tags: list[str] = []
    # [proj: NAME]
    mp = re.search(r'\[proj:([^\]]+)\]', message, flags=re.IGNORECASE)
    if mp:
        proj = mp.group(1).strip()
    mt = re.search(r'\[tags?:\s*([^\]]+)\]', message, flags=re.IGNORECASE)
    if mt:
        tags = [t.strip() for t in mt.group(1).split(',') if t.strip()]
    return proj, tags


def parse_progress_notes(day: dt.date, block: str) -> Iterable[Note]:
    for line in block.splitlines():
        line = line.strip().lstrip('-').strip()
        m = NOTE_RE.match(line)
        if not m:
            continue
        s, e, message, dirs = m.groups()
        start = dt.datetime.strptime(f'{day:%Y-%m-%d} {s}', '%Y-%m-%d %H:%M')
        end = dt.datetime.strptime(f'{day:%Y-%m-%d} {e}', '%Y-%m-%d %H:%M')
        if end < start:
            end = start
        duration = int((end - start).total_seconds() // 60)
        dir_list = [d.strip() for d in dirs.split(';')] if ';' in dirs else [dirs.strip()]
        proj, tags = parse_proj_and_tags(message)
        yield Note(day=day, start=start, end=end, text=message, dirs=dir_list, duration_min=duration, proj=proj, tags=tags)


def top_level_dir(path: str) -> str:
    if path in ('.', ''):
        return '.'
    p = Path(path)
    parts = p.parts
    return parts[0] if parts else '.'


def infer_project(note: Note) -> str:
    if note.proj:
        return note.proj
    # Directory-based heuristic
    tops = {top_level_dir(d) for d in note.dirs}
    if 'presentation' in tops or 'docs' in tops:
        if 'presentation' in tops:
            return 'Presentation'
        return 'Documentation'
    if 'src' in tops:
        return 'Code/Analysis'
    if 'figures' in tops:
        return 'Visualization'
    if 'scripts' in tops:
        return 'Repo Ops'
    return 'General'


def format_hhmm(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f'{h:02d}:{m:02d}'


def build_weekly(args) -> tuple[str, Path]:
    # Resolve week
    if args.week:
        try:
            year, w = args.week.split('-W')
            year, w = int(year), int(w)
        except Exception as e:
            raise SystemExit(f'Invalid --week format: {args.week}')
    else:
        base_date = dt.date.today()
        if args.date:
            base_date = dt.datetime.strptime(args.date, '%Y-%m-%d').date()
        if args.prev:
            base_date = base_date - dt.timedelta(days=7)
        year, w = iso_week_from_date(base_date)

    start, end = date_range_for_iso_week(year, w)

    # Collect daily files
    days = [start + dt.timedelta(days=i) for i in range(7)]
    dailies = [journal_path_for(d) for d in days if journal_path_for(d).exists()]

    # Aggregate
    all_notes: list[Note] = []
    done_tasks: list[str] = []
    refs: set[str] = set()

    for d in days:
        p = journal_path_for(d)
        if not p.exists():
            continue
        text = p.read_text(encoding='utf-8')
        focus = extract_section(text, 'Focus for Today')
        work = extract_section(text, 'Work Log')
        issues = extract_section(text, 'Issues & References')
        done, _ = parse_tasks(focus)
        done_tasks.extend(done)

        # Parse progress notes
        # Find the bullet list under "- **Progress Notes:**"
        lines = work.splitlines()
        progress_lines = []
        in_progress = False
        for ln in lines:
            s = ln.strip()
            if s.startswith('- **Progress Notes:**'):
                in_progress = True
                continue
            if in_progress:
                if s.startswith('- **'):
                    break
                if s.startswith('- ') or s.startswith('  - '):
                    progress_lines.append(s[2:] if s.startswith('  - ') else s[2:])
        for note in parse_progress_notes(d, '\n'.join(progress_lines)):
            all_notes.append(note)

        # Collect references
        for ln in issues.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s.startswith('-'):
                # Try to extract path-like tokens
                m = re.findall(r'([\w./-]+\.(?:md|png|nc|py|txt))', s)
                refs.update(m)

    # Time aggregation
    total_min = sum(n.duration_min for n in all_notes)
    by_project: dict[str, int] = defaultdict(int)
    by_topdir: dict[str, int] = defaultdict(int)
    for n in all_notes:
        proj = infer_project(n)
        by_project[proj] += n.duration_min
        for d in n.dirs:
            by_topdir[top_level_dir(d)] += n.duration_min

    # Build content
    template = WEEKLY_TEMPLATE.read_text(encoding='utf-8')
    content = template
    content = content.replace('<YYYY-Www>', f'{year}-W{w:02d}')
    content = content.replace('<DATE_RANGE>', f'{start:%Y-%m-%d} – {end:%Y-%m-%d}')

    # Overview numbers (avoid global token collisions)
    days_count = len(dailies)
    avg_min = int(total_min / days_count) if days_count else 0
    content = content.replace('작업일수: <N>', f'작업일수: {days_count}')
    content = content.replace('총 시간: <HH:MM>', f'총 시간: {format_hhmm(total_min)}')
    content = content.replace('일평균: <HH:MM>', f'일평균: {format_hhmm(avg_min)}')
    top_projects = ', '.join(sorted(by_project, key=by_project.get, reverse=True)[:3]) or 'General'
    content = content.replace('<P1>, <P2>, <P3>', top_projects)

    # Achievements (take up to ~6)
    ach_lines = '\n'.join(f'- {t}' for t in done_tasks[:6]) or '- <주요 완료 없음>'
    content = content.replace('- <주요 완료 1>\n- <주요 완료 2>\n- <주요 완료 3>', ach_lines)

    # Progress by Project (top 3)
    proj_section = []
    for proj in sorted(by_project, key=by_project.get, reverse=True)[:3]:
        mins = by_project[proj]
        # sample highlights: top 2 notes by length within this project
        highlights = [n.text for n in all_notes if infer_project(n) == proj]
        highlights = sorted(set(highlights), key=len, reverse=True)[:2]
        # top dirs
        dirs_acc: dict[str, int] = defaultdict(int)
        for n in all_notes:
            if infer_project(n) != proj:
                continue
            for d in n.dirs:
                dirs_acc[top_level_dir(d)] += n.duration_min
        top_dirs = ', '.join(sorted(dirs_acc, key=dirs_acc.get, reverse=True)[:3]) or '.'
        proj_section.append(
            f"- 프로젝트명: {proj}\n  - 시간: {format_hhmm(mins)}\n  - 핵심 진전: {'; '.join(highlights) if highlights else '<요약>'}\n  - 주요 경로: {top_dirs}"
        )
    content = content.replace(
        "- 프로젝트명: <Project A>\n  - 시간: <HH:MM>\n  - 핵심 진전: <핵심 1>; <핵심 2>\n  - 주요 경로: <dir1>, <dir2>\n- 프로젝트명: <Project B>\n  - 시간: <HH:MM>\n  - 핵심 진전: <핵심>\n  - 주요 경로: <dir>",
        '\n'.join(proj_section) if proj_section else '- (프로젝트 분류 없음)'
    )

    # Work Highlights (top 5 distinct)
    hl_candidates = sorted(set(n.text for n in all_notes), key=len, reverse=True)[:5]
    hl_block = '\n'.join(f'- {t}' for t in hl_candidates) or '- <하이라이트 없음>'
    content = content.replace('- <가장 임팩트 있는 하이라이트 1>\n- <하이라이트 2>\n- <하이라이트 3>', hl_block)

    # Metrics & Time: top dirs (3)
    topdirs_fmt = ', '.join(f"{d} ({format_hhmm(by_topdir[d])})" for d in sorted(by_topdir, key=by_topdir.get, reverse=True)[:3]) or '. (00:00)'
    content = content.replace('<dir> (<HH:MM>), <dir> (<HH:MM>)', topdirs_fmt)

    # Issues & References
    if refs:
        ref_line = '- ' + ', '.join(sorted(refs))
    else:
        ref_line = '- <없음>'
    content = content.replace('- 오답노트/이슈: <path1>, <path2>', ref_line)

    # By Day block (chronological)
    by_day: dict[dt.date, list[Note]] = defaultdict(list)
    for n in all_notes:
        by_day[n.day].append(n)
    by_day_lines: list[str] = []
    weekday_map = {1: 'Mon', 2: 'Tue', 3: 'Wed', 4: 'Thu', 5: 'Fri', 6: 'Sat', 7: 'Sun'}
    for d in sorted(by_day):
        notes = sorted(by_day[d], key=lambda x: x.start)
        daily_total = sum(n.duration_min for n in notes)
        by_day_lines.append(f"- {d:%Y-%m-%d} ({weekday_map[d.isoweekday()]}) — 총 {format_hhmm(daily_total)}")
        for n in notes:
            dirs = '; '.join(n.dirs)
            by_day_lines.append(f"  - {n.start:%H:%M}–{n.end:%H:%M} | {n.text} | {dirs}")
    content = content.replace('<BY_DAY_BLOCK>', '\n'.join(by_day_lines) if by_day_lines else '- <기록 없음>')

    # Daily links
    links = '\n'.join(f'- {d:%Y-%m-%d}: docs/journal/{d.year}/{d:%Y-%m-%d}.md' for d in days if journal_path_for(d).exists())
    content = content.replace('- <YYYY-MM-DD>: docs/journal/<YYYY>/<YYYY-MM-DD>.md', links)

    # Path
    out_dir = JOURNAL_DIR / f'{year}' / 'weekly'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{year}-W{w:02d}.md'

    return content, out_path


def main(argv=None):
    args = parse_args(argv)
    content, out_path = build_weekly(args)
    if args.dry:
        print(content)
        return 0
    out_path.write_text(content, encoding='utf-8')
    print(f'Weekly journal created: {out_path.relative_to(BASE_DIR)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
