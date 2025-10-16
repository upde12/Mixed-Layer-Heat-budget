---
title: GrADS SDF "Index exceeds dimension bound" on time axis
date: 2025-10-01 10:22
category: data_io
tags: [grads, netcdf4, time-axis, mlhb]
related:
  - scripts/run_mlhb_monthly.py
  - scripts/run_adv_schemes.py
  - /Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/
---

## 상황 요약
- GrADS에서 `sdfopen ml_budget_1993.nc` 실행 시 다음 오류:
```
Scanning self-describing file:  ml_budget_1993.nc
 NetCDF: Index exceeds dimension bound
 SDF Error: nc_get_vara_double failed to read coordinate axis value
 gadsdf: Error reading first time value in SDF file.
```

## 원인 진단
- 월평균 파일의 `time` 좌표가 CF 규약 `units/calendar` 속성이 불완전해 GrADS SDF 파서가 첫 시간값을 읽지 못함.
- 또한 월별 파이프라인에서 일별 파일을 즉시 정리(scratch 삭제)하므로, 작성 중(또는 삭제 직전) 파일을 열면 HDF 에러가 발생할 수 있음.

## 해결 절차
1) 월평균 작성 시 `time` 축에 CF 속성을 명시하도록 수정:
   - `units = "days since 1970-01-01 00:00:00"`, `calendar = "standard"`, dtype=float64, FillValue 없음.
   - 변경 파일: `scripts/run_mlhb_monthly.py`, `scripts/run_adv_schemes.py`.
2) 월평균 계산 시 `skipna=True` 적용해 NaN 전파를 줄임.
3) 작성 중인 일별 scratch 파일은 열지 말고, 월평균 산출(`output/monthly/*.nc`)만 열도록 안내.

## 예방 및 메모
- CF 규격(time, lat, lon 속성) 준수 여부를 `ncdump -h`로 확인.
- 월별 파일은 `.tmp` → `rename`(원자적 교체)로 작성되므로, 그 경로를 열어야 일관성이 보장됨.
- 필요 시 월별 산출에 `history`/`source`에 파이프라인 버전을 남겨 추적성을 높임.
