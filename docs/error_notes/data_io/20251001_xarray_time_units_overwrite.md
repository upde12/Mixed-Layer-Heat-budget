---
title: xarray CF time encoding 충돌 – time.attrs.units vs encoding.units
date: 2025-10-01 11:45
category: data_io
tags: [xarray, netcdf, cf, time-axis]
related:
  - llm-ops/scripts/run_mlhb_monthly.py
  - llm-ops/scripts/run_adv_schemes.py
---

## 상황 요약
- 월평균 NetCDF 저장 중 xarray CF 인코더가 time 좌표의 `units` 속성 덮어쓰기 충돌로 실패.

## 에러 메시지
```
ValueError: failed to prevent overwriting existing key units in attrs on variable 'time'.
This is probably an encoding field used by xarray to describe how a variable is serialized.
```

## 원인 진단
- time 좌표에 `attrs.units`를 수동 설정하면서 동시에 `encoding["units"]`도 지정함 → xarray CF 인코더 충돌.

## 해결 절차
1) time 좌표의 `attrs`에서 `units`/`calendar` 키를 제거하고, 설명용 `long_name`만 유지.
2) `encoding`에만 `units="days since 1970-01-01 00:00:00"`, `calendar="standard"`, `dtype=f8`, `_FillValue=None`를 지정.
3) 월평균 산출은 `.tmp` → `os.replace`로 원자적 저장 완료본만 열람.

## 예방 및 메모
- CF 메타는 encoding을 우선 사용하고, `attrs`에는 설명 필드만 둔다.
- 집계 시 `skipna=True`로 NaN 전파 최소화.
- 상세 구현: `llm-ops/scripts/run_mlhb_monthly.py`, `llm-ops/scripts/run_adv_schemes.py` 참조.

