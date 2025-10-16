# (옵션) 4) 보너스: 용어·파일 매핑 및 빠른 품질진단 치트시트

## 용어/기호
- \(T_m\): 혼합층 평균 온도, \(T_b\): 혼합층 바닥 온도, \(\Delta T=T_m-T_b\)
- \(h\): 혼합층 깊이(MLD), \(w_e=\partial_t h+\nabla\!\cdot(h\mathbf v_m)\)
- QNET: \((\mathrm{SW}+\mathrm{LW}+\mathrm{LHF}+\mathrm{SHF}-q(h))/(\rho c_p h_{\rm den})\)
- ADV: \(-u_m\partial_xT_m-v_m\partial_yT_m\)
- DIFF: \((A_h/h_{\rm den})\nabla\!\cdot[h\nabla T_m-\Delta T\nabla h]\)
- DIFFV: \(-K_v/h_{\rm den}\cdot(\partial T/\partial z)|_{-h}\)

## 파일/변수 매핑
- 연도별 NetCDF: `ml_budget_YYYY.nc`
- 변수: `T_ML`(Tm), `Tb`(Tb), `T0`(T(0)), `MLD`(h),
  `TEN`, `TEN_cen`, `ADV`, `QNET`, `ENT`, `DIFF`, `DIFFV`,
  `CLOS_d2_ten`, `CLOS_d2_ten_cen`

## 빠른 통계(GrADS)
```grads
* 열기
sdfopen ml_budget_2016.nc

* dT
define dT = T_ML - Tb
set gxout stat; d dT

* ENT / 닫힘
define C = TEN - (QNET + ADV + ENT + DIFF + DIFFV)
d ENT; d C
```
