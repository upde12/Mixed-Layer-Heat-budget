# 2) 최신 코드 개요 · 변경 이력 · 실행 명령어 (moved)

> 안내: 이 문서는 MLHB 전용 프로젝트로 이동했습니다(위치 안내: MLHB/docs/heat_budget/01_code_and_runs.md). 본 레포에서는 개요/인덱스만 유지합니다.

## 최신 안정 버전(요지)
파일: `process_d2nf.py`  
핵심 특징:
- **D2‑NF** 구현: `TEN = QNET + ADV + ENT + DIFF + DIFFV`.
- **Tm/Tb 계산(수정 완료)**: half‑level 겹침 적분, \(T_b\) 선형보간, \(T(0)\) 외삽 저장.
- **MLD 계산**: 기본은 Δσ₀=0.03, 10 m 참조로 재계산(`--mld-source product`로 Copernicus `mlotst` 사용 가능).
- **텐던시 2종** 저장: `ten`(forward), `ten_cen`(centered).  
- **수평 이류 스킴 선택**: `--adv-scheme flux`를 기본으로 사용(보존형). `centered`, `upwind`는 비교·민감도용 옵션.  
- **엔트레인먼트 모드**: `dhdt/deepening/centered/full/centered_deepening` 스위치.  
- **분모 선택**: 기본 \(h\), 옵션으로 \(\bar h\)(`--use-hbar-denom`).  
- **출력(연도별 NetCDF, time×lat×lon, float32)**  
  - 파일: `ml_budget_YYYY.nc`  
  - 변수: `T_ML, Tb, T0, U_ML, V_ML, MLD, TEN, TEN_cen, ADV, QNET, ENT, DIFF, DIFFV, CLOS_d2_ten, CLOS_d2_ten_cen`

> 단위 주의: 계산은 K s⁻¹, 파일 저장은 **K day⁻¹**입니다(추가 × 86400 불필요).

## 주요 변경 이력(핵심 포인트)
- **v0 (NCL)**: D2 형태 유사, Tm/Tb 부분층 처리 미흡 → \(\Delta T\) 과대.  
- **v1 (Python 초기)**: 일일 처리/저장, 병렬 프레임, QNET 침투 반영.  
- **v2**: `we-mode`/cap/잔차 출력 등 **안정화 옵션** 추가.  
- **v3**: **forward + centered 텐던시** 동시 저장.  
- **v4 (현재)**: **Tm/Tb robust**(half-level + Tb 보간 + T(0) 저장) → **ENT 정상화**.  
- **v4.1(옵션)**: \((\partial T/\partial z)|_{-h}\) **3점 최소제곱** 기울기 스니펫 제시(선택 적용 가능).

## 실행 예시(프로파일별 프리셋)

### ① 보수적(검증/논문 기본; 내부 안정화 옵션 예시)
```bash
python process_d2nf.py \
  --indir  /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
  --outdir /Volumes/HJPARK4/Decadal/source/ML_budget/output \
  --fluxdir /Volumes/HJPARK4/MHW/data/ERA5/daily_EA \
  --years  2016:2016 --workers 1 \
  --ah 100 --kv 1e-4 \
  --use-hbar-denom \
  --we-mode dhdt \
  --adv-scheme flux
# 기본은 Δσ₀=0.03, 참조 10 m 재계산. 제품 MLD 사용 시 --mld-source product 추가.
```

### ② 자연스러움(요청 반영: 분모 하한 X, deepening‑only, cap 없음)
```bash
python process_d2nf.py \
  --indir  /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
  --outdir /Volumes/HJPARK4/Decadal/source/ML_budget/output \
  --fluxdir /Volumes/HJPARK4/MHW/data/ERA5/daily_EA \
  --years  2016:2016 --workers 1 \
  --ah 100 --kv 1e-4 \
  --we-mode deepening \
  --adv-scheme flux

# cap/ΔTcap 미지정 = 상한 없음, --use-hbar-denom 미지정 = 분모 h
# 제품 MLD 사용 시 --mld-source product, 임계값 조정은 --mld-threshold, 참조 깊이는 --mld-ref-depth.
```

### ③ 비교 실행(중심차분 vs 중심차분+deepening-only)
```bash
# 1993-01~04 월평균 두 버전 산출(entrainment+detrainment vs entrainment-only)
python scripts/run_mlhb_monthly_dual.py \
  --start 1993-01 --end 1993-04 \
  --indir  /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
  --fluxdir /Volumes/HJPARK4/MHW/data/ERA5/daily_EA \
  --out-root /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly_centered \
  --workers auto --mld-source recompute --mld-threshold 0.03 --mld-ref-depth 10 \
  --adv-scheme flux
```

### ④ 수평 이류 스킴 비교(기본/풍상/보존형)
```bash
# 1993-01~04 기간 동안 centered/upwind/flux 이류 스킴별 일별·월평균 산출
python scripts/run_adv_schemes.py \
  --start-date 1993-01-01 --end-date 1993-04-30 \
  --schemes centered,upwind,flux \
  --we-mode centered_deepening \
  --indir /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
  --fluxdir /Volumes/HJPARK4/MHW/data/ERA5/daily_EA \
  --out-root /Volumes/HJPARK4/Decadal/source/ML_budget/output/adv_schemes
```

## 입/출력 요약
- 입력 NetCDF: `GLO_PHY_MY_YYYYMMDD*.nc` (thetao, uo, vo, mlotst 등)  
- 외부 플럭스: `sw_GLORYS.data`, `lw_GLORYS.data`, `lhf_GLORYS.data`, `shf_GLORYS.data` (into‑ocean +)  
- 출력 NetCDF: `ml_budget_YYYY.nc` 내 변수(`T_ML`, `Tb`, `TEN`, `QNET`, `ADV`, `ENT`, `DIFF`, `DIFFV`, `CLOS_*`).
- 전역 속성: `mld_source`, `mld_threshold_dsigma0`, `mld_ref_depth_m`, `fully_mixed_fraction` 등 파라미터 로그 확인.

## 자주 쓰는 빠른 검증(GrADS)
```grads
* 파일 열기(NetCDF 단일 파일)
sdfopen ml_budget_2016.nc

* 닫힘(변수명은 대소문자 구분 없음)
define C = TEN - (QNET + ADV + ENT + DIFF + DIFFV)
set gxout stat
d C

* ENT 규모(K/day)
d ENT

* dT 확인
define dT = T_ML - Tb
d dT
```
