---
title: SODA 월 MLHB — 25°N 이남 U/V 결측(마스킹) 원인과 해결
date: 2025-10-13 11:40
category: data_io
tags: [soda, mlhb, uv, yu_xu, subsetting, masking, c-grid, thickness_weighted, nan_propagation, coastal]
related:
  - llm-ops/scripts/build_mlhb_monthly_from_soda.py
  - llm-ops/docs/reports/2025/2025-10-10_soda_mlhb_plan.md
---

## 상황 요약
- 현상: 25°N 이남에서 `ADV/ENT`가 넓게 NaN(결측)으로 떨어짐. `T_ML`은 정상이나 `U_ML/V_ML`이 NaN이라 연쇄적으로 `ADV/DIV_HU/w/ENT`가 NaN.
- 재현 기준: SODA3.4.2 월 파일(1993년) 기반 ECS 서브셋(19–45°N, 109–146°E), 월 MLHB 산출.

## 원인
1) 격자 서브셋 불일치
   - tracer 좌표(`yt_ocean/xt_ocean`)만 서브셋하고, 속도 좌표(`yu_ocean/xu_ocean`)는 서브셋하지 않아 경계 불일치 발생.
   - 결과: 경계 인근에서 U/V 평균과 마스크가 트레이서 격자와 맞지 않아 U/V가 NaN으로 증가.

2) U/V 혼합층 평균의 NaN 전파
   - 기존 구현: `cumsum(Uz*dz)` + 부분층 `UK*part`에서 한 레벨의 NaN이 전체 누적합을 오염(특히 `NaN*0` 함정 포함).
   - 결과: 얕은 `h`나 일부 레벨 결측이 있는 열에서 `U_ML/V_ML`이 쉽게 NaN.

3) 실제 데이터 결측(연안 C‑grid 특성)
   - 일부 열은 0→h 전 구간에서 U/V 자체가 존재하지 않음(연안/마스킹). 위 두 원인 제거 후에도 잔여 픽셀이 소수 남음.

## 진단·확인 절차
1) 단계별 마스크 출력(디버그)
   - 빌더 실행 시 `--emit-masks`로 월별 마스크 NetCDF 생성: `MASK_T_ML`, `MASK_U_ML`, `MASK_V_ML`, `MASK_ADV`, `MASK_DIV_HU`, `MASK_WE`, `MASK_ENT`, `MASK_H_RAW/FINAL` 등.
   - 1993‑01(25°N 이남) 기준:
     - 수정 전(격자 미서브셋/NaN‑비견고 평균): T 정상 중 U/V 결측 ≈ 685/795
     - 격자 서브셋/정렬 후: 25/795
     - 0→h 전 구간 U/V 결측 열 수: 25(위 잔여와 일치)

2) 가설 검증 루프(요지)
   - H1: 평균 NaN 전파 → NaN‑견고 평균 적용 → 일부 개선, 여전히 큼.
   - H2: yu/xu 미서브셋 → yu/xu 동시 서브셋·정렬 → 685→25로 대폭 감소.
   - H3: 연안 전구간 결측 → 정책적 폴백 필요(0 또는 최근접).

## 조치
- 격자 서브셋 정렬: `subset_to_region`에서 `yu_ocean/xu_ocean`도 `yt_ocean/xt_ocean` 범위에 맞춰 슬라이스하고, 크기 차이는 중앙 기준으로 트리머 정렬.
- U/V 평균 NaN‑견고화: 유효 레벨만 두께가중 가산(분모=유효두께 합), 부분층은 유효할 때만 기여.
- 폴백 옵션 추가: `--uv-fill-mode {none,nearest,zero}`
  - 연안 전구간 결측 열의 기본 대응을 선택 가능. 본 사례는 `zero`로 결측 25→0 해결.

## 예방(체크리스트)
- [ ] 트레이서(`yt/xt`) 서브셋과 속도(`yu/xu`) 서브셋을 항상 동시 적용·정렬.
- [ ] 혼합층 평균(U/V) 계산 시 NaN‑견고 두께가중 평균 사용(부분층 NaN×0 방지).
- [ ] 디버그 마스크(`--emit-masks`)로 남부 경계/연안에서 U/V 결측 분포를 사전 점검.
- [ ] 연안 전구간 결측 열에 대한 폴백 정책을 문서화(`uv-fill-mode=zero|nearest|none`).

## 참고
- 계획 문서: `llm-ops/docs/reports/2025/2025-10-10_soda_mlhb_plan.md`
- 구현 파일: `llm-ops/scripts/build_mlhb_monthly_from_soda.py`

