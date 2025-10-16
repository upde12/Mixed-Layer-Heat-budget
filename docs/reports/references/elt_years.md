# ELT Years (Canonical Set)

다음 연도 집합을 ELT(El Niño–La Niña Transition 등 분석용 특이 연도) 기본값으로 사용한다.

- 1983, 1988, 1998, 2010, 2016, 2020

메모
- 합성/그리드 스크립트에서 연도 목록이 필요한 경우 기본값으로 위 집합을 사용하고, 문서·캡션에는 사용한 연도 목록을 명시한다.
- 비교/대조 실험 시에는 본 집합과 대안 집합을 `compare_elt_sets.py`로 함께 보고(상관 r, RMS 비율, 부호 일치)한다.

관련 파일
- 스크립트(합성): `llm-ops/scripts/source_panel_mlhb_composite.py:1`
- 스크립트(연도 비교): `llm-ops/scripts/compare_elt_sets.py:1`
- 지침(보고): `llm-ops/docs/guidelines/09_reporting_guidelines.md:1`

## NT Years (Non‑Transition Peaks)

ELT(전이 해)가 아닌 상태에서 연변동 성분 피크가 나타난 연도(문헌·원고 정리 기준):

- 1991, 1994, 2001, 2004, 2006, 2008, 2013

메모
- NT 연도 집합은 ELT 대비 여름(JAS) 중심의 복사 구동(CGT 연계) 사례 분석에 사용한다.
- 도식/합성 시에는 ELT 집합과 동일한 절차로 NT 집합을 병행 보고하고, 캡션에 집합명을 명시한다.

## WNP Variant (120–155E, 15–35N)

본 변형은 WNP 도메인(120–155E, 15–35N)을 기준으로 한 문서·플롯의 기본 연도 집합이다. MHW_JC 관련 산출물에는 이 변형을 우선 적용한다.

- Domain: 120–155E, 15–35N (area‑weighted by cos(lat))

ELT (Extended; add 1995 only)
- 1983, 1988, 1995, 1998, 2010, 2016, 2020

NT (Dynamic; HP>0 & non‑ELT)
- 1984, 1991, 1994, 1999, 2001, 2004, 2008, 2013, 2017, 2021

Notes (method for NT dynamic list)
- Input: `/Volumes/HJPARK4/MHW/source/detect_hobday/mhw_days_wnp_1982_2022_bl1987_2017.nc` (Hobday 2016 monthly MHW days)
- Steps: monthly → annual sum → area‑weighted regional mean → std‑normalize (÷std, no demeaning) → LP=5‑yr cutoff low‑pass (interior: zero‑phase; boundary: trailing 5‑yr at series end) → HP=orig/std−LP → years with HP>0 and not in ELT.
- Boundary policy adds 2021 (HP evaluated with trailing 5‑yr LP).
- Last updated: 2025‑10‑14.
