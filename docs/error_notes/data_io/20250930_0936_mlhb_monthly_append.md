---
title: 월별 MLHB NetCDF가 t=1만 저장됨
date: 2025-09-30 09:36
category: data_io
tags: [netcdf, monthly-aggregation, mlhb]
related:
  - scripts/run_mlhb_monthly.py
  - /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly.nc
  - logs/mlhb_monthly.log
---

## 상황 요약
- 월별 파이프라인 실행 후 NetCDF를 GrADS에서 열었더니 `t=2`가 정의되지 않았다는 메시지가 발생.
- `ncdump -h` 확인 시 `time = UNLIMITED ; // (1 currently)`로 단일 시점만 기록되어 있었음.

## 에러 메시지
```
GrADS: Time dimension error
"SDFG1A Error:  t=2 is not a valid time coordinate"
```

## 원인 진단
- `scripts/run_mlhb_monthly.py`의 `append_monthly`가 기존 파일을 덮어쓰면서 `time` 축을 유지하지 못함.
- `xarray.Dataset.to_netcdf`에 `append_dim`을 넘기려 했지만 의존 버전에서 지원되지 않아 실패 → 다시 덮어쓰는 사이클 반복.

## 해결 절차
1. 기존 `mlhb_monthly.nc` 삭제 후 1993-01~03 월을 재생성.
2. `append_monthly`를 수정해 기존 파일을 열어 새 월 평균과 `xr.concat(dim="time")`으로 결합한 뒤 재저장.
3. NetCDF 저장 시 `.tmp` 파일에 먼저 기록하고 `os.replace`로 원본을 교체해 읽기 중단 없는 원자적 갱신을 보장.
4. 수정된 스크립트로 월별 배치를 재시작 (`nohup env PYTHONUNBUFFERED=1 .venv/bin/python scripts/run_mlhb_monthly.py --start 1993-09 --end 2020-12 …`).
5. `xr.open_dataset(...).time.values`로 다중 시점 누적을 확인.

## 예방 및 메모
- 동일한 로직을 사용하는 다른 월평균 파이프라인에도 concat→재쓰기 + `.tmp`→rename 패턴을 적용.
- 월별 파일 점검 시 `ncdump -v time` 혹은 GrADS `q time`을 포함한 smoke test를 루틴화.
- NetCDF 쓰기 옵션 변경 시 사용 중인 xarray/netcdf4 버전에서 지원 여부를 먼저 확인.
- 장시간 배치 중 중간 결과를 봐야 하면, `cp mlhb_monthly.nc mlhb_monthly_preview.nc`처럼 스냅숏을 떠서 GrADS에서 확인.
