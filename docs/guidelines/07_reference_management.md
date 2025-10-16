# 7) 참고문헌 관리 지침
<!-- owner: MLHB-core; canonical: true; depends_on: docs/guidelines/05_storage_output_guidelines.md; last_review: 2025-09-30 -->

본 문서는 참고문헌(PDF 원문), 요약본, 개요(overview) 관리 규칙을 정의합니다. 과학적 토론/발표의 근거 제시 원칙은 `docs/guidelines/06_scientific_communication.md`를 따릅니다.

## A. 저장 위치와 구조
- 루트 기준 `references/<주제>/`에 원문 PDF를 저장한다. 예: `references/MLHB/`, `references/EA_warming/`.
- 각 주제 폴더에는 `README.md`를 두고 파일명, DOI, 원문 링크, 소스를 기록한다.
- 논문별 요약본은 해당 주제 폴더의 `_extracted/` 하위에 Markdown으로 저장한다. 예: `references/MLHB/_extracted/Price1986_...md`.
- 슬라이드·발표에서 추출한 요약은 `presentation/_extracted/`에 저장하며, 원 논문 요약과 중복될 경우 상호 링크를 건다.

## B. 파일명·메타데이터 규칙
- PDF 파일명 권장 형식: `FirstAuthor_LastName_Year_Journal_ShortKey.pdf`  
  예: `Price_Weller_Pinkel_1986_JGR_DiurnalCycling.pdf`
- 경로·링크는 항상 루트 기준 상대 경로를 사용한다.
- `README.md`에는 최소한 다음을 기록한다: 제목, 저자, 연도, 저널/출판처, DOI/URL, 로컬 파일 경로.

## C. 개요(overview) 정리 규칙
- `overview.md`는 주제별 참고 요약 모음이다. 항목 정렬은 첫 번째 저자 성(Last name) 기준 A–Z 순서로 한다.
- 항목에는 핵심 결론·핵심 수치·그림/표 번호(예: “Fig. 1a–c”, “Table 2”)를 포함한다.

## D. 요약본(`_extracted/`) 작성·갱신 규칙
- 저장된 요약본이 있는 논문을 참조할 때는 요약본을 먼저 읽고 핵심 내용을 파악한다.
- 요약본만으로 부족할 때 본문을 직접 확인하여 필요한 정보(결론·수치·그림/표 번호)를 보강한다.
- 사용자의 요구에 응답하면서 특정 논문의 세부 정보를 활용했다면, 응답 직전에 해당 내용을 간단히 정리해 요약본에 추가한다.
- 새로 참조한 논문에 요약본이 없으면 최소 템플릿(서지, 범위, 방법, 주요 결과)을 작성한다.

## E. 운영 워크플로(요약)
1) PDF 확보 → 적절한 `references/<주제>/`로 이동·파일명 규칙 적용.  
2) `README.md`에 DOI/링크/파일 경로 기록.  
3) `_extracted/`에 요약본 작성 또는 갱신.  
4) 필요 시 `overview.md` 갱신(A–Z 정렬 유지).  
5) 저장 지시 시, 오늘 추가·수정한 개요·요약 항목을 `journal_end.py --notes`에 반영.

## F. 품질 체크리스트
- [ ] 파일명·경로 규칙 준수(상대경로).  
- [ ] `README.md`에 DOI/URL/소스 기록.  
- [ ] 개요 정렬(A–Z) 및 그림/표 번호 표기.  
- [ ] 요약본에 핵심 결론·수치·도표 참조 포함.  
- [ ] 외부 탐색 시 `06_scientific_communication.md`의 검색·보고 규칙 준수.

