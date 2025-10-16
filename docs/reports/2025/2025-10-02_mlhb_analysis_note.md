---
title: MLHB 분석 노트 — 1993-01 운영 재정비 요약
date: 2025-10-02
owner: MLHB-core
related:
  - docs/history/2025-10-02_mlhb_ops_summary.md
  - docs/guidelines/09_reporting_guidelines.md
  - llm-ops/src/process_d2nf.py
  - llm-ops/scripts/run_mlhb_monthly.py
  - llm-ops/scripts/aggregate_monthly_with_flags.py
  - llm-ops/scripts/plot_mlhb_terms_daily_policy_compare.py
  - llm-ops/scripts/plot_mlhb_terms_monthly_policy_compare.py
  - llm-ops/scripts/compute_corr_ten_total.py
---

## 요약(TL;DR)
- 정책(초안): SHALLOW_LT10 마스킹, Deep-no-cross/Inverse≥10 m 포함(전층=MLD), ENT=0/DIFFV=0, TEN 앵커=forward.
- I 포함(I=1)이 I 제외(I=0) 대비 닫힘(C) 품질을 소폭 개선(전역/ECS RMS·IQR ↓).
- 일/월 패널, I 토글 8조합 월평균, 상관·R² 지도 등 도구 정비 및 지침(land=회색, 이산 레벨≤21) 반영 완료.

## 배경·목표
- 혼합층 열수지(MLHB) 운영 재정비: Δσ0@10 m 기준 미도달 컬럼 처리, 얕은 수심 셸프 제외, 시간 정합(TEN) 개선, 해안 인접 QNET/h 과대 대응.

## 자료·방법
- 데이터: GLORYS daily(T/S/U/V), ERA5 daily flux.
- 기간/영역: 1993-01(전역, ECS/쿠로시오 확대 사례 포함).
- 정책/전처리:
  - SHALLOW_LT10 제외(마스킹).
  - Deep-no-cross/Inverse≥10 m 포함: 전층=MLD로 취급, ENT=0/DIFFV=0.
  - TEN 앵커 forward(앞차분).
  - Δσ0=0.03(@10 m)로 MLD 재계산, fully_mixed/no-cross 마스크 기록.

## 도구·변경
- process_d2nf.py: `--ten-anchor` 도입; 마스크 4종 저장; fully_mixed에서 ENT/DIFFV=0 클램핑.
- run_mlhb_monthly.py: `--keep-daily`, `--ten-anchor` 전달.
- aggregate_monthly_with_flags.py: S/D/I on/off 8조합 집계.
- plotters: 일/월 항목·정책 비교 플로터(wide/tall 레이아웃, land=회색, MIX=ENT+DIFF+DIFFV 지원, 얕은수심 마스킹 옵션).
- compute_corr_ten_total.py: corr(TEN,TOTAL)·R²[%] 지도(vmin/vmax/colormap 지정, land=회색).

## 핵심 결과(1993-01)
- I 토글(월평균 C 닫힘; S=1, D=1 고정)
  - 전역: I=0 RMS=0.10965, IQR=0.05927 → I=1 RMS=0.10899, IQR=0.05863.
  - ECS(23–34N, 118–130E): I=0 RMS=0.13959, IQR=0.05546 → I=1 RMS=0.13721, IQR=0.05272.
- 일별(1/02, 1/27) ECS/쿠로시오 확대: I=1에서 패턴 정합·노이즈 개선 관찰.
- 상관·R² 지도(1/02–31): corr 0.5–1.0(이산 11레벨), R²[%]=corr²×100(이산 11레벨) 저장.

## 대표 그림
- 월 I 비교(가로): `/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/mlhb_terms_monthly/mlhb_terms_monthly_compare_199301_S1D1_Iwide.png`
- 일 I 비교(ECS, 1/27, shallow mask): `/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/mlhb_terms_daily_regions/mlhb_terms_compare_I_ECS_19930127_wide_shallowMasked.png`
- corr 0.5–1.0(이산 11레벨): `/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/corr/ten_total/corr_ten_total_199301_pos050_100_disc.png`
- R²[%] 0–100(이산 11레벨): `/Volumes/HJPARK4/Decadal/source/ML_budget/Figure/corr/ten_total/r2_ten_total_199301_percent.png`

## 표(요약 수치)
- C(닫힘) 품질(1993‑01)

| 영역 | RMS(I=0) | RMS(I=1) | IQR(I=0) | IQR(I=1) |
|---|---:|---:|---:|---:|
| 전역 | 0.10965 | 0.10899 | 0.05927 | 0.05863 |
| ECS | 0.13959 | 0.13721 | 0.05546 | 0.05272 |

## 정책·결정(콜아웃)
- SHALLOW_LT10: 마스킹(제외).
- Deep‑no‑cross/Inverse≥10 m: 전층=MLD 포함, ENT=0/DIFFV=0.
- TEN 앵커: forward 기본.
- 지도: land=회색, 이산 레벨 ≤21.

## 재현(발췌 커맨드)
- 월 실행(forward+daily 보존)
```
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
- 8조합 월평균 + 두 조합 비교 패널
```
.venv/bin/python llm-ops/scripts/aggregate_monthly_with_flags.py \
  --daily /.../tmp_daily/1993/01/ml_budget_1993.nc \
  --out-root /.../output/monthly/mlhb_monthly_forward_199301_flags
.venv/bin/python llm-ops/scripts/plot_mlhb_terms_monthly_policy_compare.py \
  --file0 /.../mlhb_monthly_forward_199301_flags_S1D1I0.nc \
  --file1 /.../mlhb_monthly_forward_199301_flags_S1D1I1.nc \
  --out   /.../Figure/mlhb_terms_monthly/mlhb_terms_monthly_compare_199301_S1D1_Iwide.png \
  --vars TEN,TOTAL,QNET,ADV,MIX,CLOS_d2_ten --layout wide
```
- 일별 I 토글(ECS, shallow mask)
```
.venv/bin/python llm-ops/scripts/plot_mlhb_terms_daily_policy_compare.py \
  --file /.../tmp_daily/1993/01/ml_budget_1993.nc --date 1993-01-27 \
  --out  /.../Figure/mlhb_terms_daily_regions/mlhb_terms_compare_I_ECS_19930127_wide_shallowMasked.png \
  --vars TEN,TOTAL,QNET,ADV,ENT,DIFF,DIFFV --layout wide \
  --lat-min 23 --lat-max 34 --lon-min 118 --lon-max 130 --mask-shallow
```
- 상관·R² 지도(1/02–31)
```
.venv/bin/python llm-ops/scripts/compute_corr_ten_total.py \
  --daily /.../tmp_daily/1993/01/ml_budget_1993.nc \
  --start 1993-01-02 --end 1993-01-31 \
  --out-nc  /.../output/diagnostics/corr_ten_total_199301.nc \
  --out-png /.../Figure/corr/ten_total/corr_ten_total_199301_pos050_100_disc.png \
  --vmin 0.5 --vmax 1.0 --cmap RdBu_r
```

## 토의·한계
- 해안 인접 QNET/h 과대 구간: 셸프(<50–100 m)·해안 근접(1–2셀)·항 지배율(>0.7) 조합 마스킹을 보고/진단에 적용 권장(물리 계산은 유지).
- ADV 이산화 민감도(cent→upwind/flux) 비교 계획.
- Inverse 표시 트랙(ILD/제품 MLD 대체)은 별도 연구 범위(핵심 트랙에는 미포함).

## 결론·권고
- 운영 기본값 승인 제안: SHALLOW 마스킹, Deep‑no‑cross/Inverse 전층=MLD 포함(ENT=0/DIFFV=0), TEN=forward, land=회색, 레벨≤21.
- I=1을 기본 트랙으로 채택(닫힘 품질·정합성 우세), I=0은 보조 비교 산출.

## 다음 단계
- 1993‑01→04 확대: I=0/1 및 마스킹 유무별 C·R²·유효격자 비율 비교표/지도.
- 러너 기본값 반영 및 문서화(코드/가이드 업데이트).
- 보고 템플릿 도입: 월별 브리프 자동화(그림+표+결론 한 장).

