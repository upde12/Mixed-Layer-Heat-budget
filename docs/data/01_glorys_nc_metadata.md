# GLORYS Daily Physics File Metadata (from `ncdump -h`)

## Core dimensions
- `time`: length 1, units `hours since 1950-01-01` (gregorian calendar)
- `depth`: length 50, increasing positively downward, units `m`
- `latitude`: length 301, units `degrees_north`
- `longitude`: length 361, units `degrees_east`

## Coordinate variables
| Name      | Dimensions | Units             | Notes |
|-----------|------------|-------------------|-------|
| `time`    | `time`     | hours since 1950-01-01 | Axis `T`, long name "Time" |
| `depth`   | `depth`    | m                 | Axis `Z`, positive down |
| `latitude`| `latitude` | degrees_north     | Axis `Y` |
| `longitude`| `longitude` | degrees_east    | Axis `X` |

## Data variables
| Name    | Dimensions                       | Units      | Scale factor | Add offset | Fill value | Description |
|---------|----------------------------------|------------|--------------|------------|------------|-------------|
| `thetao`| `time, depth, latitude, longitude` | degrees_C | 7.32444226741791e-04 | 21.0       | -32767      | Sea-water potential temperature |
| `uo`    | `time, depth, latitude, longitude` | m s-1     | 6.10370188951492e-04 | 0.0        | -32767      | Eastward velocity |
| `vo`    | `time, depth, latitude, longitude` | m s-1     | 6.10370188951492e-04 | 0.0        | -32767      | Northward velocity |
| `mlotst`| `time, latitude, longitude`        | m         | 0.152592554688454    | -0.152592554688454 | -32767 | Density ocean mixed layer thickness |
| `so`    | `time, depth, latitude, longitude` | 1e-3      | 0.00152592547237873 | -0.00152592547237873 | -32767 | Sea-water salinity |

### Valid range information
- `thetao`: valid_min `-32766`, valid_max `21306`
- `uo`: valid_min `-3123`, valid_max `4314`
- `vo`: valid_min `-3680`, valid_max `3639`
- `mlotst`: valid_min `1`, valid_max `4525`
- `so`: valid_min `1`, valid_max `28249`

> **주의:** Copernicus PUM(2024)에서는 `mlotst`를 “10 m 깊이 대비 0.2 °C 등가의 밀도 증가가 발생하는 깊이”라고 설명하지만, NetCDF 메타데이터에는 구체적인 온도 기준이 명시되어 있지 않습니다. 실제 값은 대체로 0.001–0.05 kg m⁻³ 수준(≈0.01–0.1 °C 등가)으로 나타나므로, 분석 시 제품 버전·자료 설명서를 다시 확인하고 사용하는 것이 안전합니다.

## Global attributes
- `institution`: MERCATOR OCEAN
- `source`: MERCATOR GLORYS12V1
- `history`: `2023/06/01 16:20:05 MERCATOR OCEAN Netcdf creation`
- `title`: `daily mean fields from Global Ocean Physics Analysis and Forecast updated Daily`
- `Conventions`: `CF-1.4`
- `references`: <http://www.mercator-ocean.fr>
- `comment`: `CMEMS product`
- `copernicusmarine_version`: `2.2.1`

## Coding notes
- Use `_FillValue` (short integers) when detecting missing data before applying scale/offset.
- Convert stored short integers to physical units: `physical_value = scale_factor * raw_value + add_offset`.
- The time coordinate uses hours since 1950-01-01; convert to datetime as needed.
- Depth axis increases downward; remember to handle sign conventions in derivative calculations.
