"""Cartopy-based map plotting utilities aligned with project guidelines.

The script draws vector/scalar surface fields on a PlateCarree map while
following the in-repo plotting checklist. It also encodes the cartopy
broadcasting fix recorded in the visualization error note (2025-09-22).
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Tuple

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter

PLATE_CARREE = ccrs.PlateCarree()


def _select_time_slice(field: xr.DataArray, time_selector: str) -> xr.DataArray:
    """Return a latitude/longitude slice chosen via index or datetime-like string."""
    if time_selector.isdigit():
        return field.isel(time=int(time_selector))
    try:
        return field.sel(time=np.datetime64(time_selector))
    except (KeyError, ValueError):
        raise ValueError(
            "`time` must be an integer index or ISO-like timestamp present in the data."
        )


def _broadcast_lon_lat(field: xr.DataArray) -> Tuple[np.ndarray, np.ndarray]:
    """Return 2D longitude/latitude arrays aligned with the field.

    Uses :func:`xr.broadcast` to avoid the "length 1" longitude bug recorded in
    ``docs/error_notes/visualization/20250922_1735_cartopy.md``.
    """
    lon = field.coords["longitude"]
    lat = field.coords["latitude"]
    lon2d, lat2d = xr.broadcast(lon, lat)
    return lon2d.values, lat2d.values


def _diverging_limits(field: xr.DataArray, percentile: float = 98.0) -> Tuple[float, float]:
    data = field.values
    mask = np.isfinite(data)
    if not mask.any():
        raise ValueError("Selected field contains no finite values.")
    envelope = float(np.nanpercentile(np.abs(data[mask]), percentile))
    if envelope == 0.0:
        envelope = float(np.nanmax(np.abs(data[mask])))
    if envelope == 0.0:
        envelope = 1.0
    return -envelope, envelope


def _format_title(field: xr.DataArray) -> str:
    variable = field.name or "variable"
    time_val = field.coords.get("time")
    if time_val is not None:
        if np.isscalar(time_val.values):
            timestamp = np.datetime_as_string(time_val.values, unit="D")
        else:
            timestamp = str(time_val.values)
        return f"{variable} at {timestamp}"
    return variable


def plot_scalar_field(
    dataset_path: Path,
    variable: str,
    time_selector: str,
    output_path: Path | None = None,
    percentile: float = 98.0,
    cmap: str = "coolwarm",
) -> Path:
    """Draw a PlateCarree map for a scalar surface field and save it to disk."""
    dataset_path = Path(dataset_path)
    output_dir = Path("figures")
    output_dir.mkdir(parents=True, exist_ok=True)

    with xr.open_dataset(dataset_path) as ds:
        field = ds[variable]
        slice_da = _select_time_slice(field, time_selector)

    lon2d, lat2d = _broadcast_lon_lat(slice_da)
    vmin, vmax = _diverging_limits(slice_da, percentile=percentile)

    fig = plt.figure(figsize=(9, 4.5), constrained_layout=True)
    ax = plt.axes(projection=PLATE_CARREE)
    ax.set_global()
    ax.set_extent([
        float(slice_da.longitude.min()),
        float(slice_da.longitude.max()),
        float(slice_da.latitude.min()),
        float(slice_da.latitude.max()),
    ], crs=PLATE_CARREE)
    ax.add_feature(cfeature.LAND, facecolor="lightgray", zorder=0)
    ax.coastlines()

    mesh = ax.pcolormesh(
        lon2d,
        lat2d,
        slice_da.values,
        cmap=cmap,
        vmin=vmin,
        vmax=vmax,
        transform=PLATE_CARREE,
    )

    cbar = plt.colorbar(mesh, ax=ax, orientation="horizontal", pad=0.05, fraction=0.05)
    units = slice_da.attrs.get("units")
    if units:
        cbar.set_label(units)

    ax.set_title(_format_title(slice_da))

    gl = ax.gridlines(draw_labels=True, dms=False, x_inline=False, y_inline=False)
    gl.top_labels = False
    gl.right_labels = False
    gl.xformatter = LongitudeFormatter(number_format=".0f", degree_symbol="°",)
    gl.yformatter = LatitudeFormatter(number_format=".0f", degree_symbol="°")

    if output_path is None:
        timestamp = slice_da.coords["time"].dt.strftime("%Y%m").item()
        output_path = output_dir / f"{variable}_{timestamp}_with_land.png"
    else:
        output_path = Path(output_path)

    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PlateCarree map plotter")
    parser.add_argument(
        "--dataset",
        default="data/processed/era5_monthly.nc",
        help="Path to NetCDF dataset with longitude/latitude/time dimensions.",
    )
    parser.add_argument(
        "--variable",
        default="metss",
        help="Variable name to plot (default: metss).",
    )
    parser.add_argument(
        "--time",
        required=True,
        help="Time index (integer) or timestamp (e.g. 1993-01-01).",
    )
    parser.add_argument(
        "--percentile",
        type=float,
        default=98.0,
        help="Percentile for symmetric color scaling (default: 98).",
    )
    parser.add_argument(
        "--output",
        help="Optional explicit output path. Defaults to figures/<var>_<time>_with_land.png",
    )
    parser.add_argument(
        "--cmap",
        default="coolwarm",
        help="Matplotlib colormap to use (default: coolwarm).",
    )
    return parser


def main(args: list[str] | None = None) -> Path:
    parser = build_arg_parser()
    parsed = parser.parse_args(args=args)
    return plot_scalar_field(
        dataset_path=Path(parsed.dataset),
        variable=parsed.variable,
        time_selector=parsed.time,
        output_path=Path(parsed.output) if parsed.output else None,
        percentile=parsed.percentile,
        cmap=parsed.cmap,
    )


if __name__ == "__main__":
    saved_path = main()
    print(f"Saved figure to {saved_path}")
