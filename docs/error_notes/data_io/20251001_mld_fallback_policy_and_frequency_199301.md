---
title: Δσ₀ 임계기준 MLD – 교차 미도달 칼럼 처리정책과 1993-01 빈도
date: 2025-10-01 16:05
category: data_io
tags: [mld, density-threshold, policy, fallback]
related:
  - llm-ops/src/process_d2nf.py
  - llm-ops/scripts/compute_mld_fallback_stats.py
  - llm-ops/scripts/plot_mld_profile_recomputed.py
---

## 배경
- Δσ₀=0.03@10 m 기준으로 혼합층을 재계산할 때, 10 m 아래로 내려가도 임계에 도달하지 않는 칼럼이 존재한다(강한 성층/얕은 수심/고염·저온 조합 등). 이 경우 MLD 처리정책이 필요하다.

## 정책 후보
1) Missing(전 항 NaN): 물리적 일관성↑, 표본 감소로 통계 편향 우려.
2) Bottom fallback(최심층을 MLD로): 공간 연속성↑, 얕은 수심에서 ENT/DIFFV 의미 왜곡 위험.

권장: 기본은 Missing, 시각화 등 연속 지도가 필요할 때만 fallback을 옵션으로 적용. 일별 파일에 `FALLBACK`/`SHALLOW_LT10` 마스크를 저장하고, 월평균에서 `--mask-fallback`로 제외 가능하게 한다.

## 관측/사례
- 1993‑01‑02 (37.17°N, 137.08°E): Δσ₀(10 m 기준) 교차 없음, 최심층 ≈ 55.8 m.
  - 제품/기존 실행물에서 MLD≈0.5 m 사례 확인(정책/로직 불일치).

## 월간 빈도(1993‑01)
- 스크립트: `llm-ops/scripts/compute_mld_fallback_stats.py`
- 결과 요약: `days=31`, `valid_cells=1,898,998`, `fallback_cells=331,714`, `fraction≈0.1747`.
- 산출 파일: `/Volumes/HJPARK4/Decadal/source/ML_budget/output/diagnostics/mld_fallback_199301.nc`

## 재현
```bash
. .venv/bin/activate
python llm-ops/scripts/compute_mld_fallback_stats.py \
  --month 1993-01 \
  --indir /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
  --out /Volumes/HJPARK4/Decadal/source/ML_budget/output/diagnostics/mld_fallback_199301.nc
```

## 후속 작업
- `process_d2nf.py`에 `--fallback-policy {missing,bottom}` 스위치 도입, 마스크 변수/전역 속성 기록.
- 월평균 러너에 `--mask-fallback` 옵션 추가, 표본수·fraction 메타 기록.

