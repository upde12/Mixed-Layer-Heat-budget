"""Python reproduction of the NCL-based mixed-layer heat budget diagnostics.

This script mirrors the data ingest, anomaly/regression calculations, and plotting
performed by ``Figure/source.ncl`` located in the external Decadal work tree.
It reads the precomputed binary fields, applies the same 9-point smoothing to the
horizontal advection term, computes the linear trend offsets and RHS anomalies, and
exports two figures: a stand-alone "total" trend map and a compact 3x2 panel with
the remaining RHS terms.

Example
-------
Run the script from the repository root (adjust base directory if needed)::

    python -m src.analysis.source_panel \
        --base-dir /Volumes/HJPARK4/Decadal \
        --trend-output figures/budget3_total.pdf \
        --rhs-output figures/budget3_rhs.pdf

If the output paths are omitted, both PDFs are written next to the original
``budget3`` figures under ``Figure`` inside the Decadal directory.
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
import matplotlib.pyplot as plt

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
except ImportError:  # pragma: no cover - optional dependency
    ccrs = None
    cfeature = None

SECONDS_PER_DAY = 86400.0
DAYS_PER_YEAR = 365.0
FILL_VALUE = 9.96921e36

Shape4D = Tuple[int, int, int, int]


def _format_level_label(value: float) -> str:
    """Return a readable tick label without losing significant information."""
    if not np.isfinite(value):
        return ""
    if abs(value) < 1e-12:
        return "0"

    text = f"{value:.6f}"
    cleaned = text.rstrip("0").rstrip(".")
    if cleaned in {"-0", "-0."}:
        return "0"
    return cleaned


def _select_tick_values(levels: Iterable[float], max_labels: int = 8) -> np.ndarray:
    values = np.asarray(list(levels), dtype=float)
    if values.size <= max_labels:
        return values

    first, last = values[0], values[-1]
    size = values.size
    min_step = 1
    while (size - 1) // min_step + 1 > max_labels:
        min_step += 1

    zero_idx = int(np.argmin(np.abs(values))) if first < 0 < last else None

    candidate_steps = [s for s in range(min_step, size) if (size - 1) // s + 1 <= max_labels]
    if not candidate_steps:
        candidate_steps = [min_step]

    chosen_step = candidate_steps[0]
    if zero_idx is not None:
        prioritized = [
            s
            for s in candidate_steps
            if zero_idx % s == 0 and (size - 1) % s == 0
        ]
        if not prioritized:
            prioritized = [s for s in candidate_steps if zero_idx % s == 0]
        if prioritized:
            chosen_step = prioritized[0]
    else:
        divisible = [s for s in candidate_steps if (size - 1) % s == 0]
        if divisible:
            chosen_step = divisible[0]

    indices = list(range(0, size, chosen_step))
    if indices[-1] != size - 1:
        indices.append(size - 1)

    if zero_idx is not None and zero_idx not in indices:
        indices.append(zero_idx)

    indices = sorted(set(indices))

    base_values = values[indices]
    if zero_idx is not None:
        zero_value = values[zero_idx]
        neg = base_values[base_values < 0]
        pos = base_values[base_values > 0]
        spacing = values[1] - values[0]
        # enforce symmetry by mirroring available ticks around zero
        mirrored_neg = [-p for p in pos]
        mirrored_pos = [-n for n in neg]
        combined = np.concatenate((base_values, mirrored_neg, mirrored_pos, [zero_value]))
        base_values = np.unique(np.round(combined, decimals=6))

    return np.sort(base_values)


def _set_colorbar_ticks(cbar, values: Iterable[float]) -> None:
    numeric = np.asarray(list(values), dtype=float)
    labels = [_format_level_label(val) for val in numeric]
    if cbar.orientation == "horizontal":
        cbar.ax.set_xticks(numeric)
        cbar.ax.set_xticklabels(labels)
    else:
        cbar.ax.set_yticks(numeric)
        cbar.ax.set_yticklabels(labels)


def read_fbinary(path: Path, shape: Shape4D, dtype: np.dtype = np.float32) -> np.ndarray:
    """Read a flat binary float array and reshape to *shape*.

    The files were written by NCL's ``fbindirwrite`` using little-endian 32-bit floats.
    """
    total = math.prod(shape)
    data = np.fromfile(path, dtype=dtype)
    if data.size != total:
        raise ValueError(
            f"Unexpected size for {path}: got {data.size} floats, expected {total}"
        )
    array = data.reshape(shape).astype(np.float32, copy=False)
    mask = np.abs(array) >= FILL_VALUE * 0.1
    array[mask] = np.nan  # treat canonical fill values as NaN
    return array


def shift_lat(arr: np.ndarray, offset: int) -> np.ndarray:
    """Shift array along the latitude dimension (-2) inserting NaNs where data is missing."""
    if offset == 0:
        return arr.copy()
    result = np.full_like(arr, np.nan)
    if offset > 0:
        result[..., offset:, :] = arr[..., :-offset, :]
    else:  # offset < 0, shift northwards
        result[..., :offset, :] = arr[..., -offset:, :]
    return result


def shift_lon(arr: np.ndarray, offset: int, wrap: bool) -> np.ndarray:
    """Shift array along longitude (last dim)."""
    if offset == 0:
        return arr.copy()
    if wrap:
        shifted = np.roll(arr, shift=offset, axis=-1)
        return shifted
    result = np.full_like(arr, np.nan)
    if offset > 0:
        result[..., :, offset:] = arr[..., :, :-offset]
    else:
        result[..., :, :offset] = arr[..., :, -offset:]
    return result


def smth9(data: np.ndarray, p: float, q: float, wrap: bool) -> np.ndarray:
    """Apply NCL's ``smth9`` nine-point smoother to the last two dimensions.

    Parameters mirror NCL's signature:
    ``p`` weights the four orthogonal neighbours (N, S, E, W) and ``q`` weights the
    diagonal neighbours. Set ``wrap`` to ``True`` to make the longitude dimension cyclic.
    Missing values (NaNs) are preserved as in the original routine - if the centre cell
    or any of its eight neighbours are NaN, the centre value is returned unchanged.
    """
    if data.ndim < 2:
        raise ValueError("smth9 expects at least 2-D input")

    leading_size = int(np.prod(data.shape[:-2]))
    ny, nx = data.shape[-2:]
    reshaped = data.reshape(leading_size, ny, nx)
    out = np.empty_like(reshaped)

    for idx, plane in enumerate(reshaped):
        centre = plane
        north = shift_lat(centre, -1)
        south = shift_lat(centre, 1)
        west = shift_lon(centre, -1, wrap)
        east = shift_lon(centre, 1, wrap)

        northwest = shift_lon(north, -1, wrap)
        northeast = shift_lon(north, 1, wrap)
        southwest = shift_lon(south, -1, wrap)
        southeast = shift_lon(south, 1, wrap)

        valid_mask = (
            np.isfinite(centre)
            & np.isfinite(north)
            & np.isfinite(south)
            & np.isfinite(east)
            & np.isfinite(west)
            & np.isfinite(northwest)
            & np.isfinite(northeast)
            & np.isfinite(southwest)
            & np.isfinite(southeast)
        )

        updated = centre.copy()
        if np.any(valid_mask):
            sides = west + east + north + south
            corners = northwest + northeast + southwest + southeast
            updated_vals = (
                centre[valid_mask]
                + (p / 4.0)
                * (sides[valid_mask] - 4.0 * centre[valid_mask])
                + (q / 4.0)
                * (corners[valid_mask] - 4.0 * centre[valid_mask])
            )
            updated[valid_mask] = updated_vals
        updated[~np.isfinite(centre)] = np.nan
        out[idx] = updated

    return out.reshape(data.shape)


def linear_regression_slope(time: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Return the least-squares slope along axis 0 while respecting NaNs."""
    time = np.asarray(time, dtype=np.float64)
    vals = np.asarray(values, dtype=np.float64)
    if vals.shape[0] != time.size:
        raise ValueError("Time axis length must match the first dimension of values")

    demeaned_time = time - time.mean()
    reshape = (time.size,) + (1,) * (vals.ndim - 1)
    time_reshaped = demeaned_time.reshape(reshape)
    mask = np.isfinite(vals)

    vals_masked = np.where(mask, vals, np.nan)
    mean_vals = np.nanmean(vals_masked, axis=0)

    numerator = np.nansum(time_reshaped * (vals_masked - mean_vals), axis=0)
    denominator = np.nansum((demeaned_time**2).reshape(reshape) * mask, axis=0)

    slope = np.full_like(mean_vals, np.nan, dtype=np.float64)
    valid = denominator > 0
    slope[valid] = numerator[valid] / denominator[valid]
    return slope


@dataclass
class BudgetFields:
    lat: np.ndarray
    lon: np.ndarray
    trend_offset: np.ndarray
    rhs_anomalies_native: np.ndarray
    rhs_anomalies_residual: np.ndarray


def _compute_rhs_anomalies(
    rhs: np.ndarray,
    ti: int,
    tl: int,
) -> np.ndarray:
    """Return annual-mean RHS anomalies scaled to W m⁻²."""

    RHSm = np.nanmean(rhs, axis=2)
    RHSmm = np.nanmean(RHSm, axis=1)
    RHSa = RHSm - RHSmm[:, None, :, :]
    rhs_anom = np.nanmean(RHSa[:, ti : tl + 1, :, :], axis=1)
    # Convert K s^-1 to K decade^-1
    rhs_anom *= SECONDS_PER_DAY * DAYS_PER_YEAR * 10.0
    return rhs_anom


def compute_budget_fields(base_dir: Path) -> BudgetFields:
    """Replicate the diagnostic calculations from ``source.ncl``."""
    base_dir = base_dir.expanduser().resolve()
    data_dir = base_dir / "output" / "budget_gpt"

    shape = (30, 12, 301, 361)

    T = read_fbinary(data_dir / "T_ML.data", shape)
    qnet = read_fbinary(data_dir / "qnet.data", shape)
    adv = read_fbinary(data_dir / "adv.data", shape)
    adv = smth9(adv, 0.50, 0.25, wrap=True)
    adv = smth9(adv, 0.50, 0.25, wrap=True)
    adv = smth9(adv, 0.50, 0.25, wrap=True)

    ent = read_fbinary(data_dir / "ent.data", shape)
    diff = read_fbinary(data_dir / "diff.data", shape)
    diffv_native = read_fbinary(data_dir / "diffv.data", shape)
    ten = read_fbinary(data_dir / "ten.data", shape)

    # Derive vertical diffusion residually so that Qnet + subsurface terms closes to ten.
    diffv_residual = ten.astype(np.float64)
    diffv_residual -= qnet
    diffv_residual -= adv
    diffv_residual -= ent
    diffv_residual -= diff
    diffv_residual = diffv_residual.astype(np.float32)

    rhs_native = np.empty((6,) + shape, dtype=np.float32)
    rhs_native[0] = qnet
    rhs_native[2] = adv.astype(np.float32)
    rhs_native[3] = ent
    rhs_native[4] = diff
    rhs_native[5] = diffv_native
    rhs_native[1] = np.nansum(rhs_native[2:6], axis=0)

    rhs_residual = rhs_native.copy()
    rhs_residual[5] = diffv_residual
    rhs_residual[1] = np.nansum(rhs_residual[2:6], axis=0)

    Tm = np.nanmean(T, axis=1)
    Tmm = np.nanmean(Tm, axis=0)

    Ta = Tm - Tmm

    ti = 2011 - 1993
    tl = 2022 - 1993

    time_short = np.linspace(2011.0, 2022.0, num=tl - ti + 1)
    time_full = np.linspace(1993.0, 2022.0, num=Tm.shape[0])

    short_slope = linear_regression_slope(time_short, Ta[ti : tl + 1])
    full_slope = linear_regression_slope(time_full, Ta)

    trend_offset = short_slope - full_slope
    trend_offset[np.isclose(trend_offset, 0.0, atol=1e-10)] = np.nan
    trend_offset *= 10.0

    rhs_anom_native = _compute_rhs_anomalies(rhs_native, ti, tl)
    rhs_anom_residual = _compute_rhs_anomalies(rhs_residual, ti, tl)

    lat = np.linspace(20.0, 45.0, 301)
    lon = np.linspace(110.0, 140.0, 361)

    return BudgetFields(
        lat=lat,
        lon=lon,
        trend_offset=trend_offset,
        rhs_anomalies_native=rhs_anom_native,
        rhs_anomalies_residual=rhs_anom_residual,
    )


def add_common_map_decor(ax, *, left_labels: bool = True, bottom_labels: bool = True) -> None:
    if ccrs is None:
        ax.set_xlim(110, 140)
        ax.set_ylim(20, 45)
        ax.set_aspect("auto")
        if bottom_labels:
            ax.set_xlabel("Longitude")
        else:
            ax.set_xlabel("")
        if left_labels:
            ax.set_ylabel("Latitude")
        else:
            ax.set_ylabel("")
        return

    ax.set_extent([110, 140, 20, 45], crs=ccrs.PlateCarree())
    coastline_width = 1.0 if ccrs is not None else 1.0
    land_edge_width = 0.6
    ax.coastlines(resolution="50m", linewidth=coastline_width, color="black")
    land_feature = cfeature.NaturalEarthFeature(
        "physical",
        "land",
        "50m",
        edgecolor="black",
        facecolor="none",
    )
    ax.add_feature(land_feature, linewidth=land_edge_width)
    gl = ax.gridlines(draw_labels=True, linestyle="--", linewidth=0.5, color="grey")
    gl.top_labels = False
    gl.right_labels = False
    gl.left_labels = left_labels
    gl.bottom_labels = bottom_labels


def plot_trend_map(fields: BudgetFields, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    subplot_kwargs = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
    fig, ax = plt.subplots(figsize=(5.5, 5.2), subplot_kw=subplot_kwargs)
    fig.subplots_adjust(left=0.08, right=0.96, top=0.9, bottom=0.2)

    lon2d, lat2d = np.meshgrid(fields.lon, fields.lat)
    cmap = plt.get_cmap("RdBu_r")
    levels_trend = np.linspace(-2.5, 2.5, 21)

    cs = ax.contourf(
        lon2d,
        lat2d,
        fields.trend_offset,
        levels=levels_trend,
        cmap=cmap,
        extend="both",
        transform=ccrs.PlateCarree() if ccrs is not None else None,
    )
    add_common_map_decor(ax)
    ax.set_title("Trend Offset (2011-2022 minus 1993-2022)", pad=6)

    pos = ax.get_position()
    cax = fig.add_axes([pos.x0, pos.y0 - 0.06, pos.width, 0.02])
    trend_ticks = _select_tick_values(levels_trend, max_labels=7)
    cbar = fig.colorbar(cs, cax=cax, orientation="horizontal", ticks=trend_ticks)
    cbar.set_label(r"K decade$^{-1}$")
    _set_colorbar_ticks(cbar, trend_ticks)

    fig.savefig(output)
    plt.close(fig)


def plot_rhs_panels(
    fields: BudgetFields,
    rhs_anomalies: np.ndarray,
    output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    subplot_kwargs = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}

    fig_height = 11.0
    left, right = 0.055, 0.985
    top, bottom = 0.97, 0.12
    hspace = 0.12
    wspace = 0.10

    lon_span = float(fields.lon[-1] - fields.lon[0])
    lat_span = float(fields.lat[-1] - fields.lat[0])
    available_height = fig_height * (top - bottom)
    axis_height = available_height / (3 + 2 * hspace)
    axis_width = axis_height * (lon_span / lat_span)
    available_width = axis_width * (2 + wspace)
    fig_width = available_width / (right - left)
    # Automatically pick the width that keeps GeoAxes aspect and balances
    # horizontal/vertical gaps (~0.35 in each direction).

    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = fig.add_gridspec(
        3,
        2,
        left=left,
        right=right,
        top=top,
        bottom=bottom,
        wspace=wspace,
        hspace=hspace,
    )

    axes_matrix = []
    for row in range(3):
        row_axes = []
        for col in range(2):
            ax = fig.add_subplot(gs[row, col], **subplot_kwargs)
            row_axes.append(ax)
        axes_matrix.append(row_axes)
    axes = np.array(axes_matrix)

    lon2d, lat2d = np.meshgrid(fields.lon, fields.lat)
    cmap = plt.get_cmap("RdBu_r")
    # RHS anomalies are in K decade^-1; empirical scale ~O(100) after conversion
    levels_rhs = np.linspace(-100.0, 100.0, 17)

    titles = [
        "Surface Heat Flux (Qnet)",
        "Adv.+Ent.+Diff.",
        "Horizontal Advection",
        "Entrainment",
        "Lateral Diffusion",
        "Vertical Diffusion",
    ]

    axes = axes.ravel()
    mappables: list[plt.cm.ScalarMappable] = []

    for idx, (ax, arr, title) in enumerate(zip(axes, rhs_anomalies, titles)):
        row, col = divmod(idx, 2)
        data = np.array(arr, copy=True)
        if idx == 1:
            mask = np.isclose(data, 0.0, atol=1e-8)
            data = np.where(mask, np.nan, data)
        cs = ax.contourf(
            lon2d,
            lat2d,
            data,
            levels=levels_rhs,
            cmap=cmap,
            extend="both",
            transform=ccrs.PlateCarree() if ccrs is not None else None,
        )
        add_common_map_decor(ax, left_labels=(col == 0), bottom_labels=(row == 2))
        label = f"({chr(ord('a') + idx)})"
        ax.set_title(f"{label} {title}", pad=6, loc="left")
        mappables.append(cs)

    positions = [ax.get_position() for ax in axes]
    x0 = min(pos.x0 for pos in positions)
    x1 = max(pos.x1 for pos in positions)
    y0 = min(pos.y0 for pos in positions) - 0.05
    cax = fig.add_axes([x0, y0, x1 - x0, 0.02])
    rhs_ticks = _select_tick_values(levels_rhs, max_labels=9)
    cbar = fig.colorbar(mappables[0], cax=cax, orientation="horizontal", ticks=rhs_ticks)
    cbar.set_label(r"K decade$^{-1}$")
    _set_colorbar_ticks(cbar, rhs_ticks)

    fig.savefig(output)
    plt.close(fig)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_base = Path("/Volumes/HJPARK4/Decadal")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=default_base,
        help="Root of the Decadal dataset (contains Figure/, output/, data/).",
    )
    parser.add_argument(
        "--trend-output",
        type=Path,
        default=None,
        help="Destination for the total trend map. Defaults to Figure/budget3_trend_python.png.",
    )
    parser.add_argument(
        "--rhs-output",
        type=Path,
        default=None,
        help="Destination for the RHS panel figure using native diffv. Defaults to Figure/budget3_rhs_native_python.png.",
    )
    parser.add_argument(
        "--rhs-residual-output",
        type=Path,
        default=None,
        help="Destination for the RHS panel figure using residual diffv. Defaults to Figure/budget3_rhs_residual_python.png.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    figure_dir = args.base_dir / "Figure"
    trend_output = args.trend_output or (figure_dir / "budget3_trend_python.png")
    rhs_output = args.rhs_output or (figure_dir / "budget3_rhs_native_python.png")
    rhs_residual_output = args.rhs_residual_output or (
        figure_dir / "budget3_rhs_residual_python.png"
    )

    fields = compute_budget_fields(args.base_dir)
    plot_trend_map(fields, trend_output)
    plot_rhs_panels(fields, fields.rhs_anomalies_native, rhs_output)
    plot_rhs_panels(fields, fields.rhs_anomalies_residual, rhs_residual_output)


if __name__ == "__main__":
    main()
