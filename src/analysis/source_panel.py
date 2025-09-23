"""Python reproduction of the NCL-based mixed-layer heat budget panel figure.

This script mirrors the data ingest, anomaly/regression calculations, and plotting
performed by ``Figure/source.ncl`` located in the external Decadal work tree.
It reads the precomputed binary fields, applies the same 9-point smoothing to the
horizontal advection term, computes the linear trend offsets and RHS anomalies, and
renders the 4x2 panel figure.

Example
-------
Run the script from the repository root (adjust base directory if needed)::

    python -m src.analysis.source_panel \
        --base-dir /Volumes/HJPARK4/Decadal \
        --output figures/budget3_python.pdf

The output filename is optional; by default the PDF is written next to the original
``budget3.pdf`` under ``Figure`` inside the Decadal directory.
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
    rhs_anomalies: np.ndarray


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

    ent = read_fbinary(data_dir / "ent.data", shape)
    diff = read_fbinary(data_dir / "diff.data", shape)
    diffv = read_fbinary(data_dir / "diffv.data", shape)

    rhs = np.empty((6,) + shape, dtype=np.float32)
    rhs[0] = qnet
    rhs[2] = adv.astype(np.float32)
    rhs[3] = ent
    rhs[4] = diff
    rhs[5] = diffv
    rhs[1] = np.nansum(rhs[2:6], axis=0)

    Tm = np.nanmean(T, axis=1)
    RHSm = np.nanmean(rhs, axis=2)

    Tmm = np.nanmean(Tm, axis=0)
    RHSmm = np.nanmean(RHSm, axis=1)

    Ta = Tm - Tmm
    RHSa = RHSm - RHSmm[:, None, :, :]

    ti = 2011 - 1993
    tl = 2022 - 1993

    time_short = np.linspace(2011.0, 2022.0, num=tl - ti + 1)
    time_full = np.linspace(1993.0, 2022.0, num=Tm.shape[0])

    short_slope = linear_regression_slope(time_short, Ta[ti : tl + 1])
    full_slope = linear_regression_slope(time_full, Ta)

    trend_offset = short_slope - full_slope
    trend_offset[np.isclose(trend_offset, 0.0, atol=1e-10)] = np.nan
    trend_offset *= 10.0

    rhs_anom = np.nanmean(RHSa[:, ti : tl + 1, :, :], axis=1)
    rhs_anom *= SECONDS_PER_DAY * DAYS_PER_YEAR

    lat = np.linspace(20.0, 45.0, 301)
    lon = np.linspace(110.0, 140.0, 361)

    return BudgetFields(lat=lat, lon=lon, trend_offset=trend_offset, rhs_anomalies=rhs_anom)


def add_common_map_decor(ax):
    if ccrs is None:
        ax.set_xlim(110, 140)
        ax.set_ylim(20, 45)
        ax.set_aspect("auto")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        return

    ax.set_extent([110, 140, 20, 45], crs=ccrs.PlateCarree())
    ax.coastlines(resolution="110m", linewidth=0.8)
    ax.add_feature(cfeature.LAND, facecolor="none", edgecolor="black", linewidth=0.3)
    gl = ax.gridlines(draw_labels=True, linestyle="--", linewidth=0.5, color="grey")
    gl.top_labels = False
    gl.right_labels = False


def plot_budget_panels(fields: BudgetFields, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)

    subplot_kwargs = {"projection": ccrs.PlateCarree()} if ccrs is not None else {}
    fig, axes = plt.subplots(4, 2, figsize=(9, 11), subplot_kw=subplot_kwargs)
    axes = axes.ravel()

    lon2d, lat2d = np.meshgrid(fields.lon, fields.lat)

    cmap = plt.get_cmap("RdBu_r")
    levels_trend = np.linspace(-1.5, 1.5, 17)
    levels_rhs = np.linspace(-10.0, 10.0, 17)

    panels = [fields.trend_offset] + [fields.rhs_anomalies[i] for i in range(fields.rhs_anomalies.shape[0])]
    titles = [
        "Trend Offset (2011-2022 minus 1993-2022)",
        "Surface Heat Flux (Qnet)",
        "Sum of Subsurface Terms",
        "Horizontal Advection",
        "Entrainment",
        "Lateral Diffusion",
        "Vertical Diffusion",
    ]

    mappables = []
    for idx, (ax, arr) in enumerate(zip(axes, panels)):
        levels = levels_trend if idx == 0 else levels_rhs
        cs = ax.contourf(
            lon2d,
            lat2d,
            arr,
            levels=levels,
            cmap=cmap,
            extend="both",
            transform=ccrs.PlateCarree() if ccrs is not None else None,
        )
        add_common_map_decor(ax)
        ax.set_title(titles[idx])
        label = chr(ord("a") + idx)
        ax.text(
            0.02,
            0.95,
            f"({label})",
            transform=ax.transAxes,
            fontsize=12,
            fontweight="bold",
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="black", linewidth=0.6),
        )
        mappables.append(cs)

    # Hide any unused slots (the last subplot in the 4x2 grid).
    for ax in axes[len(panels) :]:
        ax.set_visible(False)

    cbar1 = fig.colorbar(mappables[0], ax=axes[:1], orientation="horizontal", pad=0.08)
    cbar1.set_label("K decade^-1")

    cbar2 = fig.colorbar(mappables[1], ax=axes[1:], orientation="horizontal", pad=0.06)
    cbar2.set_label("W m^-2")

    fig.tight_layout()
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
        "--output",
        type=Path,
        default=None,
        help="Destination PDF/PNG file. Defaults to Figure/budget3_python.pdf inside the base directory.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    output = args.output or (args.base_dir / "Figure" / "budget3_python.pdf")
    fields = compute_budget_fields(args.base_dir)
    plot_budget_panels(fields, output)


if __name__ == "__main__":
    main()
