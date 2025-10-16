# 3) 코드 실행 지침
<!-- owner: MLHB-core; canonical: true; depends_on: docs/guidelines/05_storage_output_guidelines.md, docs/guidelines/01_llm_guidelines.md; last_review: 2025-10-01 -->

## A. 환경 준비(로컬 실행)
- 파이썬/가상환경
  - Python 3.9+ 권장. 리포 루트에서 `.venv` 생성 후 활성화해 사용한다.
  - 설치 예: `.venv/bin/python -m pip install --upgrade pip xarray netCDF4 gsw`
  - 실행은 항상 `.venv/bin/python <script.py>` 형태를 사용한다.
- 경로/권한
  - 입·출력/플럭스 경로가 외장 볼륨이라면 마운트 상태를 먼저 확인한다(`/Volumes/...`).
  - 저장/출력 규칙과 경로 기본값은 `05_storage_output_guidelines.md`를 따른다.

## B. 실행 원칙(일반)
- 메인라인 진입점: `scripts/run_mlhb_monthly_main.py`를 사용한다(ADV=centered, TEN=forward 고정). 레거시 러너(`run_mlhb_monthly.py`)는 비교·실험용으로만 사용한다.
- 로그/백그라운드: 장시간 실행은 `nohup ... > logs/<name>.log 2>&1 &`로 실행하고 PID/로그를 기록한다.
- 원자적 저장: 최종 산출은 임시 파일(`*.tmp`)에 쓴 뒤 `os.replace`로 교체한다(부분 작성 파일 열람 금지).
- NetCDF/CF: time 좌표(units=`days since 1970-01-01 00:00:00`, calendar=`standard`)와 좌표 메타는 CF 규격을 따른다(상세는 05 문서 E 절).
- NaN 처리/집계: 분모≤0/결측은 NaN 유지, 기간 평균은 `skipna=True`로 전파 최소화.

## C. 병렬/자원 할당
- `--workers`: 연도별 병렬 처리에 사용(연도 수>1일 때 유효). 단일 연도 실행은 1코어로 동작한다.
- SSD 권장 동시성: 4–8(외장 I/O 상황에 따라 점진 조정). HDD/네트워크 스토리지는 2–3 권장.
- 우선순위: 다른 작업 영향 최소화를 위해 `nice -n 10`(선택) 사용을 권장한다.

## D. 모니터링/검증
- 진행 체크: `tail -f logs/<run>.log` / 일시 중지·중단은 PID 기준으로 관리.
- 파일 점검: `ncdump -h <file.nc>`로 CF 속성 확인, 필요 시 GrADS `sdfopen`으로 시범 오픈.
- 품질 체크: 닫힘 `C = TEN - (QNET + ADV + ENT + DIFF + DIFFV)` 통계, NaN 비율, 전역 속성(파라미터) 확인.

## E. 재현성/기록(운영 루틴 연계)
- 시작/종료 루틴과 시간 기록 규칙은 `01_llm_guidelines.md` B/E 절을 따른다.
- 결정/옵션 변경은 임시 메모(`docs/journal/tmp/<date>_notes.md`)와 로그에 병기한다.

## F. 오류/복구 메모(요지)
- 외장 미마운트: 경로가 `[missing]`이면 마운트 후 재시작.
- GrADS SDF 오류(시간축): CF time 속성 누락/부분 작성 파일 접근 가능성. 월평균 최종 산출만 열고, time units/calendar를 확인한다. 관련 노트: `docs/error_notes/data_io/20251001_grads_time_axis_index_exceeds.md`.
 - xarray CF 시간 인코딩 충돌: `failed to prevent overwriting existing key units in attrs on variable 'time'` 발생 시, time 좌표의 `attrs`에서는 `units`/`calendar`를 제거하고 `encoding`에만 지정한다(관련 노트: `docs/error_notes/data_io/20251001_xarray_time_units_overwrite.md`).

## G. 예시
```bash
# 가상환경 준비(최초 1회)
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip xarray netCDF4 gsw

# 1993–1998 다연도 월평균(메인라인; SSD 6워커 예)
nohup .venv/bin/python scripts/run_mlhb_monthly_main.py \
  --start 1993-01 --end 1998-12 \
  --indir  /Volumes/HJPARK4/MHW/data/GLORYS/ncfiles \
  --fluxdir /Volumes/HJPARK4/MHW/data/ERA5/daily_EA \
  --out    /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_1993_1998_main.nc \
  --temp-root /Volumes/HJPARK4/Decadal/source/ML_budget/tmp_daily \
  --python .venv/bin/python --workers 6 \
  --ah 100 --kv 1e-4 --we-mode deepening \
  --mld-source recompute --mld-threshold 0.03 --mld-ref-depth 10.0 \
  > logs/mlhb_1993_1998_main.log 2>&1 &
```

## H. 실행 후 검증·재시작 체크리스트
- 즉시 로그 점검(에러 패턴)
  - `tail -n 80 logs/<run>.log`로 오류/스택트레이스 확인.
  - 대표 패턴과 조치
    - `failed to prevent overwriting existing key units in attrs on variable 'time'` → time CF 메타는 `encoding`으로만 지정(오답노트: `docs/error_notes/data_io/20251001_xarray_time_units_overwrite.md`).
    - `NetCDF: Index exceeds dimension bound` (GrADS) → 월평균 최종 산출만 열기, time CF 속성 확인(오답노트: `docs/error_notes/data_io/20251001_grads_time_axis_index_exceeds.md`).
    - `No such file or directory`(입력/출력 경로) → 볼륨 마운트/경로 확인 후 재시작.
- 산출 파일 존재/메타 확인(CF)
  - `ncdump -h /path/to/monthly.nc`에서 `dimensions: time = UNLIMITED;`와 `time:units = "days since 1970-01-01 00:00:00"`, `time:calendar = "standard"` 확인.
  - 빠른 xarray 점검(선택):
    ```bash
    python - <<'PY'
    import xarray as xr, sys
    ds = xr.open_dataset(sys.argv[1]); print('dims=', dict(ds.dims)); print('time0=', ds.time.values[:3])
    PY /path/to/monthly.nc
    ```
- NaN/닫힘 품질 점검(요지)
  - `C = TEN - (QNET + ADV + ENT + DIFF + DIFFV)` 통계로 닫힘 확인(GrADS/파이썬 택1).
  - 변수별 NaN 비율을 샘플로 확인해 극단 값/결측 전파 여부 확인.
- 실패 시 회복/재시작
  - 월 단위 에러: 해당 월 scratch 제거 후 같은 커맨드로 재실행(월별 파이프라인은 idempotent; 월평균은 concat→정렬→원자적 교체).
  - 연 단위 에러: `logs/<run>.log`에서 마지막 성공 월 확인 → 실패 월부터 재실행(`--start`/`--end` 조정) 또는 전체 재실행.
  - 항상 최종 산출(output/monthly/*.nc)만 열어 검증한다(작성 중 scratch 금지).

## I. TEOS-10 사용 규칙(밀도/열팽창)
- 변환·계산 원칙
  - GLORYS 등 원자료의 염분(`SP`)과 잠재온도(`thetao`)는 TEOS-10으로 변환해 사용한다: `SA = gsw.SA_from_SP(SP, p, lon, lat)`, `CT = gsw.CT_from_pt(SA, thetao)`.
  - 밀도: 보존온도 `CT`를 사용할 때는 `gsw.rho(SA, CT, p)`를 사용한다. `rho_t_exact(SA, t, p)`는 실제 현장온도 `t`에만 사용한다.
  - 잠재밀도편차: `sigma0 = gsw.sigma0(SA, CT)`.
  - 열팽창계수: `alpha = gsw.alpha(SA, CT, p)`(표층은 `p=0 dbar`).
- 주석·해석 메모
  - 등가 온도차 근사: `ΔT_equiv ≈ Δσ0 / (ρ · α)`는 염분 기여를 무시한 주석용 근사치로, ρ·α는 10 m 기준에서 평가한다.
  - xarray는 GLORYS 로딩 시 `decode_times=False`로 원시 배열을 가져온 뒤 TEOS-10 계산을 적용한다.
- 코드 예시
  ```python
  import gsw
  SA = gsw.SA_from_SP(SP, p, lon, lat)
  CT = gsw.CT_from_pt(SA, thetao)
  sigma0 = gsw.sigma0(SA, CT)
  rho0 = gsw.rho(SA, CT, 0.0)
  alpha0 = gsw.alpha(SA, CT, 0.0)
  ```

## I‑1. 연직 확산(DIFFV) 부호 컨벤션(z↓) — 2025-10-10 교정
- 좌표: GLORYS 깊이 `z`는 아래로 증가(z↓).
- 위로 향하는 확산 플럭스: `F_up = K_v · ∂T/∂z_down`.
- 혼합층 경향 항: `DIFFV = F_up / h = (K_v/h) · ∂T/∂z_down`.
- 구현 규칙: `src/process_d2nf*.py`에서 `DIFFV = (kv * Tz_mh) / hden`(양의 부호)로 계산·저장한다.
- QA: 월 파일에서 `res = TEN-(QNET+ADV+ENT+DIFF)`와 `DIFFV`의 상관은 양(+), `C = TEN-(QNET+ADV+ENT+DIFF+DIFFV)`의 평균≈0.

## J. 메인라인 vs 레거시(정책 고정)
- 메인라인(`src/process_d2nf_main.py` / `scripts/run_mlhb_monthly_main.py`)
  - ADV 스킴: centered(고정)
  - TEN 앵커: forward(고정; `TEN_cen`은 진단으로 병기)
  - we‑mode: 기본 deepening(필요 시 비교만)
- 레거시(`src/process_d2nf.py` / `scripts/run_mlhb_monthly.py`)
  - 옵션·비교 실험 전용. 운영에서는 사용하지 않는다(혼선 방지).

## L. SODA 아노말리 기준(정책)
- 기후창: 1982–2020(포함) 고정. SODA 기반 월/계절(3개월) 아노말리는 이 창에 대해 계산한다.
- 적용 범위: 월 아노말리, prevOND/JFM/AMJ/JAS/OND 3개월 창, 오버레이용 `net_heating` 월 기후값.
- 실행 시 유의:
  - 입력 파일이 2021+까지 존재하더라도 아노말리 기준은 1982–2020으로 유지한다.
  - 스크립트에서 `--last-year`는 입력 자료의 마지막 해를, `--clim-start/--clim-end`는 기후창을 명시한다(권장: `--clim-start 1982 --clim-end 2020`).
  - 캡션/노트에 `clim=1982–2020`과 `last_year=...`를 병기해 재현성을 확보한다.

## K. 원시 월 바이너리(0.25° ECS) 연도축 추정 규칙
- 대상: MHW Days(`dur_mon_ECS.data` 등), SST(`ssts_mon.data` 등) 월 스택(raw float32; 101×145 격자).
- 금지: 마지막 해를 하드코딩(예: 2021) 가정하지 않는다.
- 절차(둘 중 하나 이상 충족):
  1) CTL 파싱: `TDEF <N> LINEAR 01Jan<Y0> 1yr` → `last_year = Y0 + N - 1`.
  2) 파일 길이 기반: `months = (filesize/4)/(101*145)` → `years = months/12`; `last_year`는 실행 인자로 명시(`--last-year`).
- 시작년 계산: `start_year = last_year - (years - 1)`.
- 실행 전 로그에 `months/years/start_year/last_year`를 기록하고, CTL과 상이 시 중단한다.
- 시즌 정렬 사전검증: ONDJ vs ONDJ_NEXT 차맵을 산출해 Jan 기여/경계 정렬을 확인한다.
- 보고 시 캡션/노트에 `last_year=...`, `clim=...`, `mode=anomaly|absolute`를 명시한다.
