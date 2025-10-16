# 혼합층 열수지 분석 매뉴얼 (moved)

> 안내: 이 문서는 MLHB 전용 프로젝트로 이동했습니다(위치 안내: MLHB/docs/heat_budget/manual.md). 본 레포에서는 개요/인덱스만 유지합니다.

본 매뉴얼은 황해(Yellow Sea), 동중국해(East China Sea), 동해(East/Japan Sea)를 대상으로 혼합층 열수지(Mixed-Layer Heat Budget; MLHB)를 수행하기 위한 표준 절차를 정리한다. 주관적 판단을 최소화하고 관행을 따른다. 각 선택에는 가능한 한 문헌을 병기하며, 원문은 `references/MLHB/`에 보관한다(미존재 시 다운로드 필요). 참고문헌 보관·파일명·요약본(`_extracted/`) 관리 규칙은 `docs/guidelines/07_reference_management.md`를 따른다.

## 1. 범위와 표기
- 지역: 황해, 동중국해, 동해. 얕은 대륙붕(황해/동중국해)과 심해분지(동해)를 모두 포괄.
- 시간해상도: 일별(Daily) 분석을 기본으로 하되, 월평균 분석 시 차분/평활 규칙은 동일.
- 부호/단위: 표면 순열플럭스(Qnet)는 바다로 유입(+)으로 정의. 모든 항은 K s⁻¹(시각화 시 ×86400=K day⁻¹).

## 2. 데이터와 전처리
- 물리장: GLORYS Daily `thetao`, `so`, `uo`, `vo`, `mlotst`, `depth` 등.
- 플럭스: ERA5 또는 동등 자료의 순열(Qnet)과 단파 침투 항목. 침투 단파(q(h))는 반드시 혼합층 열수지에서 차감.
- 바다얼음: 해빙 농도(`sic`) 사용. `sic > 0.15` 셀은 기본적으로 MLHB 분석에서 제외하거나, 표면 플럭스를 해빙-해양 열교환으로 대체(연구 목적에 따라 선택).
- 지형/수심: 황해/동중국해 얕은 수심(≤ 50–100 m) 고려. 수심보다 깊은 MLD는 금지(MLD ≤ H_bathymetry; 정책 권고 — 현재 처리 로직은 별도 구현 필요).

## 3. 혼합층 깊이(MLD) 정의
운영 원칙: 본 매뉴얼은 “밀도 임계값(Δσ₀)” 단일 기준만 사용한다. 대체 기준(온도/구배)과 임의 스무딩은 사용하지 않으며, 필요 시 별도 부록 문서를 참조한다.

### 3.1 1차 기준(밀도 임계값; 기본)
- 정의: 10 m 참조 밀도 대비 Δσ₀ ≥ 0.03 kg m⁻³ 이 되는 가장 얕은 깊이를 MLD로 정의. 참조는 10 m(표층 스킨 영향 회피). [de Boyer Montégut et al., 2004]
- 계산: TEOS‑10(Absolute Salinity, Conservative Temperature) 기반으로 σ₀ 계산 후 선형보간으로 교차점 추정.
- 권고: 강한 표층 담수 유입(강 하구·장마) 시에도 밀도 기준을 우선 사용(온도 기준은 오판 위험).
 - 실행 구현: 기본은 Δσ₀=0.03, 10 m 참조 깊이로 밀도 기반 MLD를 **재계산**한다. 필요 시 `--mld-source product`를 넘겨 Copernicus 제품 `mlotst`를 그대로 사용할 수 있다. 임계값(`--mld-threshold`)과 참조 깊이(`--mld-ref-depth`)는 인자로 조정 가능하다.

### 3.2 대체 기준(참고용; 운영 불사용)
- 온도 임계값·구배 기준은 본 운영에서는 사용하지 않는다. 해당 기준으로 선행연구 재현이 필요한 경우에만 ‘부록: 대체 기준·특수 처리’를 참고한다. [Monterey & Levitus, 1997; de Boyer Montégut et al., 2004]

### 3.3 예외/마스킹(문헌 준거; 최소 적용)
- 해빙 마스킹: `sic > 0.15` 격자는 분석에서 제외(빙-해양 열교환 별도 모형이 없는 한).  
- 수심 상한: MLD ≤ 수심(`H_bathymetry`)을 강제.  
- 교차 실패: Δσ₀ 기준이 끝까지 충족되지 않으면 “완전 혼합”으로 보고 해당 열수층의 가장 깊은 유효 깊이를 사용한다(=bathymetry). 완전 혼합 표식은 추후 엔트레인먼트 해석 시 별도 참고용으로 기록한다.

### 3.4 품질 점검
- 프로파일 시각화: T/S/σ₀ vs z 프로파일과 함께 MLD·10 m 참조·Δσ₀/ΔT 주석 표기.
- 수치 가드레일: T ∈ [−5, 40] °C, S ∈ [0, 40] psu, σ₀ ∈ [20, 30] kg m⁻³. 위반 시 셀 제외 또는 재계산.

## 4. 열수지 방정식과 항목 정의
온도형 D2‑NF 형태를 사용한다(리포 기본). 혼합층 평균 온도 T_m에 대해:
- Ten: ∂T_m/∂t
- Adv: −(u·∇)T_m  [중심차분(기본) 또는 1차 풍상(연안 전선 등 고구배 구간)]
- Qnet: (Q_sw + Q_lw + Q_lhf + Q_shf − q(h)) / (ρ₀ c_p h)
- Ent: (T_b − T_m) w_e / h  [w_e: 유효 엔트레인먼트 속도]
- Diff_v: ∂/∂z(K_v ∂T/∂z)|_{z=h}  [모델 출력 또는 근사]
- Residual/Closure: Ten − (Qnet + Adv + Ent + Diff_v)

부호 규약과 단위는 §1과 동일.

## 5. 이산화/수치 스킴
- 시간차분: 일별 원장에서는 전진차분(Flux는 일평균). 월평균에서는 중앙 차분을 권장(경계월 영향 완화).
- 수평 구배/발산: 등격자상 2차 중심차분. 강한 전선/연안에서는 1차 풍상으로 전환 옵션 제공. 지구 곡률 보정: dx = a cosφ Δλ, dy = a Δφ.
- 보간: MLD·10 m·Tb 등은 깊이축 선형보간. 마지막 부분층은 사다리꼴 근사.
- 평활/필터: 주파수 누출·격자 잡음이 큰 경우 1–2회 공간 러닝 평균(3×3)까지 허용. 적용 여부는 로그에 기록.

## 6. 엔트레인먼트 정의
코드(`src/process_d2nf.py`)의 `--we-mode`와 일치시키기 위해 모드별 정의를 명시한다.

- dhdt(코드 기본): w_e = dh/dt  
  - 수평 발산항 ∇·(hU)를 포함하지 않는 가장 단순 정의.
- full: w_e = dh/dt + ∇·(hU)  
  - 연안/전선의 수렴·발산 영향을 반영(신호 풍부) — 노이즈 위험.
- deepening: w_e = max(dh/dt + ∇·(hU), 0)  
  - 물리 해석이 명확(깊어질 때 냉각), 잡음에 강함. 보고서 해석에 권장.
- centered: w_e = dh/dt(centered time) + ∇·(hU)  
  - dh/dt를 전후일 중앙차분으로 계산(경계일 영향 완화).

보호 한계:
- 분모 하한은 두지 않는다. 혼합층 두께가 0 또는 결측이면 해당 격자의 항을 NaN으로 남기고 후처리에서 제외한다.
- 완전 혼합 플래그: Δσ₀ 교차가 끝까지 발생하지 않아 bathymetry 깊이를 사용하는 경우, 해당 격자의 `ENT`와 `DIFFV`는 0으로 강제한다.

## 7. 지역별 주의사항(요약)
- 황해/동중국해: 얕은 수심이 많아 수심 상한(MLD≤H) 준수.  
- 동해: 겨울철 해빙 영향 가능 → `sic>0.15` 마스킹.  
- 모든 해역: 밀도 기준 단일 적용, 임의 스무딩 불사용.

## 8. 로그/재현성
- 파라미터(Δσ₀, ΔT, 참조깊이, we-mode, 스킴 선택, 평활 유무)를 결과와 함께 저장.
- 일지 `Issues & References`에 사용 파일경로·스크립트 옵션·transcript 링크를 기록.
- NetCDF 전역 속성 `fully_mixed_fraction`(시간·공간 평균 완전혼합 비율)을 확인해 fallback 구간 비중을 기록.

## 9. 권고 워크플로(운영 축약판)
1) MLD 계산: 밀도 기준(§3.1)만 적용 → 교차 실패 시 결측 처리(§3.3).  
2) 품질 점검: 프로파일 플롯·가드레일 검증(§3.4).  
3) 항 계산: Qnet(침투단파 제거), Adv, Ent, Diff_v, Ten(§4–§5).  
4) 닫힘 점검: Residual이 작고 공간적으로 무작위성 확인.  
5) 민감도: Δσ₀(0.02–0.05), we‑mode(deepening/dhdt) 비교.

## 10. 참고 문헌(초안)
- de Boyer Montégut, C., Madec, G., Fischer, A. S., Lazar, A., & Iudicone, D. (2004). Mixed layer depth over the global ocean: An examination of profile data and a profile-based climatology. J. Geophys. Res. Oceans, 109(C12003). doi:10.1029/2004JC002378.
- Monterey, G., & Levitus, S. (1997). Seasonal variability of mixed layer depth for the world ocean. NOAA NESDIS Atlas 14.
- Price, J. F., Weller, R. A., & Pinkel, R. (1986). Diurnal cycling: Observations and models of the upper ocean response to diurnal heating, cooling, and wind mixing. J. Geophys. Res., 91(C7), 8411–8427.
- Large, W. G., McWilliams, J. C., & Doney, S. C. (1994). Oceanic vertical mixing: A review and a model with a nonlocal K-profile boundary layer parameterization. Rev. Geophys., 32(4), 363–403.

원문 PDF는 `references/MLHB/`에 저장한다(접근 불가 시 사용자에게 다운로드 승인 요청). 자세한 보관·요약 규칙은 `docs/guidelines/07_reference_management.md` 참조.
