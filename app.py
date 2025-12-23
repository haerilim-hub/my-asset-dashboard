import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime

# ==========================================
# 👇 [설정] 관리자 비밀번호
ADMIN_PASSWORD = "1855"
# ==========================================

# 👇 질문자님의 구글 시트 주소
FIXED_URL = "https://docs.google.com/spreadsheets/d/1OTxV5LBaOZeRRDBlcXJrSLOyNsW_smIii08DYKpl6dI/edit?gid=644186025#gid=644186025"

@st.cache_data(ttl=60)
def load_data(url):
    try:
        if "/d/" in url:
            sheet_id = url.split('/d/')[1].split('/')[0]
        else:
            return None, "주소 형식이 이상합니다."
        
        gid_match = re.search(r'gid=(\d+)', url)
        gid_param = f"&gid={gid_match.group(1)}" if gid_match else ""
        csv_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv{gid_param}'
        
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip()
        
        # ★ [수정됨] 숫자 변환 로직 강화 (괄호 처리 추가)
        cols_to_numeric = ['원금', '평가액', '평가손익']
        for col in cols_to_numeric:
            if col in df.columns and df[col].dtype == 'object':
                # 1. 쉼표 제거
                df[col] = df[col].str.replace(',', '')
                # 2. 괄호가 있으면 마이너스로 변환 (예: (100) -> -100)
                df[col] = df[col].str.replace('(', '-', regex=False).str.replace(')', '', regex=False)
                # 3. 실수형으로 변환
                df[col] = df[col].astype(float)
        
        if '기준일자' in df.columns:
            df['기준일자'] = pd.to_datetime(df['기준일자'])
        else:
            return None, "⚠️ '기준일자' 컬럼이 없습니다."

        return df, None
    except Exception as e:
        return None, f"오류 발생: {e}"

# --- 메인 화면 ---
st.set_page_config(layout="wide", page_title="투자 자산 대시보드")

# 사이드바 메뉴 구성
st.sidebar.header("⚙️ 메뉴 선택")
menu = st.sidebar.radio("이동할 페이지", ["📊 대시보드 보기", "📝 데이터 입력 도우미"])

st.sidebar.divider()
st.sidebar.header("🔒 접근 권한")
input_password = st.sidebar.text_input("관리자 비밀번호", type="password")

# 데이터 로드
df, error_msg = load_data(FIXED_URL)

# ==============================================================================
# [PAGE 1] 대시보드 보기
# ==============================================================================
if menu == "📊 대시보드 보기":
    
    if st.sidebar.button("🔄 데이터 새로고침"):
        st.cache_data.clear()
        st.rerun()

    if error_msg:
        st.error(error_msg)
    elif df is not None:
        
        # 권한 체크
        if input_password == ADMIN_PASSWORD:
            st.sidebar.success("🔓 관리자 모드")
            st.sidebar.subheader("🕵️‍♀️ 필터링")
            subject_list = ['전체'] + list(df['주체'].unique())
            selected_subject = st.sidebar.selectbox("주체 선택", subject_list)
            
            if selected_subject != '전체':
                final_df = df[df['주체'] == selected_subject]
                display_title = selected_subject
            else:
                final_df = df
                display_title = "전체"
        else:
            final_df = df[df['주체'] == '공동'] 
            display_title = "공동"
            if input_password != "":
                st.sidebar.error("비밀번호 불일치")

        # 시각화 탭
        tab1, tab2 = st.tabs(["📊 자산 현황", "📈 성장 추이"])

        with tab1:
            if not final_df.empty:
                latest_date = final_df['기준일자'].max()
                daily_df = final_df[final_df['기준일자'] == latest_date].copy()
                
                st.title(f"📊 {display_title} 자산 현황 ({latest_date.strftime('%Y-%m
