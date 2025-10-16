---
title: MHW/SST 월 스택 – 마지막 해(last-year) 추정 불일치(2021 vs 2022)
date: 2025-10-10 17:30
category: data_io
tags: [time_axis, monthly, ecs, mhw, sst, last_year, ctl, seasonal_alignment]
related:
  - llm-ops/scripts/plot_mhw_days_monthly_composite.py
  - llm-ops/scripts/plot_mhw_days_seasonal_composite.py
  - llm-ops/scripts/compare_mhw_days_ondj_vs_ond.py
  - llm-ops/scripts/plot_sst_monthly_composite.py
---

## 상황 요약
- ELT 시즌 합성에서 ONDJ(Oct(prev)–Jan(curr)) 결과가 durn_93의 OND(Oct–Dec)과 매우 유사하게 나타남.
- 원인 조사 결과, MHW/SST 월 스택의 마지막 해를 2021로 **하드코딩 가정**하여 연도축 매핑이 어긋남(실제는 2022까지 존재).
- 그 결과 ONDJ/OND 비교·해석이 체계적으로 틀어질 수 있음(특히 prev/curr 경계 포함 계절에서).

## 원인
- 스크립트가 월 스택의 연도축을 `last_year=2021`로 가정하여 `start_year = last_year - (years_count - 1)`로 역산.
- 로컬 자원(`dur_mon_ECS.data`, `ssts_mon.data` 등)은 2022까지 포함됨. CTL 또는 파일 길이로 확인 가능.

## 재현·확인 절차
1) 월 스택 길이 확인(101×145, float32 가정):
```bash
# months = (filesize / 4) / (101*145); years = months / 12
python - <<'PY'
import os
p = "/Volumes/HJPARK4/MHW/source/detect/dur_mon_ECS.data"
sz = os.path.getsize(p)
per = 101*145
months = (sz//4)//per
years = months/12
print("bytes=", sz, "months=", months, "years=", years)
PY
```
2) CTL 존재 시 TDEF 확인(연 단위 정의가 있을 수 있음): `TDEF <Nyears> LINEAR 01Jan<Y0> 1yr` → `last_year = Y0 + Nyears - 1`.
3) 정렬 점검: ONDJ와 ONDJ_NEXT 차맵 생성(정상 시 Jan 기여가 반영되어 차이가 0이 아님).

## 영향 범위
- MHW Days/SST 합성 스크립트로 생성한 ONDJ/OND 패널 및 비교 그림.
- anomaly/absolute 모드 모두 영향. 색상 스케일 고정 여부와 무관하게 연도축 불일치가 1년 오프셋을 유발.

## 조치
- 스크립트에 `--last-year` 옵션을 추가(기본 2021, 필요 시 2022로 지정)하거나, CTL 파싱으로 자동 추정.
- 비교/검증: ONDJ vs OND(공통 스케일), ONDJ vs ONDJ_NEXT(차맵) 재생성.
- 캡션/노트에 `last_year=...; clim=...`을 명시해 재현성 확보.

## 예방(체크리스트)
- [ ] 실행 전 월 스택 길이로 `months/years` 계산해 로그에 기록.
- [ ] CTL(TDEF)과 파일 길이가 **일치하는지** 교차 확인.
- [ ] `--last-year`를 명시하거나, CTL 파싱으로 자동 설정(없으면 오류로 중단).
- [ ] ONDJ/ONDJ_NEXT 차맵으로 시즌 경계 정렬을 사전 검증.

## 참고
- 계절 정의(본 레포): ONDJ는 prev 10–12 + curr 1, ONDJ_NEXT는 curr 10–12 + next 1.
- 해석·보고 전 `last_year` 가정은 반드시 문서화한다.

