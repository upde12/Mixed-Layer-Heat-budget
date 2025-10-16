# 137E Project Overview

- 목적: JMA 137°E 반복 정선 자료로 Kawakami (2021) ‘net Kuroshio transport’ 재현 및 확장(절대화 보정, 검증, 기후 연계 분석).
- 현재 상태: 데이터 인벤토리와 핵심 레퍼런스 요약, MATLAB 코드 맵과 실행 메모 정리 완료. 초기 재현은 Python 기반 시각화 동등성 확인부터 진행.

## 데이터·코드 지도
- 데이터 루트: `137E/` — 월별 전처리 `.anl`(1967–2023), 계절평균, 원시/미러(`JMA137E/data`), 그림, 산출물.
- 폴더 가이드: `137E/README.md`
- 레퍼런스:
  - Kawakami (2021) PDF: `137E/JMA137E/ref/Kawakami2021_Article_TemporalVariationsOfNetKuroshi.pdf`
  - 요약본: `137E/JMA137E/ref/kawakami2021_summary.md`
- MATLAB 스크립트 개요: `137E/matlab_scripts_overview.md`, `137E/matlab_scripts_overview_ko.md`
- 유틸: `137E/pvector/`(UNESCO 해수함수, P‑vector 데모), `JMA137E/prog/`(.anl 로더/보간 및 그림)

## 재현 방법 개요(Kawakami 2021)
1) 계절 단면(OI) 생성: 수평 160 km, 수직 400 dbar 지수 커널; 격자 간격 31–34°N 1/3°, 30–31°N 1/2°, 3–30°N 1°, 수직 1 dbar, 0–2000 dbar.
2) 동역고/유속: 1000 dbar 기준 동역고 → 동서 지오스트로픽 유속(동향 +). 1250 dbar 참조 민감도 점검.
3) 경계 검출: 동역고(또는 유속) 분포로 B0–B3 결정(북쪽 한류/쿠로시오/KCC/남쪽 한계).
4) 수송 적분: 각 영역 0–1000 dbar 적분 → 냉핵/쿠로시오/KCC 수송, 합을 net Kuroshio transport로 정의.
5) 연평균·강제 진단: 동·하계 평균으로 연평균 시계열 → 겨울 WSC(중부 북태평양)과 지연(~2년) 상관, AL/NPSH EOF 모드 런닝 상관.
6) SST/열플럭스 영향: 큰/작은 수송년 합성으로 Kuroshio/KE의 늦겨울 SST 및 상향 난류열플럭스 비교.

## 초기 실행 계획(Python 우선)
- Step A — 형상 동등성 검증(진행됨: 1967‑01 완료)
  - 스크립트: `137E/JMA137E/prog/source_gpt/replot_196701_sections.py`
  - 입력: `137E/anl/196701/anl/*.anl`
  - 처리: 헤더 파싱(위도 도‑분→십진), 변수(THEATA/Salinity/SIG‑TH) 추출, 깊이 0:5:2000 m 보간(외삽 없음; NaN 마스킹)
  - 시각 설정: parula 유사 컬러맵, θ=2–28(1), S=34–35(0.1), σθ=1022–1028(0.2); x=2–35°N(5° major/1° minor), y=0–1000/2000 m(200 m major/100 m minor)
  - 산출: `137E/JMA137E/prog/figure_gpt/` Iptem/Isal/Ipden PNG 3종 → 원본(`137E/JMA137E/pic/`)과 육안 일치 확인
- Step B — 1000 dbar ref 상대유속:
  - θ/S/압력으로 동역고 상대(1000 dbar) 계산 → 인접 스테이션 차분으로 v_geo.
- Step C — 경계·적분:
  - B0–B3 자동 결정(단순 규칙→후에 개선), 0–1000 dbar 적분으로 월별/계절별 수송 산출.
- Step D — 연평균·강제 진단:
  - JRA‑55 접근성 검토(내부 보유본/경로) 후 WSC 지연 상관·EOF/웨이블릿.

## 결정·메모
- 의사결정(2025‑10‑16): 1차는 그림 동등성으로 Python 파이프라인을 검증(.mat 저장은 선택), 이후 수송 계산으로 확장.
- MATLAB 보조: `JMA_137E_20250901.m`는 경로 하드코딩 교체 시 보간·그림 산출 가능. `sw_gvel_argo.m`은 수직 차원 58 가정이 있어 일반화 필요.

## TODOs
- [ ] 대상 월 확정(198701 또는 199407)
- [ ] Python 로더/보간/그림(θ/염분/σθ) 스크립트 추가 → `137E/py/plot_section.py`
- [ ] 색상·등치선·축 설정을 MATLAB과 동등화(시각검증)
- [ ] 1000 dbar 기준 동역고·상대유속 계산 모듈 추가
- [ ] B0–B3 경계 자동화(규칙 기반 → 스무딩/봉우리 탐색)
- [ ] 0–1000 dbar 적분 및 월/계절/연평균 시계열 생성
- [ ] 문헌 값/경향과 1차 비교(시기·스케일·지연)
- [ ] (선택) JRA‑55 WSC·AL/NPSH 지표와 진단(접근 경로 정리 필요)

## 산출물 링크
- 137E 폴더 가이드: `137E/README.md`
- Kawakami 요약: `137E/JMA137E/ref/kawakami2021_summary.md`
- MATLAB 스크립트 개요: `137E/matlab_scripts_overview_ko.md`, `137E/matlab_scripts_overview.md`
 - Python 재현(1967‑01): `137E/JMA137E/prog/source_gpt/replot_196701_sections.py` / `137E/JMA137E/prog/figure_gpt/`

필요 시 위 단계들을 스크립트화하여 `llm-ops/scripts` 또는 `137E/py` 하위에 추가하고, 그림/수치 결과는 `137E/JMA137E/out|pic`에 정리합니다.
