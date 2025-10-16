# 11) 컨텍스트 초과 비상 복구 지침
<!-- owner: MLHB-core; canonical: true; depends_on: docs/guidelines/01_llm_guidelines.md, docs/guidelines/03_code_execution.md, docs/guidelines/05_storage_output_guidelines.md, docs/guidelines/09_reporting_guidelines.md; last_review: 2025-10-13 -->

## A. 배경/트리거
- 트리거: 대화 입력이 모델 컨텍스트 한도를 초과해 스트림이 끊기는 경우.
- 대표 메시지: `Your input exceeds the context window of this model. Please adjust your input and try again.`
- 위험: 미완 성과물/메시지 손실, 이후 대화 불가. 즉시 임시 보전 → 정식 저장 → 일지 기록 → 문서화 순으로 복구한다.

## B. 60초 트리아지(즉시)
1. 붙여넣은 전체 대화를 임시 보전: `docs/discussions/transcripts/<DATE>_session_paste.tmp.txt`.
2. 오늘 핵심/경로만 5–7줄 메모: `docs/journal/tmp/<DATE>_notes.md`.
3. 재시작 원칙만 확정: Core Mode + `size=7` + `no-run`(확장/자동 실행 억제). 참조: `docs/guidelines/01_llm_guidelines.md`.

## C. 미저장 구간 판별(붙여넣기 vs 기존 RAW 비교)
- 기준 파일
  - 기존 원문: `docs/discussions/transcripts/<DATE>_session_raw.txt`
  - 붙여넣기: `docs/discussions/transcripts/<DATE>_session_paste.tmp.txt`
- 절차(권장: 앵커 방식)
  1) 붙여넣기 끝에서부터 `stream error:`/공백을 제외한 마지막 의미 줄을 역순으로 훑어, 기존 RAW에도 존재하는 “마지막 공통 줄(anchor)”을 찾는다.
  2) 붙여넣기에서 그 앵커의 마지막 발생 이후 라인을 “미저장 꼬리(tail)”로 추출 → `docs/discussions/transcripts/<DATE>_session_tail_unsaved.txt`.
- 간단 대안(diff; 순서/중복에 민감)
```bash
diff --new-line-format='%L' --old-line-format='' --unchanged-line-format='' \
  docs/discussions/transcripts/<DATE>_session_raw.txt \
  docs/discussions/transcripts/<DATE>_session_paste.tmp.txt \
  > docs/discussions/transcripts/<DATE>_session_tail_unsaved.txt
```

## D. 부산물(산출 파일) 수집
- 시간창: 끊김 시각±10분(붙여넣기에 보이는 마지막 타임스탬프가 있으면 기준으로 사용).
- 변경/신규 파일 확인
```bash
git status -s > docs/discussions/recovery/<DATE>_artifacts_gitstatus.txt
find . -type f -newermt '<YYYY-MM-DD HH:MM>' ! -path './.git/*' \
  > docs/discussions/recovery/<DATE>_artifacts_newer_than.txt
```
- 요약본(상대 경로)만 보고서/일지에 기재하고, 대화에는 “경로+라인” 참조만 사용.

## E. 임시 메모/일지 루틴 연계
- 즉시 메모(타임스탬프+작업 디렉터리 자동 기록)
```bash
python3 llm-ops/scripts/log_tmp_note.py "Context overflow: 미저장 꼬리 추출/부산물 수집 착수" --workdir "$PWD"
```
- 맥락 확보(전날 Next Steps/최근 7일 완료)
```bash
python3 llm-ops/scripts/journal_start.py
```

## F. 정식 저장(원자적)
- 원칙: 최종 파일에 직접 쓰지 말고 `*.tmp`로 작성 후 `os.replace`(원자적 교체). 참조: `docs/guidelines/05_storage_output_guidelines.md` F.
- 병합 예시(미저장 tail을 RAW 뒤에 덧붙이기)
```bash
cat docs/discussions/transcripts/<DATE>_session_raw.txt \
    docs/discussions/transcripts/<DATE>_session_tail_unsaved.txt \
  > docs/discussions/transcripts/<DATE>_session_raw.txt.tmp && \
mv docs/discussions/transcripts/<DATE>_session_raw.txt.tmp \
   docs/discussions/transcripts/<DATE>_session_raw.txt
```

## G. 문서화(복구 노트)
- 경로: `docs/discussions/recovery/<DATE>_context_overflow_recovery.md`
- 포함: 배경/시점/증상/앵커 요약/미저장 라인 수/산출물 목록/조치/다음 액션/근거 경로.
- 템플릿: `docs/discussions/recovery/RECOVERY_template.md` 참조.

## H. 재시작 프롬프트 템플릿(대화 최소 시드)
```
Core Mode, no-run, size=7, scope=<선택: exec|plot|report|storage|ref>
오늘 목표(≤3): 1) … 2) … 3) …
마지막 성공 지점(앵커 요약): …
참조 파일(본문 금지): path:line, path:line
질문(≤3): 1) … 2) … 3) …
```

## I. 예방
- 긴 본문은 항상 파일에 저장 후 “경로+라인”만 대화에 공유(붙여넣기 금지).
- `size=N` 상시 지정, 스코프 명시(`scope=…`)로 자동 확장 억제. 참조: `docs/guidelines/01_llm_guidelines.md` B‑0.
- 결과물 저장은 항상 원자적(`*.tmp`→교체); scratch 열람 금지(최종 산출만 사용). 참조: `docs/guidelines/05_storage_output_guidelines.md` F.
- 실행 로그/옵션/경로는 일지와 함께 병기. 참조: `docs/guidelines/03_code_execution.md` E/H.

## J. 체크리스트(출고 전)
- [ ] 붙여넣기 임시본을 저장했고, 미저장 꼬리를 추출했다.
- [ ] 산출물(신규/변경) 목록을 수집/보관했다.
- [ ] RAW 원문에 꼬리를 병합했고, 원자적으로 교체했다.
- [ ] 복구 노트를 작성하고 근거 경로를 포함했다.
- [ ] `journal_end.py --notes`로 요약을 기록했다.

## K. 빠른 실행 스니펫
```bash
# 1) 붙여넣기 보전
cat > docs/discussions/transcripts/<DATE>_session_paste.tmp.txt

# 2) 미저장 꼬리(간단 diff 버전)
diff --new-line-format='%L' --old-line-format='' --unchanged-line-format='' \
  docs/discussions/transcripts/<DATE>_session_raw.txt \
  docs/discussions/transcripts/<DATE>_session_paste.tmp.txt \
  > docs/discussions/transcripts/<DATE>_session_tail_unsaved.txt

# 3) 병합(원자적 교체)
cat docs/discussions/transcripts/<DATE>_session_raw.txt \
    docs/discussions/transcripts/<DATE>_session_tail_unsaved.txt \
  > docs/discussions/transcripts/<DATE>_session_raw.txt.tmp && \
mv docs/discussions/transcripts/<DATE>_session_raw.txt.tmp \
   docs/discussions/transcripts/<DATE>_session_raw.txt

# 4) 산출물 목록화
git status -s > docs/discussions/recovery/<DATE>_artifacts_gitstatus.txt
find . -type f -newermt '<YYYY-MM-DD HH:MM>' ! -path './.git/*' \
  > docs/discussions/recovery/<DATE>_artifacts_newer_than.txt

# 5) 일지 기록
python3 llm-ops/scripts/log_tmp_note.py "Context overflow: 복구 완료/산출물 N건" --workdir "$PWD"
python3 llm-ops/scripts/journal_end.py --notes "Context overflow 복구: 미저장 N줄 병합, 산출물 M건, 다음 3액션: …"
```

