# 3) 일일 운영 및 LLM 지침

## A. 공통 용어와 참조
- `루트` = `~/Desktop/GPT/Mixed-Layer-Heat-budget`, `리포` = `upde12/Mixed-Layer-Heat-Budget`.
- `오답노트` = `docs/error_notes/` 이하 기록물, `패턴 로그` = `data/efficiency_patterns.json`.
- 파일·경로를 언급할 때는 항상 루트 기준 상대 경로를 사용한다.
- 저장·출력 경로 결정 규칙은 `docs/guidelines/05_storage_output_guidelines.md`를 우선 확인한다.
- 과학적 글쓰기·발표·토론 시에는 `docs/guidelines/06_scientific_communication.md`의 근거 제시 원칙을 따른다.

## B. 시작 루틴
이 지침을 확인하면 아래 절차를 즉시 수행한다. 응답에서는 지침을 확인했다는 사실만 간단히 언급하고, 확인한 문서를 일일이 나열하지 않는다. 사용자가 의문문으로 질문할 때는 우선 질문 자체에 답하고, 추가 작업(예: 그림 생성)은 명령형 요청이 있을 때만 진행한다. "저장" 또는 기록 요청을 받으면 아래 절차에 따라 즉시 `python3 scripts/journal_end.py --notes "<요약>"` 형태로 실행해 내용을 기록한다.
1. 지침 확인 직후 `python3 scripts/journal_start.py`를 실행해 전날 `Next Steps`와 최근 7일 완료 항목을 불러오고, 스크립트가 출력한 요약/추천 사항을 간단히 정리해 공유한다.
2. 오늘 작업과 맞닿는 키워드로 `python3 scripts/search_error_notes.py <키워드>`를 실행하고 참고할 내용이 있으면 요약해 공유한다.
3. 지도/시각화 요청이 예상되면 `docs/guidelines/02_plot_guidelines.md`와 관련 오답노트를 확인했음을 명시한다.
4. 필요한 경우 빠른 참고 자료는 `docs/cheatsheet/01_quick_checks.md`를 우선 조회한다.
5. 필요한 데이터를 미리 준비하고, 예상 리스크를 일지 `Issues & References`에 적어둔다.
- `python3 scripts/journal_end.py` 실행 시 `--notes` 또는 `--notes-file`로 시간대·핵심 작업·주요 경로를 포함한 요약을 기록해 Work Log에 반영한다.
- 작업이 하나 끝날 때마다 `docs/journal/tmp/<date>_notes.md` 등에 시간·파일·핵심내용을 메모하고, 저장 직전 이 메모를 `journal_end.py --notes`에 반영한 뒤 초기화한다.
- `python3 scripts/log_tmp_note.py "<요약>"` 명령으로 해당 메모를 즉시 추가하고, 메모가 비어 있지 않은지 답변 전 항상 확인한다. 이 스크립트는 실행 위치(또는 `--workdir`로 지정한 경로)를 자동 기록하므로, 파일·디렉토리 추적이 가능하도록 필요 시 `--workdir`를 사용해 명확히 남긴다.
- 임시 메모는 `- HH:MM 설명 [dir: 경로1; 경로2]` 형식을 유지한다. 저장 시 `journal_end.py`가 이 기록을 시간 구간별 요약(예: `HH:MM–HH:MM | 작업 | 경로`)으로 변환해 Work Log에 반영한다.
- 저장 지시를 받으면 `journal_end.py` 실행 전에 오늘 추가·수정한 overview/glossary 등 참고 요약 항목을 정리해 `--notes`에 포함한다.

## C. 진행 중 운영 규칙
- 작업 중 읽거나 수정한 파일의 경로를 `[경로](경로)` 형태로 출력해 클릭 가능한 링크로 남긴다.
- 각 명령·실험의 목적을 먼저 말하고 실행한다. 결과 요약 시 핵심 수치와 경로만 전달한다.
- 사용자에게 전달하는 모든 최종 응답은 기본적으로 한국어로 작성한다.
- 외부/내부 검색 구분: 사용자가 “웹에서 검색/웹 검색/인터넷에서 찾아봐”라고 지시하면 외부 웹 탐색을 수행한다. “내부 검색/레포에서 찾아봐/repo 검색”은 리포지토리 내부에서만 검색한다. 외부 탐색 결과를 사용할 때는 `06_scientific_communication.md`의 외부 소스 규칙(신뢰도 평가, 인용 형식, 보고 항목)을 따른다.
- 진행 상황을 기록하라는 요청(예: "저장해")을 받으면 아래 순서를 따른다.
  1. 이번 대화에서 새로 드러난 비효율을 `scripts/pattern_tracker.py log`로 기록하고,
  2. 관련 이슈가 있다면 즉시 오답노트(`scripts/log_error_note.py`)를 갱신하며,
  3. 마지막으로 `python3 scripts/journal_end.py --notes "<요약>"`를 실행해 일지에 반영하며, 추가로 해당 노트에 이번 작업에서 다룬 주요 디렉터리·파일 경로를 명시한다.
- 오답노트 참고·갱신 이력은 일지 `Issues & References` 섹션에 기록한다.
- 사용자가 "대화 내용을 모두 저장해" 등 전체 기록 저장을 지시하면, 현재 채팅 세션을 즉시 `docs/discussions/` 이하에 있는 포맷(예: `transcripts/2025-09-23_session_raw.txt`) 그대로 정리해 추가한다.
- 오답노트를 새로 작성할 때는 관련 대화 기록 경로(`docs/discussions/...`)를 `--related` 항목에 포함해 추적 가능하도록 한다.
- 에러가 발생하면 메시지·스택트레이스를 모두 기록하고, 같은 메시지로 오답노트를 재검색한 뒤 원인 규명 → 수정 방안을 순차적으로 제안·수행한다.
- 사용자가 결과에 불만족할 때는 피드백을 정리하고 수정 방향을 합의한 뒤 재시도하며, 변경 사항과 효과를 요약해 보고한다. 이때 `docs/error_notes/<카테고리>/`에 `note_template.md`를 기반으로 조치 기록을 남기고, 반복 원인으로 판단되면 `python3 scripts/pattern_tracker.py log --tags user-feedback --note "<핵심요약>"`을 실행해 `data/efficiency_patterns.json`을 갱신한다.
- 지도·시각화 요청 시 `docs/guidelines/02_plot_guidelines.md`를, 열수지 분석 요청 시 `docs/guidelines/03_heat_budget_guidelines.md`를 읽고 필요한 내용을 공유한다.
- 외부 지침(예: 코드 리뷰 모드 요청, 테스트 정책)이 주어지면 해당 모드에서 기대되는 산출물과 제한을 먼저 확인하고 나서 작업한다.

## D. 종료 루틴
1. 하루를 마무리하거나 지금까지의 진행 상황을 저장할 때 `python3 scripts/journal_end.py`를 실행해 `Focus for Today` 미완료 항목을 `Next Steps`로 정리한다.
2. 일지 `Work Log`에 주요 작업과 산출물 경로를 기록하고 `Focus for Today` 완료 여부를 체크한다.
3. 새로 만든 오답노트·패턴 기록을 링크하며, 학습한 교훈이나 에러 처리를 문서화한다.
4. 다음 업무에 바로 착수할 작업을 3개 이하로 명확히 적는다.

## E. 패턴 및 비효율 관리
- 동일한 비효율이나 반복 수정이 세 번째 등장하면 `python3 scripts/pattern_tracker.py log --tags scope-mismatch` 등으로 패턴을 기록하고, `docs/error_notes/templates/efficiency_pattern_template.md`의 항목을 채운다.
- 주간 회고 시점에는 `python3 scripts/pattern_tracker.py weekly-review --note "<메모>"`로 누적 패턴을 점검하고 필요한 지침 초안을 제안한다.
- 패턴 기록 여부와 연계된 오답노트 링크를 일지 `Issues & References`에 남긴다.

## F. 자동화 및 스크립트 메모
- `docs/journal/templates/daily_template.md` 기반 날짜별 파일 생성 스크립트를 유지하고, 지침 열람/진행 상황 저장 명령 시 자동 호출을 검토한다.
- 필요 시 `journal_start.py`, `journal_end.py` 스크립트에 CLI `--start`/`--end` 옵션을 추가해 템플릿 생성과 체크리스트 출력을 지원한다.
