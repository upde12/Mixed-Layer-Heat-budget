---
title: 얕은 수심(<10 m) 처리 정책 – Shelf mode(계산 유지 + 마스크 병기)
date: 2025-10-01 16:40
category: data_io
tags: [mld, shelf, policy, masking]
related:
  - llm-ops/src/process_d2nf.py
  - llm-ops/scripts/run_mlhb_monthly.py
  - llm-ops/scripts/plot_mld_fallback_daily_maps.py
---

## 배경
- Δσ₀=0.03(@10 m) 기준에서 수심이 10 m보다 얕은 칼럼은 기준층(z=10 m)이 정의되지 않는다. 기존 접근은 NaN(제외)이었으나, SST 반응(가열률) 해석에서는 얕은 칼럼을 포함하는 편이 직관적이다.

## 결정(2025-10-01)
1) 얕은 수심(<10 m): 계산은 유지하고 지도/통계에 `SHALLOW_LT10` 마스크를 함께 표기한다. 필요 시 후처리에서 이 마스크로 제외한다.
2) 깊지만 Δσ₀ 미도달(deep-no-cross): 포함. 혼합층 경계 부재로 간주해 bottom‑fallback(ENT=0, DIFFV=0)을 적용한다.
3) 역전(10 m보다 깊은 층에서 Δσ₀<0; 이하 "INVERSE_GE10"): 기본 제외. 필요 시 별도 분석(제품 MLD 대체, 얕은 기준 적용 등)에서만 사용.

## 운영 메모
- 두 트랙 제시를 권장한다.
  - 기본(논문/예산): SHALLOW_LT10/INVERSE_GE10 제외, deep‑no‑cross 포함.
  - SST(보고/운영): SHALLOW_LT10 포함, deep‑no‑cross 포함.
- 산출 메타: `fallback_fraction`, `shelf_fraction`(=SHALLOW_LT10 비율) 병기.

## 구현(추후 반영 계획)
- process_d2nf.py
  - `--fallback-policy {missing,bottom}` 유지 + `SHALLOW_LT10`, `INVERSE_GE10`, `FALLBACK` 마스크 변수 기록.
- run_mlhb_monthly.py
  - `--mask-fallback`(기본 트랙), `--shelf-mode`(SST 트랙) 옵션으로 집계 분기.

## 근거/검증 지표
- SST 회귀: d(SST)/dt vs QNET/(ρCp h)에서 SHALLOW_LT10 포함 시 기울기·상관 개선 여부.
- 닫힘(C): 기본 트랙에서 SHALLOW/INVERSE 제외가 C의 IQR/RMS를 줄이는지.
