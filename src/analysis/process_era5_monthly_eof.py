import argparse
import math
import re
from pathlib import Path

import numpy as np
import xarray as xr

DATA_DIR = Path('/Volumes/HJPARK4/MHW/data/ERA5/daily')
OUTPUT_MONTHLY = Path('data/processed/era5_monthly.nc')
OUTPUT_EOF = Path('data/processed/era5_monthly_metss_eof.nc')
TARGET_VAR = 'metss'
CHUNKS = {'time': 744, 'latitude': 70, 'longitude': 140}


def _filter_files(files, start_year=None, end_year=None):
    def extract_year(path: Path) -> int:
        match = re.match(r'download(\d{4})', path.stem)
        if not match:
            return None
        return int(match.group(1))

    selected = []
    for f in files:
        year = extract_year(f)
        if year is None:
            continue
        if start_year is not None and year < start_year:
            continue
        if end_year is not None and year > end_year:
            continue
        selected.append(f)
    return selected


def build_monthly_dataset(start_year=None, end_year=None, resume=False):
    files = sorted(DATA_DIR.glob('download*.nc'))
    if not files:
        raise FileNotFoundError(f'No download*.nc files found in {DATA_DIR}')

    files = _filter_files(files, start_year, end_year)
    if not files:
        raise ValueError('선택한 연도 범위에 해당하는 파일이 없습니다.')

    OUTPUT_MONTHLY.parent.mkdir(parents=True, exist_ok=True)
    new_monthlies = []
    for path in files:
        with xr.open_dataset(path, engine='netcdf4', chunks=CHUNKS) as ds:
            if TARGET_VAR not in ds:
                raise KeyError(f'{TARGET_VAR} not found in {path}')

            print(f'[{path.name}] 월평균 계산 중...')
            monthly = (
                ds[TARGET_VAR]
                .resample(time='MS')
                .mean()
                .astype('float32')
                .compute()
            )
            new_monthlies.append(monthly)
            print(f'[{path.name}] 저장 준비 완료')

    combined = xr.concat(new_monthlies, dim='time') if new_monthlies else None
    if combined is None:
        raise RuntimeError('월평균 계산 결과가 비어 있습니다.')

    if resume and OUTPUT_MONTHLY.exists():
        with xr.open_dataset(OUTPUT_MONTHLY) as existing_ds:
            existing = existing_ds[TARGET_VAR]
            combined = xr.concat([existing, combined], dim='time')

    combined_ds = combined.to_dataset(name=TARGET_VAR)
    combined_ds.to_netcdf(OUTPUT_MONTHLY, mode='w', engine='netcdf4')
    print(f'총 {combined.sizes["time"]} 개 월평균 기록 저장 완료')
    return xr.open_dataset(OUTPUT_MONTHLY)


def compute_eof(monthly, n_modes=5):
    if 'metss' not in monthly:
        raise KeyError('Monthly dataset does not contain "metss" variable needed for EOF analysis')

    print('EOF 분석 시작...')
    metss = monthly['metss']
    # Remove mean
    anom = metss - metss.mean(dim='time')

    lat = anom['latitude'].values
    lon = anom['longitude'].values

    # Weight by sqrt(cos(lat)) to respect area
    weights_lat = np.sqrt(np.cos(np.deg2rad(lat)))
    weights_2d = xr.DataArray(
        weights_lat[:, None] * np.ones((lat.size, lon.size)),
        coords={'latitude': lat, 'longitude': lon},
        dims=('latitude', 'longitude')
    )
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
    print('EOF 분석 완료: 결과 저장됨')
    return eof_ds


def main():
    parser = argparse.ArgumentParser(description='ERA5 월평균 및 EOF 계산')
    parser.add_argument('--start-year', type=int, help='처리 시작 연도 (예: 1993)')
    parser.add_argument('--end-year', type=int, help='처리 종료 연도 (예: 1997)')
    parser.add_argument('--resume', action='store_true', help='기존 월평균 파일 유지 후 이어서 기록')
    parser.add_argument('--skip-eof', action='store_true', help='EOF 계산을 건너뜀')
    args = parser.parse_args()

    monthly = build_monthly_dataset(args.start_year, args.end_year, args.resume)
    if not args.skip_eof:
        compute_eof(monthly)


if __name__ == '__main__':
    main()
