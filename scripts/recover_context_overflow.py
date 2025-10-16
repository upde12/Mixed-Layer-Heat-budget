#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import sys
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTS = ROOT / "docs" / "discussions" / "transcripts"
RECOVERY = ROOT / "docs" / "discussions" / "recovery"


def read_lines(p: Path):
    try:
        with p.open("r", encoding="utf-8", errors="ignore") as f:
            return f.read().splitlines()
    except FileNotFoundError:
        return []


def write_text(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        f.write(text)


def atomic_replace(target: Path, content: str):
    tmp = target.with_suffix(target.suffix + ".tmp")
    write_text(tmp, content)
    os.replace(tmp, target)


def find_tail_by_anchor(raw_lines, paste_lines, back_search=50, min_anchor=5):
    n_raw = len(raw_lines)
    n_paste = len(paste_lines)
    if n_raw == 0:
        return paste_lines  # nothing saved yet
    max_anchor = min(back_search, n_raw, n_paste)
    for anchor in range(max_anchor, min_anchor - 1, -1):
        tail_anchor = tuple(raw_lines[-anchor:])
        # slide over paste and find last occurrence
        for j in range(n_paste - anchor, -1, -1):
            if tuple(paste_lines[j : j + anchor]) == tail_anchor:
                return paste_lines[j + anchor :]
    # fallback: diff-based new lines (order-preserving approximation)
    import difflib

    diff = difflib.ndiff(raw_lines, paste_lines)
    tail = [ln[2:] for ln in diff if ln.startswith("+ ")]
    return tail


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser(description="Recover from context overflow by merging unsaved tail and documenting artifacts.")
    ap.add_argument("--date", type=str, default=dt.date.today().isoformat(), help="Date tag YYYY-MM-DD")
    ap.add_argument("--raw", type=str, default=None, help="Path to existing raw transcript; defaults to docs/discussions/transcripts/<DATE>_session_raw.txt")
    ap.add_argument("--paste", type=str, default=None, help="Path to pasted tmp transcript; defaults to docs/discussions/transcripts/<DATE>_session_paste.tmp.txt")
    ap.add_argument("--stdin", action="store_true", help="Read paste content from STDIN and write to --paste path")
    ap.add_argument("--merge", action="store_true", help="Append unsaved tail to RAW (atomic replace)")
    ap.add_argument("--window-minutes", type=int, default=10, help="Artifacts time window (minutes before now)")
    ap.add_argument("--newer-than", type=str, default=None, help="Artifacts newer-than timestamp 'YYYY-MM-DD HH:MM' (overrides window)")
    ap.add_argument("--do-journal", action="store_true", help="Call log_tmp_note.py and journal_end.py with a summary note")
    ap.add_argument("--note", type=str, default=None, help="Custom journal note (optional)")
    args = ap.parse_args()

    date_tag = args.date
    raw_path = Path(args.raw) if args.raw else TRANSCRIPTS / f"{date_tag}_session_raw.txt"
    paste_path = Path(args.paste) if args.paste else TRANSCRIPTS / f"{date_tag}_session_paste.tmp.txt"
    tail_path = TRANSCRIPTS / f"{date_tag}_session_tail_unsaved.txt"

    paste_path.parent.mkdir(parents=True, exist_ok=True)

    if args.stdin:
        content = sys.stdin.read()
        write_text(paste_path, content)

    raw_lines = read_lines(raw_path)
    paste_lines = read_lines(paste_path)
    if not paste_lines:
        print(f"[ERROR] Paste file empty or missing: {paste_path}", file=sys.stderr)
        sys.exit(2)

    tail_lines = find_tail_by_anchor(raw_lines, paste_lines)
    write_text(tail_path, "\n".join(tail_lines) + ("\n" if tail_lines else ""))

    merged = False
    if args.merge:
        merged_content = "\n".join(raw_lines + (tail_lines if tail_lines else []))
        # normalize trailing newline once
        if not merged_content.endswith("\n"):
            merged_content += "\n"
        atomic_replace(raw_path, merged_content)
        merged = True

    # Artifacts listing
    RECOVERY.mkdir(parents=True, exist_ok=True)
    gs_out = run(["git", "status", "-s"], cwd=ROOT)
    art_git = RECOVERY / f"{date_tag}_artifacts_gitstatus.txt"
    write_text(art_git, gs_out.stdout)

    if args.newer_than:
        newer_than = args.newer_than
    else:
        t = dt.datetime.now() - dt.timedelta(minutes=args.window_minutes)
        newer_than = t.strftime("%Y-%m-%d %H:%M")
    find_cmd = [
        "bash",
        "-lc",
        f"find . -type f -newermt '{newer_than}' ! -path './.git/*' | sed 's#^./##'",
    ]
    fc = run(find_cmd, cwd=ROOT)
    art_newer = RECOVERY / f"{date_tag}_artifacts_newer_than.txt"
    write_text(art_newer, fc.stdout)

    # Recovery note (skeleton)
    rec_md = RECOVERY / f"{date_tag}_context_overflow_recovery.md"
    unsaved_n = len(tail_lines)
    newer_count = len([ln for ln in fc.stdout.splitlines() if ln.strip()])
    rec_body = f"""
# Context Overflow Recovery — {date_tag}

## Summary
- Unsaved tail lines: {unsaved_n}
- Artifacts (newer-than {newer_than}): {newer_count} files
- Merged into RAW: {"yes" if merged else "no"}

## Files
- RAW: {raw_path.relative_to(ROOT)}
- PASTE: {paste_path.relative_to(ROOT)}
- TAIL: {tail_path.relative_to(ROOT)}
- Artifacts (git): {art_git.relative_to(ROOT)}
- Artifacts (newer): {art_newer.relative_to(ROOT)}

## Anchor/Tail Notes
- Anchor-based tail extraction applied; fallback diff used if needed.

## Next Actions (≤3)
1) Review merged RAW and TAIL.
2) Triage artifacts list and move to proper locations if needed.
3) Continue with minimal prompt (Core Mode, size=7, scope=… ).
""".strip()
    write_text(rec_md, rec_body + "\n")

    # Optional journaling
    if args.do_journal:
        note = args.note or f"Context overflow recovery: unsaved={unsaved_n}, artifacts={newer_count}, merged={'yes' if merged else 'no'}"
        run(["python3", str(ROOT / "scripts" / "log_tmp_note.py"), note, "--workdir", str(ROOT)])
        run([
            "python3",
            str(ROOT / "scripts" / "journal_end.py"),
            "--notes",
            note,
        ])

    # Summary to stdout
    print("[OK] Tail lines:", unsaved_n)
    print("[OK] Tail file:", tail_path.relative_to(ROOT))
    if merged:
        print("[OK] RAW merged atomically:", raw_path.relative_to(ROOT))
    print("[OK] Artifacts(git):", art_git.relative_to(ROOT))
    print("[OK] Artifacts(newer):", art_newer.relative_to(ROOT))
    print("[OK] Recovery note:", rec_md.relative_to(ROOT))


if __name__ == "__main__":
    main()

