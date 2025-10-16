---
title: xarray Dataset 변수 dims 지정 오류 – ("lat","lon") 튜플 필요
date: 2025-10-01 15:55
category: data_io
tags: [xarray, dataset, dims]
related:
  - llm-ops/scripts/compute_mld_fallback_stats.py
---

## 상황
- 월간 fallback 통계 NetCDF 생성 중 다음 오류 발생:
```
ValueError: Variable 'fallback_days': Could not convert tuple of form (dims, data[, attrs, encoding])
```

## 원인
- `xr.Dataset({...})` 구성 시 변수 정의를 `(dim1, dim2, data)`처럼 넘겼고, 일부 항목은 실수로 `("lat", "lon", array)`가 아닌 `("lat",)`, `ndim=0`로 해석되었다.
- xarray는 변수 정의에 `(("lat","lon"), data)` 형태의 ‘튜플 안 튜플’을 요구한다.

## 해결
- 변수 선언을 다음과 같이 교정:
```python
ds_out = xr.Dataset({
  "fallback_days": (("lat", "lon"), fallback_days),
  "shallow_days":  (("lat", "lon"), shallow_days),
  "valid_days":    (("lat", "lon"), valid_days),
  "fallback_fraction": (("lat", "lon"), np.where(valid_days>0, fallback_days/valid_days, np.nan)),
}, coords={"lat": ("lat", lat1d), "lon": ("lon", lon1d)})
```

## 참고
- 분모=0에 대한 경고(`invalid value encountered in divide`)는 `where(valid_days>0, ...)`로 NaN 처리.

