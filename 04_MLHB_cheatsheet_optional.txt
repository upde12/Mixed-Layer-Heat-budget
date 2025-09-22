# (옵션) 4) 보너스: 용어·파일 매핑 및 빠른 품질진단 치트시트

## 용어/기호
- \(T_m\): 혼합층 평균 온도, \(T_b\): 혼합층 바닥 온도, \(\Delta T=T_m-T_b\)
- \(h\): 혼합층 깊이(MLD), \(w_e=\partial_t h+\nabla\!\cdot(h\mathbf v_m)\)
- QNET: \((\mathrm{SW}+\mathrm{LW}+\mathrm{LHF}+\mathrm{SHF}-q(h))/(\rho c_p h_{\rm den})\)
- ADV\_NF: \(-u_m\partial_xT_m-v_m\partial_yT_m\)
- DIFF: \((A_h/h_{\rm den})\nabla\!\cdot[h\nabla T_m-\Delta T\nabla h]\)
- DIFFV: \(-K_v/h_{\rm den}\cdot(\partial T/\partial z)|_{-h}\)

## 파일 매핑
- `T_MLYYYY`=Tm, `TbYYYY`=Tb, `T0YYYY`=T(0), `MLDYYYY`=h
- `tenYYYY`, `ten_cenYYYY`, `advNFYYYY`, `qnetYYYY`, `entYYYY`, `diffYYYY`, `diffvYYYY`
- `clos_d2_tenYYYY`, `clos_d2_ten_cenYYYY`

## 빠른 통계(GrADS)
```grads
* dT
open T_ML.ctl; open Tb.ctl
define dT = T_ML - Tb
set gxout stat; d dT

* ENT / 닫힘
open ent.ctl; open ten.ctl; open qnet.ctl; open advNF.ctl; open diff.ctl; open diffv.ctl
define C = ten - (qnet + advNF + ent + diff + diffv)
d ent*86400; d C
```
