# 137E 단면 — 축/틱 라벨 불일치 및 레이아웃 공백 — 2025-10-16

## 증상
- 원본(MATLAB) 그림과 비교 시, 재생성된 Python 그림에서
  - x축에 35°N을 넘어 50°N까지 라벨이 표시됨.
  - θ/S 패널(표시범위 0–1000 m)에서 축은 0–2000 m까지 보이는 것처럼 하단에 큰 공백이 남음.
  - 제목/컬러바 두께/폰트가 원본보다 약해 시각 가중치가 다르게 보임.

## 재현 경로
- 스크립트: `137E/JMA137E/prog/source_gpt/replot_196701_sections.py`
- 입력: `137E/anl/196701/anl/*.anl`
- 출력: `137E/JMA137E/prog/figure_gpt/Fig1_JMA_I*.png`

## 원인
1) 틱 라벨 수동 지정 실수
   - `ax.set_xticks(np.arange(0,55,5))` 후 `ax.set_xticklabels([...0°..50°N])`을 고정 리스트로 지정해, `xlim=(2,35)`와 상관없이 보이는 전체 축 라벨이 0–50°N으로 고정됨.
   - 수동 라벨은 로케이터(Locator)와 분리되어 범위/해상도 변경 시 쉽게 불일치 발생.

2) y축 틱 범위 고정에 따른 레이아웃 왜곡
   - `_setup_axes()`에서 `ax.set_yticks(np.arange(0,5200,200))`로 고정하여, θ/S 패널의 `ylim=(0,1000)`과 시각적 불일치가 발생. 렌더러가 여백을 과도하게 잡아 하단 공백처럼 보임.

3) 스타일 차이
   - 기본 폰트/컬러바 폭 사용으로 원본 대비 제목 가중치/컬러바 존재감이 작음.

## 교정(해결) 지침
1) 라벨링은 로케이터+포매터 조합 사용(수동 리스트 지양)
   - X(위도): `FixedLocator`(가시 범위 내 정수 5° 간격만) + `FuncFormatter`(‘0°’, ‘5°N’ 등)
   - Y(깊이): `FixedLocator(np.arange(0, ylim_max+1, 200))` + `FuncFormatter('{:d} m')`

2) 범위별 틱 제한
   - `ticks = np.arange(start, stop+step/2, step); ticks = ticks[(ticks>=x0)&(ticks<=x1)]`
   - `ax.set_xticks(ticks); ax.set_xlim(x0, x1)`
   - y축도 동일하게 `ylim`에 맞춰 major/minor 둘 다 재설정.

3) 레이아웃 잠금
   - 모든 아티팩트 추가 후 `ax.set_xlim/ylim` 재호출 → `ax.autoscale(enable=False)`로 잠금.
   - 필요 시 `bbox_inches='tight'` 저장, 컬러바는 `axes_grid1.make_axes_locatable`로 폭·여백 제어.

4) 스타일 정합
   - 제목 폰트크기(원본 수준), 스파인 두께(≈1.5), 컬러바 폭(2–2.5% fig 폭)로 조정.

## 참고 코드 스니펫
```python
from matplotlib.ticker import FixedLocator, FuncFormatter

def set_section_axes(ax, xlim=(2,35), ylim=(0,1000)):
    ax.set_xlim(*xlim); ax.set_ylim(*ylim); ax.invert_yaxis()
    # X ticks within view at 5° step
    xt = np.arange(0, 55, 5)
    xt = xt[(xt>=xlim[0]) & (xt<=xlim[1])]
    ax.xaxis.set_major_locator(FixedLocator(xt))
    ax.xaxis.set_minor_locator(FixedLocator(np.arange(0, 55, 1)))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v,pos: ('0°' if v==0 else f'{int(v)}°N')))
    # Y ticks within view at 200 m step
    yt = np.arange(0, ylim[1]+1, 200)
    ax.yaxis.set_major_locator(FixedLocator(yt))
    ax.yaxis.set_minor_locator(FixedLocator(np.arange(0, ylim[1]+1, 100)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v,pos: f'{int(v)} m'))
    ax.autoscale(enable=False)
```

## 상태
- 원인 파악 및 재도식 시 반영 완료. 지침 반영 필요(아래).

---

## (추가) Parula 상단 노랑 구간 미표시 — 2025-10-16

### 증상
- 동일 스케일(예: S 34.0–35.0)에서 원본(MATLAB) 컬러바는 상단이 선명한 노랑까지 포함되지만, 재생성본은 초록에서 끝나 노랑 구간이 보이지 않음.

### 원인
- 컬러레벨 문제가 아니라 컬러맵 자체가 축약됨.
  - 초기 구현은 Parula의 축약 샘플(노랑 직전까지)만 내장 후 256단계로 보간했음 → 상단 노랑이 결여.
  - `vmin/vmax`는 원본과 동일하여(예: 34.0–35.0) 스케일링 이슈가 아님을 확인.

### 해결
- `parula_colormap()`을 256‑스텝 Parula 테이블(상단 노랑 포함)로 교체해 `ListedColormap`으로 사용.
- 외부 패키지 의존 없이 스크립트 내장(재현성 보장). 필요 시 공식 256 RGB 표로 교체 가능.

### 코드 요지
```python
def parula_colormap():
    # data: 파룰라 원형에 맞춘 RGB 샘플(상단 노랑 포함)
    data = np.array([...])  # 상단 yellow까지 포함 샘플
    xi = np.linspace(0, data.shape[0]-1, 256)
    r = np.interp(xi, np.arange(data.shape[0]), data[:,0])
    g = np.interp(xi, np.arange(data.shape[0]), data[:,1])
    b = np.interp(xi, np.arange(data.shape[0]), data[:,2])
    return ListedColormap(np.stack([r,g,b], axis=1), name='parula_256')
```

### 링크
- 수정 파일: `137E/JMA137E/prog/source_gpt/replot_196701_sections.py`
- 비교 샘플: 염분 패널 색상(노랑 유무) — 재생성본 vs 원본

## 링크
- 원본: `137E/JMA137E/pic/Fig1_JMA_Iptem_196701_137E.png`
- 재생성본: `137E/JMA137E/prog/figure_gpt/Fig1_JMA_Iptem_196701_137E.png`
