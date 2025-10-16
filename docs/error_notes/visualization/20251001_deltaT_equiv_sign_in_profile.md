---
title: ΔT_equiv 표기 부호 오류 – 프로파일 주석에서의 등가 온도차
date: 2025-10-01 15:30
category: visualization
tags: [teos10, density, profile, annotation]
related:
  - llm-ops/scripts/plot_mld_profile_recomputed.py
---

## 상황 요약
- 혼합층 프로파일 그림 주석에 표기하는 `ΔT_equiv`(온도만으로 같은 Δσ₀를 만들 등가 온도차)의 부호가 잘못되어 온도 증가가 밀도 증가로 표시되는 등 직관에 반하는 수치가 출력됨.

## 수식/원인
- TEOS‑10에서 밀도변화의 1차 근사는 `δσ₀ ≈ ρ·β·ΔS − ρ·α·ΔT`.
- 따라서 온도만의 등가 변화는 `ΔT_equiv ≈ −Δσ₀ / (ρ·α)`가 되어야 한다.
- 코드에서 `ΔT_equiv = Δσ₀ / (ρ·α)`로 계산해 부호가 반대로 출력되었다.

## 조치
- `plot_mld_profile_recomputed.py` 128행 근방을 다음과 같이 수정:
  - 변경 전: `delta_t_equiv = delta_sigma / (rho_ref * alpha_ref)`
  - 변경 후: `delta_t_equiv = - delta_sigma / (rho_ref * alpha_ref)`
- 추가로 ρ 계산은 TEOS‑10 `rho(SA, CT, p)`를 사용(CT 경로). `rho_t_exact`는 실온도 경로용임.

## 검증
- ENTPOS 사례(1993‑01‑02, 34.0°N, 127.17°E): `Δσ₀ ≈ +0.030 kg m⁻³` → `ΔT_equiv ≈ −0.17 °C`로 정상화.

## 예방
- 주석 수식 변경 시 ‘단위·부호 체크리스트’를 플롯 지침 B‑섹션에 포함하고, TEOS‑10 사용 규칙(03 지침 I 절)을 우선 확인한다.

