---
title: MLHB 운영·정책·도구 요약 — 2025-10-02
date: 2025-10-02
owner: MLHB-core
related:
  - docs/journal/2025/2025-10-02.md
  - docs/history/2025-10-01_mlhb_ops_progress.md
  - docs/guidelines/02_plot_guidelines.md
  - docs/guidelines/03_code_execution.md
  - llm-ops/src/process_d2nf.py
  - llm-ops/scripts/run_mlhb_monthly.py
  - llm-ops/scripts/aggregate_monthly_with_flags.py
  - llm-ops/scripts/plot_mlhb_terms_daily.py
  - llm-ops/scripts/plot_mlhb_terms_daily_policy_compare.py
  - llm-ops/scripts/plot_mlhb_terms_monthly.py
  - llm-ops/scripts/plot_mlhb_terms_monthly_policy_compare.py
  - llm-ops/scripts/compute_corr_ten_total.py
---

## 1) 정책 결정(요지)
- 얕은 수심(SHALLOW_LT10): 진단·시각화·집계에서 마스킹(제외)한다.
- 깊은 미교차(Deep-no-cross)·역전(Inverse≥10 m): 전층을 혼합층(MLD)으로 취급해 포함한다.
  - 이때 ENT=0, DIFFV=0으로 둔다(계면 부재·경계 항 무의미). QNET/ADV/DIFF는 그대로 사용.
- TEN 앵커: forward(앞차분)를 기본으로 사용한다.
- land/무효 마스킹: 지도형 시각화에서 land는 회색으로 표시한다(set_bad('lightgrey')).
- 등치선/레벨: 변수별 최적화하되 레벨 개수는 21개를 넘지 않는다.
- 해안 인접(QNET/h 과대) 구간: 필요 시 셸프/해안 근접/항 지배율 기준을 조합한 마스크로 제외(진단·시각화용).

## 2) 코드·도구 변경
- process_d2nf.py
  - TEN 앵커 옵션 도입: `--ten-anchor {backward,forward,centered}`(기본 backward; 운영은 forward로 설정).
  - 일별 마스크 기록: `MASK_FULLY_MIXED`, `MASK_SHALLOW_LT10`, `MASK_DEEP_NO_CROSS`, `MASK_INVERSE_GE10`.
- run_mlhb_monthly.py
  - `--keep-daily`로 일별 산출 보존, `--ten-anchor` 전달.
- 플로터/집계 스크립트
  - 일/월 패널(항목): land=회색 반영, MIX(ENT+DIFF+DIFFV) 파생 지원.
  - I-토글 비교: `plot_mlhb_terms_daily_policy_compare.py`(가로/세로 레이아웃, `--mask-shallow`), 월 비교 플로터 추가.
  - 8조합 월평균 집계: `aggregate_monthly_with_flags.py`(S/D/I on/off 조합).
  - 상관/설명력 지도: `compute_corr_ten_total.py`(TEN vs TOTAL 상관, R²[%] 파생 가능; land=회색, vmin/vmax/Greys 지원).

## 3) 검증 결과(1993-01 사례)
- 일별/영역 확대: 1/02, 1/27 동중국해(ECS), 일본 남쪽, 동한만 및 쿠로시오 3구간 패널 생성.
- I 토글(전역·ECS): I=1(포함)에서 C(닫힘) RMS/IQR이 소폭 개선(시간 정합·유효 샘플 증가).
- 상관·R² 지도(1/02–31): TEN vs TOTAL 상관 지도(0.5–1.0 범위, 이산 11레벨), R²[%] 지도 저장.

## 4) 재현 경로(핵심 커맨드)
- 1993-01 forward TEN + 일별 보존
  ```bash
  .venv/bin/python llm-ops/scripts/run_mlhb_monthly.py \
    --start 1993-01 --end 1993-01 \
    --indir /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
    --fluxdir /Volumes/HJPARK4/MHW/data/ERA5/daily_EA \
    --out /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly_recompute_199301.nc \
    --temp-root /Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily \
    --python .venv/bin/python --workers 6 \
    --ah 100 --kv 1e-4 --mld-source recompute \
    --mld-threshold 0.03 --mld-ref-depth 10.0 \
    --ten-anchor forward --keep-daily
  ```
- 8조합 월평균 및 패널(I 토글 예)
  ```bash
  .venv/bin/python llm-ops/scripts/aggregate_monthly_with_flags.py \
    --daily /.../tmp_daily/1993/01/ml_budget_1993.nc \
    --out-root /.../output/monthly/mlhb_monthly_forward_199301_flags
  .venv/bin/python llm-ops/scripts/plot_mlhb_terms_monthly_policy_compare.py \
    --file0 /.../mlhb_monthly_forward_199301_flags_S1D1I0.nc \
    --file1 /.../mlhb_monthly_forward_199301_flags_S1D1I1.nc \
    --out   /.../Figure/mlhb_terms_monthly/mlhb_terms_monthly_compare_199301_S1D1_Iwide.png \
    --vars TEN,TOTAL,QNET,ADV,MIX,CLOS_d2_ten --layout wide
  ```
- 일별 I-토글(얕은수심 마스킹·ECS 예)
  ```bash
  .venv/bin/python llm-ops/scripts/plot_mlhb_terms_daily_policy_compare.py \
    --file /.../tmp_daily/1993/01/ml_budget_1993.nc --date 1993-01-27 \
    --out  /.../Figure/mlhb_terms_daily_regions/mlhb_terms_compare_I_ECS_19930127_wide_shallowMasked.png \
    --vars TEN,TOTAL,QNET,ADV,ENT,DIFF,DIFFV --layout wide \
    --lat-min 23 --lat-max 34 --lon-min 118 --lon-max 130 --mask-shallow
  ```
- 상관·R² 지도(1/02–31)
  ```bash
  .venv/bin/python llm-ops/scripts/compute_corr_ten_total.py \
    --daily /.../tmp_daily/1993/01/ml_budget_1993.nc \
    --start 1993-01-02 --end 1993-01-31 \
    --out-nc  /.../output/diagnostics/corr_ten_total_199301.nc \
    --out-png /.../Figure/corr/ten_total/corr_ten_total_199301_pos050_100_disc.png \
    --vmin 0.5 --vmax 1.0 --cmap RdBu_r
  # R^2[%]
  # r2 = corr^2 * 100 을 별도 PNG로 저장(11레벨)
  ```

## 5) 운영 메모
- 얕은 수심(SHALLOW_LT10) 제외, 나머지 두 경우(Deep-no-cross, Inverse≥10 m) 포함 정책은 `T0`(SST)와 `T_ML`(전층=MLD) 병기 분석으로 보완한다.
  - 필요 시 월평균 파일에 `delta_T0_TML = T0 - T_ML` 파생 추가 검토.
- 해안 인접 QNET 지배 구간은 셸프(예: <50–100 m)·해안 근접(1–2셀)·항 지배율(>0.7) 조합 마스킹을 시각화/통계에 적용(물리 계산은 유지).

## 6) 다음 단계
- 1993-01–04 범위로 확대: I 토글·마스킹 유무에 따른 C(닫힘), R², 유효 격자 비율 비교.
- 러너 기본값 정식화: forward TEN, land=회색, 얕은 수심 마스크 옵션 노출.
- 보고용 템플릿: 월/일 패널, 상관·R², 정책 요약을 한 장으로 묶는 리포트 스크립트(선택).

## 7) 추가 결정/정리 — 2025-10-02
- 이류 스킴(upwind 시험 결과)
  - 데이터/설정: daily `ml_budget_1993.nc`(1993‑01), Kuroshio 박스(28–36°N, 128–140°E).
  - 비교 지표(월 1993‑01): checker_rms(월 ADV) 0.0960→0.1831(+90.6%), corr(TEN,TOTAL) 0.3475→0.3324(−0.0151), 닫힘 RMS 0.2201→0.3926(+78.3%).
  - 결론: upwind는 본 트랙에서 비채택. centered 유지. (향후 필요 시 face‑기반 상풍+제한자(TVD) 조합 재검토)

- 상관 지도 이산 레벨(보고 설정)
  - 범위 0.5–1.0, 0.05 간격 총 11레벨(≤21 원칙 충족), `BoundaryNorm` 이산화, land=lightgrey, `RdBu_r`, `shading="nearest"`.
  - 산출: `/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/corr/ten_total/corr_ten_total_199301_pos050_100_disc.png`.

- 전층=MLD 포함 정책에서의 ENT/DIFFV 처리(재확인)
  - 얕은 수심(SHALLOW_LT10): 보고/통계에서 마스킹(제외).
  - Deep‑no‑cross·Inverse(≥10 m): 전층=MLD로 포함. 계면 부재로 ENT=0, DIFFV=0(코드 클램프 일치). QNET/ADV/DIFF는 그대로 사용.
  - 해석 보조: T0(SST) vs T_ML을 병기. 필요 시 `delta_T0_TML = T0 - T_ML` 파생(월평균)에 추가 검토.

- 연안/셸프 마스킹(보고용)
  - 해안 인접 QNET/h 과대 구간에 대해 depth(<50–100 m) + coast 1–2셀 + QNET 지배율(>0.7) 조합 마스크를 시각화·통계에서 사용(물리 계산은 유지).

### Decision Register(발췌)
- 2025‑10‑02 — Advection: upwind 비채택(centred 유지). 근거: checker_rms↑, corr↓, C_RMS↑.
- 2025‑10‑02 — Correlation map: 0.5–1.0, 11레벨, land=회색, RdBu_r.
- 2025‑10‑02 — Fallback 포함 정책: Deep‑no‑cross/Inverse는 전층=MLD 포함, ENT=0, DIFFV=0.

## 8) 메인라인 파이프라인(운영용)
- 코드: `src/process_d2nf_main.py` (고정값: ADV=centered, TEN=forward)
- 러너: `scripts/run_mlhb_monthly_main.py` (레거시 러너는 비교·실험 전용)
- 메타 기록: 산출 NetCDF 전역 속성에 `adv_scheme='centered'`, `ten_anchor='forward'` 병기됨.
- 보고 지침 연계: 상관 지도는 0.5–1.0, 11레벨 이산(02 지침 B‑1).
