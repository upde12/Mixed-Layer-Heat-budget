---
title: MLHB 운영·정책·도구 진척 요약 — 2025-10-01
date: 2025-10-01
owner: MLHB-core
related:
  - docs/journal/2025/2025-10-01.md
  - docs/error_notes/data_io/20251001_shallow_shelf_mode_policy.md
  - docs/error_notes/data_io/20251001_inverse_seasonality_maps_1993.md
  - docs/error_notes/data_io/20251001_xarray_dims_tuple_dataset_error.md
  - docs/error_notes/visualization/20251001_deltaT_equiv_sign_in_profile.md
  - scripts/compute_mld_fallback_stats.py
  - scripts/plot_mld_fallback_daily_maps.py
  - scripts/plot_inverse_fraction_year.py
  - scripts/plot_mld_profile_recomputed.py
---

## 1) 오늘의 핵심 결정(Policy)
- SHALLOW_LT10(수심<10 m): 계산은 유지하되, 지도·통계에는 마스크를 함께 표기(필요 시 후처리에서 제외).  
- DEEP_NO_CROSS(10 m≤z, 0 ≤ max Δσ₀ < 0.03): 포함. 혼합층 경계 부재로 간주해 bottom‑fallback(ENT=0, DIFFV=0).  
- INVERSE_GE10(10 m≤z, max Δσ₀ < 0): 핵심 트랙에서는 제외(NaN). 보조(SST) 트랙에서만 ILD/제품 대체를 ‘표시용’으로 고려.  

배경: inverse는 겨울철 급냉 직후 10 m가 가장 무거운 렌즈가 되는 상황에서 발생. σ₀ 기준으로는 ‘겉보기 역전’이 가능하며, 안정성은 in‑situ ρ 또는 N²로 판단해야 함(대부분 N²>0).

## 2) 코드·도구 변경
- 프로파일 플로터(scripts/plot_mld_profile_recomputed.py)  
  - TEOS‑10 ρ(SA,CT,p) 사용(CT 경로) 정합.  
  - ΔT_equiv 부호 교정: −Δσ₀/(ρ·α).  
  - depth-mode 추가(auto=1.2×MLD, fixed), in‑situ ρ 곡선 옵션(`--density insitu`), N² 하단 패널 추가.  

- 월간 경량 통계(scripts/compute_mld_fallback_stats.py)  
  - 분류·집계 추가: `deepnocross_days`, `inverse_days`(=INVERSE_GE10), `shallow_days`, `valid_days`, 각 fraction.  
  - NetCDF 메타: `inverse_definition = "max(Δσ0(z)-Δσ0(10m), z≥ref) < 0"` 기록.  

- 일별 지도(scripts/plot_mld_fallback_daily_maps.py)  
  - 4‑클래스 지도: 0=normal, 1=fallback(deep-no-cross), 2=shallow<10 m, 3=inverse_ge10.  
  - 육지 마스킹, 이산 컬러맵(BoundaryNorm)으로 colorbar‑데이터 일치, 고가시성 색상.

- 연간 12‑패널 지도(scripts/plot_inverse_fraction_year.py)  
  - 월별 `inverse_fraction`을 3×4 패널로 렌더, 단일 colorbar.

## 3) 지침·오답노트 업데이트
- 시각화 지침(02): 지도는 육지 마스킹, 쉐이딩은 colorbar 색과 실제 데이터가 일치하도록 `bounds/norm` 명시.  
- 코드 실행 지침(03): TEOS‑10 사용 규칙(ρ/α/σ₀) 추가.  
- 오류 노트:  
  - ΔT_equiv 부호 오류(수정 근거/공식).  
  - xarray Dataset dims 지정 오류((("lat","lon"), data) 필요).  
  - 얕은 수심 Shelf 모드 정책 초안, inverse 계절성 지도 요약.

## 4) 결과(1993 사례)
- 월별 진단 NetCDF: `/Volumes/HJPARK4/Decadal/source/ML_budget/output/diagnostics/mld_masks_1993MM.nc`  
- 12‑패널 inverse‑fraction 지도: `/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/inverse_fraction/1993_inverse_fraction_12panel.png`  
- 월별 평균(격자 합계/유효 대비, 대략):  
  - 1–2월 inverse ≈ 0.5–1.5%, deep‑no‑cross ≈ 13%, shallow ≈ 3%.  
  - 하절기 inverse ≈ 0.03–0.05%, deep‑no‑cross ≈ 0.4–0.5%.

## 5) 향후 계획
- 일별 산출에 마스크 3종(`SHALLOW_LT10`, `DEEP_NO_CROSS`, `INVERSE_GE10`)을 기록하고, 월평균 러너에 핵심/보조 트랙 옵션(`--mask-fallback`, `--shelf-mode`, `--inverse-policy`)을 추가.  
- 겨울철 inverse 이벤트에 대해 T/S 분해(δσ₀_T, δσ₀_S), QNET·ΔSST 합성, 전선 근접성 분석으로 물리적 원인 정량화.  
- 황해/동중국해 마스크 기반 영역 평균 inverse 시계열 작성.

## 6) 오늘의 변천 포인트(생각의 흐름)
1) 실행·저장 지침 재정비 → NetCDF CF time 충돌 해결, 원자 저장 확립.  
2) `--hmin` 완전 제거(0/결측 두께는 NaN).  
3) 프로파일 품질: TEOS‑10 일치, ΔT_equiv 부호 수정, auto‑depth 도입.  
4) MLD 정의의 한계 인지: shallow/inverse/deep‑no‑cross 분리 필요성 확인.  
5) 정책 수립: SHALLOW 포함(마스크 병기), DEEP_NO_CROSS 포함, INVERSE_GE10 제외(핵심).  
6) 통계·지도 도구 확장 → 계절성(겨울↑) 확인, 향후 냉각 인지형 보조 트랙(ILD/Carry) 검토.

