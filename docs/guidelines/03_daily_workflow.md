# 5) 일일 작업 루틴 지침

## A. 기본 규칙
- 매 작업일은 **"안녕?" 인사 → 전날 일지 확인 → 오늘 목표 설정**으로 시작한다.
- 업무 종료 시 **"퇴근할게 수고했어" 인사 → 일지 업데이트 → 미완료 항목을 `Next Steps`로 이동**한다.
- 오답노트를 참고/갱신하는 과정을 일지의 `Issues & References` 섹션에 기록한다.

## B. 시작 루틴 체크리스트
1. `scripts/journal_start.py`를 실행해 전날 일지의 `Next Steps`를 오늘 `Focus for Today`에 자동 배치하고, 완료 항목을 `Yesterday Recap`에 채운다.
2. `scripts/search_error_notes.py`로 전날 겪은 문제와 관련된 오답노트를 재확인한다.
3. 필요한 데이터를 미리 준비하고, 예상 리스크를 `Issues & References`에 적어둔다.

## C. 종료 루틴 체크리스트
1. `scripts/journal_end.py`를 실행해 `Focus for Today`에서 남은 항목을 `Next Steps`로 자동 이동시킨다.
2. 일지 `Work Log`에 주요 작업과 산출물 경로를 기록한다.
3. `Focus for Today`의 완료 여부를 체크하고, 새로운 교훈/에러 처리를 오답노트에 기록하고 일지에 링크한다.
4. 다음날 바로 착수할 작업을 3개 이하로 명확히 적는다.

## D. 자동화
- `docs/journal/templates/daily_template.md`를 기반으로 날짜별 파일을 생성할 수 있는 스크립트를 작성해두고, 출근/퇴근 인사 시 자동 호출을 검토한다.
- 필요 시 `journal_start.py`, `journal_end.py` 스크립트를 작성해 CLI에서 `--start`/`--end` 옵션으로 템플릿 생성과 체크리스트 출력을 지원한다.

> 일일 루틴을 지키면 프로젝트 맥락을 잃지 않고, 오답노트와 업무 기록이 자연스럽게 연결된다.
