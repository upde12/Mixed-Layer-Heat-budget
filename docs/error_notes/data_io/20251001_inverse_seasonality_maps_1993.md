---
title: Inverse(Δσ0<0 below 10 m) 계절성 및 지도 — 1993
date: 2025-10-01 17:05
category: data_io
tags: [mld, inverse, seasonality, diagnostics]
related:
  - llm-ops/scripts/compute_mld_fallback_stats.py
  - llm-ops/scripts/plot_inverse_fraction_year.py
  - /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/inverse_fraction/1993_inverse_fraction_12panel.png
---

## 요약
- Δσ0=0.03(@10 m) 기준에서 10 m 아래 σ0가 전 구간 더 가벼운 inverse 케이스의 월별 빈도를 1993년 12개월에 대해 산출했다. 겨울철(1–2, 12월) 빈도가 상대적으로 높고, 하절기에는 급감한다.

## 산출물
- 월별 진단 NetCDF: `/Volumes/HJPARK4/Decadal/source/ML_budget/output/diagnostics/mld_masks_1993MM.nc`
  - 변수: `inverse_days`, `deepnocross_days`, `shallow_days`, `valid_days`, `inverse_fraction` 등
- 연간 12‑패널 지도: `/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/inverse_fraction/1993_inverse_fraction_12panel.png`

## 메모
- inverse 빈도(그리드 평균 대략치): 1–2월 ≈0.5–1.5%, 12월 ≈1.1%, 5–7월 ≈0.03–0.05%.
- 해석: 겨울 급랭 이벤트 직후 10 m가 가장 무거운 ‘렌즈’가 되는 상황이 잦고, 여름에는 표층 가열·담수 영향으로 Δσ0<0 발생이 드묾.
- 안정성은 in‑situ ρ 및 N²로 대부분 양(안정)임을 사례 검증으로 확인.

