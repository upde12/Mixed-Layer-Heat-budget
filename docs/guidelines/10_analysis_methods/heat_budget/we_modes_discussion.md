# 엔트레인먼트 계산 방법 — 논의와 근거 (moved)

> 안내: 이 문서는 MLHB 전용 프로젝트로 이동했습니다(위치 안내: MLHB/docs/heat_budget/we_modes_discussion.md). 본 레포에서는 개요/인덱스만 유지합니다.

본 문서는 혼합층 열수지(MLHB)에서 엔트레인먼트 속도 `w_e` 정의 선택(dh/dt, Dh/Dt, dh/dt+∇·(hU), deepening-only)에 관한 문헌 근거와 실무 권고를 정리합니다. 각 주장에는 로컬로 보관된 동료심사 문헌 PDF 경로를 병기합니다.

## 요약 권고
- 표준 정의: `w_e = ∂t h + ∇·(h U_m)`가 혼합층 두께 연속과 합치(두께 방정식)됩니다. 관측 기반 MLHB 문헌에서 널리 채택됩니다. [Foltz 2013 JCLI: `references/MLHB/Foltz_Schmid_Lumpkin_2013_JCLI_NETA_MLHB.pdf`], [Dong et al. 2007 JCLI: `references/MLHB/Dong_Gille_Sprintall_2007_JCLI_SouthernOcean_MLHB.pdf`]
- 실무(관측 기반 월평균) 해석용: deepening-only `w_e = max(∂t h + ∇·(hU), 0)` 사용을 권장합니다. 깊어질 때의 냉각(엔트레인먼트) 해석이 명확하고, 음의 `w_e`(shoaling)로 인한 잡음·부호 전환을 억제해 닫힘(residual) 변동을 줄이는 경향이 있습니다. [Price et al. 1986 JGR: 야간 깊어짐·엔트레인먼트 사례 `references/MLHB/Price_Weller_Pinkel_1986_JGR_DiurnalCycling.pdf`], [Foltz 2013 JCLI: 북동열대대서양 MLHB 닫힘·항 기여 정량 `references/MLHB/Foltz_Schmid_Lumpkin_2013_JCLI_NETA_MLHB.pdf`], [Dong et al. 2007 JCLI: 남빙양 MLHB 평가 `references/MLHB/Dong_Gille_Sprintall_2007_JCLI_SouthernOcean_MLHB.pdf`]
- 보수적 대안: `w_e = ∂t h`(dh/dt only)은 단순·저잡음이 장점이나, 두께 발산 `∇·(hU)` 효과를 누락해 물리적 완결성이 떨어집니다. 비교 기준으로만 사용하세요. [Foltz 2013 JCLI: 방법 비교 맥락 `references/MLHB/Foltz_Schmid_Lumpkin_2013_JCLI_NETA_MLHB.pdf`]
- 비권장 정의: `Dh/Dt = ∂t h + U_m·∇h`만 사용할 경우 필요한 `h∇·U_m` 항을 빠뜨려 두께 연속과 일치하지 않습니다(혼합층 두께 방정식에 부합하지 않음). [Dong 2007 JCLI: 두께 연속 기반 진단 `references/MLHB/Dong_Gille_Sprintall_2007_JCLI_SouthernOcean_MLHB.pdf`], [Foltz 2013 JCLI: 두께항 구성 `references/MLHB/Foltz_Schmid_Lumpkin_2013_JCLI_NETA_MLHB.pdf`]
- 관련 항목: 수직 확산(DIFFV)과의 분리 해석은 필수입니다. 대서양 콜드텅에서의 유의한 난류(등밀도면 횡단) 열수송 기여가 보고됩니다. [Hummels et al. 2014 Clim Dyn: `references/MLHB/Hummels_etal_2014_ClimDyn_AtlanticColdTongue_MLHB.pdf`], [Large et al. 1994 Rev. Geophys.: KPP 경계층 `references/MLHB/Large_McWilliams_Doney_1994_KPP_review.pdf`]
- MLD 선택 민감도: `h` 정의(임계값, 참조깊이, 제품 vs 재계산)가 MLHB 항(특히 ENT, QNET/ρCp h)에 큰 영향을 줍니다. 분석·보고 시 MLD 설정을 명시하세요. [de Boyer Montégut et al. 2004 JGR: Δσ₀ 임계값·기후학 `references/MLHB/deBoyerMontegut_etal_2004_JGR_MLD.pdf`], [Elzahaby et al. 2022 Frontiers in Climate: MHW 진단의 MLD 민감도 `references/MLHB/Elzahaby_etal_2022_Frontiers_MLD_MLHB_Diagnostics.pdf`]

## 세부 근거와 해석
### 용어 정리
- **Entrainment**: 혼합층이 깊어질 때(`w_e > 0`) 하층의 물이 혼합층으로 편입되며 표층을 주로 냉각한다.
- **Detrainment**: 혼합층이 얕아질 때(`w_e < 0`) 혼합층 물이 아래로 빠져나가며 shoaling 구간의 가열/냉각 잔차는 detrainment에 해당한다.

1) 두께 연속과 표준 `w_e`
- 혼합층 두께 `h`의 연속 방정식으로부터 `w_e = ∂t h + ∇·(hU_m)`가 유도되며, 다수의 관측 기반 MLHB 연구가 이 형태(또는 이에 상응하는 두께 변화·발산 분해)를 채택합니다. [Foltz 2013 JCLI `references/MLHB/Foltz_Schmid_Lumpkin_2013_JCLI_NETA_MLHB.pdf`], [Dong 2007 JCLI `references/MLHB/Dong_Gille_Sprintall_2007_JCLI_SouthernOcean_MLHB.pdf`]

2) dh/dt만 사용할 때의 장·단점
- 장점: 구현 단순·저잡음으로 관측 기반 격자장에서 안정적입니다. [Foltz 2013 JCLI `references/MLHB/Foltz_Schmid_Lumpkin_2013_JCLI_NETA_MLHB.pdf`]
- 단점: `∇·(hU)` 효과를 누락해 전선/연안 수렴·발산의 `w_e` 구성 성분을 반영하지 못합니다. [Dong 2007 JCLI `references/MLHB/Dong_Gille_Sprintall_2007_JCLI_SouthernOcean_MLHB.pdf`]

3) deepening-only의 물리적 해석과 닫힘
- 해양 관측·모형에서 엔트레인먼트는 주로 혼합층이 깊어질 때(야간 냉각/풍혼합) 활성화되어 표층 냉각에 기여하는 것으로 관측·모형화됩니다. [Price 1986 JGR `references/MLHB/Price_Weller_Pinkel_1986_JGR_DiurnalCycling.pdf`]
- 관측 기반 월평균 MLHB에서는 음의 `w_e`(shoaling)에 의한 부호 전환·잡음을 억제하기 위해 `w_e>0`만 사용(deepening-only)하거나 경계조건을 두는 접근이 흔하며, 닫힘 잔차의 변동이 감소하는 경향이 보고됩니다. [Foltz 2013 JCLI `references/MLHB/Foltz_Schmid_Lumpkin_2013_JCLI_NETA_MLHB.pdf`], [Dong 2007 JCLI `references/MLHB/Dong_Gille_Sprintall_2007_JCLI_SouthernOcean_MLHB.pdf`]

4) DIFFV(수직 확산)와의 분리
- 등밀도면을 통한 난류 열수송(수직 확산/혼합) 기여는 엔트레인먼트 항과 구분해 진단해야 하며, 특정 해역/계절에는 상당한 비중을 가질 수 있습니다. [Hummels 2014 Clim Dyn `references/MLHB/Hummels_etal_2014_ClimDyn_AtlanticColdTongue_MLHB.pdf`], [Large 1994 Rev. Geophys. `references/MLHB/Large_McWilliams_Doney_1994_KPP_review.pdf`]

5) MLD 정의의 영향
- Δσ₀ 임계값·참조깊이 선택과 제품(`mlotst`) vs 재계산 여부가 `h`를 통해 ENT, QNET/ρCp h를 바꾸며, 사건 해석·속성 추정에 민감합니다. 문서화·민감도 분석이 권장됩니다. [de Boyer Montégut 2004 JGR `references/MLHB/deBoyerMontegut_etal_2004_JGR_MLD.pdf`], [Elzahaby 2022 Frontiers `references/MLHB/Elzahaby_etal_2022_Frontiers_MLD_MLHB_Diagnostics.pdf`]

## 코드 구현 매핑(레포)
- CLI: `--we-mode {dhdt, deepening, full, centered, centered_deepening}` — `src/process_d2nf.py`
- 해석 프리셋: 보수(`--use-hbar-denom --we-mode dhdt`), 자연해석(`--we-mode deepening`) — `docs/guidelines/10_analysis_methods/heat_budget/README.md`
- MLD 재계산(Δσ₀=0.03, ref=10 m) 기본 — `docs/guidelines/10_analysis_methods/heat_budget/manual.md`

## 참고 문헌(로컬 PDF)
- Price, Weller & Pinkel (1986) JGR — `references/MLHB/Price_Weller_Pinkel_1986_JGR_DiurnalCycling.pdf`
- Large, McWilliams & Doney (1994) Rev. Geophys. — `references/MLHB/Large_McWilliams_Doney_1994_KPP_review.pdf`
- de Boyer Montégut et al. (2004) JGR — `references/MLHB/deBoyerMontegut_etal_2004_JGR_MLD.pdf`
- Dong, Gille & Sprintall (2007) JCLI — `references/MLHB/Dong_Gille_Sprintall_2007_JCLI_SouthernOcean_MLHB.pdf`
- Foltz, Schmid & Lumpkin (2013) JCLI — `references/MLHB/Foltz_Schmid_Lumpkin_2013_JCLI_NETA_MLHB.pdf`
- Hummels et al. (2014) Clim Dyn — `references/MLHB/Hummels_etal_2014_ClimDyn_AtlanticColdTongue_MLHB.pdf`
- Elzahaby et al. (2022) Frontiers in Climate — `references/MLHB/Elzahaby_etal_2022_Frontiers_MLD_MLHB_Diagnostics.pdf`
