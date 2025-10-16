# 5) 저장 및 출력 지침
<!-- owner: MLHB-core; canonical: true; depends_on: ; last_review: 2025-09-29 -->

## A. 적용 범위
- 외장 저장 장치(예: `/Volumes/*`)에서 분석·시각화 작업을 수행할 때 적용한다.
- 소스 코드 작성, 데이터 전처리, 그림/표 산출 등 저장 행위 전반을 포함한다.

## B. 외장 저장소 작업 규칙
1. **소스 코드와 산출물 동시 저장**: 외장하드 경로에서 작업하는 동안 생성·수정한 파이썬 스크립트, 노트북, 모듈을 포함한 모든 소스 코드는 외장하드 내 적절한 디렉터리에 저장한다. **그림을 생성하는 스크립트는 해당 그림이 저장되는 디렉터리(예: `Figure/`)와 동일 경로(또는 그 하위 `scripts/`)에 반드시 함께 둔다.** 계산 전용 모듈은 `Decadal/source/` 등 전용 소스 디렉터리에 보관한다.
2. **결과물 현지 보관**: 분석 결과(그림, 테이블, 로그 등)도 동일 외장 경로에 보관하고, 다른 위치로 임시 복사했을 경우 즉시 외장 경로로 동기화한다. 별도 지시가 없는 한 그림 산출물은 PNG로 저장하고, 필요 시 추가 포맷(PDF 등)을 병행한다.
3. **경로 명시**: 스크립트 내 기본 출력 경로나 `--output` 옵션 기본값을 설정할 때 외장 경로가 기본이 되도록 한다.
4. **로컬 라이브러리 활용 방식**: 루트 리포(`~/Desktop/GPT/Mixed-Layer-Heat-budget`)에 있는 소스 파일은 참고용으로만 유지하고, 실제 실행·출력은 가능하면 외장하드 경로에서 수행한다. 로컬 복사본을 수정할 경우 외장 버전도 동일하게 반영했는지 확인한다.
5. **동기화 검증**: 외장 경로 외 다른 위치에 중간 산출물이 생성되었는지 정기적으로 확인하고, 발견 즉시 외장 경로로 이동·정리한다.

## C. 소스 코드 라이브러리 구조화
1. **루트 내 라이브러리 배치**: 새로 작성하는 모든 소스 코드는 루트(`~/Desktop/GPT/Mixed-Layer-Heat-budget`)의 `src/` 하위에 위치한 라이브러리 구조로 편입한다. 외장하드 작업 시에도 계산 로직은 `Decadal/source/` 등 전용 디렉터리에, 그림 생성 스크립트는 대응하는 `Figure/` 하위에 두어 두 위치가 역할별로 분리되도록 한다.
2. **성격별 모듈화**: 기능에 따라 모듈을 분리한다.
   - 데이터 다운로드·전처리는 `src/io/`, `src/preprocess/` 등 입·출력 관련 하위 모듈로 정리한다.
   - 분석·통계 계산은 `src/analysis/` 또는 세부 도메인별 폴더를 사용한다.
   - 시각화·보고용 코드는 `src/visualization/` 하위에 배치하고, 공통 스타일/유틸은 `src/visualization/utils.py` 등으로 재사용성을 확보한다.
3. **외장 라이브러리 미러링**: 외장 경로에 코드를 둘 때도 동일한 패키지 구조를 유지해 import 경로 혼선을 방지하고, 필요 시 `PYTHONPATH`를 외장 경로의 `src` 루트를 가리키도록 설정한다.
4. **문서화**: 새 모듈을 만들면 `docs/README` 또는 관련 가이드라인에 간단한 사용법과 저장 위치를 기록해 팀이 공유할 수 있도록 한다.

## D. 점검 체크리스트
- [ ] 외장 경로에 소스 코드와 결과물이 모두 있는지 확인했다.
- [ ] 코드가 루트 `src/` 구조에 맞춰 분류·저장되어 있다.
- [ ] 출력 경로 기본값이 외장 경로를 가리키는지 검토했다.
- [ ] 변경 사항을 관련 문서/일지에 반영했다.

## E. NetCDF/CF 출력 규칙
- time 좌표(CF)
  - `units = "days since 1970-01-01 00:00:00"`, `calendar = "standard"`, `long_name = "time"`.
  - dtype는 float64(`f8`), `_FillValue=None`로 지정, 차원은 `unlimited`.  
  - 주의: `attrs.units`/`attrs.calendar`와 `encoding.units`/`encoding.calendar`를 동시에 지정하지 않는다(인코딩 충돌). CF 메타는 encoding으로만 지정.
- lat/lon 좌표
  - `long_name`/`standard_name`/`units` 일관: latitude(`degrees_north`), longitude(`degrees_east`).
  - 1D 또는 2D(curvilinear) 모두 허용하되, 데이터 변수와 차원/형상이 일치해야 한다.
- 변수 단위와 인코딩
  - 계산은 K s⁻¹, 파일 저장은 K day⁻¹(추가 ×86400 불필요).  
  - `data_vars`: `zlib=True`, `complevel=4` 권장. 좌표 변수는 비압축.  
  - time 인코딩 예: `{dtype: f8, _FillValue: None, units: "days since 1970-01-01 00:00:00"}`.
- 전역 속성(메타)
  - `we_mode`, `adv_scheme`, `mld_source`, `mld_threshold_dsigma0`, `mld_ref_depth_m`, `created`(ISO8601), `fully_mixed_fraction` 등 핵심 파라미터 기록.
- NaN/집계 규칙
  - 분모≤0/결측은 NaN 유지(강제 대치 금지).  
  - 월/기간 평균 집계 시 `skipna=True`로 NaN 전파 최소화(모두 NaN인 경우만 NaN 유지).

## F. 원자적 저장·집계 규칙
- 파일 쓰기: 최종 파일명에 직접 쓰지 말고 `*.tmp`로 저장 후 `os.replace`(rename)로 교체한다.  
- scratch 접근: 작업 중간 산출(tmp/ scratch)은 열람하지 말고, 최종 산출(output/*.nc)만 사용한다.  
- 호환 점검: `ncdump -h`로 CF 속성 확인 후 필요 시 GrADS `sdfopen`으로 시범 오픈 테스트를 수행한다.

참고: 시각화(플롯·지도) 관련 스타일·검증·저장 옵션은 `docs/guidelines/02_plot_guidelines.md`를 따른다.

## G. 실행 검증·회복(출력 관점)
- 실행 직후 로그 검사: `tail -n 80 logs/<run>.log`에서 에러 패턴을 확인한다.
- 월평균 산출 검증: `/output/monthly/*.nc`에 대해 `ncdump -h`로 `time` 차원/CF 속성(time:units/calendar)과 변수 단위를 점검한다.
- 부분 작성 파일 금지: scratch(tmp_daily) 또는 `.tmp` 파일은 열지 않는다. 최종 파일만 사용한다.
- 오류 시 회복 절차(권장)
  1) 실패한 월의 scratch 디렉터리를 제거한다(다른 월은 유지).
  2) 동일 커맨드를 재실행한다(월평균은 concat 후 `os.replace`로 교체되어 안전하다).
  3) 반복 실패할 경우 오답노트에 원인/조치/재현 절차를 기록하고, 실행 지침의 관련 항목(본 문서 E–F, 03 실행 지침 H)을 교정한다.

참고: 실행 자체에 대한 상세 체크리스트와 재시작 지침은 `docs/guidelines/03_code_execution.md` H 절을 따른다.
