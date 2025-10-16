#!/usr/bin/env python3
"""Answer Quality Auditor

Reads answer text (from --in file or stdin) and runs rule-based checks:
 - Evidence: file/line refs, code identifiers, numeric+unit hints
 - Language: forbid vague terms, ensure Korean presence
 - Units: MLHB K s^-1 <-> K day^-1 conversion requires ×86400 mention
 - Links: external links flagged (internal preferred)
 - MLHB keywords: we-mode/MLD options mentioned when relevant

Outputs a human-readable report by default, or JSON with --json.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

BASE_DIR = Path(__file__).resolve().parents[1]


@dataclass
class RuleResult:
    name: str
    ok: bool
    detail: str


def read_text(path: str | None) -> str:
    if path:
        return Path(path).read_text(encoding='utf-8')
    import sys
    return sys.stdin.read()


# Simple heuristics
FILE_REF_RE = re.compile(r"\b([A-Za-z0-9_./-]+\.[A-Za-z0-9_]+)(?::(\d+))?\b")
CODE_IDENT_RE = re.compile(r"--[A-Za-z0-9_-]+|\b[A-Za-z_][A-Za-z0-9_]*\(\)")
NUM_UNIT_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(K\s*/?\s*day|K\s*day-1|K\s*/?\s*s|K\s*s-1|W\s*m\^-2)\b", re.IGNORECASE)
HANGUL_RE = re.compile(r"[\u3131-\u318F\uAC00-\uD7A3]")
VAGUE_TERMS = [
    "아마", "대충", "그런 것 같", "그럴 수도", "추측", "maybe", "probably", "likely ", "guess"
]
EXTERNAL_RE = re.compile(r"https?://|mailto:")


def check_evidence(text: str) -> RuleResult:
    files = FILE_REF_RE.findall(text)
    code = CODE_IDENT_RE.findall(text)
    nums = NUM_UNIT_RE.findall(text)
    ok = bool(files or code or nums)
    detail = f"files={len(files)}, code_ids={len(code)}, num_units={len(nums)}"
    return RuleResult("evidence", ok, detail)


def check_language(text: str) -> RuleResult:
    has_ko = bool(HANGUL_RE.search(text))
    found_vague = [t for t in VAGUE_TERMS if t.lower() in text.lower()]
    ok = has_ko and not found_vague
    detail = ("ko=" + ("yes" if has_ko else "no") + ", vague=" + ",".join(found_vague or ["none"]))
    return RuleResult("language", ok, detail)


def check_units(text: str) -> RuleResult:
    mentions_ks = re.search(r"K\s*(?:/\s*s|s-1)", text, re.IGNORECASE)
    mentions_kd = re.search(r"K\s*(?:/\s*day|day-1)", text, re.IGNORECASE)
    mentions_86400 = "86400" in text
    # If both K/s and K/day are mentioned but not 86400, warn
    ok = True
    detail = ""
    if mentions_ks and mentions_kd and not mentions_86400:
        ok = False
        detail = "K/s↔K/day 언급에 ×86400 미표기"
    else:
        detail = "ok or not-applicable"
    return RuleResult("units_mlhb", ok, detail)


def check_links(text: str) -> RuleResult:
    external = EXTERNAL_RE.findall(text)
    ok = len(external) == 0
    detail = f"external_links={len(external)} (요청 시에만 사용)"
    return RuleResult("links_policy", ok, detail)


def check_keywords(text: str) -> RuleResult:
    keys = ["we-mode", "Δσ0", "mld", "centered", "deepening", "dhdt", "centered_deepening"]
    present = [k for k in keys if k.lower() in text.lower()]
    # informational; doesn't fail
    return RuleResult("mlhb_keywords", True, "present=" + (",".join(present) or "none"))


def score(results: List[RuleResult]) -> int:
    # Basic score: pass count * 20 (max 100), informational rules excluded
    penalize = {"evidence", "language", "units_mlhb", "links_policy"}
    passed = sum(1 for r in results if r.name in penalize and r.ok)
    return int(passed / len(penalize) * 100)


def run_checks(text: str) -> Dict:
    results = [
        check_evidence(text),
        check_language(text),
        check_units(text),
        check_links(text),
        check_keywords(text),
    ]
    total = score(results)
    return {
        "score": total,
        "results": [{"name": r.name, "ok": r.ok, "detail": r.detail} for r in results],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Audit answer text for QA rules')
    ap.add_argument('--in', dest='infile', help='Input file; otherwise read stdin')
    ap.add_argument('--json', action='store_true', help='Output JSON')
    args = ap.parse_args(argv)

    text = read_text(args.infile)
    data = run_checks(text)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    print(f"QA Score: {data['score']}")
    for r in data['results']:
        mark = 'OK ' if r['ok'] else 'FAIL'
        print(f" - {mark} {r['name']}: {r['detail']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
