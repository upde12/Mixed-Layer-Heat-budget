---
title: DIFFV(연직 확산) 부호 컨벤션 교정 — z↓ 좌표에서의 일관성
date: 2025-10-10 10:20
category: data_io
tags: [mlhb, diffusion, sign, convention, qa]
related:
  - llm-ops/src/process_d2nf_main.py
  - llm-ops/src/process_d2nf.py
  - llm-ops/scripts/source_panel_mlhb.py
  - llm-ops/docs/guidelines/03_code_execution.md
---

## 요약
- 문제: GLORYS 깊이 좌표(z)가 아래로 증가(z↓)임에도, 연직 확산 항을 `DIFFV = -(Kv*Tz_mh)/h`로 저장하여 물리 기대(위로 향하는 플럭스=가열)와 부호가 반대로 기록됨.
- 증상: 월평균에서 `res = TEN - (QNET + ADV + ENT + DIFF)`와 `DIFFV`가 일관되게 음의 상관(`corr<0`)을 보임 → `DIFFV ≈ -res`.
- 조치(2025-10-10): 계산식을 `DIFFV = (Kv*Tz_mh)/h`로 교정. z↓ 좌표에서 `F_up = Kv·∂T/∂z_down`, 경향은 `F_up/h` 이므로 양(+) 부호가 일관.

## 배경/원인
- 표준 식(위로 증가 z_up): `DIFFV = -(Kv/h) · (∂T/∂z_up)|z=-h`.
- z_up→z_down 변환: `∂T/∂z_up = -∂T/∂z_down` ⇒ `-(Kv/h)·∂T/∂z_up = +(Kv/h)·∂T/∂z_down`.
- 코드가 z_down 기울기(`Tz_mh`)를 쓰면서 위 식의 ‘−’를 추가로 적용해 한 번 더 뒤집힘.

## 영향을 받는 파일/라인
- `src/process_d2nf_main.py:641` → `DIFFV = (kv * Tz_mh)/hden`로 수정.
- `src/process_d2nf.py:780` → 동일 수정.

## 검증(권장)
1) 월 파일 중 하나(예: 2019‑01)에서 `res = TEN-(QNET+ADV+ENT+DIFF)`와 `DIFFV`의 상관이 양(+)인지 확인.
2) 닫힘: `C = TEN-(QNET+ADV+ENT+DIFF+DIFFV)`의 평균≈0, RMS/IQR 감소 여부 확인.

## 임시 회피(보고/그림)
- 재산출 전까지는 `scripts/source_panel_mlhb.py --diffv-mode residual`로 DIFFV=잔차(`TEN-(QNET+ADV+ENT+DIFF)`)를 사용하면 닫힘/부호가 일치.

## 후속 조치
- 동계/하계 2개월 시범 재계산 → QA 통과 시 전체 기간 재계산.
- 보고/지침에 z↓ 좌표 사용 시 연직 확산 부호 컨벤션 명시(03 실행 지침 I, 10 방법론 README에 반영).

---

QA 체크리스트(요지)
- [ ] z좌표 컨벤션(z↓)과 DIFFV 부호 일치 확인(표식/주석 포함)
- [ ] `corr(res, DIFFV) > 0` (샘플 월)
- [ ] C 닫힘 통계 재확인(RMS/IQR)

