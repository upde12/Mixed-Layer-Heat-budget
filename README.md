# Mixed-Layer-Heat-budget

혼합층 열수지(MLHB) 분석 코드와 참고 문서를 위한 저장소입니다.

## Directory Layout
- `src/` : 실행 코드. 현재는 `process_d2nf.py`가 포함되어 있으며 D2-NF 형태의 혼합층 열수지를 계산합니다.
- `docs/history/` : 프로젝트 변천사와 개념 정리. `01_evolution.md`부터 순차 번호를 새로 매겼습니다.
- `docs/guidelines/` : LLM 협업 지침과 분석 방법 가이드를 모았습니다. MLHB 문서는 `docs/guidelines/10_analysis_methods/heat_budget/` 이하(요약 README, `01_code_and_runs.md`, `manual.md` 등)에 정리되어 있습니다.
  - 일반 실행 지침: `docs/guidelines/03_code_execution.md`
  - `docs/cheatsheet/` : 빠른 점검용 치트시트. `01_quick_checks.md`에 핵심 체크리스트가 정리되어 있습니다.
- `docs/data/` : 입력 자료 및 메타데이터 요약. `01_glorys_nc_metadata.md`가 포함되어 있습니다.

각 폴더는 `01_*.md`, `02_*.md` 식으로 다시 번호를 매기면 되며, 새 문서를 추가할 때도 동일한 규칙을 따르십시오.

## Development Notes
- 파이썬 스크립트는 `src/`에서 관리하며, 추후 테스트나 추가 모듈이 생기면 `tests/`, `notebooks/` 등의 디렉터리를 이 구조에 맞춰 추가하세요.
- 문서 업데이트 시에는 각 카테고리에 맞는 폴더를 사용하고, 새 번호를 부여해 변경 이력을 명확히 유지합니다.
