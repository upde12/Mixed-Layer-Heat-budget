#!/usr/bin/env python3
"""Daily journal start helper."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
JOURNAL_DIR = BASE_DIR / "docs" / "journal"
TEMPLATE_PATH = JOURNAL_DIR / "templates" / "daily_template.md"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Create/update daily journal at start of day")
    parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
    parser.add_argument("--no-carry", action="store_true", help="Do not carry over previous Next Steps")
    return parser.parse_args(argv)


def resolved_date(date_str: str | None) -> dt.date:
    if date_str:
        return dt.datetime.strptime(date_str, "%Y-%m-%d").date()
    return dt.date.today()


def journal_path_for(date: dt.date) -> Path:
    year_dir = JOURNAL_DIR / f"{date.year}"
    year_dir.mkdir(parents=True, exist_ok=True)
    return year_dir / f"{date:%Y-%m-%d}.md"


def read_template(date: dt.date) -> str:
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return text.replace('<YYYY-MM-DD>', f"{date:%Y-%m-%d}")


def get_previous_journal(target_date: dt.date) -> Path | None:
    candidates = sorted(JOURNAL_DIR.rglob('20??-??-??.md'))
    for path in reversed(candidates):
        name = path.stem
        try:
            journal_date = dt.datetime.strptime(name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if journal_date < target_date:
            return path
    return None


def extract_next_steps(path: Path) -> list[str]:
    text = path.read_text(encoding='utf-8')
    marker = "## Next Steps"
    idx = text.find(marker)
    if idx == -1:
        return []
    section_start = text.find('\n', idx) + 1
    next_header = text.find('\n## ', section_start)
    if next_header == -1:
        next_header = len(text)
    block = text[section_start:next_header]
    steps = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith('- ['):
            if '<TODO' in stripped or 'carried forward' in stripped:
                continue
            text_part = stripped.split(']', 1)[1].strip()
            steps.append(text_part)
    return steps


def replace_section(text: str, title: str, lines: list[str]) -> str:
    marker = f"## {title}"
    idx = text.find(marker)
    if idx == -1:
        return text
    section_start = text.find('\n', idx) + 1
    next_header = text.find('\n## ', section_start)
    if next_header == -1:
        next_header = len(text)
    new_block = "".join(f"- [ ] {line}\n" for line in lines) if lines else ""
    return text[:section_start] + new_block + text[next_header:]


def reset_next_steps(previous_path: Path):
    text = previous_path.read_text(encoding='utf-8')
    marker = "## Next Steps"
    idx = text.find(marker)
    if idx == -1:
        return
    section_start = text.find('\n', idx) + 1
    next_header = text.find('\n## ', section_start)
    if next_header == -1:
        next_header = len(text)
    placeholder = "- [ ] <TODO 1>\n- [ ] <TODO 2>\n"
    new_text = text[:section_start] + placeholder + text[next_header:]
    previous_path.write_text(new_text, encoding='utf-8')


def main(argv=None):
    args = parse_args(argv)
    date = resolved_date(args.date)
    journal_path = journal_path_for(date)
    created = False
    if not journal_path.exists():
        template = read_template(date)
        journal_path.write_text(template, encoding='utf-8')
        created = True

    carried_steps: list[str] = []
    prev_path = None
    if not args.no_carry:
        prev_path = get_previous_journal(date)
        if prev_path:
            carried_steps = extract_next_steps(prev_path)

    if carried_steps:
        text = journal_path.read_text(encoding='utf-8')
        text = replace_section(text, "Focus for Today", carried_steps)
        journal_path.write_text(text, encoding='utf-8')
        if prev_path:
            reset_next_steps(prev_path)

    status = "created" if created else "updated"
    print(f"Journal {status}: {journal_path.relative_to(BASE_DIR)}")
    if carried_steps:
        print("Carried over tasks:")
        for item in carried_steps:
            print(f" - {item}")
    elif prev_path:
        print("No pending Next Steps found in previous journal.")


if __name__ == '__main__':
    raise SystemExit(main())
