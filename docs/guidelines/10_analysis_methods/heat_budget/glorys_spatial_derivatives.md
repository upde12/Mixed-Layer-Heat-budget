# GLORYS: 공간 미분·이류 계산 실무 노트 (moved)

> 안내: 이 문서는 MLHB 전용 프로젝트로 이동했습니다(위치 안내: MLHB/docs/heat_budget/glorys_spatial_derivatives.md). 본 레포에서는 개요/인덱스만 유지합니다.

본 노트는 다음 자료를 근거로 작성되었습니다. [PUM]/[QUID]/[NEMO]/[xgcm] 태그는 각각 외부 문서의 직접 근거를, [Internal]은 레포 코드 구현과의 일치를, [Practice]는 널리 쓰이는 수치 안정화 권고(운영 상의 베스트 프랙티스)를 뜻합니다. 권고는 동일 주제의 대안 중 “운영 시 기본으로 채택할 것을 제안”한다는 의미이며, 과학적 가능성의 배제를 뜻하지 않습니다. 인용한 주요 문서의 로컬 사본과 외부 링크는 하단 참고에 제공합니다.

GLORYS(ORCA 곡선 격자, Arakawa C‑grid)에서 공간 미분과 이류(−U·∇T)를 계산할 때 필요한 실무 규칙만 모았습니다. MLHB 일반론은 제외하고, 그리드/메트릭/스태거링에 따른 구현 요령을 요약합니다.

## 0) 기본 운영 설정(2025-09-30 확정)
- 메트릭: `dx_row = R·cosφ·Δλ`, `dy = R·Δφ` (정식 e1/e2 파일은 사용하지 않음).
- 이류 스킴: `--adv-scheme flux`를 기본으로 사용(보존형; centered/upwind는 비교용 옵션).
- 혼합층 옵션: `--we-mode centered_deepening`을 기본으로 사용.
- 안정화: 필요 시 3×3 러닝평균 1회까지 허용(적용 여부를 일지에 기록).

### 선택 근거
1. **문헌 일치** — GLORYS PUM / NEMO 매뉴얼에서 권장하는 보존형(Flux form)과 위·경도 기반 메트릭 적용을 충족하면서, 추가 mesh 메트릭 파일 없이도 계산 가능하다.
2. **코드 구현** — `src/process_d2nf.py`의 flux 스킴은 U/V 플럭스를 면 위치에서 계산한 뒤 발산, div(U,V) 교정까지 포함해 NEMO 방식과 일치한다.
3. **검증 결과** — 1993-01~04 GLORYS 일별 자료로 비교한 결과(경로: `/Volumes/HJPARK4/Decadal/source/ML_budget/output/adv_schemes/kuroshio/adv_kuroshio_diagnostics.nc`)에서 체커보드 RMS가 centered 0.330 → flux 0.327 K/day로 감소했고 영역 평균도 보존(0.038 K/day). Upwind는 RMS 0.552로 오히려 잡음이 커졌다.

## 1) 그리드·스태거링
- ORCA 곡선(삼중극) 격자: 셀 크기 가변, 고위도에서 Δλ가 급변. [PUM][QUID][NEMO]
- 스태거링: 스칼라(T/S/MLD)는 T점, 속도는 U/V점(Arakawa C‑grid). [NEMO][PUM]
- 속도 성분: CMEMS GLORYS `uo/vo`는 일반적으로 동/북향 성분(eastward/northward). 파일 메타(`standard_name`)로 확인. [PUM]

## 2) 메트릭(dx, dy)
- 위경도 차분은 물리 거리로 나누어야 합니다. [NEMO][xgcm]
  - dT/dx ≈ (T(i+1) − T(i−1)) / (2·R·cosφ·Δλ) [NEMO]
  - dT/dy ≈ (T(j+1) − T(j−1)) / (2·R·Δφ), R≈6.371e6 m [NEMO]
- 행(row)별 cosφ를 적용해 `dx_row`를 사용하고, 고위도/연안에서 dx≪dy 불균형을 고려. [Internal][Practice]

## 3) 공위치화(보간)과 보존형 계산
- Advective form(T점): U/V를 T점으로 보간 후 중앙차분 [xgcm][Internal]
  - U_T(i,j)=0.5·[U(i,j)+U(i−1,j)], V_T(i,j)=0.5·[V(i,j)+V(i,j−1)] [Internal]
  - ADV=−(U_T·∂xT + V_T·∂yT) [Internal]
- Flux form(권장, 적분 보존): [NEMO][xgcm][Practice]
  - x플럭스 Fx@U = U(i+1/2,j)·T를 U위치로 보간 [xgcm]
  - y플럭스 Fy@V = V(i,j+1/2)·T를 V위치로 보간 [xgcm]
  - ADV = −[(Fx(i+1/2)−Fx(i−1/2))/Δx + (Fy(j+1/2)−Fy(j−1/2))/Δy] [xgcm][NEMO]

## 4) 곡선 격자 일관성
- ‘동/북’ 성분이라면 위·경도 기반 미분(지리좌표)과 일관되게 사용. [PUM][NEMO]
- i/j 방향 미분과 동/북 성분을 섞지 말 것(혼용 시 오차). [NEMO][Practice]

## 5) 마스크·경계
- NaN/마스크(육지·빙구역) 선적용. [Practice]
- 해안선 인접 셀: 중앙차분 대신 1차 일방차분 또는 확장 마스크로 노이즈 억제. [Practice]
- 삼중극(fold) 인근: Δλ 랩핑을 대권거리 기반으로 처리하여 연속성 확보. [Practice]

## 6) 수직·혼합층 관련 미분
- ∂T/∂z|_{−h}: z‑level(부분층)에서 −h 깊이를 선형보간 후 중앙차분(마지막 부분층 사다리꼴). [Internal][Practice]
- 혼합층 평균장은 먼저 두께가중 평균(Tm, Um, Vm)을 구한 뒤 수평구배를 계산. [Internal]

## 7) 혼합층 두께 발산(∇·(hU))
- 보존형으로 계산 권장: [NEMO][Practice]
  - (hU)@U = h(T→U 보간)·U, (hV)@V = h(T→V 보간)·V [Internal][Practice]
  - ∇·(hU) = d/dx(hU) + d/dy(hV), 각 방향 Δx, Δy로 나눔. [Internal][NEMO]
- dh/dt는 동일 T격자에서 전진/중앙 중 한 가지로 고정. [Internal]

## 8) 시간 평균·정의
- 월평균 분석 시 정의를 명시: overline(U)·∇overline(T) vs overline(−U·∇T)는 다를 수 있음. [Practice]
- 텐던시·이류·플럭스의 시간대상(일/월 평균)을 일치. [Internal][Practice]

## 9) 필터링·가드레일
- 고구배/연안 노이즈 완화를 위해 3×3 러닝평균(1–2회)까지 허용(적용 여부 기록). 과스무딩 금지. [Practice]
- 얕은 h에서 분모 폭주 문제는 존재하나, 문헌에 표준화된 하한값은 확인되지 않는다. 기본 운영에서는 분모 하한을 두지 않고, 0 또는 결측이 감지되면 해당 격자를 NaN으로 유지해 후처리에서 제외한다. [Internal]

## 10) 검증 루틴(빠른 체크)
- ∂xT, ∂yT 단위/크기 범위 점검(지역 의존 10^−7–10^−5 K m^−1 수준). [Practice]
- 부호 검산: 동향 유속·양의 ∂xT이면 −U∂xT<0(냉각) 등 직관 검증. [Practice]
- Flux vs Advective form 영역 평균 비교(경계 처리 영향 확인). [Internal][Practice]
- 극/국경 랩핑 후 이상치 유무. [Practice]

## 참고(외부/로컬 문서)
- CMEMS GLORYS PUM(변수·격자·단위): references/GLORYS/CMEMS-GLO-PUM-001-030.pdf [로컬][PUM] · 외부: https://documentation.marine.copernicus.eu/PUM/CMEMS-GLO-PUM-001-030.pdf
- CMEMS GLORYS QUID(품질/알고리즘): references/GLORYS/CMEMS-GLO-QUID-001-030.pdf [로컬][QUID] · 외부: https://documentation.marine.copernicus.eu/QUID/CMEMS-GLO-QUID-001-030.pdf
- NEMO ocean engine(격자/메트릭·보존형 이산화의 개념 근거): 현재 로컬 안정본 부재 — 최신 매뉴얼은 https://www.nemo-ocean.eu 에서 “Documentation/Manual” 참조. [NEMO]
- xgcm(격자·메트릭 인지 계산): https://xgcm.readthedocs.io/en/stable/ [xgcm]
