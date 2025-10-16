# 부록: 대체 기준·특수 처리(참고용, moved)

> 안내: 이 문서는 MLHB 전용 프로젝트로 이동했습니다(위치 안내: MLHB/docs/heat_budget/appendix_alternatives.md). 본 레포에서는 개요/인덱스만 유지합니다.

본 문서는 운영 매뉴얼에서 사용하지 않는 보조 방법을 참고용으로 정리합니다. 특정 선행연구의 재현이 필요한 경우에만 선택적으로 활용하세요.

## A. 대체 MLD 기준
- 온도 임계값(temperature threshold): 10 m 대비 ΔT ≥ 0.2–0.5 °C.  
  - 출처 예: Monterey & Levitus (1997); de Boyer Montégut et al. (2004) 요약.  
  - 주의: 담수층/염분 변동에 취약. 본 운영에서는 사용하지 않음.

- 구배 기준(gradient method): |∂σ₀/∂z| 또는 |∂T/∂z|이 임계값을 넘는 첫 깊이.  
  - 잡음이 큰 경우 보조 지표로 사용되는 관행이 있으나, 스칼라 임계 설정에 민감.

## B. 특수 상황 처리(대안)
- 완전혼합 구조로 임계 교차 없음: 일부 알고리즘에서는 “MLD = 최대 관측(모델) 깊이 또는 수심”으로 대치하는 관행이 있음.  
  - 본 운영은 임의 대치를 피하고 결측(NA) 처리 후 분석에서 제외.

- 표층 담수 스파이크 완화: 최상층(3–5 m) median/box smoothing 후 재평가하는 실무 사례가 있으나, 표준화된 문헌 합의는 제한적.  
  - 본 운영은 스무딩을 적용하지 않음.

## C. 참고 문헌
- Monterey, G., & Levitus, S. (1997). NOAA NESDIS Atlas 14.  
- de Boyer Montégut, C., et al. (2004). JGR Oceans, 109(C12003).  
