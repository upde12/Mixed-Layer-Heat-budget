# 1) ML Heat Budget 분석의 변천사(물리 개념 중심 요약)

## 목표
- **MHW(해양 폭염) 기간의 SST 변화 원인**을 혼합층 열수지 항목으로 **정량 분해**.
- 해역: **NW Pacific / 동중국해–쿠로시오 주변**(중위도 성층-전선대 혼재).

## 초기 구상 → 문제 인식
- **방정식 선택의 혼선**:  
  - 초기에 `flux-form(열함량)`과 `non-flux(온도)` 표현을 혼용.  
  - 결과적으로 **큰 항의 상쇄**로 해석이 어려워짐(특히 이류/두께효과).
- **엔트레인먼트 과대**:  
  - 일간 **MLD 톱니**와 \(\nabla\!\cdot(h\mathbf v)\) 수치잡음 → \(w_e\) 과대,  
    \(h\) 얕음 + \(\Delta T\) 과대로 **ENT가 다른 항을 압도**.
- **\(\Delta T=T_m-T_b\)** 과대:  
  - 혼합층 평균 적분에서 **마지막(부분)층을 직사각형**으로 처리한 구현 버그 → \(T_m\) 과대, \(\Delta T\) 수 K.

## 개념 정리(채택된 형태: D2‑NF)
\[
\frac{\partial T_m}{\partial t}
= -\,\mathbf v_m\!\cdot\nabla T_m
+ \frac{Q_{\rm sfc}-q(h)}{\rho c_p\,h_{\rm den}}
+ \frac{A_h}{h_{\rm den}} \nabla\!\cdot\!\big[\,h\nabla T_m-\Delta T\nabla h\,\big]
- \frac{w_e}{h_{\rm den}}\Delta T
- \frac{K_v}{h_{\rm den}}\big(\partial_z T\big)\big|_{z=-h}
\]
- 좌변이 **SST 경향(TEN)** → MHW 해석에 직관적.
- \(q(h)\): **단파 침투**(2-밴드) 보정.  
- \(w_e=\partial_t h+\nabla\!\cdot(h\mathbf v_m)\). 사건 해석에서는 **deepening‑only**도 자주 사용.

## 구현 개선의 흐름
1) **NCL → Python 이행**, 일일 처리·즉시 저장·병렬(연도 단위).  
2) **Tm/Tb 계산 교정**(핵심):  
   - half‑level **겹침 가중** 적분으로 \(T_m\) 산출,  
   - \(T_b\)는 **셀내 선형 보간**,  
   - (선택) 표면 \(T(0)\) 저장(상층 외삽).  
   → \(\Delta T\)가 **0.1–0.6 K** 범위로 안정.
3) **엔트레인먼트 안정화 옵션** 추가:  
   - `we-mode`(dhdt/deepening/centered/full), `we-cap-md`, `hmin`, `ent-only-cooling` 등.  
   - 이후 데이터 품질 확보 후 **제약 해제** 모드로 운영 가능.
4) **텐던시 이중 저장**: forward + centered → 월평균 민감도/경계일 영향 점검.
5) **닫힘/잔차 출력**: `clos_d2_ten*`, `ent_resid_*`로 구성항 스케일 검증.

## 물리 해석 프레임(정착)
- **QNET**: 표면 열수지(단파 침투 차감).  
- **ADV\_NF**: 혼합층 평균 온도 구배에 대한 비보존 이류(전선 이동/수송 신호).  
- **ENT**: 혼합층 **깊어질 때만**(deepening) 주로 **냉각** 역할. 하층이 더 따뜻하면 **가열(>0)**도 가능.  
- **DIFF/DIFFV**: 수평/연직 난류; DIFFV는 **성층 기울기**와 \(K_v/h\)에 비례.
- **검증**: (i) 닫힘, (ii) 범위 가드레일(\(h,\Delta T,w_e\)), (iii) ENT vs 잔차 ENT 일치.

## 현재 합의된 운영 철학
- **분석 주체**는 `D2‑NF`(온도 방정식).  
- **MLD는 0.2 K·10 m 참조**를 기본으로 하되, 제품 정의 확인.  
- **제약은 최소화**: 깊어질 때만 적용(deepening‑only), **cap 해제** 가능.  
- Tm/Tb는 **수치적 일관성 확보가 최우선**, 나머지 안정화는 상황별 스위치.
