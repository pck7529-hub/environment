# app.py
# 고1 통합과학 환경오염 단원용
# 서울시 대기오염 측정정보를 네이버 지도 위에 시각화하는 Streamlit 앱

import json
import random
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components


# =========================
# 1. 기본 설정
# =========================

st.set_page_config(
    page_title="서울 대기오염 탐구 지도",
    page_icon="🌫️",
    layout="wide"
)

st.title("🌫️ 서울 대기오염 탐구 지도")
st.caption("고등학교 1학년 통합과학 · 환경오염 단원 탐구 활동용 웹앱")


# =========================
# 2. 서울시 자치구 측정소 좌표
#    실제 수업에서는 측정소 정보 API와 연결해도 되지만,
#    Streamlit Cloud에서 안정적으로 실행되도록 주요 자치구 좌표를 기본 탑재함
# =========================

DISTRICT_COORDS = {
    "종로구": (37.572950, 126.979357),
    "중구": (37.563646, 126.997330),
    "용산구": (37.532527, 126.990490),
    "성동구": (37.563341, 127.037102),
    "광진구": (37.538617, 127.082375),
    "동대문구": (37.574368, 127.040019),
    "중랑구": (37.606324, 127.092584),
    "성북구": (37.589400, 127.016749),
    "강북구": (37.639610, 127.025657),
    "도봉구": (37.668773, 127.047071),
    "노원구": (37.654259, 127.056294),
    "은평구": (37.617612, 126.922700),
    "서대문구": (37.579225, 126.936800),
    "마포구": (37.566324, 126.901491),
    "양천구": (37.516872, 126.866399),
    "강서구": (37.550979, 126.849538),
    "구로구": (37.495486, 126.887537),
    "금천구": (37.456872, 126.895426),
    "영등포구": (37.526371, 126.896228),
    "동작구": (37.512402, 126.939252),
    "관악구": (37.478154, 126.951484),
    "서초구": (37.483712, 127.032411),
    "강남구": (37.517236, 127.047325),
    "송파구": (37.514543, 127.105936),
    "강동구": (37.530125, 127.123762),
}


# =========================
# 3. 대기오염 물질 기준
#    색상은 학생들이 직관적으로 비교하도록 단계화함
# =========================

POLLUTANTS = {
    "PM10": {
        "label": "미세먼지 PM10",
        "unit": "㎍/㎥",
        "thresholds": [30, 80, 150],
        "explain": "입자가 비교적 큰 먼지입니다. 도로 재비산먼지, 공사장, 황사, 연소 과정 등이 영향을 줄 수 있습니다."
    },
    "PM25": {
        "label": "초미세먼지 PM2.5",
        "unit": "㎍/㎥",
        "thresholds": [15, 35, 75],
        "explain": "매우 작은 입자입니다. 자동차 배출가스, 난방, 산업 활동, 2차 생성 입자 등이 영향을 줄 수 있습니다."
    },
    "O3": {
        "label": "오존 O₃",
        "unit": "ppm",
        "thresholds": [0.030, 0.090, 0.150],
        "explain": "햇빛이 강한 낮 시간에 질소산화물과 휘발성유기화합물이 광화학 반응을 일으키며 높아질 수 있습니다."
    },
    "NO2": {
        "label": "이산화질소 NO₂",
        "unit": "ppm",
        "thresholds": [0.030, 0.060, 0.200],
        "explain": "차량 통행, 보일러, 연소 과정과 관련이 큽니다. 출퇴근 시간대 도로 주변에서 높아질 수 있습니다."
    },
    "CO": {
        "label": "일산화탄소 CO",
        "unit": "ppm",
        "thresholds": [2, 9, 15],
        "explain": "불완전 연소에서 발생합니다. 차량, 난방, 화재, 밀폐된 공간의 연소 활동과 관련됩니다."
    },
    "SO2": {
        "label": "아황산가스 SO₂",
        "unit": "ppm",
        "thresholds": [0.020, 0.050, 0.150],
        "explain": "황 성분이 포함된 연료의 연소, 일부 산업 활동과 관련됩니다."
    },
}


def get_grade_and_color(value, thresholds):
    """농도값을 4단계 등급과 색으로 변환"""
    if pd.isna(value):
        return "자료 없음", "#9e9e9e"

    if value <= thresholds[0]:
        return "낮음", "#2ecc71"      # 초록
    elif value <= thresholds[1]:
        return "보통", "#f1c40f"      # 노랑
    elif value <= thresholds[2]:
        return "높음", "#e67e22"      # 주황
    else:
        return "매우 높음", "#e74c3c"  # 빨강


# =========================
# 4. 데이터 불러오기 함수
# =========================

@st.cache_data(ttl=600)
def fetch_seoul_air_data(api_key, service_name):
    """
    서울 열린데이터광장 API 호출
    기본 URL 형식:
    http://openapi.seoul.go.kr:8088/{KEY}/json/{SERVICE}/1/1000/
    """
    url = f"http://openapi.seoul.go.kr:8088/{api_key}/json/{service_name}/1/1000/"
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    data = response.json()

    # 서울 API는 최상위 키가 서비스명인 경우가 많음
    # 예: {"서비스명": {"list_total_count": ..., "row": [...]}}
    rows = None
    for value in data.values():
        if isinstance(value, dict) and "row" in value:
            rows = value["row"]
            break

    if rows is None:
        raise ValueError(f"API 응답에서 row 데이터를 찾지 못했습니다. 응답 일부: {str(data)[:300]}")

    return pd.DataFrame(rows)


def make_sample_data():
    """API 키가 없을 때도 수업 시연이 가능하도록 샘플 데이터 생성"""
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    rows = []

    for district, (lat, lng) in DISTRICT_COORDS.items():
        rows.append({
            "MSRDT": now.strftime("%Y%m%d%H"),
            "MSRSTE_NM": district,
            "PM10": random.randint(15, 120),
            "PM25": random.randint(5, 65),
            "O3": round(random.uniform(0.010, 0.120), 3),
            "NO2": round(random.uniform(0.010, 0.090), 3),
            "CO": round(random.uniform(0.2, 1.8), 1),
            "SO2": round(random.uniform(0.002, 0.030), 3),
        })

    return pd.DataFrame(rows)


def normalize_columns(df):
    """
    서울 데이터의 컬럼명이 달라져도 최대한 대응하기 위한 정리 함수
    """
    df = df.copy()

    rename_candidates = {
        "측정일시": "MSRDT",
        "측정시간": "MSRDT",
        "측정소명": "MSRSTE_NM",
        "자치구": "MSRSTE_NM",
        "구분": "MSRSTE_NM",
        "미세먼지": "PM10",
        "초미세먼지": "PM25",
        "오존": "O3",
        "이산화질소": "NO2",
        "일산화탄소": "CO",
        "아황산가스": "SO2",
    }

    df = df.rename(columns={c: rename_candidates.get(c, c) for c in df.columns})

    # 날짜 컬럼 처리
    if "MSRDT" in df.columns:
        df["MSRDT"] = df["MSRDT"].astype(str)
        df["DATETIME"] = pd.to_datetime(df["MSRDT"], format="%Y%m%d%H", errors="coerce")

        # 다른 형식의 날짜일 경우 재시도
        if df["DATETIME"].isna().all():
            df["DATETIME"] = pd.to_datetime(df["MSRDT"], errors="coerce")
    else:
        df["DATETIME"] = datetime.now().replace(minute=0, second=0, microsecond=0)

    # 측정소명 또는 자치구명 처리
    if "MSRSTE_NM" not in df.columns:
        df["MSRSTE_NM"] = "알 수 없음"

    # 숫자형 변환
    for col in POLLUTANTS.keys():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 좌표 붙이기
    df["lat"] = df["MSRSTE_NM"].map(lambda x: DISTRICT_COORDS.get(str(x), (None, None))[0])
    df["lng"] = df["MSRSTE_NM"].map(lambda x: DISTRICT_COORDS.get(str(x), (None, None))[1])

    # 좌표가 없는 행 제거
    df = df.dropna(subset=["lat", "lng"])

    return df


# =========================
# 5. 사이드바 입력
# =========================

st.sidebar.header("⚙️ 데이터·지도 설정")

default_seoul_key = st.secrets.get("SEOUL_API_KEY", "") if hasattr(st, "secrets") else ""
default_naver_key = st.secrets.get("NAVER_MAP_CLIENT_ID", "") if hasattr(st, "secrets") else ""

seoul_api_key = st.sidebar.text_input(
    "서울데이터광장 API 키",
    value=default_seoul_key,
    type="password",
    help="Streamlit Cloud에서는 Secrets에 SEOUL_API_KEY로 저장할 수 있습니다."
)

naver_client_id = st.sidebar.text_input(
    "네이버 Maps API Client ID / ncpKeyId",
    value=default_naver_key,
    type="password",
    help="Streamlit Cloud에서는 Secrets에 NAVER_MAP_CLIENT_ID로 저장할 수 있습니다."
)

service_name = st.sidebar.text_input(
    "서울데이터광장 서비스명",
    value="airHour",
    help="데이터셋의 Open API 서비스명을 입력합니다. 만약 오류가 나면 서울데이터광장 API 화면의 서비스명을 확인해 바꿔 주세요."
)

uploaded_file = st.sidebar.file_uploader(
    "또는 CSV 파일 업로드",
    type=["csv"],
    help="서울데이터광장에서 내려받은 AIR_HOUR_YYYY.csv 파일을 업로드하면 과거 날짜·시간 탐구가 가능합니다."
)


# =========================
# 6. 데이터 로딩
# =========================

data_source_message = ""

try:
    if uploaded_file is not None:
        # 서울시 CSV는 보통 CP949 또는 UTF-8 계열일 수 있어 두 번 시도
        try:
            raw_df = pd.read_csv(uploaded_file, encoding="utf-8")
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            raw_df = pd.read_csv(uploaded_file, encoding="cp949")

        data_source_message = "업로드한 CSV 파일을 사용 중입니다."

    elif seoul_api_key:
        raw_df = fetch_seoul_air_data(seoul_api_key, service_name)
        data_source_message = "서울데이터광장 Open API 데이터를 사용 중입니다."

    else:
        raw_df = make_sample_data()
        data_source_message = "API 키가 없어 수업 시연용 샘플 데이터를 사용 중입니다."

except Exception as e:
    st.error("데이터를 불러오는 중 문제가 발생했습니다.")
    st.exception(e)
    st.info("API 키 또는 서비스명을 확인해 주세요. 수업 시연을 위해 샘플 데이터로 전환합니다.")
    raw_df = make_sample_data()
    data_source_message = "오류 발생으로 샘플 데이터를 사용 중입니다."

df = normalize_columns(raw_df)

st.info(data_source_message)


# =========================
# 7. 탐구 조건 선택
# =========================

if df.empty:
    st.warning("지도에 표시할 수 있는 데이터가 없습니다. 측정소명과 좌표 매칭을 확인해 주세요.")
    st.stop()

available_times = sorted(df["DATETIME"].dropna().unique())

if len(available_times) == 0:
    selected_time = None
    time_filtered = df.copy()
else:
    selected_time = st.sidebar.selectbox(
        "탐구할 날짜·시간 선택",
        options=available_times,
        format_func=lambda x: pd.to_datetime(x).strftime("%Y-%m-%d %H:00")
    )
    time_filtered = df[df["DATETIME"] == selected_time].copy()

pollutant = st.sidebar.selectbox(
    "탐구할 대기오염 물질",
    options=list(POLLUTANTS.keys()),
    format_func=lambda x: f"{POLLUTANTS[x]['label']} ({POLLUTANTS[x]['unit']})"
)

if pollutant not in time_filtered.columns:
    st.warning(f"현재 데이터에 {pollutant} 컬럼이 없습니다.")
    st.stop()

pollutant_info = POLLUTANTS[pollutant]
unit = pollutant_info["unit"]
thresholds = pollutant_info["thresholds"]

time_filtered["value"] = pd.to_numeric(time_filtered[pollutant], errors="coerce")
time_filtered[["grade", "color"]] = time_filtered["value"].apply(
    lambda x: pd.Series(get_grade_and_color(x, thresholds))
)

time_filtered = time_filtered.dropna(subset=["value"])


# =========================
# 8. 핵심 지표
# =========================

col1, col2, col3, col4 = st.columns(4)

avg_value = time_filtered["value"].mean()
max_row = time_filtered.loc[time_filtered["value"].idxmax()] if not time_filtered.empty else None
min_row = time_filtered.loc[time_filtered["value"].idxmin()] if not time_filtered.empty else None

col1.metric("선택 물질", pollutant_info["label"])
col2.metric("서울 평균", f"{avg_value:.3g} {unit}" if pd.notna(avg_value) else "-")
col3.metric("가장 높은 지점", f"{max_row['MSRSTE_NM']} · {max_row['value']:.3g}" if max_row is not None else "-")
col4.metric("가장 낮은 지점", f"{min_row['MSRSTE_NM']} · {min_row['value']:.3g}" if min_row is not None else "-")


# =========================
# 9. 네이버 지도 HTML 생성
# =========================

def make_naver_map_html(map_data, naver_key, pollutant_label, unit):
    """Streamlit components로 네이버 지도와 원형 마커 표시"""

    points = []
    for _, row in map_data.iterrows():
        points.append({
            "name": str(row["MSRSTE_NM"]),
            "lat": float(row["lat"]),
            "lng": float(row["lng"]),
            "value": None if pd.isna(row["value"]) else float(row["value"]),
            "grade": str(row["grade"]),
            "color": str(row["color"]),
        })

    points_json = json.dumps(points, ensure_ascii=False)

    html = f"""
    <div id="map" style="width:100%;height:620px;border-radius:16px;"></div>

    <script type="text/javascript"
        src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId={naver_key}">
    </script>

    <script>
    const points = {points_json};

    const map = new naver.maps.Map('map', {{
        center: new naver.maps.LatLng(37.5665, 126.9780),
        zoom: 11,
        zoomControl: true,
        zoomControlOptions: {{
            position: naver.maps.Position.TOP_RIGHT
        }}
    }});

    const infoWindow = new naver.maps.InfoWindow({{
        borderWidth: 0,
        backgroundColor: "white",
        anchorSize: new naver.maps.Size(12, 12)
    }});

    points.forEach(function(p) {{
        const marker = new naver.maps.Circle({{
            map: map,
            center: new naver.maps.LatLng(p.lat, p.lng),
            radius: 850,
            strokeColor: p.color,
            strokeOpacity: 0.95,
            strokeWeight: 2,
            fillColor: p.color,
            fillOpacity: 0.58
        }});

        const label = new naver.maps.Marker({{
            position: new naver.maps.LatLng(p.lat, p.lng),
            map: map,
            icon: {{
                content: `
                    <div style="
                        padding:4px 7px;
                        background:white;
                        border:1px solid #444;
                        border-radius:10px;
                        font-size:12px;
                        font-weight:700;
                        box-shadow:0 1px 4px rgba(0,0,0,0.25);
                        white-space:nowrap;">
                        ${{p.name}}<br>${{p.value}}
                    </div>
                `,
                anchor: new naver.maps.Point(28, 12)
            }}
        }});

        naver.maps.Event.addListener(marker, 'click', function() {{
            infoWindow.setContent(`
                <div style="padding:12px;min-width:190px;font-family:Arial, sans-serif;">
                    <b style="font-size:15px;">${{p.name}}</b><br>
                    <span>{pollutant_label}</span><br>
                    <b style="font-size:20px;color:${{p.color}};">${{p.value}} {unit}</b><br>
                    <span>등급: ${{p.grade}}</span>
                </div>
            `);
            infoWindow.open(map, new naver.maps.LatLng(p.lat, p.lng));
        }});
    }});

    const legend = document.createElement("div");
    legend.innerHTML = `
        <div style="
            position:absolute;
            left:16px;
            bottom:16px;
            z-index:100;
            background:white;
            padding:12px 14px;
            border-radius:12px;
            box-shadow:0 2px 8px rgba(0,0,0,0.25);
            font-size:13px;
            line-height:1.7;">
            <b>농도 색상</b><br>
            <span style="color:#2ecc71;">●</span> 낮음<br>
            <span style="color:#f1c40f;">●</span> 보통<br>
            <span style="color:#e67e22;">●</span> 높음<br>
            <span style="color:#e74c3c;">●</span> 매우 높음
        </div>
    `;
    document.body.appendChild(legend);
    </script>
    """
    return html


st.subheader("🗺️ 날짜·시간별 대기오염 지도")

if not naver_client_id:
    st.warning("네이버 지도 API 키가 입력되지 않았습니다. 사이드바에 Naver Maps API Client ID 또는 ncpKeyId를 입력하면 지도가 표시됩니다.")
else:
    map_html = make_naver_map_html(
        time_filtered,
        naver_client_id,
        pollutant_info["label"],
        unit
    )
    components.html(map_html, height=650)


# =========================
# 10. 그래프와 표
# =========================

left, right = st.columns([1.1, 0.9])

with left:
    st.subheader("📊 지점별 농도 비교")

    chart_df = time_filtered.sort_values("value", ascending=False)

    fig = px.bar(
        chart_df,
        x="MSRSTE_NM",
        y="value",
        color="grade",
        hover_data=["MSRSTE_NM", "value", "grade"],
        labels={
            "MSRSTE_NM": "측정 지점",
            "value": f"{pollutant_info['label']} 농도 ({unit})",
            "grade": "등급"
        },
        title=f"{pollutant_info['label']} 지점별 농도"
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("🔎 상위 농도 지점")

    top_n = st.slider("상위 몇 개 지점을 볼까요?", 3, 10, 5)

    show_cols = ["MSRSTE_NM", "value", "grade"]
    st.dataframe(
        chart_df[show_cols].head(top_n).rename(columns={
            "MSRSTE_NM": "측정 지점",
            "value": f"농도 ({unit})",
            "grade": "등급"
        }),
        use_container_width=True,
        hide_index=True
    )


# =========================
# 11. 시간 변화 탐구
# =========================

st.subheader("⏱️ 선택 지점의 시간 변화 탐구")

district_options = sorted(df["MSRSTE_NM"].dropna().unique())
selected_district = st.selectbox("시간 변화를 볼 측정 지점", district_options)

district_df = df[df["MSRSTE_NM"] == selected_district].copy()

if pollutant in district_df.columns:
    district_df[pollutant] = pd.to_numeric(district_df[pollutant], errors="coerce")
    district_df = district_df.dropna(subset=["DATETIME", pollutant]).sort_values("DATETIME")

    if len(district_df) > 1:
        line_fig = px.line(
            district_df,
            x="DATETIME",
            y=pollutant,
            markers=True,
            labels={
                "DATETIME": "날짜·시간",
                pollutant: f"{pollutant_info['label']} 농도 ({unit})"
            },
            title=f"{selected_district}의 {pollutant_info['label']} 시간 변화"
        )
        st.plotly_chart(line_fig, use_container_width=True)
    else:
        st.info("현재 데이터가 한 시점만 포함되어 있어 시간 변화 그래프를 만들 수 없습니다. 과거 CSV를 업로드하면 시간 변화 탐구가 가능합니다.")


# =========================
# 12. 학생 탐구 질문
# =========================

st.subheader("🧪 학생 탐구 질문")

if max_row is not None:
    st.markdown(f"""
### 관찰
선택한 시점에서 **{max_row['MSRSTE_NM']}**의 **{pollutant_info['label']}** 농도가 가장 높습니다.  
측정값은 **{max_row['value']:.3g} {unit}**, 등급은 **{max_row['grade']}**입니다.

### 원인 추론을 위한 질문
1. 이 지점은 큰 도로, 교차로, 버스터미널, 공사장, 산업 시설과 가까운가?
2. 선택한 시간이 출근 시간, 퇴근 시간, 낮 시간, 야간 시간 중 언제인가?
3. 같은 시간에 주변 자치구도 함께 높아졌는가, 아니면 특정 지점만 높아졌는가?
4. PM10과 PM2.5가 함께 높다면 먼지 발생 또는 연소 활동을 의심할 수 있는가?
5. O₃가 높다면 햇빛이 강한 낮 시간의 광화학 반응과 관련이 있을까?
6. NO₂가 높다면 차량 통행량과 관련이 있을까?

### 물질별 과학적 힌트
{pollutant_info["explain"]}
""")


# =========================
# 13. 수업 활용 안내
# =========================

with st.expander("📘 수업 활용 방법"):
    st.markdown("""
1. 학생들은 날짜와 시간을 바꾸며 대기오염 농도가 높은 지점을 찾습니다.
2. 지도에서 높은 농도의 지점을 클릭해 위치와 농도를 확인합니다.
3. 그래프에서 다른 지점과 비교합니다.
4. 특정 지점의 시간 변화 그래프를 보고 농도가 높아지는 시간대를 찾습니다.
5. 지도, 시간대, 주변 환경을 근거로 원인을 가설로 세웁니다.

예시 가설:
- “출근 시간대에 NO₂가 높아진 것은 차량 통행량 증가 때문일 것이다.”
- “낮 시간에 O₃가 높아진 것은 햇빛에 의한 광화학 반응 때문일 것이다.”
- “PM10이 특정 지점에서만 높다면 공사장, 도로먼지, 지역적 배출원이 있을 수 있다.”
""")

with st.expander("🔐 Streamlit Cloud Secrets 예시"):
    st.code(
        """
SEOUL_API_KEY = "서울데이터광장에서 발급받은 인증키"
NAVER_MAP_CLIENT_ID = "네이버 Maps API ncpKeyId 또는 Client ID"
        """,
        language="toml"
    )

st.caption("자료 출처: 서울 열린데이터광장 · 서울시 대기오염 측정정보")
