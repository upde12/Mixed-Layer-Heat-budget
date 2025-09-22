#!/usr/bin/env python3
"""CLI helper to append a new error note entry."""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
NOTES_DIR = BASE_DIR / "docs" / "error_notes"
CATEGORIES = {
    "data_io": "데이터 I/O",
    "performance": "성능/자원",
    "visualization": "시각화",
    "environment": "환경/의존성",
    "remote_ops": "원격/네트워크",
}


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"\s+", "-", value).strip("-")
    return value or "note"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="오답노트 기록 생성기")
    parser.add_argument("--title", required=True, help="기록 제목")
    parser.add_argument("--category", required=True, choices=CATEGORIES.keys(), help="오답노트 범주")
    parser.add_argument("--summary", default="", help="상황 요약 한 줄")
    parser.add_argument("--error", default="", help="에러 메시지 본문")
    parser.add_argument("--cause", default="", help="원인 진단 요약")
    parser.add_argument("--resolution", default="", help="해결 절차 요약")
    parser.add_argument("--tags", default="", help="쉼표로 구분된 태그 목록")
    parser.add_argument("--related", action="append", default=[], help="관련 파일/링크 (필요 시 여러 번 입력)")
    parser.add_argument("--error-from-stdin", action="store_true", help="표준입력에서 에러 메시지를 읽어온다")
    parser.add_argument("--dry-run", action="store_true", help="파일을 쓰지 않고 결과만 출력")
    return parser.parse_args(argv)


def build_note_content(args: argparse.Namespace) -> str:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    related = args.related or []
    related_block = "\n".join(f"  - {item}" for item in related) if related else "  -"
    error_block = args.error.strip()
    content = f"""---
title: {args.title}
date: {now}
category: {args.category}
tags: [{', '.join(tags)}]
related:
{related_block}
---

## 상황 요약
- {args.summary or '작성 필요'}

## 에러 메시지
```
{error_block or '에러 로그 추가 필요'}
```

## 원인 진단
- {args.cause or '원인 분석 추가 필요'}

## 해결 절차
1. {args.resolution or '해결 방법 기록 필요'}

## 예방 및 메모
- 후속 조치 및 참고 링크를 작성하세요.
"""
    return content


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.error_from_stdin:
        stdin_data = sys.stdin.read().strip()
        args.error = "\n".join(filter(None, [args.error, stdin_data])) if args.error else stdin_data

    slug = slugify(args.title)
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    category_dir = NOTES_DIR / args.category
    category_dir.mkdir(parents=True, exist_ok=True)
    note_path = category_dir / f"{timestamp}_{slug}.md"

    content = build_note_content(args)

    if args.dry_run:
        print(content)
        print(f"(dry-run) {note_path}")
        return 0

    note_path.write_text(content, encoding="utf-8")
    print(f"오답노트 저장 완료: {note_path.relative_to(BASE_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
