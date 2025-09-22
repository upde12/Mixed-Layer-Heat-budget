# 4) 지도형 시각화 지침

## A. 공통 규칙
- **위·경도 격자 지도**를 그릴 땐 항상 **지형(육지)과 해안선**을 함께 표시한다.
- 기본 투영은 `PlateCarree`; 특수 투영이 필요하면 명시적으로 기록한다.
- 데이터 필드가 왜곡되지 않도록 `transform=ccrs.PlateCarree()` 등 투영 인자를 정확히 지정한다.

## B. 구현 체크리스트
1. Cartopy/Matplotlib 사용 시 `ax.add_feature(cfeature.LAND, facecolor='lightgray')`, `ax.coastlines()` 호출을 기본 포함한다.
2. 컬러바 단위를 명확히 표기하고, 동일 패널 내에서는 `vmin/vmax`를 공유해 비교 가능성을 유지한다.
3. **영을 중심으로 변동하는 변수**(advection, 응력 등)를 시각화할 때는 `vmin`과 `vmax`를 절대값 기준으로 대칭(예: ±1.5)으로 두고, `cmap='coolwarm'` 또는 사용자 정의 diverging 컬러맵을 사용해 `0` 주변이 흰색, 양수는 붉은색, 음수는 푸른색으로 표현한다.
4. 패널 조합 그래프는 `constrained_layout=True` 또는 `fig.subplots_adjust()`를 활용해 여백을 최소화하고, 필요 없는 여분 제목/라벨을 제거해 공간 효율을 높인다.
5. 그리드라인 라벨은 과도하지 않게 조정하고, 경도는 °E/°W, 위도는 °N/°S 표기 규약을 따른다.
6. 고해상도 데이터가 필요할 경우 Natural Earth 10m 리소스를 캐시해 사용한다.
7. 지도 저장 파일명에는 변수명, 기간, `with_land` 여부 등 맥락을 포함한다.

## C. 재현성 메모
- 지도 코드 스니펫은 `src/visualization` 하위에 모듈화해 재사용성을 높인다.
- 외부 환경에서 실행 시 필요한 패키지(`cartopy`, `shapely`, `pyproj`) 버전을 README 또는 환경파일에 반영한다.
