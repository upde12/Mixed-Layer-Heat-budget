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
- `python3 scripts/log_tmp_note.py "<요약>"` 명령으로 해당 메모를 즉시 추가하고, 메모가 비어 있지 않은지 답변 전 항상 확인한다. 이 스크립트는 실행 위치(또는 `--workdir`로 지정한 경로)를 자동 기록하므로, 파일·디렉토리 추적이 가능하도록 필요 시 `--workdir`를 사용해 명확히 남긴다. 트리거 단어(`좋아`, `아니`) 사용 시에는 메모 본문에 트리거 단어를 직접 적지 말고, 당시 작업 맥락만 기록한다.
- 임시 메모는 `- HH:MM 설명 [dir: 경로1; 경로2]` 형식을 유지한다. 저장 시 `journal_end.py`가 이 기록을 시간 구간별 요약(예: `HH:MM–HH:MM | 작업 | 경로`)으로 변환해 Work Log에 반영한다.
- 저장 지시를 받으면 `journal_end.py` 실행 전에 오늘 추가·수정한 overview/glossary 등 참고 요약 항목을 정리해 `--notes`에 포함한다.

## 경량 실행 모드와 트리거
지침 확인으로 인한 지연을 줄이기 위해, 기본 동작은 “경량 모드”로 한다. 질문에 필요한 최소 범위의 지침만 조건부로 조회한다.

- 기본(경량 모드)
  - 불필요한 문서 일괄 확인을 생략한다. 필요한 경우에만 관련 지침을 연다.
  - 지침 확인 시간 예산: 최대 10초 또는 1–2개 파일 내 핵심 섹션만 확인.
  - 광범위 검토가 필요하면 먼저 의도를 확인한다(“자세히 볼까요?” 등).

- 트리거 기반 확인
  - 시각화(“그림/플롯/지도”, Cartopy/Matplotlib 언급) → `docs/guidelines/02_plot_guidelines.md` + 관련 오답노트만 확인
  - 과학 커뮤니케이션(“근거/인용/논증/발표/토론/슬라이드”) → `docs/guidelines/06_scientific_communication.md`만 확인
  - 저장/출력/경로(“저장/경로/외장/동기화/기본 출력”) → `docs/guidelines/05_storage_output_guidelines.md` 확인
  - MLHB 분석(“열수지/MLD/GLORYS/D2-NF/we-mode”) → 관련 코드/매뉴얼/오답노트만 확인

- 시작 루틴과의 관계
  - B-3(시각화 지침 확인)는 “시각화 트리거”가 있을 때만 수행한다.
  - 과학 커뮤니케이션 지침(06)은 사용자가 과학적 토의/발표/인용을 요청한 경우에만 확인한다.
  - 기타 지침도 해당 트리거가 있을 때만 열람·인용한다.

- 실행 예
  - 코드/개념 단답 질의: 경량 모드 유지, 문서 열람 생략 또는 1개 파일 제한
  - 그림 요청: 02 지침 + 관련 오답노트만 확인 후 진행
  - 슬라이드/논증 요청: 06 지침만 확인 후 근거 규칙 적용

위 원칙은 답변의 신속성을 우선하고, 필요 시에만 깊이 있는 지침을 참조하도록 하기 위한 것이다. 트리거 감지는 사용자 요청의 키워드와 현재 작업 맥락(최근 명령/파일 경로)을 함께 고려한다.

## C. 진행 중 운영 규칙
- 파일 경로 표기 규칙(클릭 가능 링크)
  - 채팅/CLI 응답: 경로를 백틱으로 감싸 `path` 또는 `path:line` 형태로 쓴다. 예) `docs/journal/2025/2025-09-29.md:2`
  - 문서/마크다운: `[텍스트] (타깃)` 형태로 쓴다. 예) `[docs/journal/2025/2025-09-29.md] (LLM_OPS/docs/journal/2025/2025-09-29.md)`
  - 임시 메모 형식: 예) `[dir: LLM_OPS/scripts] [LLM_OPS/scripts](LLM_OPS/scripts)` — 첫 번째 대괄호 블록은 파서용, 두 번째는 클릭용 링크다.
- 각 명령·실험의 목적을 먼저 말하고 실행한다. 결과 요약 시 핵심 수치와 경로만 전달한다.
- 언어 규칙(강화):
  - 사용자가 한국어로 말하면 반드시 한국어로 답한다. 별도 지시가 없으면 대화는 계속 한국어를 유지한다.
  - 사용자가 영어(또는 타 언어)로 요청하면 그 언어로 답하되, 이후 사용자가 한국어로 돌아오면 즉시 한국어로 복귀한다.
  - 코드/경로/명령/식별자 등은 원문 표기를 그대로 유지하고, 서술·해설은 한국어로 작성한다.
  - 외부 인용문·에러 로그는 원문을 보존하고, 해설·요약은 한국어로 제공한다.
  - 규칙을 위반해 비한국어 응답을 보냈다면 즉시 간단히 사과하고, 동일 내용의 한국어 요약을 이어서 제공한다. 또한 `python3 scripts/log_tmp_note.py "언어 규칙 위반: 영어 응답 → 한국어로 교정" --tag guidelines`로 메모를 남긴다.
- 사용자가 대화 중 "좋아" 또는 "아니"라고 말하면, 직전 작업 맥락을 요약해 `python3 scripts/log_tmp_note.py "Trigger <단어>: <맥락>" --workdir <경로>`를 즉시 실행해 트리거 로그를 남긴다. 실행 후에는 메모가 성공적으로 추가됐는지 확인하고, 누락을 인지한 경우 즉시 보완 기록을 남긴다.
- 외부/내부 검색 구분: 사용자가 “웹에서 검색/웹 검색/인터넷에서 찾아봐”라고 지시하면 외부 웹 탐색을 수행한다. “내부 검색/레포에서 찾아봐/repo 검색”은 리포지토리 내부에서만 검색한다. 외부 탐색 결과를 사용할 때는 `06_scientific_communication.md`의 외부 소스 규칙(신뢰도 평가, 인용 형식, 보고 항목)을 따른다.
 - 링크 제공(검증) 규칙: 외부 웹 주소를 제공하기 전에 반드시 다음을 확인한다.
   1) HTTP 상태가 200 OK인지, 2) 기대한 콘텐츠 유형(PDF/HTML)과 제목·키워드가 의도와 일치하는지.  
   - 403/404/리다이렉트만 보이는 주소나 세션/로그인 필요 링크는 그대로 제공하지 않는다. 대신 “접근 필요(기관/로그인)”를 명시하고, 사용자가 열 수 있는 최상위 랜딩/DOI만 안내한다.  
   - 링크가 불안정하거나 만료 위험이 있을 때는 경로만 설명하고(예: 저널 랜딩에서 PDF 버튼), 저장소에는 로컬 사본 경로를 병기한다(`references/...`).
- 진행 상황을 기록하라는 요청(예: "저장해")을 받으면 아래 순서를 따른다.
  1. 이번 대화에서 새로 드러난 비효율을 `scripts/pattern_tracker.py log`로 기록하고,
  2. 관련 이슈가 있다면 즉시 오답노트(`scripts/log_error_note.py`)를 갱신하며,
  3. 마지막으로 `python3 scripts/journal_end.py --notes "<요약>"`를 실행해 일지에 반영하며, 추가로 해당 노트에 이번 작업에서 다룬 주요 디렉터리·파일 경로를 명시한다.
- 오답노트 참고·갱신 이력은 일지 `Issues & References` 섹션에 기록한다.
- 사용자가 "대화 내용을 모두 저장해" 등 전체 기록 저장을 지시하면, 현재 채팅 세션을 즉시 `docs/discussions/` 이하에 있는 포맷(예: `transcripts/2025-09-23_session_raw.txt`) 그대로 정리해 추가한다.
- 긴 대화나 핵심 의사결정이 예상되면 초반에 `python3 scripts/create_transcript_stub.py --note "<맥락>"`로 템플릿을 생성해 두고, 세션 종료 전에 반드시 대화 전문을 붙여 넣어 `docs/discussions/transcripts/`에 남긴다. 여러 번 생성할 경우 `--suffix`로 구분하고, 저장 후 일지 `Issues & References`에 해당 경로를 적는다.
- 오답노트를 새로 작성할 때는 관련 대화 기록 경로(`docs/discussions/...`)를 `--related` 항목에 포함해 추적 가능하도록 한다.
- 에러가 발생하면 메시지·스택트레이스를 모두 기록하고, 같은 메시지로 오답노트를 재검색한 뒤 원인 규명 → 수정 방안을 순차적으로 제안·수행한다.
- 사용자가 결과에 불만족할 때는 피드백을 정리하고 수정 방향을 합의한 뒤 재시도하며, 변경 사항과 효과를 요약해 보고한다. 이때 `docs/error_notes/<카테고리>/`에 `note_template.md`를 기반으로 조치 기록을 남기고, 반복 원인으로 판단되면 `python3 scripts/pattern_tracker.py log --tags user-feedback --note "<핵심요약>"`을 실행해 `data/efficiency_patterns.json`을 갱신한다.
- 지도·시각화 요청 시 `docs/guidelines/02_plot_guidelines.md`를, 분석 방법 지침은 `docs/guidelines/10_analysis_methods/README.md`에서 해당 방법(예: 혼합층 열수지)을 찾아 참고한다.
- 외부 지침(예: 코드 리뷰 모드 요청, 테스트 정책)이 주어지면 해당 모드에서 기대되는 산출물과 제한을 먼저 확인하고 나서 작업한다.

### 메시지 전 송신 체크리스트(간단)
- [ ] 한국어로 작성했는가(사용자가 명시적으로 다른 언어를 요청하지 않았는가)?
- [ ] 경로/명령/코드는 백틱으로 감싸 클릭 가능하게 했는가?
- [ ] 불필요한 장황함 없이 바로 실행 가능한 다음 단계를 제시했는가?

## D. 종료 루틴
1. 하루를 마무리하거나 지금까지의 진행 상황을 저장할 때 `python3 scripts/journal_end.py`를 실행해 `Focus for Today` 미완료 항목을 `Next Steps`로 정리한다.
2. 일지 `Work Log`에 주요 작업과 산출물 경로를 기록하고 `Focus for Today` 완료 여부를 체크한다.
3. 새로 만든 오답노트·패턴 기록을 링크하며, 학습한 교훈이나 에러 처리를 문서화한다.
4. 다음 업무에 바로 착수할 작업을 3개 이하로 명확히 적는다.

### (주간) 월요일 아침 루틴
- 직전 주 주간 기록 생성: `python3 scripts/journal_weekly.py --prev` → `docs/journal/<YYYY>/weekly/<YYYY-Www>.md` 검토/보강.
- `Next Week Focus` 3개 확정 후 `scripts/pattern_tracker.py weekly-review --note "<주간 요약>"` 실행.

### (월간) 말일/초일 루틴
- `docs/journal/templates/monthly_template.md` 기반으로 `docs/journal/<YYYY>/monthly/<YYYY-MM>.md` 작성.
- 프로젝트 단위 진척도(%)와 핵심 산출물 경로를 반드시 포함한다.

## E. 패턴 및 비효율 관리
- 동일한 비효율이나 반복 수정이 세 번째 등장하면 `python3 scripts/pattern_tracker.py log --tags scope-mismatch` 등으로 패턴을 기록하고, `docs/error_notes/templates/efficiency_pattern_template.md`의 항목을 채운다.
- 주간 회고 시점에는 `python3 scripts/pattern_tracker.py weekly-review --note "<메모>"`로 누적 패턴을 점검하고 필요한 지침 초안을 제안한다.
- 패턴 기록 여부와 연계된 오답노트 링크를 일지 `Issues & References`에 남긴다.

## F. 자동화 및 스크립트 메모
- `docs/journal/templates/daily_template.md` 기반 날짜별 파일 생성 스크립트를 유지하고, 지침 열람/진행 상황 저장 명령 시 자동 호출을 검토한다.
- 임시 메모 태그: `scripts/log_tmp_note.py`는 `--proj`와 `--tag` 옵션을 지원해 `[proj: ...]`, `[tags: ...]`를 자동 부착한다(주간/월간 요약 그룹화 용).
- 필요 시 `journal_start.py`, `journal_end.py` 스크립트에 CLI `--start`/`--end` 옵션을 추가해 템플릿 생성과 체크리스트 출력을 지원한다.
