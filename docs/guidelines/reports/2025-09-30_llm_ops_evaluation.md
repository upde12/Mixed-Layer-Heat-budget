# LLM 운영 지침 평가 보고서 — MLHB (2025-09-30)
<!-- owner: MLHB-core; canonical: false; depends_on: docs/guidelines/01_llm_guidelines.md, docs/guidelines/06_scientific_communication.md, docs/guidelines/05_storage_output_guidelines.md, scripts/journal_start.py, scripts/journal_end.py, scripts/log_tmp_note.py, scripts/pattern_tracker.py; last_review: 2025-09-30 -->

## 1) 목적·범위
- 목적: 현재 LLM 운영 지침과 보조 스크립트(저널/메모/패턴)를 객관적으로 점검하고, 즉시 적용 가능한 개선안을 제시한다.
- 범위: `docs/guidelines/01_llm_guidelines.md`, `docs/guidelines/06_scientific_communication.md`, `docs/guidelines/05_storage_output_guidelines.md`, `scripts/journal_*`, `scripts/log_tmp_note.py`, `scripts/pattern_tracker.py`, 최근 일지/메모.

## 2) 요약 평가(Executive Summary)
- 전반: 상위 10–15% 수준의 체계·도구화. “경량 모드(트리거 기반)”와 “증거 제시 규율”이 잘 잡혀 있음.
- 강점: 최소 열람·지연 통제, 자동 저널링(캐리오버/체크포인트), 내부 근거 우선, 오답/비효율 환류 구조.
- 개선 필요 핵심 4가지(TL;DR):
  1) 저널 링크 깨짐(별칭 라벨을 링크로 재사용) → 링크 타깃 재해석 필요.
  2) 문서/일지 링크 검증 자동화 부재 → `validate_links.py` 도입.
  3) 답변 품질 사전 점검 자동화 → `audit_answers.py`(근거·파일참조·금지어) 도입.
  4) 경로 별칭(`MLHB/…`) 규약의 “출력물까지 일관 적용” 미흡 → 별칭 해석 유틸 공통화.

## 3) 운영 플로우(현행)
1. 지침 확인(경량 모드) → 시작 루틴 실행(`python3 scripts/journal_start.py`).
2. 임시 메모는 `python3 scripts/log_tmp_note.py "<요약>"`로 누적(`docs/journal/tmp/<date>_notes.md`).
3. 저장 지시 시 `python3 scripts/journal_end.py --notes ...`로 Work Log 갱신·체크포인트 기록.
4. 이슈/비효율은 `scripts/pattern_tracker.py`로 로그화 및 주간 리마인드.

참조: `docs/guidelines/01_llm_guidelines.md`(시작/저장 루틴, 경량 모드), `docs/guidelines/06_scientific_communication.md`(증거 규칙).

## 4) 강점(근거)
- 최소 열람 정책: 외부/내부 검색 구분과 트리거 기반 확인이 명확함 (`docs/guidelines/01_llm_guidelines.md:25` 주변).
- 자동 저널링·추적성: 시작 시 캐리오버/요약, 종료 시 시간대별 요약 주입·체크포인트(`scripts/journal_start.py:167`, `scripts/journal_end.py:277`).
- 증거 중심 커뮤니케이션: 공리/내부/외부 근거 레벨과 외부 탐색 제한을 문서화(`docs/guidelines/06_scientific_communication.md:19`).
- 환류 장치: 패턴 트래커의 태그 임계치 알림·주간 검토(`scripts/pattern_tracker.py:85`).

## 5) 문제·리스크와 개선안(증거 포함)

### A) 일일 저널에서 링크가 깨짐(별칭 라벨을 링크로 재사용)
- 현상: 임시 메모 → 일일 저널로 이관 시, 예시 형태(예: `MLHB/...`, `references/MLHB/overview_MLD.md`)가 실제 파일 상대경로로 변환되지 않아 깨짐.
- 증거(파일:라인):
  - `docs/journal/2025/2025-09-30.md:21` — `MLHB/scripts`
  - `docs/journal/2025/2025-09-30.md:31` — `references/MLHB/overview_MLD.md`
  - `docs/journal/2025/2025-09-29.md:19` — `MLHB/scripts`(링크 없이 라벨만 남음인 케이스 포함)
  - 생성 경로: `scripts/log_tmp_note.py`는 임시 메모에 “별칭 라벨 + 실제 상대경로 링크”를 함께 저장(`scripts/log_tmp_note.py:101-111`).
  - 이관 경로: `scripts/journal_end.py`는 임시 메모의 `[dir: …]` 라벨만 파싱하고, 링크는 버린 뒤 라벨 자체를 링크 타깃으로 사용(`scripts/journal_end.py:120-161`).
- 영향: 일지에서 클릭이 실패해 추적성·검증성이 저하. 링크 검증 자동화 전 단계에서 체계적 단절.
- 개선안(코드 스케치): `journal_end.py`가 별칭 라벨(`MLHB/...`)을 일지 파일 기준 상대경로로 재해석해야 함.
  1) `log_tmp_note.py`의 `_resolve_link_target` 동등 기능을 `journal_end.py`에 추가(중복 최소화를 원하면 공통 유틸 모듈화 권장).
  2) `summarize_tmp_entries(...)`가 링크 문자열을 구성할 때 라벨을 실제 경로로 변환.

  예시 패치 아이디어:
  ```python
  # journal_end.py 상단
  from pathlib import Path

  def _resolve_note_link_target(journal_file: Path, workdir_label: str) -> str:
      ROOT_ALIAS = 'MLHB'
      base_dir = Path(__file__).resolve().parents[1]
      if workdir_label == ROOT_ALIAS:
          target = base_dir
      elif workdir_label.startswith(f"{ROOT_ALIAS}/"):
          target = base_dir / workdir_label[len(f"{ROOT_ALIAS}/"):]
      else:
          p = Path(workdir_label)
          return workdir_label if p.is_absolute() else workdir_label
      return Path(os.path.relpath(str(target), start=str(journal_file.parent))).as_posix()

  # summarize_tmp_entries(...) 내부 (기존 155–161행 대체)
  parts = [p.strip() for p in re.split(r'[;,]', dirs) if p.strip()]
  link_items = []
  for label in parts:
      target = _resolve_note_link_target(Path('<DAILY_FILE>'), label)  # main()에서 일지 경로 전달하도록 시그니처 확장 권장
      link_items.append(f"[{label}] ({target})")
  link_str = ' · '.join(link_items) if link_items else '.'
  ```
  - 구현 시그니처 변경 제안: `summarize_tmp_entries(entries, end_time, journal_path)` 형태로 `Path` 주입.

### B) 문서/일지의 링크 검증 자동화 부재
- 현상: 경로 별칭과 상대경로 혼용, 과거 절대경로(`/Users/...`)가 일부 잔존.
- 증거: `docs/journal/2025/2025-09-30.md:20`, `docs/journal/2025/2025-09-29.md:58` 등 절대경로 링크.
- 영향: 도큐먼트 이식성 저하, 깨진 링크 누적 가능.
- 개선안: `scripts/validate_links.py` 신설(보고만 수행, 수정은 보류).
  - 요구사항
    - 입력: 기본 `docs/`, 옵션 `--root-alias MLHB`.
    - 동작: 모든 `.md` 스캔 → `[...] (path)` 추출 → 별칭(`MLHB/...`)은 리포 루트 기준으로, 그 외는 각 파일 기준 상대경로로 해석 → 존재 여부·디렉터리/파일·확장자 검사 → 리포트 출력.
    - 출력: 깨진 링크 목록(파일:라인, 표시 텍스트, 해석 경로), 별칭/절대경로 사용 빈도 통계.
  - 후속: 01 지침에 “저장 전 링크 검증” 체크 항목 추가(‘출고 전 3점 체크’ 항목).

### C) 답변 품질 사전 점검 자동화 미흡(근거/파일참조/금지어)
- 현상: 문서상 규범은 충분하나(06/01), 답변 텍스트의 형식적 품질을 자동 점검하는 도구 부재.
- 영향: 장황/모호 표현, 근거 생략, 파일 경로 미표기가 섞여 들어갈 수 있음.
- 개선안: `scripts/audit_answers.py` 신설(표준 입력 또는 파일 입력 받아 룰 기반 점검).
  - 체크 규칙(초안)
    - 내부 근거 표기 비율(파일경로, 변수/스크립트 지칭) ≥ N% 권고.
    - “추측/아마/대충/그런 것 같음” 등 금지어 빈도 보고.
    - 코드/파일 언급 시 `repo-상대경로:라인` 형식 포함 여부.
    - 외부 웹 언급 여부와 06 지침 위반 가능성 경고.
  - 출력: 항목별 Pass/Fail + 개선 메시지.

### D) 경로 별칭(`MLHB/…`) 규약의 공통 유틸 부재
- 현상: `ROOT_ALIAS='MLHB'`가 여러 스크립트에 분산 정의(`scripts/journal_start.py`, `scripts/log_tmp_note.py` 등). 링크 해석 로직도 중복/불일치.
- 영향: 링크/경로 규약 변경 시 반영 누락 위험.
- 개선안: `src/utils/paths.py`(또는 `scripts/_utils_paths.py`)에 별칭 해석·상대경로 변환 유틸을 단일화. 저널/메모 양쪽에서 동일 함수 사용.

### E) 저장 가드(≈1h) 규칙의 문서화 수준
- 현상: `journal_end.py`는 최근 저장 이후 50분 미만이면 요약 이관을 생략(`scripts/journal_end.py:231-236`). 지침 본문(01)에서는 이 가드의 존재/의도 안내가 부족.
- 영향: 사용자가 저장 요청을 했는데 로그 반영이 간헐적으로 누락됐다고 느낄 수 있음.
- 개선안: `docs/guidelines/01_llm_guidelines.md`에 “저장 최소 간격(≈1h)”과 `--force` 사용 규칙을 명시.

## 6) 우선순위·로드맵(2주)
- 주간 1(핵심 결함 제거)
  1) 일지 링크 재해석 패치(`journal_end.py`) — 고우선.
  2) 링크 검증기(`validate_links.py`) — 고우선.
  3) 01 지침에 저장 가드 문구 추가 — 중우선.
- 주간 2(품질 체계 강화)
  4) 별칭/경로 유틸 공통화 — 중우선.
  5) 답변 품질 점검기(`audit_answers.py`) — 중우선.
  6) 루트 `AGENTS.md`(레포 온보딩/관례 요약) — 중우선.

## 7) 변경 단위 제안(작업 패키지)
- 패키지 A: “저널 링크 정합성”
  - 변경: `scripts/journal_end.py`(링크 해석), `scripts/log_tmp_note.py`(주석/도크스트링 보강), 선택 시 `src/utils/paths.py` 신설.
  - 검증: `docs/journal/tmp/<today>_notes.md`에 2–3개 샘플 기록 → `journal_end.py --force` → 일지 내 링크 클릭.
- 패키지 B: “링크 검증기 추가”
  - 신규: `scripts/validate_links.py`.
  - 검증: `python3 scripts/validate_links.py --root-alias MLHB` 출력 확인, 깨진 링크 목록을 일시 보류/수정 큐로 기록.
- 패키지 C: “지침·온보딩 보강”
  - 변경: `docs/guidelines/01_llm_guidelines.md`(저장 가드 문구), 루트 `AGENTS.md`(요약·관례·도구 소개) 초안 추가.
- 패키지 D: “답변 QA 도입”
  - 신규: `scripts/audit_answers.py`.
  - 검증: 과거 응답 3건에 적용해 리포트 샘플 확보.

## 8) 성공 지표(제안)
- 깨진 링크 비율: 주간 0% 달성(최초 런에서 현황 측정).
- 답변 내부 근거 표기율: 70%→85% 이상.
- 일지 내 “절대경로 링크” 비율: 0% 유지.
- 주간 패턴 리뷰 준수율: 100%.

## 9) 참고 증거(파일·라인)
- `docs/guidelines/01_llm_guidelines.md:12` — 시작 루틴(저널 시작·오답노트·저장 규칙)
- `docs/guidelines/01_llm_guidelines.md:25` — 경량 모드·트리거 기반 확인
- `docs/guidelines/06_scientific_communication.md:19` — 외부 탐색 제한(명시적 요청 필요)
- `scripts/journal_start.py:167` — 임시 메모 파일 생성·요약·클릭 가능한 경로 주입
- `scripts/journal_end.py:120` — 임시 메모 파싱(링크 무시), `:155–161` — 라벨을 링크로 재사용(문제 포인트)
- `scripts/log_tmp_note.py:101–111` — 별칭 라벨 + 실제 상대경로 링크 동시 기록(정상 포인트)
- `scripts/pattern_tracker.py:85` — 태그 임계치 기반 알림(지침 초안 신호)
- `docs/journal/2025/2025-09-30.md:21,31` — 깨진 링크 사례
- `docs/journal/2025/2025-09-29.md:19` — 라벨만 남은 사례

## 10) 부록: 스크립트 초안 스펙

### A. `scripts/validate_links.py`
- 사용: `python3 scripts/validate_links.py [--root docs] [--root-alias MLHB]`
- 로직:
  1) `root` 하위 `.md` 전수 스캔 → Markdown 링크 추출.
  2) 링크 타깃 해석: `MLHB/...` → 리포 루트 기준, 그 외 → 파일 기준 상대경로.
  3) 존재 확인(파일/디렉터리), 경로 정규화, 통계 산출.
  4) 리포트 출력(JSON/텍스트 선택) + 종료코드(깨진 링크 있으면 1).

### B. `scripts/audit_answers.py`
- 사용: `python3 scripts/audit_answers.py --in <file>|- [--rules default]`
- 룰(초안): 내부 근거 표기 유무, 파일·라인 포맷 검출, 금지어 사전, 외부 웹 언급 감지.
- 출력: 항목별 Pass/Fail·세부 메시지, 총점(선택).

---

질문이나 우선 적용하고 싶은 패키지가 있으면 알려 주세요. 필요하면 A(저널 링크 정합성)부터 바로 작업 가능합니다.

## 11) 구현 진행 상황(2025-09-30) — 적용 결과 보고

### A) 저널 링크 정합성 — 완료
- 코드 변경: `scripts/journal_end.py`에 별칭 해석 헬퍼 추가 및 요약 주입 시 일지 파일 기준 상대경로로 링크 생성(`scripts/journal_end.py:120`, `scripts/journal_end.py:155-161` 근방).
- 검증: `docs/journal/2025/2025-09-30.md:38` — `[MLHB/scripts](../../../scripts)`로 정상 변환 확인.
- 과거 기록 정리: `scripts/normalize_journal_links.py` 추가·실행(드라이런 후 적용).
  - 정리 결과: 총 29개 링크 교정(4파일)
    - `docs/journal/2025/2025-09-29.md` 10건, `docs/journal/2025/2025-09-30.md` 10건, `docs/journal/tmp/2025-09-29_notes.md` 8건, `docs/journal/tmp/2025-09-30_notes.md` 1건.
- 참고 명령
  - 실행: `python3 scripts/normalize_journal_links.py --dry-run` → `python3 scripts/normalize_journal_links.py`

### B) 링크 검증 — 완료(주간 루틴 연계 포함)
- 새 도구: `scripts/validate_links.py` — Markdown 링크 검사(MLHB 별칭·상대/절대 경로 해석, http/mailto/앵커 제외).
- 주간 리포트 연계: `scripts/journal_weekly.py`가 주간 파일 생성 시 자동으로 `validate_links.py --json` 실행 → “## Link Check” 섹션 삽입(`scripts/journal_weekly.py:200` 근방).
- 테스트: `python3 scripts/journal_weekly.py --week 2025-W40 --dry` — 깨진 링크 14개(파일 7개) 요약과 상위 5개 샘플 표기 확인.

### C) 답변 품질 사전 점검 — 완료(지침/도구)
- 새 지침: `docs/guidelines/08_answer_quality_check.md` — 60초 체크·규칙·예시·도구 안내.
- LLM 지침 연계: `docs/guidelines/01_llm_guidelines.md`에 “출고 전 QA 체크(08)” 섹션 추가 및 트리거에 “답변 준비/검토” 항목 반영(`docs/guidelines/01_llm_guidelines.md:24`, `docs/guidelines/01_llm_guidelines.md:39`).
- 새 도구: `scripts/audit_answers.py` — 규칙 기반 QA(증거/언어/단위/링크/키워드) 점검, 텍스트/JSON 출력 지원.
  - 예시(정상): 100점(파일 참조·K/day·×86400·외부링크 없음).
  - 예시(경고): 50점(모호 표현·외부 링크 감지).

### D) 경로 별칭 유틸 공통화 — 보류(부분 반영)
- 현황: `journal_end.py`, `normalize_journal_links.py` 각각 별칭 해석 로직 포함. 중복 최소화를 위해 `src/utils/paths.py` 등으로 통합 권장(차기 작업).

### E) 저장 최소 간격 가드 문서화 — 보류
- 현황: `scripts/journal_end.py`는 최근 저장 후 ~50분 미만인 경우 요약 이관을 생략(`scripts/journal_end.py:231-236`).
- 조치: `docs/guidelines/01_llm_guidelines.md`에 “저장 최소 간격(≈1h)”과 `--force` 사용 규칙 명시 예정.

### 되돌리기 안내(요지)
- 링크 변환 롤백: `scripts/journal_end.py`에서 `_resolve_note_link_target` 사용 부분을 제거하고 기존 링크 문자열 사용으로 복귀.
- 정리 스크립트 영향 복구: 개별 파일의 Git 히스토리에서 이전 버전으로 되돌리기.
- 주간 Link Check 제거: `scripts/journal_weekly.py` 내 Link Check 섹션 삽입 블록 삭제.
- QA 도구/지침 제거: `docs/guidelines/08_answer_quality_check.md`, `scripts/audit_answers.py` 삭제 및 `docs/guidelines/01_llm_guidelines.md`의 관련 섹션 원복.

### 다음 단계 제안(우선순위)
- 별칭·상대경로 해석 유틸 공통화(고): `src/utils/paths.py` 신설 후 `journal_end.py`/`normalize_journal_links.py`에서 사용하도록 refactor.
- 링크 검증 오탐 감소(중): `_archive/`, 플레이스홀더(‘경로’, ‘<경로>’, ‘MLHB/...’) 기본 제외/무시 목록 추가.
- 주간 QA 집계(옵션): `journal_weekly.py`에 “QA Check” 섹션(이번 주 평균 점수, 위반 상위 규칙) 삽입.

### 파일 참조
- `scripts/journal_end.py:120`, `scripts/journal_end.py:155-161` — 링크 생성 로직 변경 포인트
- `docs/journal/2025/2025-09-30.md:38` — 변환 링크 확인 샘플
- `scripts/normalize_journal_links.py:1` — 일괄 정리 유틸
- `scripts/validate_links.py:1` — 링크 검증기
- `scripts/journal_weekly.py:200` — Link Check 삽입 로직
- `docs/guidelines/08_answer_quality_check.md:1` — QA 지침
- `scripts/audit_answers.py:1` — QA 점검 CLI
- `docs/guidelines/01_llm_guidelines.md:24`, `docs/guidelines/01_llm_guidelines.md:39` — QA 지침 연결
