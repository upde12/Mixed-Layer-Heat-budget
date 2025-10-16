# 4) 시각화 지침
<!-- owner: MLHB-core; canonical: true; depends_on: docs/guidelines/05_storage_output_guidelines.md; last_review: 2025-09-29 -->

## A. 공통 규칙
- 어떤 유형의 그림이든 먼저 `scripts/search_error_notes.py <키워드>`로 기존 이슈를 검토한다.
- 플롯에 사용할 데이터는 NaN/Inf 여부와 물리적 범위(예: 온도·염분·σ₀ 등)를 확인한 뒤 사용한다.
- 그림 형식별 세부 지침이 별도로 있으니, 지도형/등고선/프로파일 등 그림 목적에 따라 해당 섹션을 반드시 참고한다.

## B. 일반 플롯 체크리스트
1. 저장 파일명에 변수명·기간·주요 옵션을 포함한다.
2. 제목, 축 라벨, 컬러바/범례가 서로 겹치지 않도록 `constrained_layout` 또는 `fig.subplots_adjust()`로 여백을 조정한다.
3. 색상표·선색은 의미와 일관되게 선택하고, 색상표를 변경했다면 범례/주석 설명도 동시에 갱신한다.
4. 축 눈금은 가능한 한 실제 값(예: `FormatStrFormatter('%.2f')` 또는 `FuncFormatter`)으로 표시해 자동 오프셋(`+2e1`)이나 불필요한 0이 붙지 않도록 한다.
5. 데이터가 차지하는 범위를 기준으로 축 한계는 ±10% 여유를 두어(예: `pad_fraction=0.1`) 그림 공간을 효율적으로 사용한다.
6. 단위 표기는 Matplotlib의 수학 표기(`r"m$^{-2}$"` 등)를 활용해 명확히 적는다.
7. 플롯을 생성한 뒤 지침 체크리스트(데이터 범위, 축·라벨 겹침, 컬러맵-범례 일치 등)를 다시 검토해 미흡한 부분이 없도록 한다.
8. 다른 사람이 바로 확인할 수 있도록 Markdown/README 등에서 `![](path/to/figure.png)` 형태의 링크를 제공한다.
9. 같은 그림(동일 제목/변수/기간/옵션)을 수정·재생성할 때는 기존 파일을 삭제하거나 동일 파일명으로 원자적으로 교체한다. 히스토리 보존이 필요할 때만 접미사(`_v2`, 날짜 등)를 사용하고, 그 경우 문서/노트의 링크를 즉시 새 파일로 업데이트한다. 저장 방식은 `05_storage_output_guidelines.md`의 원자적 저장 규칙(`.tmp`→`os.replace`)을 따른다.
10. 소스코드(플로팅 스크립트/스타일/유틸) 변경 시, 해당 그림은 즉시 재렌더링해 반영한다(동일 파일명으로 원자 교체). 코드 변경이 적용되지 않은 오래된 그림을 문서·보고에 사용하지 않는다.
11. [신설] 그림을 저장할 때, 해당 그림을 생성한 소스코드의 사본을 같은 디렉터리에 함께 보관한다(권장: 동일 폴더 또는 하위 `scripts/`).
    - 파일명 권장: `<script_name>__<YYYYMMDD-HHMM>.py` 또는 `<script_name>__<short_commit>.py`.
    - 복사 시 원자적 교체 방식을 사용한다(`.tmp`→교체). 상세 저장 규칙은 `docs/guidelines/05_storage_output_guidelines.md` B/F 절을 따른다.

### B‑2. 레이아웃/라벨링(지도형 공통; 권장 기본값)
- 라벨 위치: 왼쪽 열만 y라벨, 하단 행만 x라벨을 노출하는 것을 권장한다(겹침/공간 제약 시 생략 가능).
- 그리드: 위·경도 5° 간격 고정 권장. Cartopy 사용 시 `LongitudeFormatter/LatitudeFormatter`로 °기호와 N/E 표기, Matplotlib 단독 시 `MultipleLocator(5)`+`FuncFormatter('{:.0f}°E')` 방식으로 동등 적용. 눈금 글꼴 7–10pt 범위에서 문서 형식에 맞춰 조정.
- 제목/폰트: 패널 제목≈11pt, 라벨/그리드≈8–10pt 권장(문서 레이아웃에 따라 ±1pt 조정). 스파인 두께≈0.7–0.8.
- 영역 고정: 데이터 범위로 `ax.set_extent([...])`를 적용해 잘림/여백 과소를 방지(필요 시 ±0.2° pad). 불규칙 좌표/정사영 외에는 PlateCarree 권장.
- 공통 스케일: 패널 공통 `vmin/vmax`를 권장(데이터 백분위 95–98% 대칭). 이산 레벨은 ≤21 유지. 끝값은 사람이 읽기 좋은 값(±1,1.5,2,2.5,3,5,6,8,10×10^k)으로 스냅을 권장.
- 컬러바: 단일 가로 컬러바를 하단에 배치. 겹침 방지를 위해 다음을 준수한다.
  - y위치는 하단 서브플롯의 `y0`보다 최소 0.06 낮게 배치하고, 절대 하한은 `y=0.03` 이상으로 유지한다.
  - 높이는 0.018–0.028 범위에서 문서 형식에 맞춰 조정한다.
  - 라벨은 `labelpad≥4`를 권장해 색막대와 글자 간격을 확보한다.
  - 겹침 발생 시 우선 컬러바 y를 더 낮추고, 필요한 경우 전체 `bottom` 여백을 +0.02 확장한다.
- 렌더러 표기(권장): 캡션/노트에 `renderer=cartopy` 또는 `renderer=mpl-fallback`을 간단히 표기해 재현성을 높인다.

### B‑3. 시즌 정렬 검증(ONDJ 등 경계 포함 계절)
- ELT형 계절(예: ONDJ=prev Oct–Dec + curr Jan) 합성은 연도 경계에 민감하다.
- 사전 검증:
  - ONDJ와 ONDJ_NEXT(=curr Oct–Dec + next Jan) 차맵을 생성해 Jan 기여/정렬을 확인한다.
  - 월 스택 마지막 해(`last_year`)를 명시하거나 CTL에서 자동 추정해 연도축 오프셋을 방지한다.
- 캡션 예: `seasons=ONDJ; last_year=2022; clim=1993–2021; mode=anomaly; adv_smooth_iter=0`.

### B‑1. 상관 지도(권장 설정)
- `corr(TEN, TOTAL)` 범위가 0.5–1.0인 경우, 0.05 간격 이산 11레벨을 사용(≤21 원칙 충족). 
- `BoundaryNorm`로 이산화, 컬러맵=`RdBu_r`, land 색상=`lightgrey`, `shading="nearest"`.

## C. 지도 및 등고선 시각화
- 기본 투영은 `PlateCarree`; 특수 투영이 필요하면 명시적으로 기록한다.
- land masking(육지/무효 격자)은 회색으로 표시한다(`cmap.set_bad('lightgrey')` 등). 데이터 색상표는 변수 특성에 맞게 유지한다(예: 발산형 `RdBu_r`, 연속형 `viridis`).
  - Cartopy/Matplotlib 사용 시 `ax.coastlines()`와 `cfeature.NaturalEarthFeature`로 육지·해안선을 추가하고 해상도(`50m` 등)를 일관되게 유지한다.
  - 필드가 왜곡되지 않도록 `transform=ccrs.PlateCarree()` 등 투영 인자를 명시한다.
  - 지도형 시각화에서는 반드시 육지를 마스킹한다(예: 유효 해양 격자만 색을 채우고, 육지는 `NaN`으로 두거나 별도 배경색 처리).
- **등고선/등치선**을 그릴 때는 다음을 준수한다.
  1. 값 범위 대비 적절한 레벨 수를 선택하고, 0을 포함할 때는 양·음 대칭을 유지한다.
  2. `contour`/`contourf`의 레벨 범위를 명시적으로 지정하며, legend나 colorbar를 통해 값 정보를 제공한다.
  3. 지도 기반 등고선은 지형 및 좌표 격자와 시각적으로 충돌하지 않도록 해상도·두께를 조정한다.
  4. 레벨 개수는 변수별로 최적화하되 21개를 넘지 않는다(과도한 색 구분으로 인한 가독성 저하 방지).
- 컬러바 단위를 명확히 표기하고, 동일 패널 내에서는 `vmin/vmax`를 공유해 비교 가능성을 유지한다.
- 쉐이딩(colormesh/contourf) 사용 시 colorbar의 색이 실제 그림 내 데이터에 모두 대응하도록 `vmin/vmax`/`bounds`/`norm`을 명시해 외삽 색이 나타나지 않게 한다(이산 마스크는 `ListedColormap`+`BoundaryNorm` 권장).
- 고해상도 데이터가 필요할 경우 Natural Earth 10m 리소스를 캐시해 사용한다.

### C‑0. 지도형 플롯 강제 규칙(항상)
- Cartopy 필수: 보고/출고용 지도는 Cartopy(PlateCarree)로 렌더링한다. Cartopy 미설치/실패 시 보고용 이미지 생성 금지(개발용 프리뷰만 허용).
- 해안선/육지: `coastlines(color='black', linewidth≈0.8)` + `NaturalEarthFeature('land','50m', edgecolor='black', facecolor='lightgrey', linewidth≈0.6)`.
- 그리드/라벨: 5° 고정(`MultipleLocator(5)`), °기호가 포함된 경·위도 포매터(`LongitudeFormatter/LatitudeFormatter`). 좌열만 y라벨, 하단만 x라벨을 노출한다.
- 영역 고정: `ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=PlateCarree())`로 데이터 범위를 고정(잘림/여백 과소 방지).
- 컬러바: 단일 가로 컬러바를 하단에 배치한다. 축 눈금과 겹치지 않도록 y위치에 0.06–0.08 여백을 두고, 높이는 0.022–0.028로 설정한다.
- 스케일/레벨: 공통 `vmin/vmax`는 데이터 백분위(권장 95–98%)를 대칭으로 사용하고, 끝값은 사람이 읽기 좋은 값(±{1,1.5,2,2.5,3,5,6,8,10}×10^k)으로 스냅한다. 이산 레벨은 ≤21.
- 폰트/스파인: 제목≈11pt, 축·그리드 라벨≈9–10pt, 스파인 두께≈0.7–0.8.
- 원자적 저장: `.tmp`→`os.replace`로 교체하여 문서 링크가 끊기지 않게 한다.

예시(파이썬 스니펫)
```python
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.ticker import LatitudeFormatter, LongitudeFormatter
import matplotlib.ticker as mticker

fig, ax = plt.subplots(subplot_kw=dict(projection=ccrs.PlateCarree()), figsize=(4.2, 3.2))
land50 = cfeature.NaturalEarthFeature('physical','land','50m', edgecolor='black', facecolor='lightgrey', linewidth=0.6)
ax.add_feature(land50, zorder=0)
ax.coastlines(resolution='50m', color='black', linewidth=0.8)
gl = ax.gridlines(draw_labels=True, linewidth=0.3, color='gray', alpha=0.4, linestyle=':')
gl.xlocator = mticker.MultipleLocator(5); gl.ylocator = mticker.MultipleLocator(5)
gl.xformatter = LongitudeFormatter(number_format='.0f', degree_symbol='°')
gl.yformatter = LatitudeFormatter(number_format='.0f', degree_symbol='°')
gl.top_labels = gl.right_labels = False; gl.left_labels = True; gl.bottom_labels = True
ax.set_extent([lon.min(), lon.max(), lat.min(), lat.max()], crs=ccrs.PlateCarree())
```

### C‑1. 지도 요소 권장 기본값(권장·유연 적용)
- Coastlines: 해안선은 검은색(`color='black'`)·`linewidth≈0.8`로 렌더링한다.
- Land: 육지는 연회색(`facecolor='lightgrey'`)으로 칠하고, 윤곽선(`edgecolor='black'`, `linewidth≈0.6`)을 함께 표시한다(`NaturalEarthFeature('land','50m')`).
- Gridlines: `linewidth≈0.3`, `color='gray'`, `alpha≈0.4`, `linestyle=':'`.
- 라벨 표기: 5° 고정 눈금과 °기호가 포함된 포매터를 사용한다(예: 125°E, 35°N).

### C‑2. 패널(3×2) 권장 여백/간격(참고값·상황 조정)
- left=0.08, right=0.985, top=0.97, bottom=0.18, wspace=0.10, hspace=0.12.
- 컬러바 높이=0.025, y위치=최하단 패널 y0−0.06~0.08 범위에서 조정.

## D. 혼합층 프로파일 시각화
- GLORYS 서브셋의 위·경도 범위(예: 20–45°N, 110–140°E)를 먼저 확인하고, 해안/얕은 수심에서 `mlotst`가 NaN일 수 있으므로 후보 지점을 고른 뒤 유효 값을 확인한다.
- σ₀ 계산에는 TEOS-10 라이브러리(`gsw`)를 사용한다. `SA_from_SP`, `CT_from_pt`, `sigma0` 호출이 가능하도록 환경에 `gsw` 설치 여부를 점검한다.
- 플롯 체크리스트
  1. 잠재온도(°C), 염분(psu), σ₀(kg m⁻³)를 하나의 그림에 중첩한다. `gsw`로 변환한 값이 물리적 범위(예: T ∈ [−5,40] °C, S ∈ [0,40], σ₀ ∈ [20,30])에 있는지 확인한다.
  2. 각 축/라벨 색상을 곡선 색상과 동일하게 맞추고, `ax.twiny()` 축은 서로 다른 spine 위치(예: 1.05/1.18)와 `xaxis.set_label_coords()`(예: 0.5, 1.13/1.30)로 라벨을 숫자 위에 충분히 띄워 배치한다. tick `pad`는 작게(≈2) 두어 숫자가 축에 바짝 붙도록 한다.
  3. 혼합층 깊이(`mlotst`)는 점선으로 표시해 표층 대비 σ₀ 증가를 시각적으로 확인한다.
  4. 표층 vs. 혼합층 하단 σ₀ 차이를 수치로 출력해 GLORYS 정의(10 m 대비 약 0.2 °C 등가 밀도 증가)와 일관성을 검증한다.
  5. 혼합층 구조만 볼 때는 y축을 표층 근처(예: 0–200 m)로 제한한다.
- 스크립트 예시: `python scripts/plot_mld_profile.py --file <nc> --lat <lat> --lon <lon> --out <png> --max-depth 200`.

## E. 재현성 메모
- 지도/등고선 코드 스니펫은 `src/visualization` 하위에 모듈화해 재사용성을 높인다.
- 외부 환경에서 실행 시 필요한 패키지(`cartopy`, `shapely`, `pyproj`, `gsw`) 버전을 README 또는 환경파일에 반영한다.
 - 저장 경로/라이브러리 구조 일반 원칙은 `docs/guidelines/05_storage_output_guidelines.md`를 따른다.

## F. 소스 변경→즉시 재생성 정책(강화)
- 적용 범위: `src/visualization/**`, `scripts/plot_*.py`, 패널/지도 렌더러, 색상·레벨·마스크 로직, 캡션 주석 등 시각 출력에 영향을 주는 모든 코드 변경.
- 원칙
  - 코드 변경을 커밋/저장했다면, 영향 받는 그림은 즉시 재렌더링한다.
  - 파일명은 그대로 유지하고 원자적으로 교체해(임시파일→`os.replace`) 문서 링크가 끊기지 않게 한다.
  - 캡션/주석에 코드·설정 요약(윈도우, 스무딩, 마스크/정책, 단위, 스케일 방식)을 포함해 재현성 추적성을 높인다.
  - 임시적 시각 보정(예: 특정 항만 부호 flip)은 캡션에 반드시 명시한다(`DIFFV_flip=yes` 등) — 검증/재산출이 끝나면 제거한다.
- 권장 워크플로(예)
  - 패널/지도 재렌더(MLHB 예시)
    ```bash
    . .venv/bin/activate
    python llm-ops/scripts/source_panel_mlhb.py \
      --monthly "/Volumes/HJPARK4/Decadal/source/ML_budget/output/monthly/mlhb_monthly_main_*.nc" \
      --trend-output "/Volumes/HJPARK4/Decadal/Figure/decadal_mlhb/trend_offset.png" \
      --rhs-output   "/Volumes/HJPARK4/Decadal/Figure/decadal_mlhb/rhs_native.png" \
      --rhs-prc 98 --trend-vclip 2.5 --adv-smooth-iter 0 --dpi 170
    ```
  - 변경 감지 후 재렌더(간단 쉘 패턴)
    ```bash
    SRC=llm-ops/scripts/source_panel_mlhb.py
    OUT=/Volumes/HJPARK4/Decadal/Figure/decadal_mlhb/rhs_native.png
    if [ "$SRC" -nt "$OUT" ]; then
      python "$SRC" ... --rhs-output "$OUT"
    fi
    ```
- QA 체크(출고 전)
  - [ ] 변경된 코드 버전/커밋과 그림 타임스탬프가 일치하는가?
  - [ ] 스케일 방식이 명시되었는가? (백분위/클립 값)
  - [ ] 정책/예외(예: flip, 마스크)가 캡션에 기록되었는가?

### B‑4. 단면형(137E 스타일) 축/틱 가이드
- 축 범위 고정: θ·S 패널 `ylim=0–1000 m`, σθ 패널 `ylim=0–2000 m`; `ax.autoscale(False)`로 잠금.
- 로케이터/포매터 사용: 수동 `set_xticklabels([...])` 지양. `FixedLocator`+`FuncFormatter`로 5° 간격 라벨(‘0°’, ‘5°N’, …)을 가시 범위 내에서만 표시.
- 틱 범위 제한: `ticks = np.arange(start, stop+step/2, step)` 생성 후 `xlim/ylim` 내 값만 적용. minor 틱도 동일하게 제한.
- 깊이 라벨: major 200 m, minor 100 m; 문자열은 ‘N m’ 형식 고정.
- 컬러바: 세로 막대 폭을 패널 높이의 2–2.5% 수준으로 설정(axes_grid1 권장), 눈금 간격은 변수별(θ 2°C, S 0.1, σθ 1) 고정.
- 예시 코드(요지)
```python
from matplotlib.ticker import FixedLocator, FuncFormatter

xt = np.arange(0, 55, 5); xt = xt[(xt>=x0) & (xt<=x1)]
ax.xaxis.set_major_locator(FixedLocator(xt))
ax.xaxis.set_minor_locator(FixedLocator(np.arange(0,55,1)))
ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p: ('0°' if v==0 else f'{int(v)}°N')))

yt = np.arange(0, y1+1, 200)
ax.yaxis.set_major_locator(FixedLocator(yt))
ax.yaxis.set_minor_locator(FixedLocator(np.arange(0, y1+1, 100)))
ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p: f'{int(v)} m'))
ax.set_xlim(x0,x1); ax.set_ylim(0,y1); ax.autoscale(False)
```

참고: 관련 이슈 및 교훈은 `docs/error_notes/visualization/20251016_137E_axis_ticks_layout_mismatch.md`를 확인한다.
