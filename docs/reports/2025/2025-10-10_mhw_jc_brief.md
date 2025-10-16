---
title: JCLI MHW(WNP) — Interannual Drivers Brief and Review Summary
date: 2025-10-10
owner: HJPARK
related:
  - ~/Desktop/논문/MHW_JC
  - /Volumes/HJPARK4/Decadal/Figure/elt_composite
  - llm-ops/scripts/source_panel_mlhb_seasonal.py
  - llm-ops/scripts/source_panel_mlhb_composite.py
---

**TL;DR**
- 주제: 서북태평양(WNP) 및 주변해(Marginal Seas)의 해양열파(MHW) 연변동(1982–2022)과 대규모 기후 구동.
- 핵심: 약 절반의 연변동 피크는 엘니뇨→라니냐 전이 해에 발생. ONDJ(성숙기)에는 하향 난류열속(Qnet) 주도, MJJAS(전이/발달기)에는 해양 내부항(저층 열저장·혼합) 기여가 커짐.
- 메커니즘: PSAC/KAC에 따른 남풍·하향열속 강화(ONDJ) → MHW 지속; WNPSH 서진+Rossby wave로 상층열저장↑, 겨울 MLD 심화 시 표층으로 열 출현(ECS 기여) (MJJAS).
- 비전이 피크: 여름(JAS) CGT 내 반시계 고기압이 대류 억제→단파복사 증가→MHW.
- 현재 상태: 투고 후 Major Revision 요구. 스무딩·계절 합성 패널(ONDJ/MJJAS) 보완 산출 완료; 편집자/리뷰어 코멘트 반영 준비.

**배경·목표**
- 목표: 장기온난화와 분리된 연변동(≲6년) MHW 신호의 구동원을 규명하고, ENSO 전이/비전이 해를 구분해 메커니즘을 통합 서술.
- 가설: (1) ONDJ=heat‑flux–driven, (2) MJJAS=ocean‑driven(저층 열저장·혼합), (3) 비전이=CGT 기반 복사 구동.

**자료·방법(요약)**
- SST: 위성 기반(41년), 대기/해양 재분석장.
- MHW 정의: Hobday et al.(2016) 방식 준용(임계 기반; 세부는 원고 참조).
- 분석: 스펙트럼으로 연변동 분리, 합성(전이/비전이·월/계절), 상호상관·회귀, 역학 지표(PSAC/KAC/WNPSH, Rossby wave 신호 등).

**핵심 결과**
- 전이 해(El Niño→La Niña):
  - ONDJ: 남풍 강화(PSAC/KAC)로 하향 난류열속(Qnet)↑ → WNP 전역 연중 MHW 지속의 시발.
  - MJJAS: WNPSH 서진·Rossby wave로 상층 열저장↑ → 계절적 MLD 심화 시 표층으로 열 출현, ECS MHW 기여.
- 비전이 피크 해: JAS에 CGT 내 반시계 고기압이 대류 억제→SW↓↑ → WNP 및 주변해 여름 MHW 유도.

**도표·그림 상태(내부)**
- 월/계절 합성 패널(ADV 9‑point smoothing=2, K month⁻¹): `/Volumes/HJPARK4/Decadal/Figure/elt_composite/elt_comp_terms_{01..12,prev11,prev12,ONDJ,MJJAS}.png`, `elt_comp_TML_*.png`.
- 의도: heat‑flux– vs ocean‑driven 위상 대비(ONDJ vs MJJAS), 월별 변동의 대잡음 완화.

**편집자/리뷰 요약(핵심)**
- 처리 편집자(핸들링) — 용어·라벨·정의 보완 요청: ONDJ/MJJAS/JAS 정의 추가, “significance→confidence”, Figure 4·5 캡션 구체화, MLD 정의 명시, Eq.(2) p·Eq.(3) σ,f0 정의, g′ 값(Qiu 2002: 0.03 cm s⁻²) 확인, sensible flux에는 2 m q 사용 권고 등.
- 리뷰 총평: 참신성(novelty) 우려(특히 R#3), 추가 분석 권고(R#2·R#3), 해석 명료화(R#1), 영역 선택 근거(WNP 집중) 보강.

**대응 계획(초안)**
- 표기·정의·캡션 정비: 용어 정의, confidence 용어 통일, 수식 변수 정의, 데이터 레벨(2 m q) 검토.
- 메커니즘 보강: ONDJ(heat‑flux), MJJAS(ocean‑driven) 비교 정량(기여율·상관 지도), 영역별(ECS/KE) 표 추가.
- 참신성: ENSO 전이 해의 “연중 지속”과 CGT‑여름 MHW 연결을 단일 프레임으로 통합·정량; 기존 연구 대비 차별점 표로 제시.
- 부록/재현: 합성 창·영역·지표 정의와 파일 경로, 스크립트 커맨드 명시.

**재현 메모(내부 산출 커맨드)**
- 월/계절 합성 패널 생성:
  - `.venv/bin/python llm-ops/scripts/source_panel_mlhb_composite.py --monthly-root /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly --years 1998,2010,2016,2020 --out-root /Volumes/HJPARK4/Decadal/Figure/elt_composite --months 1-12,prev11,prev12 --unit month --adv-smooth-iter 2`
  - `.venv/bin/python llm-ops/scripts/source_panel_mlhb_seasonal.py  --monthly-root /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly --years 1998,2010,2016,2020 --out-root /Volumes/HJPARK4/Decadal/Figure/elt_composite --seasons ONDJ,MJJAS --unit month --adv-smooth-iter 2`

**다음 단계(액션)**
- 기여율/상관 정량표 추가(ONDJ vs MJJAS; WNP/ECS/KE 박스).
- 리뷰 목록(Point‑by‑Point) 문서화 및 반영 라인 번호/그림 참조 표기.
- DIFFV residual 모드 비교·민감도(ADV smoothing 1/2/3) 부록화.

