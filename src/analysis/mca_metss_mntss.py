#!/usr/bin/env python3
"""Perform MCA between ERA5 metss and mntss for 1993 00UTC data."""
from __future__ import annotations

import numpy as np
import xarray as xr
from pathlib import Path

DATA_PATH = Path('/Volumes/HJPARK4/MHW/data/ERA5/daily/download1993.nc')
OUTPUT_PATH = Path('data/processed/mca_metss_mntss_1993.nc')
N_MODES = 5


def load_fields(path: Path):
    ds = xr.open_dataset(path)
    ds = ds[['metss', 'mntss']].sel(time=ds.time.dt.hour == 0)
    ds = ds.astype('float32').load()
    return ds


def apply_weights(field: xr.DataArray) -> xr.DataArray:
    lat = field['latitude']
    weights = np.sqrt(np.cos(np.deg2rad(lat)))
    weights_da = xr.DataArray(weights, coords={'latitude': lat}, dims=('latitude',))
    return field * weights_da


def stack_space(field: xr.DataArray) -> xr.DataArray:
    return field.stack(space=('latitude', 'longitude'))


def demean(field: xr.DataArray) -> xr.DataArray:
    return field - field.mean(dim='time')


def compute_mca(x: xr.DataArray, y: xr.DataArray, n_modes: int):
    # x, y: time x space (DataArray stacked)
    t = x.sizes['time']
    # SVD of x and y
    X = x.values
    Y = y.values

    Ux, Sx, Vhx = np.linalg.svd(X, full_matrices=False)
    Uy, Sy, Vhy = np.linalg.svd(Y, full_matrices=False)

    Vx = Vhx.T
    Vy = Vhy.T

    T = Ux.T @ Uy
    A = (Sx[:, None] * T) * Sy[None, :]

    P, s, Qt = np.linalg.svd(A, full_matrices=False)
    Q = Qt.T

    left_patterns = Vx @ P
    right_patterns = Vy @ Q

    tx = Ux @ (Sx[:, None] * P)
    ty = Uy @ (Sy[:, None] * Q)

    return s[:n_modes], left_patterns[:, :n_modes], right_patterns[:, :n_modes], tx[:, :n_modes], ty[:, :n_modes]


def main():
    ds = load_fields(DATA_PATH)
    metss = demean(apply_weights(ds['metss']))
    mntss = demean(apply_weights(ds['mntss']))

    metss_stacked = stack_space(metss)
    mntss_stacked = stack_space(mntss)

    s, left, right, tx, ty = compute_mca(metss_stacked, mntss_stacked, N_MODES)

    weights_lat = np.sqrt(np.cos(np.deg2rad(ds['latitude'].values)))
    weights_flat = np.repeat(weights_lat, ds['longitude'].size)

    left_patterns = (left / weights_flat[:, None]).reshape(len(ds['latitude']), len(ds['longitude']), -1)
    right_patterns = (right / weights_flat[:, None]).reshape(len(ds['latitude']), len(ds['longitude']), -1)

    modes = np.arange(1, N_MODES + 1)
    eof_ds = xr.Dataset(
        {
            'sigma': xr.DataArray(s[:N_MODES], dims=('mode',), coords={'mode': modes}),
            'metss_patterns': xr.DataArray(left_patterns[:, :, :N_MODES], dims=('latitude', 'longitude', 'mode'),
                                           coords={'latitude': ds['latitude'], 'longitude': ds['longitude'], 'mode': modes}),
            'mntss_patterns': xr.DataArray(right_patterns[:, :, :N_MODES], dims=('latitude', 'longitude', 'mode'),
                                           coords={'latitude': ds['latitude'], 'longitude': ds['longitude'], 'mode': modes}),
            'metss_time_series': xr.DataArray(tx[:, :N_MODES], dims=('time', 'mode'),
                                              coords={'time': ds['time'], 'mode': modes}),
            'mntss_time_series': xr.DataArray(ty[:, :N_MODES], dims=('time', 'mode'),
                                              coords={'time': ds['time'], 'mode': modes}),
        }
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    eof_ds.to_netcdf(OUTPUT_PATH)


if __name__ == '__main__':
    main()
