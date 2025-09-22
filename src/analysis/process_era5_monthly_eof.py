import math
from pathlib import Path

import numpy as np
import xarray as xr

DATA_DIR = Path('/Volumes/HJPARK4/MHW/data/ERA5/daily')
OUTPUT_MONTHLY = Path('data/processed/era5_monthly.nc')
OUTPUT_EOF = Path('data/processed/era5_monthly_metss_eof.nc')
TARGET_VAR = 'metss'
CHUNKS = {'time': 744, 'latitude': 70, 'longitude': 140}


def build_monthly_dataset():
    files = sorted(DATA_DIR.glob('download*.nc'))
    if not files:
        raise FileNotFoundError(f'No download*.nc files found in {DATA_DIR}')

    OUTPUT_MONTHLY.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT_MONTHLY.exists():
        OUTPUT_MONTHLY.unlink()

    first = True
    for path in files:
        with xr.open_dataset(path, engine='netcdf4', chunks=CHUNKS) as ds:
            if TARGET_VAR not in ds:
                raise KeyError(f'{TARGET_VAR} not found in {path}')

            monthly = (
                ds[TARGET_VAR]
                .resample(time='MS')
                .mean()
                .astype('float32')
                .compute()
            )

            monthly_ds = monthly.to_dataset(name=TARGET_VAR)
            mode = 'w' if first else 'a'
            monthly_ds.to_netcdf(
                OUTPUT_MONTHLY,
                mode=mode,
                engine='netcdf4',
                unlimited_dims='time'
            )
            first = False

    return xr.open_dataset(OUTPUT_MONTHLY)


def compute_eof(monthly, n_modes=5):
    if 'metss' not in monthly:
        raise KeyError('Monthly dataset does not contain "metss" variable needed for EOF analysis')

    metss = monthly['metss']
    # Remove mean
    anom = metss - metss.mean(dim='time')

    lat = anom['latitude'].values
    lon = anom['longitude'].values

    # Weight by sqrt(cos(lat)) to respect area
    weights_lat = np.sqrt(np.cos(np.deg2rad(lat)))
    weights_2d = xr.DataArray(weights_lat[:, None], coords={'latitude': lat, 'longitude': lon}, dims=('latitude', 'longitude'))
    weighted = (anom * weights_2d).transpose('time', 'latitude', 'longitude')

    stacked = weighted.stack(space=('latitude', 'longitude'))
    data2d = stacked.to_numpy()

    # Mask invalid points
    valid_mask = np.isfinite(data2d).all(axis=0)
    data_valid = data2d[:, valid_mask]

    # Center already zero mean per grid cell; perform SVD
    u, s, vt = np.linalg.svd(data_valid, full_matrices=False)

    n_modes = min(n_modes, vt.shape[0])
    pcs = u[:, :n_modes] * s[:n_modes]
    total_variance = (s**2).sum()
    variance_fraction = (s[:n_modes]**2) / total_variance

    # Recover EOF patterns (unweight)
    weights_stack = (weights_lat[:, None] * np.ones((1, lon.size))).reshape(-1)

    eof_patterns = np.full((n_modes, stacked.space.size), np.nan, dtype='float32')
    eof_patterns[:, valid_mask] = vt[:n_modes, :]
    eof_patterns /= weights_stack
    eof_patterns = eof_patterns.reshape((n_modes, lat.size, lon.size))

    eof_da = xr.DataArray(
        eof_patterns,
        dims=('mode', 'latitude', 'longitude'),
        coords={'mode': np.arange(1, n_modes + 1), 'latitude': lat, 'longitude': lon},
        name='EOFs',
        attrs={'description': 'EOF spatial patterns of ERA5 eastward surface stress (metss)', 'units': 'N m-2'}
    )

    pc_da = xr.DataArray(
        pcs,
        dims=('time', 'mode'),
        coords={'time': anom['time'], 'mode': np.arange(1, n_modes + 1)},
        name='PCs',
        attrs={'description': 'Principal components corresponding to EOFs', 'units': 'N m-2'}
    )

    var_da = xr.DataArray(
        variance_fraction,
        dims=('mode',),
        coords={'mode': np.arange(1, n_modes + 1)},
        name='explained_variance_ratio'
    )

    eof_ds = xr.Dataset({'EOFs': eof_da, 'PCs': pc_da, 'explained_variance_ratio': var_da})
    eof_ds.to_netcdf(OUTPUT_EOF)
    return eof_ds


def main():
    monthly = build_monthly_dataset()
    compute_eof(monthly)


if __name__ == '__main__':
    main()
