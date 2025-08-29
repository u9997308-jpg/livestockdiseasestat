# streamlit_app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# -----------------------------
# Page config & CSS
# -----------------------------
st.set_page_config(page_title="가축 질병 발생 대시보드", layout="wide")
st.markdown(
    """
    <style>
    [data-testid="block-container"] {
        padding: 1.0rem 2.0rem;
    }
    [data-testid="stSidebar"] {
        width: 300px; min-width: 300px; padding: 0.8rem;
    }
    .divider { margin: 0.8rem 0 1.0rem 0; }
    h2, h3 { letter-spacing: -0.5px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Load data
# -----------------------------
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="cp949")
    for c in df.columns:
        if c != "연월":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["연"] = (df["연월"] // 100).astype(int)
    df["월"] = (df["연월"] % 100).astype(int)
    return df

df = load_data("가축질병발생통계.csv")

# 지역 컬럼
regions_all = [c for c in df.columns if c not in ["연월", "연", "월", "소계"]]

def ensure_total_col(frame: pd.DataFrame) -> pd.DataFrame:
    """'소계'가 없으면 지역합으로 보강"""
    if "소계" not in frame.columns or frame["소계"].isna().all():
        frame = frame.copy()
        frame["소계"] = frame[regions_all].sum(axis=1, numeric_only=True)
    return frame

df = ensure_total_col(df)

# -----------------------------
# Palettes
# -----------------------------
PALETTES = {
    "TealMint": {
        "cont": ["#003f5c", "#2f8797", "#42b3a4", "#7dd6c9", "#b9f1e3"],
        "seq":  ["#2a9d8f", "#38a3a5", "#56cfe1", "#80ed99", "#57cc99"],
        "template": "plotly_white",
    },
    "IndigoRose": {
        "cont": ["#2b2d42", "#3f3351", "#6d597a", "#b56576", "#eaac8b"],
        "seq":  ["#3f3351", "#6d597a", "#b56576", "#e56b6f", "#eaac8b"],
        "template": "plotly_white",
    },
    "SlateSunset": {
        "cont": ["#0f172a", "#334155", "#64748b", "#eab308", "#f59e0b"],
        "seq":  ["#334155", "#475569", "#64748b", "#eab308", "#f59e0b"],
        "template": "plotly_white",
    },
}
DEFAULT_THEME = "TealMint"

# -----------------------------
# Sidebar: Year/Month + YTD
# -----------------------------
st.sidebar.title("가축 질병 발생 대시보드")

year_options = sorted(df["연"].unique())
selected_year = st.sidebar.selectbox("연도 선택", year_options, index=0)

# 항상 1~12월을 보여주되, 없는 달은 0 처리
month_options = list(range(1, 13))
# 해당 연의 실제 데이터가 있는 최대 월(없으면 12로)
year_months = df.loc[df["연"] == selected_year, "월"]
default_month = int(year_months.max()) if not year_months.empty else 12
selected_month = st.sidebar.selectbox("월 선택", month_options, index=default_month-1)

# 지역 & 테마
selected_regions = st.sidebar.multiselect("지역 선택", regions_all, default=regions_all)
theme_name = st.sidebar.selectbox("시각화 테마 선택", list(PALETTES.keys()),
                                  index=list(PALETTES.keys()).index(DEFAULT_THEME))
palette = PALETTES[theme_name]

# ---- YTD 계산 (없는 달은 0으로 채움) ----
df_year = ensure_total_col(df[df["연"] == selected_year].copy())
# 월별 합계를 1..12로 재인덱스 → 누락월 0
monthly_total = (
    df_year.groupby("월")["소계"].sum()
    .reindex(range(1, 13), fill_value=0)
)
ytd = int(monthly_total.loc[1:selected_month].sum())

# 전년 동월까지 누계 비교
if (selected_year - 1) in df["연"].unique():
    prev = ensure_total_col(df[df["연"] == selected_year - 1].copy())
    prev_monthly_total = (
        prev.groupby("월")["소계"].sum()
        .reindex(range(1, 13), fill_value=0)
    )
    ytd_prev = int(prev_monthly_total.loc[1:selected_month].sum())
    delta_str = f"{ytd - ytd_prev:+,}"
else:
    ytd_prev, delta_str = None, None

st.sidebar.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.sidebar.subheader("연도 누계(YTD)")
if delta_str is None:
    st.sidebar.metric(label=f"{selected_year}년 1~{selected_month}월", value=f"{ytd:,}")
else:
    st.sidebar.metric(label=f"{selected_year}년 1~{selected_month}월", value=f"{ytd:,}", delta=delta_str)

st.sidebar.markdown("<div class='divider'></div>", unsafe_allow_html=True)
st.sidebar.info("👉 월은 항상 1–12 선택 가능하며, 데이터가 없는 달은 0으로 계산됩니다.")

# 선택 연월 데이터 (없으면 0행 생성)
selected_ym = selected_year * 100 + selected_month
row = df[(df["연"] == selected_year) & (df["월"] == selected_month)]
if row.empty:
    # 0으로 채운 가상 행(시각화/지표 유지용)
    zero_data = {c: 0 for c in regions_all}
    zero_data.update({"연월": selected_ym, "연": selected_year, "월": selected_month, "소계": 0})
    df_selected = pd.DataFrame([zero_data])
else:
    df_selected = row.copy()

# -----------------------------
# Layout columns
# -----------------------------
col = st.columns([1.15, 1.2, 1.05], gap="medium")

# -----------------------------
# col[0]: 핵심 지표 + 월별 추세
# -----------------------------
with col[0]:
    st.header("핵심 지표")

    total_cases = int(df_selected["소계"].sum())
    st.metric("전체 발생 건수", f"{total_cases:,}")

    if not selected_regions:
        st.warning("선택된 지역이 없습니다. 사이드바에서 지역을 선택하세요.")
    else:
        region_sums = df_selected[selected_regions].sum().fillna(0)
        region_max = region_sums.idxmax()
        region_min = region_sums.idxmin()
        st.metric("최다 발생 지역", f"{region_max} ({int(region_sums.max()):,})")
        st.metric("최소 발생 지역", f"{region_min} ({int(region_sums.min()):,})")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.subheader("월별 발생 추세")

    # 같은 연도의 추세 (없는 달 0으로)
    trend = (
        ensure_total_col(df[df["연"] == selected_year])[["연월", "월", "소계"]]
        .groupby("월")["소계"].sum()
        .reindex(range(1, 13), fill_value=0)
        .reset_index()
        .rename(columns={"index": "월"})
    )
    trend["연월"] = selected_year * 100 + trend["월"]

    fig_line = px.line(
        trend, x="연월", y="소계", markers=True, template=palette["template"]
    )
    fig_line.update_traces(line=dict(width=3), marker=dict(size=7))
    fig_line.update_layout(
        yaxis_title="발생건수",
        colorway=palette["seq"],
        margin=dict(l=10, r=10, t=10, b=10),
        height=330,
    )
    st.plotly_chart(fig_line, use_container_width=True)

# -----------------------------
# col[1]: 지역 분포(수평 바) + 연도 히트맵
# -----------------------------
with col[1]:
    st.header("지역별 발생 분포")

    if not selected_regions:
        st.info("지역을 하나 이상 선택하세요.")
    else:
        region_sums_df = (
            df_selected[selected_regions]
            .sum()
            .fillna(0)
            .reset_index()
            .rename(columns={"index": "지역", 0: "발생건수"})
        )
        region_sums_df.columns = ["지역", "발생건수"]

        fig_bar = px.bar(
            region_sums_df.sort_values("발생건수", ascending=True),
            x="발생건수", y="지역",
            orientation="h",
            template=palette["template"],
            color="발생건수",
            color_continuous_scale=palette["cont"],
        )
        fig_bar.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=340)
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.subheader("연도별 지역 발생 히트맵")

    if selected_regions:
        df_year_full = ensure_total_col(df[df["연"] == selected_year].copy())
        # 1~12월 모두 가지도록 보강
        idx = pd.MultiIndex.from_product([range(1, 13), selected_regions], names=["월", "지역"])
        melted = (
            df_year_full.melt(id_vars=["연", "월"], value_vars=selected_regions,
                              var_name="지역", value_name="발생건수")
            .groupby(["월", "지역"])["발생건수"].sum()
            .reindex(idx, fill_value=0)
            .reset_index()
        )
        heatmap_data = melted.pivot(index="지역", columns="월", values="발생건수")

        fig_heatmap = px.imshow(
            heatmap_data,
            aspect="auto",
            color_continuous_scale=palette["cont"],
            labels=dict(x="월", y="지역", color="발생건수"),
            template=palette["template"],
        )
        fig_heatmap.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=350)
        st.plotly_chart(fig_heatmap, use_container_width=True)
    else:
        st.info("히트맵을 보려면 지역을 하나 이상 선택하세요.")

# -----------------------------
# col[2]: Top5 랭킹 + 설명
# -----------------------------
with col[2]:
    st.header("Top 지역 랭킹")

    if not selected_regions:
        st.info("지역을 선택해 주세요.")
    else:
        region_sums = (
            df_selected[selected_regions]
            .sum()
            .fillna(0)
            .reset_index()
        )
        region_sums.columns = ["지역", "발생건수"]
        top_regions = region_sums.sort_values("발생건수", ascending=False).head(5)

        fig_top = px.bar(
            top_regions, x="지역", y="발생건수",
            template=palette["template"],
            color="발생건수",
            color_continuous_scale=palette["cont"],
        )
        fig_top.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=340)
        st.plotly_chart(fig_top, use_container_width=True)

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    st.subheader("데이터 설명")
    st.markdown(
        """
        - **데이터 출처:** 농림축산식품부 가축질병 발생 통계  
        - **분석 단위:** `연월` 기준, 시도별 집계  
        - **주의:** 일부 결측치가 있을 수 있으며, '소계'는 전국 총합입니다.  
        - **활용:** 방역 자원 배분, 지역/시기별 집중 발생 모니터링, 연도별 패턴 분석 등
        """
    )
