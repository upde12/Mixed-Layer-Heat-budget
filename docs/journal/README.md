# Daily Journal Workflow

## 목표
- 매일 작업 시작과 종료 시 루틴을 표준화해 연속성과 회고 효율을 높입니다.
- 오답노트와 연계해 에러 대응 경험도 함께 축적합니다.

## 디렉터리 구조
```
docs/journal/
  README.md
  templates/
    daily_template.md
  YYYY/
    YYYY-MM-DD.md (자동/수동 생성)
```

## 출근 인사("안녕?") 시 수행
1. `scripts/journal_start.py`를 실행해 전날 `Next Steps`를 자동으로 가져오고 해당 날짜 일지를 생성/업데이트합니다. 스크립트는 전날 완료 항목을 `Yesterday Recap`에 채워 줍니다.
2. `Focus for Today` 항목을 검토하고 필요하면 추가 수정합니다.
3. 오답노트를 미리 검색합니다 (`scripts/search_error_notes.py <키워드>`).
4. 작업 중 발생할 문제에 대비해 `Issues & References` 섹션 링크 자리를 잡아둡니다.

## 퇴근 인사("퇴근할게 수고했어") 시 수행
1. `scripts/journal_end.py`를 실행해 미완료 항목을 자동으로 `Next Steps`로 이동시킵니다.
2. 오늘 완료한 작업을 `Work Log`/`Focus for Today`에 수동으로 체크하고 세부 내용을 보강합니다.
3. 새로 만든 오답노트나 업데이트한 기록을 `Issues & References`에 연결합니다.
4. 필요하다면 요약을 주간/월간 문서로 옮겨 장기 추세를 쌓습니다.

## 자동화 제안
- `scripts/journal_start.py`, `scripts/journal_end.py`를 alias로 등록해 출근/퇴근 인사와 함께 호출하면 루틴이 자동으로 수행됩니다.

> **원칙**: 하루는 반드시 "안녕?" → `Next Steps` 확인 → 작업 기록 → "퇴근할게 수고했어" → 회고 순으로 마무리합니다.
