# 2025-10-13 — Context Overflow Recovery (Afternoon)

- Anchor: 11:30 직후까지 RAW 기록 정상. 13:49 임시 메모에 복구 착수 로그만 존재, 상세 동작 미기록.
- Unsaved tail: 오후 작업(렌더·빌드·문서화)이 대화로만 진행되어 RAW에 누락.

## Actions Reconstructed
- 14:40 시범 렌더: SODA T_ML 그리드(월×연), overlay=soda-net, p98 → `elt_TML_grid_rows-months.png`
- 14:50 3개월 집계 렌더(p90): 행=ELT years, 열=prevOND/JFM/AMJ/JAS/OND → `elt_TML_grid_rows-years.png`; 스크립트 사본 보관
- 14:58 1982 월 산출 생성(10–12 포함) → 1983 prevOND 표시
- 15:20 이전 해 월 산출 생성(1987/1997/2009/2015/2019) → 모든 ELT prevOND 표시
- 15:43 최종 렌더 확인(행=연도, p90, overlay=soda-net)
- 15:50 문서·코드 보강: 오답노트(prevOND 미표시) 추가, 02 지침에 “스크립트 사본 보관” 규칙, ELT years 문서, 합성 스크립트 오버레이 옵션화

## Artifacts
- Figures: `/Volumes/HJPARK4/Decadal/Figure/elt_composite_SODA/elt_TML_grid_rows-months.png`
- Figures: `/Volumes/HJPARK4/Decadal/Figure/elt_TML_6x5_grid_3mo_sodanetheating_p90_SODA/elt_TML_grid_rows-years.png`
- Script copy: same folder `scripts/source_panel_mlhb_composite__YYYYMMDD-HHMM.py`
- Monthly outputs (SODA): `/Volumes/HJPARK4/Decadal/source/ML_budget_SODA/output/monthly/mlhb_monthly_soda_*.nc` (1982, 1987, 1997, 2009, 2015, 2019 추가)
- Docs updated:
  - `docs/error_notes/data_io/20251013_soda_prevOND_missing.md`
  - `docs/guidelines/02_plot_guidelines.md` (체크리스트 11항)
  - `docs/reports/references/elt_years.md`
  - `llm-ops/scripts/source_panel_mlhb_composite.py` (overlay 색/두께/투명도/레벨 옵션)

## Rationale / Root Cause
- prevOND는 “이전 해 10–12월” 필요 → 해당 월 산출 부재 시 셀 비표시.
- overlay=soda-net 경로는 월 기후 매핑 비용이 큼(캐시 부재).

## Preventive Steps
- 렌더 전 ELT‑1의 10–12월 존재 사전 점검; 누락 시 일괄 생성.
- SODA `net_heating` 월 기후 타깃 격자 캐시(NetCDF) 도입 검토.
- 그림 폴더에 스크립트 사본·매니페스트(입력 목록) 보관.

## Status
- RAW transcript updated with reconstructed afternoon steps.
- Daily journal and temp notes updated with time‑stamped entries.

