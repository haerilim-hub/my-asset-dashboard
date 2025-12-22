import streamlit as st
import pandas as pd
import plotly.express as px
import re

# ==========================================
# 👇 [설정] 요청하신 비밀번호로 변경했습니다.
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
        
        cols_to_numeric = ['원금', '평가액', '평가손익']
        for col in cols_to_numeric:
            if col in df.columns and df[col].dtype == 'object':
                df[col] = df[col].str.replace(',', '').astype(float)
        
        if '기준일자' in df.columns:
            df['기준일자'] = pd.to_datetime(df['기준일자'])
        else:
            return None, "⚠️ '기준일자' 컬럼이 없습니다."

        return df, None
    except Exception as e:
        return None, f"오류 발생: {e}"

# --- 메인 화면 ---
st.set_page_config(layout="wide", page_title="투자 자산 대시보드")

st.sidebar.header("🔒 접근 권한 설정")
# 비밀번호 입력창
input_password = st.sidebar.text_input("관리자 비밀번호", type="password")

df, error_msg = load_data(FIXED_URL)

if st.sidebar.button("🔄 데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()

if error_msg:
    st.error(error_msg)
elif df is not None:
    
    # [권한 설정 로직]
    if input_password == ADMIN_PASSWORD:
        st.sidebar.success("🔓 관리자 모드")
        st.sidebar.divider()
        st.sidebar.subheader("🕵️‍♀️ 필터링")
        subject_list = ['전체'] + list(df['주체'].unique())
        selected_subject = st.sidebar.selectbox("보고 싶은 주체 선택", subject_list)
        
        if selected_subject != '전체':
            final_df = df[df['주체'] == selected_subject]
            display_title = selected_subject
        else:
            final_df = df
            display_title = "전체"
    else:
        # 비밀번호가 틀리면 무조건 '공동'만 보여줌
        final_df = df[df['주체'] == '공동'] 
        display_title = "공동"
        
        if input_password != "":
            st.sidebar.error("비밀번호가 틀렸습니다.")
        else:
            st.sidebar.info("손님 모드: '공동' 자산만 보입니다.")

    # ---------------------------------------------------------
    # 시각화 시작
    # ---------------------------------------------------------
    tab1, tab2 = st.tabs(["📊 자산 현황", "📈 성장 추이"])

    with tab1:
        if not final_df.empty:
            latest_date = final_df['기준일자'].max()
            daily_df = final_df[final_df['기준일자'] == latest_date].copy()
            
            st.title(f"📊 {display_title} 자산 현황 ({latest_date.strftime('%Y-%m-%d')})")
            
            # KPI
            total_eval = daily_df['평가액'].sum()
            total_invest = daily_df['원금'].sum()
            total_profit = daily_df['평가손익'].sum()
            roi = (total_profit / total_invest) * 100 if total_invest > 0 else 0
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("평가금액", f"{total_eval:,.0f}원")
            c2.metric("투자원금", f"{total_invest:,.0f}원")
            c3.metric("평가손익", f"{total_profit:,.0f}원", delta_color="normal")
            c4.metric("수익률", f"{roi:.2f}%")
            
            st.divider()
            
            # 차트 영역
            group_by = st.radio("분석 기준:", ['테마', '증권사', '종목명', '구분'], horizontal=True)
            if group_by in daily_df.columns:
                grouped = daily_df.groupby(group_by)[['평가액', '원금']].sum().reset_index().sort_values('평가액', ascending=False)
                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(px.pie(grouped, values='평가액', names=group_by, hole=0.4), use_container_width=True)
                with col2:
                    st.plotly_chart(px.bar(grouped, x=group_by, y=['원금', '평가액'], barmode='group'), use_container_width=True)
            
            # 하단 종목별 손익 테이블
            st.divider()
            st.subheader("🏆 종목별 평가손익 순위")
            
            stock_rank = daily_df.groupby('종목명')[['평가손익', '평가액', '원금']].sum().reset_index()
            stock_rank['수익률(%)'] = (stock_rank['평가손익'] / stock_rank['원금']) * 100
            stock_rank = stock_rank.sort_values(by='평가손익', ascending=False)
            
            st.dataframe(
                stock_rank[['종목명', '평가손익', '수익률(%)', '평가액']],
                column_config={
                    "평가손익": st.column_config.NumberColumn(format="%d원"),
                    "평가액": st.column_config.NumberColumn(format="%d원"),
                    "수익률(%)": st.column_config.NumberColumn(format="%.2f%%"),
                },
                hide_index=True,
                use_container_width=True
            )

        else:
            st.warning("표시할 데이터가 없습니다.")

    with tab2:
        st.title(f"📈 {display_title} 자산 성장 그래프")
        if not final_df.empty:
            timeline = final_df.groupby('기준일자')[['평가액', '원금']].sum().reset_index()
            st.plotly_chart(px.line(timeline, x='기준일자', y=['평가액', '원금'], markers=True), use_container_width=True)
            st.plotly_chart(px.area(final_df, x='기준일자', y='평가액', color='테마'), use_container_width=True)
