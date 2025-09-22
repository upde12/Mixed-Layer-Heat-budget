# 2) 최신 코드 개요 · 변경 이력 · 실행 명령어

## 최신 안정 버전(요지)
파일: `process_d2nf.py`  
핵심 특징:
- **D2‑NF** 구현: `TEN = QNET + ADV_NF + ENT + DIFF + DIFFV` (모두 **K s⁻¹**).
- **Tm/Tb 계산(수정 완료)**: half‑level 겹침 적분, \(T_b\) 선형보간, \(T(0)\) 외삽 저장.
- **텐던시 2종** 저장: `ten`(forward), `ten_cen`(centered).  
- **엔트레인먼트 모드**: `dhdt/deepening/centered/full` 스위치.  
- **분모 선택**: 기본 \(h\), 옵션으로 \(\bar h\)(`--use-hbar-denom`).  
- **출력(일단위, Ny×Nx float32)**  
  - 상태장: `T_MLYYYY.data`, `TbYYYY.data`, `T0YYYY.data`, `U_MLYYYY.data`, `V_MLYYYY.data`, `MLDYYYY.data`  
  - 항목: `tenYYYY.data`, `ten_cenYYYY.data`, `advNFYYYY.data`, `qnetYYYY.data`, `entYYYY.data`, `diffYYYY.data`, `diffvYYYY.data`  
  - 닫힘: `clos_d2_tenYYYY.data`, `clos_d2_ten_cenYYYY.data`

> 단위 주의: **K s⁻¹**로 저장. 플롯 시 **× 86400 → K/day**.

## 주요 변경 이력(핵심 포인트)
- **v0 (NCL)**: D2 형태 유사, Tm/Tb 부분층 처리 미흡 → \(\Delta T\) 과대.  
- **v1 (Python 초기)**: 일일 처리/저장, 병렬 프레임, QNET 침투 반영.  
- **v2**: `we-mode`/cap/`hmin`/잔차 출력 등 **안정화 옵션** 추가.  
- **v3**: **forward + centered 텐던시** 동시 저장.  
- **v4 (현재)**: **Tm/Tb robust**(half-level + Tb 보간 + T(0) 저장) → **ENT 정상화**.  
- **v4.1(옵션)**: \((\partial T/\partial z)|_{-h}\) **3점 최소제곱** 기울기 스니펫 제시(선택 적용 가능).

## 실행 예시(프로파일별 프리셋)

### ① 보수적(검증/논문 기본)
```bash
python process_d2nf.py \
  --indir  /data3/GLORYS/Daily_93_21/glorys_subset \
  --outdir /data3/GLORYS/ML_budget/output_gpt \
  --fluxdir /data3/GLORYS/ML_budget/data \
  --years  2016:2016 --workers 1 \
  --ah 100 --kv 1e-4 \
  --use-hbar-denom --hmin 15 \
  --we-mode dhdt
```

### ② 자연스러움(요청 반영: 분모 하한 X, deepening‑only, cap 없음)
```bash
python process_d2nf.py \
  --indir  /data3/GLORYS/Daily_93_21/glorys_subset \
  --outdir /data3/GLORYS/ML_budget/output_gpt \
  --fluxdir /data3/GLORYS/ML_budget/data \
  --years  2016:2016 --workers 1 \
  --ah 100 --kv 1e-4 \
  --hmin 0 \
  --we-mode deepening
# cap/ΔTcap 미지정 = 상한 없음, --use-hbar-denom 미지정 = 분모 h
# (엔트레인먼트 가열 허용이 필요하면 --allow-ent-heating 옵션을 코드에 추가해야 함)
```

### ③ deepening‑only + ENT 가열 허용(옵션 한 줄 패치 필요)
argparse에 아래 줄을 추가 후:
```python
ap.add_argument("--allow-ent-heating", action="store_false", dest="ent_only_cooling",
                help="allow ENT > 0 (disable cooling-only constraint)")
```
실행:
```bash
python process_d2nf.py ... --hmin 0 --we-mode deepening --allow-ent-heating
```

## 입/출력 요약
- 입력 NetCDF: `GLO_PHY_MY_YYYYMMDD*.nc` (thetao, uo, vo, mlotst 등)  
- 외부 플럭스: `sw_GLORYS.data`, `lw_GLORYS.data`, `lhf_GLORYS.data`, `shf_GLORYS.data` (into‑ocean +)  
- 출력 `.data`: 위 목록 참고.

## 자주 쓰는 빠른 검증(GrADS)
```grads
* 닫힘
define C = ten - (qnet + advNF + ent + diff + diffv)
set gxout stat
d C

* ENT 규모(K/day)
d ent*86400

* dT 확인
open T_ML.ctl; open Tb.ctl
define dT = T_ML - Tb
d dT
```
