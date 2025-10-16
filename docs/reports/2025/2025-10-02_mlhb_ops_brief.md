---
title: MLHB 운영 브리프 — 1993-01 정책 확정 및 검증 요약
date: 2025-10-02
owner: MLHB-core
related:
  - llm-ops/src/process_d2nf_main.py
  - llm-ops/scripts/run_mlhb_monthly_main.py
  - llm-ops/docs/history/2025-10-02_mlhb_ops_summary.md
  - llm-ops/docs/guidelines/09_reporting_guidelines.md
  - llm-ops/docs/guidelines/03_code_execution.md
---

**요약(TL;DR)**
- 운영 고정: ADV=centered, TEN=forward. we‑mode 기본 deepening.
- Fallback(Deep‑no‑cross/Inverse≥10 m)은 전층=MLD로 포함하고 ENT=0·DIFFV=0. 얕은수심(<10 m)은 마스킹.
- upwind 스킴은 Kuroshio 영역(1993‑01)에서 노이즈/닫힘 지표 악화 → 비채택.
- 상관 지도는 0.5–1.0(0.05 간격, 11레벨) 이산·land=회색·RdBu_r로 보고.

**배경·목표**
- 월평균 이류항(ADV)에서 Kuroshio를 따라 체커보드/줄무늬 노이즈가 관찰됨. 안정적 운영 정책(스킴/시간앵커/마스킹)을 확정해 재현성과 해석 일관성을 확보한다.

**자료·방법(간결)**
- 데이터: GLORYS daily θ,S,u,v(1/12°; 20–45°N, 110–140°E 서브셋), ERA5 daily flux.
- 기간/영역: 1993‑01, Kuroshio 박스(28–36°N, 128–140°E) 중점.
- MLD: Δσ₀=0.03 @10 m 재계산; 교차 없음은 fully mixed 처리(전층=MLD).
- we‑mode: deepening(기본).
- 이류 스킴 비교: centered(기본) vs upwind(시험); flux는 범위 밖.
- 단위: 계산 K s⁻¹, 저장 K day⁻¹(×86400).

**핵심 결과(1993‑01, Kuroshio 박스)**
- ADV 체커보드 지표(월 평균): centered 0.0960 → upwind 0.1831(+90.6%).
- corr(TEN, TOTAL) (일평균 영역평균 시계열): 0.3475 → 0.3324(−0.0151).
- 닫힘 RMS(region×time): 0.2201 → 0.3926(+78.3%).
- 결론: upwind는 본 셋업에서 비채택, centered 유지가 합리적.

**정책 확정(운영)**
- 시간차분: TEN=forward(고정; `TEN_cen`은 진단으로 병기).
- 이류: centered(고정; upwind/flux 비채택).
- Fallback 포함: Deep‑no‑cross/Inverse(≥10 m)는 전층=MLD로 포함, ENT=0·DIFFV=0. SHALLOW_LT10는 마스킹.
- 보고용 상관 지도: 0.5–1.0, 0.05 간격 11레벨, BoundaryNorm, `RdBu_r`, land=lightgrey.

**대표 산출(예)**
- corr(TEN,TOTAL) 이산 지도(1993‑01):
  - `/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/corr/ten_total/corr_ten_total_199301_pos050_100_disc.png`

**재현(커맨드)**
- 메인라인 월평균(ADV=centered, TEN=forward 고정)
```
.venv/bin/python llm-ops/scripts/run_mlhb_monthly_main.py \
  --start 1993-01 --end 1993-01 \
  --indir /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
  --fluxdir /Volumes/HJPARK4/MHW/data/ERA5/daily_EA \
  --out /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly_main_199301.nc \
  --temp-root /Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily \
  --python .venv/bin/python --workers 6 \
  --ah 100 --kv 1e-4 --we-mode deepening --mld-source recompute \
  --mld-threshold 0.03 --mld-ref-depth 10.0 --keep-daily
```
- 상관 지도(0.5–1.0, 11레벨)
```
.venv/bin/python llm-ops/scripts/compute_corr_ten_total.py \
  --daily /Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily/1993/01/ml_budget_1993.nc \
  --start 1993-01-02 --end 1993-01-31 \
  --out-nc  /Volumes/HJPARK4/Decadal/source/ML_budget/output/diagnostics/corr_ten_total_199301.nc \
  --out-png /Volumes/HJPARK4/Decadal/source/ML_budget/Figure/corr/ten_total/corr_ten_total_199301_pos050_100_disc.png \
  --vmin 0.5 --vmax 1.0 --cmap RdBu_r
```

**토의·한계**
- centered에서도 전선 부근 체커보드 잔여 가능. 보고/통계에서 셸프·연안 1–2셀·QNET 지배율(>0.7) 조합 마스킹 권장(물리 계산은 유지).
- forward는 RHS@t와 시간 정합이 좋아 본 셋업에 적합. centered 시간차분은 결측/MLD 토글 영향으로 불안정 가능.

**참고 문헌(내부 RefID·로컬 경로)**
- we/ENT 정의·방법: `references/MLHB/Price_Weller_Pinkel_1986_JGR_DiurnalCycling.pdf`, `references/MLHB/Dong_Gille_Sprintall_2007_JCLI_SouthernOcean_MLHB.pdf`, `references/MLHB/Foltz_Schmid_Lumpkin_2013_JCLI_NETA_MLHB.pdf`
- 수직 혼합/경계층: `references/MLHB/Large_McWilliams_Doney_1994_KPP_review.pdf`, `references/MLHB/Hummels_etal_2014_ClimDyn_AtlanticColdTongue_MLHB.pdf`
- 유효 확산(참고/진단): `docs/reports/references/mlhb_effective_diffusion_refs.md`(분류 템플릿)

