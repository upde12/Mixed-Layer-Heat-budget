#!/usr/bin/env python3
"""Daily journal end helper."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
JOURNAL_DIR = BASE_DIR / "docs" / "journal"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Wrap up daily journal at end of day")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    return parser.parse_args(argv)


def resolved_date(date_str: str | None) -> dt.date:
    if date_str:
        return dt.datetime.strptime(date_str, "%Y-%m-%d").date()
    return dt.date.today()


def journal_path_for(date: dt.date) -> Path:
    return JOURNAL_DIR / f"{date.year}" / f"{date:%Y-%m-%d}.md"


def extract_section(text: str, title: str):
    marker = f"## {title}"
    idx = text.find(marker)
    if idx == -1:
        return "", idx, idx
    section_start = text.find('\n', idx) + 1
    next_header = text.find('\n## ', section_start)
    if next_header == -1:
        next_header = len(text)
    return text[section_start:next_header], section_start, next_header


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
    path = journal_path_for(date)
    if not path.exists():
        print(f"Journal not found: {path.relative_to(BASE_DIR)}")
        return 1

    text = path.read_text(encoding='utf-8')
    focus_block, focus_start, focus_end = extract_section(text, "Focus for Today")
    next_block, next_start, next_end = extract_section(text, "Next Steps (for tomorrow)")

    focus_tasks = parse_tasks(focus_block)
    next_tasks = [t for t in parse_tasks(next_block) if '<TODO' not in t[1]]

    next_texts = {t[1] for t in next_tasks}
    carried = []
    for status, task, line in focus_tasks:
        if status == ' ':  # unchecked
            if task not in next_texts:
                next_tasks.append((' ', task, line))
                next_texts.add(task)
                carried.append(task)

    if next_tasks:
        new_next = "".join(f"- [ ] {task}\n" for _, task, _ in next_tasks)
    else:
        new_next = "- [ ] <TODO 1>\n- [ ] <TODO 2>\n"

    new_text = text[:next_start] + new_next + text[next_end:]
    if new_text != text:
        path.write_text(new_text, encoding='utf-8')

    print(f"Journal updated: {path.relative_to(BASE_DIR)}")
    if carried:
        print("Moved to Next Steps:")
        for item in carried:
            print(f" - {item}")
    else:
        print("No incomplete items to carry over.")

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
