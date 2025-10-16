# 혼합층 열수지 가이드(요약)

이 문서는 혼합층 열수지(MLHB) 작업을 빠르게 수행하기 위한 요약 가이드입니다. 세부 방법론·지역 특수 처리·문헌 인용은 `manual.md`, 실행/코드 변경 이력은 `01_code_and_runs.md`를 참조하세요.

## A. 불변 규칙
- 용어: `루트`=로컬 작업 경로, `리포`=GitHub 원격.
- 단위: 계산 내부는 K s⁻¹, 파일 저장은 K day⁻¹(추가 변환 불필요).
- QNET: 바다 유입 기준(+). 침투 단파 `q(h)`는 혼합층에서 반드시 차감.
- Tm/Tb: half‑level 겹침 가중, 마지막 부분층 사다리꼴, Tb 셀내 선형보간, T(0) 외삽.
- 방정식: D2‑NF(온도형), 해석은 SST 변화 중심.
- 산출 포맷: 연도별 NetCDF(`ml_budget_YYYY.nc`) 단일 파일에 변수로 저장. 변수명은 고정(`T_ML`, `Tb`, `T0`, `U_ML`, `V_ML`, `MLD`, `TEN`, `TEN_cen`, `ADV`, `QNET`, `ENT`, `DIFF`, `DIFFV`, `CLOS_d2_ten`, `CLOS_d2_ten_cen`).

## B. 기본 체크리스트
1) 닫힘: `clos_d2_ten`/`clos_d2_ten_cen` 평균≈0, RMS 작음.  
2) 범위 가드레일:  
   - h 여름 5–30 m, 겨울 50–200 m  
   - ΔT 중앙 0.1–0.3 K(여름 0.2–0.6 K)  
   - w_e p95 ≤ 15 m/day(자연 모드 최대 25)  
   - ENT(K/day) 전형 0.05–0.5, 사건 ~1.  
3) 부호 점검: QNET, DIFFV, ENT 일관성.  
4) 아노말리: 1993–2022 월별 기후 기준.

## C. 엔트레인먼트 모드
- dhdt(코드 기본): w_e = dh/dt  
- full: w_e = dh/dt + ∇·(hU)  
- deepening: w_e = max(dh/dt + ∇·(hU), 0)  
- centered: w_e = dh/dt(centered) + ∇·(hU)  
- 분모 하한 없음: 혼합층 두께가 0 또는 결측이면 항 전체를 NaN으로 남기고, 후처리에서 제외한다.

## D. 흔한 함정
- Tm 과대 → ΔT 과대: 마지막 층 적분·표층 중복 가중 버그.  
- QNET 부호 혼동: 자료 메타 확인(+가 바다 유입).  
- dx,dy 오적용: 위도 의존 cosφ 보정.  
- 텐던시·월평균: forward vs centered 차이·경계일 영향.

## E. 해석 문장 틀
- “SST 증가는 QNET 및 ADV 감소로 설명, 얕아짐으로 ENT 냉각 약화가 기여.”  
- “DIFFV는 성층 강화와 함께 약한 가열로 작동.”  
- “닫힘 잔차는 작아 분해의 일관성 확인.”

## F. 실행 프리셋
- 보수(코드 기본에 가까움): `--use-hbar-denom --we-mode dhdt`  
- 자연(물리 해석 강조): `--we-mode deepening`.
- MLD 옵션: 기본은 Δσ₀=0.03, 10 m 참조 재계산(교차 실패 시 bathymetry까지 확장·완전 혼합으로 처리). 제품 MLD를 쓰려면 `--mld-source product`, 임계값/참조깊이는 `--mld-threshold`, `--mld-ref-depth`로 조정.

## G. 경로/데이터(예시)
- 입력: `/Volumes/HJPARK4/MHW/data/GLORYS/ncfiles/GLO_PHY_MY_YYYY*.nc`  
- 플럭스: `/Volumes/HJPARK4/MHW/data/ERA5/daily_EA/{sw,lw,lhf,shf}_GLORYS.data`  
- 출력: `/Volumes/HJPARK4/Decadal/source/ML_budget/output/ml_budget_YYYY.nc`
  
※ 위 경로는 예시이며, 로컬 환경에 맞게 조정한다.

## H. 혼합층 구조 점검 루틴
- 프로파일 시각화·검증은 `docs/guidelines/02_plot_guidelines.md`의 “D. 혼합층 프로파일 시각화”를 따름.

---
- 상세 매뉴얼: `manual.md`
 - 부록(참고): `appendix_alternatives.md`
 - 엔트레인먼트 계산 논의: `we_modes_discussion.md`
 - GLORYS 공간 미분·이류 노트: `glorys_spatial_derivatives.md`
