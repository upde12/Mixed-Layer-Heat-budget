# Context Overflow Recovery Note — <YYYY-MM-DD>
<!-- owner: MLHB-core; last_review: 2025-10-13 -->

## 1) 배경/시점/증상
- 시각: <HH:MM>
- 증상: Your input exceeds the context window… (stream error 반복)
- 영향: 대화 중단, 미완 메시지/산출물 보전 필요

## 2) 앵커와 미저장 꼬리
- 마지막 공통 줄(앵커) 요약: "…"
- 미저장 라인 수: N
- 파일: `docs/discussions/transcripts/<DATE>_session_tail_unsaved.txt`

## 3) 산출물(부산물)
- 신규/변경 목록 요약: M건
- 파일: `docs/discussions/recovery/<DATE>_artifacts_gitstatus.txt`, `..._artifacts_newer_than.txt`

## 4) 조치(실행)
- 붙여넣기 임시 보전 완료
- 미저장 꼬리 추출/검토 완료
- RAW 병합(원자적 교체) 완료
- 일지 기록(journal_end) 완료

## 5) 다음 액션(≤3)
1) …
2) …
3) …

## 6) 근거 경로(본문 금지; 경로+라인)
- `docs/discussions/transcripts/<DATE>_session_raw.txt`
- `docs/guidelines/11_context_overflow_emergency_recovery.md`

