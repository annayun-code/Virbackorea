import streamlit as st
import requests
import pandas as pd
import datetime
from datetime import timedelta
import re

# 1. 웹페이지 기본 설정 (미리보기 최적화)
st.set_page_config(
    page_title="버박코리아(Virbac) 올인원 모니터링 시스템", 
    page_icon="🐾", 
    layout="wide"
)

# 2. 네이버 API 키 설정
CLIENT_ID = "mpZq2kemw3VPbJwPf2cM"
CLIENT_SECRET = "qY_E8EjKcC"

MY_BRAND = "버박"

# 🔴 경쟁사 라인업 업데이트 (요청하신 5개 사 추가 완료!)
COMPETITORS = [
    "케어사이드", "오라틴", "페스룸", "푸르너스", "데크라", "조에티스", "베토퀴놀",
    "MSD", "엘랑코", "녹십자수의약품", "세바", "베링거인겔하임"
]

# 📌 스팸 노이즈 키워드 
EXCLUDE_KEYWORDS = ["해외직구", "중고나라", "당근마켓", "네비게이션", "무선카플레이", "맥가이버박", "DEKRA", "전기차"]

# 📌 업계 핫 트렌드 핵심 키워드
HOT_TRENDS = ["강아지 외이도염", "강아지 치석", "고양이 구내염", "강아지 영양제", "고양이 영양제"]

# 📌 본사 차원의 핵심 비즈니스 동향 키워드
MY_BRAND_CORE_KEYWORDS = [
    "수의사", "동물병원", "동물의약품", "동물의약외품", "반려동물", "강아지", "고양이",
    "출시", "학회", "웨비나", "심포지엄", "캠페인", "MOU"
]

def clean_text(text):
    if not text: return ""
    tags = ["<b>", "</b>", "&quot;", "&gt;", "&lt;", "&amp;"]
    for tag in tags:
        text = text.replace(tag, "")
    return text

def classify_brand(title, description, channel_name):
    combined_text = (title + " " + description).replace(" ", "").upper()
    
    # 1. 최우선 분류: 핫트렌드 질환/영양제 이슈 검사
    if any(trend.replace(" ", "").upper() in combined_text for trend in HOT_TRENDS):
        return "반려동물 핫트렌드"
        
    # 2. 자사 브랜드(버박) 분류 로직
    if MY_BRAND in combined_text:
        if channel_name == "뉴스":
            return "버박 (핵심 비즈니스)"
        if any(core_word.upper() in combined_text for core_word in MY_BRAND_CORE_KEYWORDS):
            return "버박 (핵심 비즈니스)"
        return "버박 (일반 언급/기타)"
        
    # 3. 경쟁사 브랜드 검사
    matched_competitors = []
    for comp in COMPETITORS:
        target_comp = comp.replace(" ", "").upper()
        if target_comp in combined_text:
            matched_competitors.append(comp)
            
    if matched_competitors:
        return ", ".join(matched_competitors)
        
    return "업계 일반 동향"

def is_noise(title, description):
    combined_text = title + " " + description
    for word in EXCLUDE_KEYWORDS:
        if word in combined_text:
            return True
    return False

def fetch_naver_data(api_type, keyword, display_count=50):
    url = f"https://openapi.naver.com/v1/search/{api_type}.json?query={keyword}&display={display_count}&sort=date"
    headers = {"X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET}
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("items", [])
    except Exception as e:
        st.warning(f"네이버 {api_type} 통신 중 일시적 오류 발생: {e}")
    return []

@st.cache_data(ttl=600)
def load_smart_data():
    all_data = []
    channels = ["news", "blog", "cafearticle"]
    channel_names = {"news": "뉴스", "blog": "블로그", "cafearticle": "네이버카페"}
    
    # 💡 검색 효율화: 검색어가 너무 길어져 오류가 나지 않도록 핵심 쿼리 그룹 분할 조합
    brand_query_1 = f"{MY_BRAND} | 케어사이드 | 오라틴 | 페스룸 | 푸르너스 | 데크라 | 조에티스"
    brand_query_2 = "베토퀴놀 | MSD | 엘랑코 | 녹십자수의약품 | 세바 | 베링거인겔하임"
    trend_query = "강아지 귓병 | 고양이 치과 | 반려동물 헬스케어"
    
    order_idx = 0
    for channel in channels:
        items_1 = fetch_naver_data(channel, brand_query_1, display_count=40)
        items_2 = fetch_naver_data(channel, brand_query_2, display_count=40)
        items_3 = fetch_naver_data(channel, trend_query, display_count=20)
        
        existing_links = set([raw["링크"] for raw in all_data] if all_data else [])
        
        for item in (items_1 + items_2 + items_3):
            link = item.get("link")
            if not link or link in existing_links: 
                continue
            
            title = clean_text(item.get("title"))
            desc = clean_text(item.get("description"))
            
            if is_noise(title, desc): 
                continue
            
            brand_category = classify_brand(title, desc, channel_names[channel])
            
            all_data.append({
                "채널": channel_names[channel],
                "분류": brand_category,
                "제목": title,
                "요약": desc,
                "링크": link,
                "api_order": order_idx
            })
            existing_links.add(link)
            order_idx += 1
            
    df = pd.DataFrame(all_data)
    if not df.empty:
        df = df.sort_values(by="api_order").drop(columns=["api_order"])
        
    return df

# --- UI 레이아웃 화면 그리기 ---
st.title("🐾 버박코리아(Virbac) 올인원 마케팅 모니터링 시스템")

seoul_time = datetime.datetime.utcnow() + timedelta(hours=9)
st.markdown(f"**실시간 갱신 시간:** {seoul_time.strftime('%Y-%m-%d %H:%M:%S')} (한국 시간 기준)")

if st.button("🔄 실시간 데이터 즉시 업데이트"):
    st.cache_data.clear()
    st.rerun()

st.divider()

try:
    df = load_smart_data()
except Exception as e:
    st.error(f"데이터 로드 중 치명적인 오류가 발생했습니다. API 키를 확인해 주세요: {e}")
    df = pd.DataFrame()

if not df.empty:
    # 1. 상단 스코어보드 현황
    st.subheader("📊 금일 실시간 수집 현황")
    c1, c2, c3, c4, c5 = st.columns(5)
    
    core_cnt = len(df[df['분류'] == "버박 (핵심 비즈니스)"])
    etc_cnt = len(df[df['분류'] == "버박 (일반 언급/기타)"])
    trend_cnt = len(df[df['분류'] == "반려동물 핫트렌드"])
    normal_cnt = len(df[df['분류'] == "업계 일반 동향"])
    comp_cnt = len(df) - (core_cnt + etc_cnt + trend_cnt + normal_cnt)

    c1.metric("🔵 자사 (핵심 비즈니스)", f"{core_cnt}건")
    c2.metric("🔷 자사 (일반 언급/기타)", f"{etc_cnt}건")
    c3.metric("🚨 펫 헬스 핫트렌드", f"{trend_cnt}건")
    c4.metric("🔴 경쟁사 동향", f"{comp_cnt}건")
    c5.metric("⚪ 일반 업계 동향", f"{normal_cnt}건")
    st.divider()

    # 2. 사이드바 필터링
    st.sidebar.header("🔍 카테고리 필터")
    filter_options = ["전체보기", "버박 (핵심 비즈니스)", "버박 (일반 언급/기타)", "🚨 반려동물 핫트렌드", "경쟁사 전체"] + COMPETITORS + ["업계 일반 동향"]
    selected = st.sidebar.selectbox("모니터링 대상 선택", options=filter_options)
    selected_channel = st.sidebar.radio("채널 선택", options=["전체 채널", "뉴스", "블로그", "네이버카페"])

    filtered_df = df.copy()
    if selected == "버박 (핵심 비즈니스)":
        filtered_df = filtered_df[filtered_df["분류"] == "버박 (핵심 비즈니스)"]
    elif selected == "버박 (일반 언급/기타)":
        filtered_df = filtered_df[filtered_df["분류"] == "버박 (일반 언급/기타)"]
    elif selected == "🚨 반려동물 핫트렌드":
        filtered_df = filtered_df[filtered_df["분류"] == "반려동물 핫트렌드"]
    elif selected == "경쟁사 전체":
        filtered_df = filtered_df[~filtered_df["분류"].isin(["버박 (핵심 비즈니스)", "버박 (일반 언급/기타)", "업계 일반 동향", "반려동물 핫트렌드"])]
    elif selected != "전체보기":
        filtered_df = filtered_df[filtered_df["분류"] == selected]
        
    if selected_channel != "전체 채널":
        filtered_df = filtered_df[filtered_df["채널"] == selected_channel]

    # 3. 피드 화면 출력
    st.subheader(f"📋 모니터링 피드 ({selected} / {selected_channel})")
    if filtered_df.empty:
        st.info("선택한 조건의 데이터가 현재 존재하지 않습니다.")
    else:
        for idx, row in filtered_df.iterrows():
            if row["분류"] == "버박 (핵심 비즈니스)":
                badge = "🔵 [자사-비즈니스]"
            elif row["분류"] == "반려동물 핫트렌드":
                badge = "🚨 [질환/영양제 트렌드]"
            elif row["분류"] == "버박 (일반 언급/기타)":
                badge = "🔷 [자사-일반급/바이럴]"
            elif row["분류"] == "업계 일반 동향":
                badge = "⚪ [일반동향]"
            else:
                badge = f"🔴 [경쟁사: {row['분류']}]"
                
            with st.container():
                st.markdown(f"### 📄 {badge} {row['제목']}")
                st.caption(f"채널: {row['채널']} | 분류: {row['분류']}")
                st.write(row["요약"])
                st.markdown(f"[🔗 원본 글 본문 바로가기]({row['링크']})")
                st.divider()
else:
    st.info("수집 조건에 부합하는 클린 데이터가 없습니다. 검색어 설정이나 API 키를 확인해 주세요.")