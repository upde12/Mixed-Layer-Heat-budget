# SODA-based MLHB Monthly Budget – Plan (ECS)
<!-- owner: MLHB-core; date: 2025-10-10; status: draft -->

## Objectives
- Reproduce the GLORYS monthly MLHB pipeline using SODA3.4.2 monthly files to compare patterns and magnitudes over ECS.
- Keep equations, signs, units, and output layout identical to GLORYS runs; adapt only for resolution and monthly cadence.

## Rationale
- SODA provides continuous monthly fields beginning in 1982, allowing analyses that align with the temporal scope of the original paper and enabling longer climatology windows and earlier ELT-year composites.
- Maintaining GLORYS-equivalent formulas ensures methodological consistency; only spatial resolution and monthly cadence differ.

## Data & Mapping
- Root: `/Volumes/HJPARK4/soda`
- Files: `soda3.4.2_mn_ocean_reg_YYYY.nc` (time=12)
- Grid: `xt_ocean(720), yt_ocean(330), st_ocean(50)`; positive-down Z
- Variables
  - Temperature `temp` [°C] → TEOS‑10 CT optional; use as K by +273.15 if needed
  - Salinity `salt` [psu]
  - Horizontal velocity `u, v` [m s‑1]
  - Vertical velocity `wt` [m s‑1] (T-points)
  - Mixed-layer depth: `mlp` (potential-density MLD, m)
  - Surface heat flux proxy: `net_heating` [W m‑2]
  - Auxiliary: `ssh`, `prho`, `taux/tauy`

## Climatology Window (Policy)
- Window: 1982–2020 (inclusive). All SODA‑based anomaly calculations use this fixed window unless otherwise stated.
- Scope: monthly anomalies, seasonal/3‑month windows (prevOND/JFM/AMJ/JAS/OND), and any climatology used for overlays (e.g., `net_heating`).
- Rationale: Consistent pre‑2021 baseline across analyses; avoids recent edge effects and aligns with primary comparison period.
- Implementation notes:
  - When building monthly climatology inside plotting/composite scripts, restrict contributing years to 1982–2020 even if files beyond 2020 exist.
  - For runs that extend beyond 2020, anomalies at later years are still referenced to the 1982–2020 climatology.
  - Document `clim=1982–2020` and, if applicable, `last_year` used for inputs in captions/notes.

## Method (monthly cadence; GLORYS-equivalent formulas)
- Constants: ρ=1026 kg m‑3, c_p=4000 J kg‑1 K‑1
- h (MLD): start with SODA `mlp` (option: recompute via Δσ0 threshold = 0.03 at ref 10 m)
- T_ML: 0→h layer-mean temperature (thickness-weighted over `st_ocean`); Tb: linear interpolation at z=−h
- TEN [K day‑1]: monthly tendency of T_ML divided by days_per_month
- QNET [K day‑1]: `(net_heating / (ρ c_p h)) × 86400`
- ADV [K day‑1]: `-(U_ML ∂xT_ML + V_ML ∂yT_ML) × 86400` (U_ML,V_ML are 0→h means)
- w_e [m s‑1]: `∂t h + ∇·(h U_ML, h V_ML)` (monthly differencing; centered when possible)
- ENT [K day‑1]: `(w_e/h)·(Tb − T_ML) × 86400`
- DIFF [K day‑1]: `(A_h/h)·∇·(h ∇T_ML) × 86400`, A_h=100 m² s‑1 (sensitivity later)
- DIFFV [K day‑1]: `(K_v/h)·(∂T/∂z)|_{−h} × 86400`, K_v=1e‑4 m² s‑1 (z↓; sign>0 for upward diffusion)
- Closure: `RES = TEN − (QNET + ADV + ENT + DIFF + DIFFV)`
- Units: store budget terms in K day‑1; coordinates CF-compliant (`time:units=days since 1970-01-01 00:00:00`)

## Outputs
- Root: `/Volumes/HJPARK4/Decadal/source/ML_budget_SODA/output/monthly`
- Files: `mlhb_monthly_soda_YYYYMM.nc` (time=1 per file)

## Revision History (2025-10-10)
- v0 (initial): Used SODA-provided MLD with fallbacks (`mlp → mlt → mls`, remaining ocean gaps → 20 m), CF/time/units aligned. Observed issues south of ~25°N (missing/too‑shallow h) and winter QNET zeros on land (masking).
- v1 (stability/masking): Propagated ocean mask to all terms; guarded TEN as time‑difference of T_ML; kept `mlp` path. Shallow h persisted in some areas (e.g., 0.5 m after clip).
- v2 (diagnostic test): Implemented Δσ₀ recomputation path (0.03 at 10 m) to check sensitivity; regenerated 1993 for side‑by‑side diagnostics only.
- Consensus (current): For SODA pipeline, we will use the MLD provided by SODA (mlp; with mlt/mls as metadata‑consistent fallbacks). Δσ₀ 재계산은 진단/검증 전용으로 유지.

## MLD Policy & Decision (in progress)
- Goal: Keep SODA analysis consistent with its own MLD definition while maintaining GLORYS‑equivalent budget formulas/units.
- Decision: Use SODA‑provided MLD (`mlp`) for production; retain recompute path only for diagnostics (not for baseline outputs).
- Definition confirmation: We are confirming the exact `mlp` criterion from the monthly files by reverse comparison on prho profiles. Candidate definitions considered:
  - Fixed density threshold: Δσθ = 0.03 kg m⁻³ at 10 m.
  - Temperature‑equivalent threshold: Δσθ = ρ·α(10 m)·ΔT with ΔT = 0.2°C at 10 m.
  - Temperature criterion (reference for `mlt`): ΔT ≈ 0.2°C.
- Bias note (monthly profiles): Monthly‑mean profiles tend to yield shallower MLD than snapshot‑mean (“mixed + thermocline averaging”); this is documented and considered in interpretation. We accept this for SODA monthly while flagging it in reports.
- Practical guards (non‑destructive):
  - Do not alter provided `mlp` values in baseline outputs.
  - Optionally publish a companion mask (e.g., `MASK_SHALLOW_LT5`) for h<5 m and shelf indicators for interpretation; no modification of `mlp` field itself.

## MLD Definitions (SODA 3.4.2, monthly) — Final
- Source: SODA3 official README (https://soda.umd.edu/soda3_readme.htm)
- Mixed‑layer depth fields are defined relative to the surface model level (z = 5 m):
  - `mlt`: depth where temperature differs from surface (5 m) temperature by 0.2 K
  - `mlp`: depth where potential density exceeds surface (5 m) density by 0.03 kg m⁻³
  - `mls`: depth where salinity differs from surface (5 m) salinity by 0.01 psu
- Important difference vs GLORYS operations in this project: GLORYS diagnostics commonly use Δσθ = 0.03 referenced to 10 m, while SODA’s `mlp` is referenced to 5 m and uses a fixed Δσθ = 0.03. Interpretations and cross‑dataset comparisons should note this distinction explicitly.

Implications
- SODA `mlp` will generally be shallower than a 10 m–referenced Δσθ definition, especially in summer and in regions with strong thermoclines and monthly‑mean profile bias.
- For production SODA MLHB budgets, we will use `mlp` as provided (with `mlt/mls` used only as ancillary context). No reverse estimation will be used in baseline results.

## Next Actions (definition confirmation)
- Implement a light diagnostic to compute monthly MLD from `prho` using the two candidate criteria above and compare against `mlp` (MAE, r) over ECS for a few months (e.g., 1993‑01/07).
- Record the best‑matching definition in this document and in the run notes; keep the other as sensitivity.
- If definition is confirmed to be Δσθ = ρ·α·0.2°C @ 10 m, document α(10 m) evaluation path used.
- Variables: `T_ML, Tb, T0, U_ML, V_ML, MLD, TEN, QNET, ADV, ENT, DIFF, DIFFV, CLOS_d2_ten(=RES)`
- Coords: `lat, lon` (1D) on the ECS subset (recommended)

## ECS Subset (recommended)
- Lat/Lon: 19–45°N, 109–146°E
- Reason: performance and comparability with existing ELT composites

## Implementation Steps
1) Builder script: `scripts/build_mlhb_monthly_from_soda.py`
   - Args: `--soda-root`, `--years`, `--region latmin,latmax,lonmin,lonmax`, `--out-root`, `--ah`, `--kv`, `--mld-source {mlp,recompute}`
   - Reads monthly file per YYYY; loops 12 months; computes fields; writes `mlhb_monthly_soda_YYYYMM.nc` atomically
   - CF time encoding; compression; NaN propagation rules mirror GLORYS
2) Quick validation (pilot 1993–1995)
   - Basic stats: mean/std of each term; RES mean≈0
   - Plot: use existing `source_panel_mlhb_composite.py`/`_seasonal.py` against SODA monthly root (anomalies vs 1982–2020)
3) Full run
   - Years: 1993–2020 (or data availability)
   - Parallelize by year
4) Reporting
   - Compare GLORYS vs SODA patterns (r, RMS ratio, sign agreement) via an adapted comparator

## Risks & Mitigations
- Monthly cadence smooths high-frequency processes → note in brief; keep formulas identical
- Vertical interpolation at −h depends on z-spacing → use robust linear interpolation with guard on bounds
- MLD choice (`mlp` vs Δσ0 recompute) affects ENT; start with `mlp`, then sensitivity
- Grid spacing: compute metric-aware ∂x,∂y using spherical distances (lat-dependent Δx)

## Example Commands (after implementation)
```
. .venv/bin/activate
# Build pilot months
python llm-ops/scripts/build_mlhb_monthly_from_soda.py \
  --soda-root /Volumes/HJPARK4/soda \
  --years 1993:1995 \
  --region 19,45,109,146 \
  --out-root /Volumes/HJPARK4/Decadal/source/ML_budget_SODA/output/monthly \
  --ah 100 --kv 1e-4 --mld-source mlp

# Render composites from SODA outputs
python llm-ops/scripts/source_panel_mlhb_composite.py \
  --monthly-root /Volumes/HJPARK4/Decadal/source/ML_budget_SODA/output/monthly \
  --years 1998,2010,2016,2020 \
  --out-root /Volumes/HJPARK4/Decadal/Figure/elt_composite_SODA \
  --months prev11,prev12,1-12 --unit month --adv-smooth-iter 2 --diffv-mode native
```

## Deliverables
- Pilot NetCDFs (1993–1995), composite panels (monthly/seasonal)
- Validation metrics table vs GLORYS, brief note on differences
