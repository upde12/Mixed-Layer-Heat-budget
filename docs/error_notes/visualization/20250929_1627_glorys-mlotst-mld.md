---
title: GLORYS mlotst 정의/일치성 불명확: 자체 MLD 재정의 필요
date: 2025-09-29 16:27
category: visualization
tags: [mld-definition, mlhb]
related:
  - docs/guidelines/10_analysis_methods/heat_budget/manual.md
  - scripts/plot_mld_profile.py
---

## 상황 요약
- GLORYS mlotst와 실제 프로파일 기준 불일치 사례 확인

## 에러 메시지
```
mlotst가 10m 참조 Δσ0 기준이라고 하나 일부 지점에서 ΔT/Δσ0 검증 불일치
```

## 원인 진단
- 자료 메타/정의 불명확 및 담수/얕은 수심/해빙 영향

## 해결 절차
1. 보수적 MLD 재산정(Δσ0 0.03 at 10m, 보조 기준/특수 처리) 후 열수지 재평가

## 예방 및 메모
- 후속 조치 및 참고 링크를 작성하세요.
