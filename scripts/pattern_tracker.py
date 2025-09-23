#!/usr/bin/env python3
"""CLI helper to log inefficiency patterns and suggest new guidelines."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = BASE_DIR / "data" / "efficiency_patterns.json"
DEFAULT_THRESHOLD = 3
WEEKLY_INTERVAL_DAYS = 7


def load_state() -> Dict[str, Any]:
    if not DATA_PATH.exists():
        return {
            "entries": [],
            "tag_alerts": {},
            "threshold": DEFAULT_THRESHOLD,
            "last_weekly_review": None,
            "next_id": 1,
        }
    try:
        state = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"패턴 데이터 파일을 읽는 중 오류 발생: {exc}")
    state.setdefault("entries", [])
    state.setdefault("tag_alerts", {})
    state.setdefault("threshold", DEFAULT_THRESHOLD)
    state.setdefault("last_weekly_review", None)
    state.setdefault("next_id", len(state["entries"]) + 1)
    return state


def save_state(state: Dict[str, Any]) -> None:
    DATA_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_tags(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def ensure_input(arg_value: str | None, prompt: str) -> str:
    if arg_value:
        return arg_value
    try:
        return input(f"{prompt}: ").strip()
    except EOFError as exc:
        raise SystemExit(f"입력이 필요하지만 제공되지 않았습니다 ({prompt}). --help를 참고하세요.") from exc


def add_entry(args: argparse.Namespace) -> None:
    state = load_state()
    timestamp = args.timestamp or dt.datetime.now().isoformat(timespec="minutes")
    tags = parse_tags(args.tags)
    context = ensure_input(args.context, "Context")
    intent = ensure_input(args.intent, "Intent")
    response = ensure_input(args.response, "Observed response")
    issue = ensure_input(args.issue, "Inefficiency summary")
    fix = ensure_input(args.fix, "Fix / follow-up")
    insight = ensure_input(args.insight, "Insight")

    entry = {
        "id": state.get("next_id", 1),
        "timestamp": timestamp,
        "context": context,
        "intent": intent,
        "response": response,
        "issue": issue,
        "fix": fix,
        "insight": insight,
        "tags": tags,
    }

    state["entries"].append(entry)
    state["next_id"] = entry["id"] + 1

    # Compute tag counts and trigger alerts when thresholds are reached.
    counts = Counter(tag for item in state["entries"] for tag in item.get("tags", []))
    threshold = state.get("threshold", DEFAULT_THRESHOLD) or DEFAULT_THRESHOLD
    alerts_triggered: List[str] = []
    tag_alerts = state.setdefault("tag_alerts", {})

    for tag in tags:
        count = counts[tag]
        if threshold <= 0:
            continue
        new_alert_level = count // threshold
        prev_alert_level = tag_alerts.get(tag, 0)
        if new_alert_level > prev_alert_level:
            alerts_triggered.append(f"태그 '{tag}'가 {count}회 기록됨 → 지침 초안을 고려하세요.")
            tag_alerts[tag] = new_alert_level
        else:
            tag_alerts.setdefault(tag, prev_alert_level)

    save_state(state)

    print("패턴이 기록되었습니다. (id={id}, timestamp={ts})".format(id=entry["id"], ts=entry["timestamp"]))
    if alerts_triggered:
        print("\n[알림] 반복된 비효율 발견:")
        for message in alerts_triggered:
            print(f" - {message}")

    if weekly_review_due(state):
        due_since = state.get("last_weekly_review")
        if due_since:
            print(f"\n[주간 정리 필요] 마지막 검토일: {due_since}. 이번 주에 패턴 분류/병합을 진행하세요.")
        else:
            print("\n[주간 정리 필요] 아직 주간 검토가 수행되지 않았습니다. 패턴 분류/병합을 진행하세요.")


def weekly_review_due(state: Dict[str, Any]) -> bool:
    last = state.get("last_weekly_review")
    if not last:
        return True
    try:
        last_date = dt.datetime.fromisoformat(last).date()
    except ValueError:
        return True
    return (dt.date.today() - last_date).days >= WEEKLY_INTERVAL_DAYS


def cmd_status(_: argparse.Namespace) -> None:
    state = load_state()
    entries = state.get("entries", [])
    counts = Counter(tag for item in entries for tag in item.get("tags", []))
    print(f"총 기록 수: {len(entries)}")
    if counts:
        print("태그별 빈도:")
        for tag, count in counts.most_common():
            print(f" - {tag}: {count}")
    else:
        print("태그별 빈도: (기록 없음)")

    if weekly_review_due(state):
        due_since = state.get("last_weekly_review") or "N/A"
        print(f"주간 검토 필요: 예 (마지막 검토일 {due_since})")
    else:
        print("주간 검토 필요: 아니오")


def cmd_weekly_review(args: argparse.Namespace) -> None:
    state = load_state()
    entries = state.get("entries", [])
    counts = Counter(tag for item in entries for tag in item.get("tags", []))

    if not entries:
        print("기록된 패턴이 없습니다. 주간 검토를 생략합니다.")
        return

    print("주간 검토 요약:")
    print(f" - 검토 대상 기록 수: {len(entries)}")
    if counts:
        print(" - 태그별 누적:")
        for tag, count in counts.most_common():
            print(f"   · {tag}: {count}")
    else:
        print(" - 태그 없음 (패턴 태깅 필요)")

    if args.note:
        print(f" - 추가 메모: {args.note}")

    state["last_weekly_review"] = dt.date.today().isoformat()
    save_state(state)
    print("주간 검토일이 업데이트되었습니다.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="비효율 패턴 기록 및 리뷰 도우미")
    sub = parser.add_subparsers(dest="command", required=True)

    log_parser = sub.add_parser("log", help="새로운 비효율 패턴을 기록합니다")
    log_parser.add_argument("--context", help="상황/맥락 요약")
    log_parser.add_argument("--intent", help="사용자 의도 요약")
    log_parser.add_argument("--response", help="관측된 응답 요약")
    log_parser.add_argument("--issue", help="비효율 요약")
    log_parser.add_argument("--fix", help="수정 또는 후속 조치")
    log_parser.add_argument("--insight", help="얻은 교훈")
    log_parser.add_argument("--tags", help="쉼표로 구분된 태그 목록")
    log_parser.add_argument("--timestamp", help="ISO 형식 타임스탬프 (기본: 현재 시각)")
    log_parser.set_defaults(func=add_entry)

    status_parser = sub.add_parser("status", help="현재 누적 상태를 요약합니다")
    status_parser.set_defaults(func=cmd_status)

    weekly_parser = sub.add_parser("weekly-review", help="주간 리뷰를 수행하고 날짜를 갱신합니다")
    weekly_parser.add_argument("--note", help="검토 메모")
    weekly_parser.set_defaults(func=cmd_weekly_review)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
