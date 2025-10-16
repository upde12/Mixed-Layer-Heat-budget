# 137E — Replot Verification Notes (1967-01)

## What we verified
- X-axis range: display 2–35°N while shading clamps to 3–34°N.
- pcolor(flat) behaviour: cells are blank if any of the four corners is NaN; last row/column dropped.
- “Tooth-like” gaps near 33.4°N are caused by the shallow 34°N station (≈1051 dbar+) having NaNs, not by mid-profile NaNs at 33.4°N.
- Colormap: Parula 256 applied from StackOverflow RGB table; CSV loader works.
- Python vs MATLAB section arrays: numerically identical up to machine epsilon (max |Δ| ≈ 3.55e−15).

## Data evidence (raw .anl)
- 34°00′N (137E/anl/196701/anl/137e-0001.anl): values switch to −999 at ≈1051 dbar.
  - 137E/anl/196701/anl/137e-0001.anl:1060
- 33°40′N (137E/anl/196701/anl/137e-0002.anl): −999 starts at ≈1264 dbar (below region of interest).
  - 137E/anl/196701/anl/137e-0002.anl:1273
- 33°20′N (137E/anl/196701/anl/137e-0003.anl): −999 starts at ≈1264 dbar (below region of interest).
  - 137E/anl/196701/anl/137e-0003.anl:1273

## Rendering rules (current Python implementation)
- Shading: pcolormesh on edge grids; edges are clamped to 34°N (north) and 3°N (south) so colors do not spill beyond 3–34°N.
- Contours: drawn on centre grids and lie strictly inside 3–34°N.
- Axis limits: 2–35°N to match original figures.

## Colormap
- Parula RGB (256×3) scraped from StackOverflow and saved to:
  - `137E/JMA137E/prog/source_gpt/parula_256.csv`
- CSV loader options:
  - `--density-cmap-csv <csv>` for density only
  - `--cmap-csv <csv>` for all panels

## MATLAB vs Python equality check
- Loaded `ptem` from `JMA137E2000m_TSD.mat` (v7.3 HDF5) for 1967‑01 and compared with Python build_section(method='1d') output.
- Shapes: both (39, 401). `array_equal` → False (expected due to rounding), `max(|Δ|)` ≈ 3.55e−15.
- Interpretation: numerical identity at machine precision; visual identity guaranteed.

## Reproduce
1) Generate Python section: `python 137E/JMA137E/prog/source_gpt/replot_196701_sections.py --density-cmap-csv 137E/JMA137E/prog/source_gpt/parula_256.csv`
2) Verify raw lines: see file/line references above.
3) Optional cross‑check: run the equality script in the Notes (h5py required).

## Next
- Add optional “MATLAB‑fidelity” mask: corner-based cell mask switch (`--render matlab|clean`) to toggle tooth-like gaps.

