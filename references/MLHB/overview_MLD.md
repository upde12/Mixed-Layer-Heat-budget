# Mixed Layer Depth (MLD) — Overview and Local References

본 문서는 혼합층 깊이(Mixed Layer Depth; MLD)의 정의, 구현 선택, 로컬 보관 중 핵심 참고문헌을 요약합니다. MLHB(혼합층 열수지) 분석에서 MLD 선택은 엔트레인먼트, QNET 분모 h, Tb 산정 등 여러 항에 직접적 영향을 주므로 일관된 기준을 유지합니다.

## A. 운영 정의와 권고
- 기본 정의(밀도 임계값): 10 m 참조 밀도 대비 Δσ₀ ≥ 0.03 kg m⁻³이 되는 가장 얕은 깊이. 참조 깊이=10 m. 코드 기본도 이 기준으로 재계산(recompute)합니다.
- 대체 기준(참고용): 온도 임계값/구배 기준은 운영에서는 사용하지 않으며, 재현 목적일 때만 별도 비교.
- 제품 MLD vs 재계산: Copernicus `mlotst`는 지역/계절별로 정의·스무딩이 상이할 수 있으므로, 기본은 재계산(recompute) 후 품질 점검을 수행합니다.

## B. 구현 메모(코드 연동)
- 소스: `src/process_d2nf.py`의 `--mld-source recompute`(기본), `--mld-threshold`, `--mld-ref-depth`로 조정 가능.
- 엔트레인먼트 we 및 ENT 항: h 선택이 `QNET/(ρCp h)` 분모, `ENT=(Tb−Tm)·we/h`, `DIFF`/`DIFFV`에도 관여.
- 품질 가드레일: 교차 실패 시 완전혼합 플래그로 기록, 해당 격자의 `ENT`/`DIFFV`를 0으로 처리(코드 구현 반영).

## C. 핵심 참고문헌(로컬 보관)
- de Boyer Montégut et al. (2004) JGR — Global MLD climatology; Δσ₀ 임계값 방법론 정립.
  - 파일: `deBoyerMontegut_etal_2004_JGR_MLD.pdf`
  - 포인트: 10 m 참조, Δσ₀ 임계값 범위(0.02–0.05) 민감도 평가, 전지구 기후학 제시.
- Monterey & Levitus (1997) NOAA Atlas 14 — 계절별 전지구 MLD 변동 종합.
  - 파일: `Monterey_Levitus_1997_NOAA_Atlas14.pdf`
  - 포인트: 온도/밀도 기준 비교, 계절 주기·분지별 특성.

관련(엔트레인먼트/경계층):
- Price, Weller & Pinkel (1986) JGR — 일변 혼합층 반응과 야간 엔트레인먼트.
  - 파일: `Price_Weller_Pinkel_1986_JGR_DiurnalCycling.pdf`
- Large, McWilliams & Doney (1994) Rev. Geophys. — KPP 경계층 모수화(수직 혼합·엔트레인먼트 근거).
  - 파일: `Large_McWilliams_Doney_1994_KPP_review.pdf`

## D. 실무 체크리스트
- Δσ₀=0.03, 참조=10 m로 재계산값과 제품 `mlotst`의 구조적 차이를 지도/프로파일로 점검.
- 민감도: Δσ₀∈[0.02, 0.05] 비교, 해빙 마스킹(sic>0.15), 얕은 대륙붕 수심 상한(MLD≤H) 검토.
- 결과 보고 시 MLD 정의·파라미터(임계값/참조깊이/소스)를 명시.

