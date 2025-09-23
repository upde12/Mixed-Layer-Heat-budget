---
title: Cartopy GeoAxes 패널 간격 왜곡
date: 2025-09-23 15:30
category: visualization
tags: [cartopy, figure-layout]
related:
  - src/analysis/source_panel.py
  - docs/discussions/transcripts/2025-09-23_session_raw.txt
  - docs/discussions/2025-09-23_rhs_panel_spacing.txt
---

## 상황 요약
- wspace=0으로도 RHS 패널 사이 여백이 생김

## 에러 메시지
```
wspace=0 & hspace=0.12 설정 상태에서 GeoAxes가 가로 폭을 축소
```

## 원인 진단
- 지도 종횡비와 figure 폭 불일치로 GeoAxes가 축 크기를 줄임

## 해결 절차
1. 지도 경계 종횡비에 맞춰 figsize와 wspace/hspace를 재계산

## 예방 및 메모
- 지도 범위를 입력받아 `figsize`, `wspace`, `hspace`를 계산하는 유틸 함수를 만들어 Cartopy 패널에 공통 적용한다.
- 간격이 어색해 보이면 즉시 `ax.get_position()`으로 bbox를 확인해 조정값을 수치로 기록한다.
- 신규 Cartopy 지도를 그리기 전에 `python3 scripts/search_error_notes.py cartopy`로 관련 시행착오를 재확인한다.
