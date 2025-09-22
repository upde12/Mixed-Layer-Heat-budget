# 3) 향후 분석 지속을 위한 LLM 지침(메모리 프롬프트)

## A. 불변 규칙
- **용어 규약**: 이 문서에서 `루트`는 로컬 작업 경로(`~/Desktop/GPT/Mixed-Layer-Heat-budget` 등)를, `리포`는 원격 GitHub 경로(`upde12/Mixed-Layer-Heat-Budget`)를 가리킵니다.
- **모든 항의 내부 단위 = K s⁻¹**. 시각화 시 **× 86400 = K/day**.
- **QNET 정의**: 해양 유입 양(+) 가정, **단파 침투 `q(h)`를 반드시 빼서** 혼합층에 분배.
- **Tm/Tb 계산법**(핵심): half‑level 겹침 가중, 마지막 부분층 사다리꼴(암묵), Tb 셀내 선형보간, T(0) 외삽.
- **방정식은 D2‑NF**(온도 형태), 해석은 **SST 변화** 중심.
- **파일 네이밍**과 **항 ↔ 파일 매핑**은 고정(ten, advNF, qnet, ent, diff, diffv, clos*).

## B. 기본 체크리스트(항상 수행)
1) **닫힘**: `clos_d2_ten`/`clos_d2_ten_cen` 평균≈0, RMS 작음.  
2) **범위 가드레일**:  
   - \(h\) 여름 5–30 m, 겨울 50–200 m  
   - \(\Delta T\) 중앙 0.1–0.3 K(여름 0.2–0.6 K)  
   - \(w_e\) p95 ≤ 15 m/day(자연 모드에선 25까지 관찰 가능)  
   - **ENT(K/day)** 전형 0.05–0.5, 사건 ~1.
3) **부호 점검**: QNET(자료 부호), DIFFV(성층·부호), ENT(깊어질 때 냉각이 기본) 일관성.
4) **아노말리 정의**: “1993–2022 월별 기후”에서의 편차(월 평균 − 월 기후).

## C. 엔트레인먼트 모드 선택 가이드
- **deepening‑only**: 물리 해석이 가장 깔끔(냉각 우세).  
- **full(centered)**: 연안/전선 수렴·발산 포함(신호 풍부) — 노이즈 가능성.  
- **cap/hmin**: 품질 문제 있을 때만 켠다. 데이터가 좋으면 끈다.

## D. 흔한 함정
- **Tm 과대** → \(\Delta T\) 수 K: 마지막 층 직사각형 적분/표층 중복 가중 버그.  
- **QNET 부호** 혼동: 자료 메타 확인(해양 유입 +).  
- **dx,dy** 오적용: 위도 의존 \(dx=dy\cos\phi\).  
- **텐던시-월평균**: forward vs centered 차이·경계일 영향 체크.

## E. 결과 해석 프레임(보고서용 문장 틀)
- “해당 사건에서 **SST 증가**는 주로 **표면 가열(QNET)**과 **수평 이류 감소(ADV\_NF)**에 의해 설명되며, **혼합층의 얕아짐**으로 **엔트레인먼트 냉각이 약화**된 것이 기여했다.”  
- “연직 확산(DIFFV)은 **성층 강화**와 함께 **약한 가열**로 작동했다.”  
- “닫힘 잔차는 전 영역에서 작아, 항목 분해의 **일관성**을 확인했다.”

## F. 실행 프리셋 기억
- 보수: `--use-hbar-denom --hmin 15 --we-mode dhdt`  
- 자연: `--hmin 0 --we-mode deepening` (+ 필요 시 `--allow-ent-heating`)

## G. 경로/데이터(기본)
- 입력: `/data3/GLORYS/Daily_93_21/glorys_subset/GLO_PHY_MY_YYYY*.nc`
- 플럭스: `/data3/GLORYS/ML_budget/data/{sw,lw,lhf,shf}_GLORYS.data`
- 출력: `/data3/GLORYS/ML_budget/output_gpt/*.data`
