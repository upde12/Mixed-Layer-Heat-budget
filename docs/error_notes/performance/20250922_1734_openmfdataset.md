---
title: open_mfdataset 월평균 병목
date: 2025-09-22 17:34
category: performance
tags: [era5, monthly, performance]
related:
  - src/analysis/process_era5_monthly_eof.py
---

## 상황 요약
- ERA5 30년치 NetCDF를 open_mfdataset으로 한 번에 열어 월평균을 내다가 작업이 20분 이상 지연

## 에러 메시지
```
ValueError: unrecognized chunk manager dask - must be one of: []
```

## 원인 진단
- dask 없이 chunked open_mfdataset를 호출해 chunk manager를 찾지 못했고 4GB 파일을 동시에 로드해 I/O 병목 발생

## 해결 절차
1. 연도별 스트리밍 후 concat하는 방식으로 리팩터링

## 예방 및 메모
- 후속 조치 및 참고 링크를 작성하세요.
