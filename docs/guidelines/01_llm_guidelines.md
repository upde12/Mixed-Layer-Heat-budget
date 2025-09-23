# 3) 일일 운영 및 LLM 지침

## A. 공통 용어와 참조
- `루트` = `~/Desktop/GPT/Mixed-Layer-Heat-budget`, `리포` = `upde12/Mixed-Layer-Heat-Budget`.
- `오답노트` = `docs/error_notes/` 이하 기록물, `패턴 로그` = `data/efficiency_patterns.json`.
- 파일·경로를 언급할 때는 항상 루트 기준 상대 경로를 사용한다.

## B. 일일 루틴 개요
- 하루를 시작할 때 이 지침을 먼저 읽고, 곧바로 `python3 scripts/journal_start.py`를 실행해 `Yesterday Recap`과 `Next Steps`를 불러온다.
- 진행 상황을 기록하라는 요청이 있으면 즉시 `python3 scripts/journal_end.py`를 실행해 현재까지의 작업을 일지에 반영한다.
- 오답노트 참고·갱신 이력은 일지 `Issues & References` 섹션에 남긴다.
- 지도·시각화 등 특수 작업이 예상되면 해당 지침을 확인하고 공유한다. 열수지 분석을 진행할 때만 `docs/guidelines/04_heat_budget_guidelines.md`를 연다.

## C. 시작 루틴
1. 이 문서를 열고 바로 `python3 scripts/journal_start.py`를 실행해 전날 `Next Steps`와 `Yesterday Recap`을 불러온다.
2. 오늘 작업과 맞닿는 키워드로 `python3 scripts/search_error_notes.py <키워드>`를 실행하고 참고할 내용이 있으면 요약해 공유한다.
3. 지도/시각화 요청이 예상되면 `docs/guidelines/02_plot_guidelines.md`와 관련 오답노트를 확인했음을 명시한다.
4. 필요한 경우 빠른 참고 자료는 `docs/cheatsheet/01_quick_checks.md`를 우선 조회한다.
5. 필요한 데이터를 미리 준비하고, 예상 리스크를 일지 `Issues & References`에 적어둔다.

## D. 진행 중 운영 규칙
- 각 명령·실험의 목적을 먼저 말하고 실행한다. 결과 요약 시 핵심 수치와 경로만 전달한다.
- 사용자에게 전달하는 모든 최종 응답은 기본적으로 한국어로 작성한다.
- 에러가 발생하면 메시지·스택트레이스를 모두 기록하고, 같은 메시지로 오답노트를 재검색한 뒤 원인 규명 → 수정 방안을 순차적으로 제안·수행한다.
- 사용자가 결과에 불만족할 때는 피드백을 정리하고 수정 방향을 합의한 뒤 재시도하며, 변경 사항과 효과를 요약해 보고한다. 이때 `docs/error_notes/<카테고리>/`에 `note_template.md`를 기반으로 조치 기록을 남기고, 반복 원인으로 판단되면 `python3 scripts/pattern_tracker.py log --tags user-feedback --note "<핵심요약>"`을 실행해 `data/efficiency_patterns.json`을 갱신한다.
- 외부 지침(예: 코드 리뷰 모드 요청, 테스트 정책)이 주어지면 해당 모드에서 기대되는 산출물과 제한을 먼저 확인하고 나서 작업한다.

## E. 종료 루틴
1. 하루를 마무리하거나 지금까지의 진행 상황을 저장할 때 `python3 scripts/journal_end.py`를 실행해 `Focus for Today` 미완료 항목을 `Next Steps`로 정리한다.
2. 일지 `Work Log`에 주요 작업과 산출물 경로를 기록하고 `Focus for Today` 완료 여부를 체크한다.
3. 새로 만든 오답노트·패턴 기록을 링크하며, 학습한 교훈이나 에러 처리를 문서화한다.
4. 다음 업무에 바로 착수할 작업을 3개 이하로 명확히 적는다.

## F. 패턴 및 비효율 관리
- 동일한 비효율이나 반복 수정이 세 번째 등장하면 `python3 scripts/pattern_tracker.py log --tags scope-mismatch` 등으로 패턴을 기록하고, `docs/error_notes/templates/efficiency_pattern_template.md`의 항목을 채운다.
- 주간 회고 시점에는 `python3 scripts/pattern_tracker.py weekly-review --note "<메모>"`로 누적 패턴을 점검하고 필요한 지침 초안을 제안한다.
- 패턴 기록 여부와 연계된 오답노트 링크를 일지 `Issues & References`에 남긴다.

## G. 자동화 및 스크립트 메모
- `docs/journal/templates/daily_template.md` 기반 날짜별 파일 생성 스크립트를 유지하고, 지침 열람/진행 상황 저장 명령 시 자동 호출을 검토한다.
- 필요 시 `journal_start.py`, `journal_end.py` 스크립트에 CLI `--start`/`--end` 옵션을 추가해 템플릿 생성과 체크리스트 출력을 지원한다.
