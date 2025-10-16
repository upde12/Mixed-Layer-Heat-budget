---
title: SODA 3‑month grid — prevOND not rendered (missing previous‑year months)
date: 2025-10-13 15:50
category: data_io
tags: [soda, mlhb, prevOND, composite, missing-months, elt, visualization]
related:
  - llm-ops/scripts/source_panel_mlhb_composite.py
  - llm-ops/scripts/build_mlhb_monthly_from_soda.py
  - llm-ops/docs/reports/references/elt_years.md
---

## 증상
- 3개월 집계 그리드(`grid-tml-aggregate=3mo-prev10`)에서 일부 행(ELT 해)의 `prevOND` 셀이 비어 있거나 패널이 렌더되지 않음.
- 예: 1983 행의 `prevOND`(=1982‑10/11/12) 미표시.

## 원인
1) 창 정의상 `prevOND = (이전 해 10–12월)`, `OND = (해당 해 10–12월)`이다. 참조: `llm-ops/scripts/source_panel_mlhb_composite.py:317`.
2) `prevOND`를 그리려면 “이전 해”의 월 산출(10, 11, 12)이 반드시 존재해야 한다.
3) SODA 기반 MLHB 월 산출 디렉터리에 이전 해 파일이 없는 경우, 해당 셀은 비게 된다.

영향 받은 사례(ELT years 기본 집합)
- 1983 → 1982(10–12) 필요
- 1988 → 1987(10–12) 필요
- 1998 → 1997(10–12) 필요
- 2010 → 2009(10–12) 필요
- 2016 → 2015(10–12) 필요
- 2020 → 2019(10–12) 필요

## 진단 절차(빠른 체크)
1) 이전 해 월 파일 존재 확인(예: 1982/1987/…):
   - 경로: `/Volumes/HJPARK4/Decadal/source/ML_budget_SODA/output/monthly`
   - 필요한 파일: `mlhb_monthly_soda_<YYYY>10.nc`, `...11.nc`, `...12.nc`
2) 원시 SODA 연도 파일 존재 확인(부재 시 월 산출 불가):
   - 경로: `/Volumes/HJPARK4/soda/soda3.4.2_mn_ocean_reg_<YYYY>.nc`

## 해결
이전 해 월 산출을 생성한 뒤 그리드를 재렌더링한다.

예시(이전 해 일괄 생성; ECS 범위, 정책 동일)
```bash
. .venv/bin/activate
for Y in 1982 1987 1997 2009 2015 2019; do
  .venv/bin/python llm-ops/scripts/build_mlhb_monthly_from_soda.py \
    --soda-root /Volumes/HJPARK4/soda \
    --years $Y \
    --region 19,45,109,146 \
    --out-root /Volumes/HJPARK4/Decadal/source/ML_budget_SODA/output/monthly \
    --ah 100 --kv 1e-4 --mld-source mlp --uv-fill-mode zero
done
```

그리드 재렌더링(예)
```bash
.venv/bin/python llm-ops/scripts/source_panel_mlhb_composite.py \
  --monthly-root /Volumes/HJPARK4/Decadal/source/ML_budget_SODA/output/monthly \
  --grid-tml-years 1983,1988,1998,2010,2016,2020 \
  --grid-tml-rows years \
  --grid-tml-aggregate 3mo-prev10 \
  --overlay-source soda-net --soda-root /Volumes/HJPARK4/soda \
  --rhs-prc 90 --unit month --adv-smooth-iter 2 \
  --out-root /Volumes/HJPARK4/Decadal/Figure/elt_TML_6x5_grid_3mo_sodanetheating_p90_SODA
```

## 예방
- 3개월 집계 이전에 “이전 해 10–12월” 파일 존재 여부를 사전 점검한다(ELT 해 리스트 L에 대해 L‑1의 10–12월 확인).
- 렌더 출력 폴더는 데이터 소스별로 분리한다(예: GLORYS vs SODA). 기존 결과 보존을 위해 새 디렉터리에 저장 후 비교한다.
- 플롯 지침(02) 준수: 그림 저장 시 생성 스크립트 사본을 같은 폴더(또는 하위 `scripts/`)에 보관해 재현성을 확보한다. 참조: `llm-ops/docs/guidelines/02_plot_guidelines.md:11`.

## 참고
- 창 정의 및 구현: `llm-ops/scripts/source_panel_mlhb_composite.py:317`
- SODA 월 산출 빌더: `llm-ops/scripts/build_mlhb_monthly_from_soda.py:1`
- ELT 연도 기준: `llm-ops/docs/reports/references/elt_years.md:1`

