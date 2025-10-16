# Guidelines CHANGELOG

## 2025-10-10 — Core Mode + scoped guideline checks

Summary: Add an explicit “Core Mode” to limit guideline reads to 01 by default, with opt‑in expansion via `scope`/`GuidesOnly` and response length control via `size`. Introduce `no-run` to suppress automatic routine execution when only checking guidelines.

- Documentation & Policy
  - `docs/guidelines/01_llm_guidelines.md`: added `B‑0. 핵심 모드(Core Mode; 기본)` with rules for `scope`, `GuidesOnly`, `size`, `no-run`, and narrow triggers for when to read 02/05/06/09/03/07.
    - Start line: docs/guidelines/01_llm_guidelines.md:14
  - De-duplicated "경량 실행 모드" triggers: header renamed to "경량 실행 모드(시간 예산)", trigger list removed; now defers to B‑0 mapping. Also replaced "예상되면" with explicit scope/request wording in start routine.

- Impact
  - Reduces unnecessary broad reads (“check guidelines” now stays on 01 unless scoped).
  - Faster responses; lower cognitive load; clearer, auditable expansion conditions.
  - Preserves correctness by mandating reads when actual work requires them (e.g., plotting/report writing/execution).

- Revert hints
  - Remove the `B‑0` subsection from `01_llm_guidelines.md` and restore prior behavior where “예상되면” could trigger broader checks.

## 2025-10-10 — DIFFV sign convention (z↓) clarified

Summary: Document the vertical diffusion sign convention under depth-positive coordinates and link to the code fix.

- Code
  - `src/process_d2nf_main.py`, `src/process_d2nf.py`: `DIFFV = (kv * Tz_mh) / hden` (z↓); previously had an extra leading minus.

- Documentation & QA
  - `docs/guidelines/03_code_execution.md`: added section I‑1 describing z↓ convention and QA checks (corr(res, DIFFV) > 0; C mean≈0).
  - Error note: `docs/error_notes/data_io/20251010_diffv_sign_convention_fix.md` records the issue, fix, and verification steps.

- Impact
  - DIFFV sign aligns with physical expectation: cooling (−) when ∂T/∂z_down < 0, warming (+) when ∂T/∂z_down > 0.
  - Consider re-running representative months (winter/summer) to validate closure and correlations before full reprocessing.

## 2025-10-01 — Removed MLHB `--hmin` option

Summary: Eliminated the unused mixed-layer thickness floor (`--hmin`) from code, runners, and documentation. The solver now leaves cells with zero/invalid thickness as NaN and downstream filters handle them.

- Code
  - `src/process_d2nf.py`: dropped `HMIN_DEF`, CLI flag, NetCDF attribute, and denominator clipping; guard now sets `hden<=0` to NaN.
  - Scripts (`run_mlhb_monthly.py`, `run_mlhb_monthly_dual.py`, `run_adv_schemes.py`): removed `--hmin` argument forwarding.

- Documentation & QA
  - Updated heat-budget README/manual/we-mode discussion/glorys spatial notes to state “no denominator floor”.
  - Scrubbed `--hmin` from presets/examples; QA/audit tools now watch `we-mode`, `Δσ0`, etc. without `hmin` keyword.
  - Daily journal template and current journal entry note the new policy (NaN on zero thickness).
  - Added general code execution guide: `docs/guidelines/03_code_execution.md` (env, nohup/logs, CF/atomic write, parallel advice).

- Impact
  - Existing runs using `--hmin` must re-run without the flag (it is now invalid). Results may show NaN where thin-layer clipping previously masked instabilities; treat them via QA filters instead of forced floor.

- Revert hints
  - Reintroduce `HMIN_DEF` constant/CLI flag in `src/process_d2nf.py` (see git history prior to 2025-10-01) and restore command-line options in helper scripts and documentation examples.

## 2025-09-29 — Local paths + NetCDF outputs

Summary: Remove legacy server paths in examples; standardize outputs to yearly NetCDF files in docs and helpers.

- Paths
  - Replaced `/data3/...` examples with local volumes in docs/workflow and heat-budget README.
  - Dropped `/data3/...` from default path candidates in `src/process_d2nf.py`.

- Output format
  - Updated docs to use `ml_budget_YYYY.nc` with variables (`T_ML`, `Tb`, `TEN`, `QNET`, `ADV`, `ENT`, `DIFF`, `DIFFV`, `CLOS_*`).
  - Cheatsheet and GrADS snippets now open NetCDF via `sdfopen` and reference variables, not `.ctl`/`.data`.

Impact:
- Avoids stale remote references; aligns documentation with current NetCDF writer already used by `process_d2nf.py`.

Revert hints:
- If external server paths are needed again, reintroduce them to the candidate lists in `src/process_d2nf.py` and restore `.data` examples in docs.

## 2025-09-29 — Heat-budget manual streamlined (density-only)

Summary: Trim manual to the operational subset: density-threshold MLD only; move alternatives and ad‑hoc smoothing to appendix.

- Manual
  - 3.2 re-scoped to “참고용(운영 불사용)” and points to appendix.
  - 3.3 reduced to minimal masks (ice 0.15), bathymetry cap, and NA on threshold failure.
  - 7. 지역 주의사항에서 스무딩 언급 제거; 단일 기준 유지 명시.
  - 9. 워크플로에서 보조 기준 분기 제거.

- Appendix
  - Added `docs/guidelines/10_analysis_methods/heat_budget/appendix_alternatives.md` for temperature/gradient criteria and non‑standard smoothing notes with citations.

Impact:
- Manual now reflects the exact method intended for use; avoids unintended method creep.

Follow-up:
- Clarified operational MLD description across manual/workflow: default is Δσ₀=0.03 (10 m) recompute, with product `mlotst` available via `--mld-source product`.
- Default code behavior now recomputes MLD (Δσ₀=0.03, 10 m reference). Added CLI flags `--mld-source`, `--mld-threshold`, `--mld-ref-depth` and documented them in manual/workflow/summary.
- Fully mixed fallback: when Δσ₀ never crosses the threshold the column is treated as fully mixed (MLD=bathymetry) and the budget sets `ENT`, `DIFFV` to zero. NetCDF files record `fully_mixed_fraction`.

## 2025-09-29 — Conditional lookup + de-dup cross-links

Summary: Add canonical metadata and cross-links to reduce redundant checks; no behavioral script changes.

- Added metadata headers (owner/canonical/depends_on/last_review)
  - docs/guidelines/01_llm_guidelines.md:1
  - docs/guidelines/02_plot_guidelines.md:1
  - docs/guidelines/05_storage_output_guidelines.md:1
  - docs/guidelines/06_scientific_communication.md:1

- 01_llm_guidelines.md
  - Added reference to 06 G-section for presentation-specific language rules
    - docs/guidelines/01_llm_guidelines.md:33

- 02_plot_guidelines.md
  - In E. 재현성 메모, added pointer to 05 for general storage/library rules
    - docs/guidelines/02_plot_guidelines.md:42

- 05_storage_output_guidelines.md
  - Appended note to defer visualization-specific options to 02
    - docs/guidelines/05_storage_output_guidelines.md:28

- 06_scientific_communication.md
  - Scoped G. 언어 사용 규칙 to presentations; linked 01 for general language
    - docs/guidelines/06_scientific_communication.md:61

Backups (for revert):
- docs/guidelines/_archive/20250929/01_llm_guidelines.md
- docs/guidelines/_archive/20250929/02_plot_guidelines.md
- docs/guidelines/_archive/20250929/05_storage_output_guidelines.md
- docs/guidelines/_archive/20250929/06_scientific_communication.md

Impact:
- Reduces unnecessary guideline lookups; clarifies ownership.
- No changes to scripts or runtime defaults.

Revert instructions:
```bash
cp docs/guidelines/_archive/20250929/01_llm_guidelines.md docs/guidelines/01_llm_guidelines.md
cp docs/guidelines/_archive/20250929/02_plot_guidelines.md docs/guidelines/02_plot_guidelines.md
cp docs/guidelines/_archive/20250929/05_storage_output_guidelines.md docs/guidelines/05_storage_output_guidelines.md
cp docs/guidelines/_archive/20250929/06_scientific_communication.md docs/guidelines/06_scientific_communication.md
```

## 2025-09-30 — Reference management split

Summary: Move “논문 요약 관리” out of scientific communication into a new dedicated guideline.

- New: `docs/guidelines/07_reference_management.md` defines storage locations, file naming, overview sorting (A–Z), and `_extracted/` summary rules.
- Update: `docs/guidelines/06_scientific_communication.md` E-section now points to 07.
- Update: `docs/guidelines/01_llm_guidelines.md` references 07 for reference/summary management and clarifies save-notes wording.

Impact:
- Clear separation between communication principles (06) and reference curation workflow (07).
