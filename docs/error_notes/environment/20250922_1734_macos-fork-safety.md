---
title: macOS fork safety 경고
date: 2025-09-22 17:34
category: environment
tags: [macos, corefoundation, here-doc]
related:
  - scripts/log_error_note.py
---

## 상황 요약
- bash here-doc으로 대형 파이썬 스크립트를 쓸 때 CoreFoundation이 fork 안전성을 요구하며 세그폴트 발생

## 에러 메시지
```
The process has forked and you cannot use this CoreFoundation functionality safely. You MUST exec().
```

## 원인 진단
- macOS에서 GUI 라이브러리가 로드된 상태에서 here-doc으로 python 호출 시 fork 제한에 걸림

## 해결 절차
1. python - <<PY 방식으로 파일을 쓰거나 OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES로 회피

## 예방 및 메모
- 후속 조치 및 참고 링크를 작성하세요.
