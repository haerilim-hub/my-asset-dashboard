import streamlit as st
import pandas as pd
import plotly.express as px
import re
from datetime import datetime, timedelta

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
        
        # 숫자 변환 로직 (공백/콤마/괄호 처리)
        cols_to_numeric = ['원금', '평가액', '평가손익']
        for col in cols_to_numeric:
            if col in df.columns:
                df[col] = df[col].astype(str)
                df[col] = df[col].str.replace(',', '').str.replace(' ', '')
                df[col] = df[col].str.replace('(-)', '-', regex=False)
                df[col] = df[col].str.replace('(', '-', regex=False).str.replace(')', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if '기준일자' in df.columns:
            df['기준일자'] = pd.to_datetime(df['기준일자'])
        else:
            return None, "⚠️ '기준일자' 컬럼이 없습니다."

        return df, None
    except Exception as e:
        return None, f"오류 발생: {e}"

# --- 메인 화면 ---
st.set_page_config(layout="wide", page_title="투자 자산 대시보드")

# 사이드바 (메뉴 선택 삭제됨 -> 바로 권한 확인)
st.sidebar.header("🔒 접근 권한")
input_password = st.sidebar.text_input("관리자 비밀번호", type="password")

if st.sidebar.button("🔄 데이터 새로고침"):
    st.cache_data.clear()
    st.rerun()

# 데이터 로드
df, error_msg = load_data(FIXED_URL)

if error_msg:
    st.error(error_msg)
elif df is not None:
    
    # 1. 권한 확인 및 기본 데이터 필터링
    if input_password == ADMIN_PASSWORD:
        st.sidebar.success("🔓 관리자 모드")
        st.sidebar.subheader("🕵️‍♀️ 필터링")
        subject_list = ['전체'] + list(df['주체'].unique())
        selected_subject = st.sidebar.selectbox("주체 선택", subject_list)
        
        if selected_subject != '전체':
            base_df = df[df['주체'] == selected_subject]
            display_title = selected_subject
        else:
            base_df = df
            display_title = "전체"
    else:
        # 비밀번호 미입력 시 '공동' 계좌만 노출
        base_df = df[df['주체'] == '공동'] 
        display_title = "공동"
        if input_password != "":
            st.sidebar.error("비밀번호 불일치")

    # 2. 기간 설정 필터링
    st.sidebar.divider()
    st.sidebar.subheader("📅 조회 기간 설정")
    period_option = st.sidebar.radio("기간 선택", ["전체", "이번주", "이번달", "올해", "직접 설정"])
    
    today = datetime.now().date()
    start_date = base_df['기준일자'].min().date()
    end_date = today

    if period_option == "이번주":
        start_date = today - timedelta(days=today.weekday())
    elif period_option == "이번달":
        start_date = today.replace(day=1)
    elif period_option == "올해":
        start_date = today.replace(month=1, day=1)
    elif period_option == "직접 설정":
        date_range = st.sidebar.date_input("날짜 범위 선택", [start_date, end_date])
        if len(date_range) == 2:
            start_date, end_date = date_range
        elif len(date_range) == 1:
            start_date = date_range[0]
    
    # 기간 필터링 적용
    mask = (base_df['기준일자'].dt.date >= start_date) & (base_df['기준일자'].dt.date <= end_date)
    final_df = base_df.loc[mask]

    # ==============================================================================
    # 대시보드 시각화
    # ==============================================================================
    tab1, tab2 = st.tabs(["📊 자산 현황", "📈 성장 추이"])

    with tab1:
        if not final_df.empty:
            # 선택된 기간 중 '가장 마지막 날짜' 기준
            latest_date = final_df['기준일자'].max()
            daily_df = final_df[final_df['기준일자'] == latest_date].copy()
            
            st.title(f"📊 {display_title} 자산 현황 ({latest_date.strftime('%Y-%m-%d')})")
            st.caption(f"📌 조회 기간: {start_date} ~ {latest_date.date()}")
            
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
            
            group_by = st.radio("차트 기준:", ['테마', '증권사', '종목명', '구분'], horizontal=True)
            if group_by in daily_df.columns:
                grouped = daily_df.groupby(group_by)[['평가액', '원금']].sum().reset_index().sort_values('평가액', ascending=False)
                col1, col2 = st.columns(2)
                with col1:
                    st.plotly_chart(px.pie(grouped, values='평가액', names=group_by, hole=0.4), use_container_width=True)
                with col2:
                    st.plotly_chart(px.bar(grouped, x=group_by, y=['원금', '평가액'], barmode='group'), use_container_width=True)
            
            st.divider()
            st.subheader("🏆 수익 랭킹")
            rank_option = st.radio("순위 기준:", ['종목별', '테마별'], horizontal=True)
            target_col = '종목명' if rank_option == '종목별' else '테마'
            
            def style_negative_red(val):
                color = 'red' if val < 0 else 'black'
                return f'color: {color}'
            def format_custom(val):
                if val < 0: return f"(-) {abs(val):,.0f}"
                return f"{val:,.0f}"

            if target_col in daily_df.columns:
                rank_df = daily_df.groupby(target_col)[['평가손익', '평가액', '원금']].sum().reset_index()
                rank_df['수익률(%)'] = (rank_df['평가손익'] / rank_df['원금']) * 100
                rank_df = rank_df.sort_values(by='평가손익', ascending=False)
                
                st.dataframe(
                    rank_df[[target_col, '평가손익', '수익률(%)', '평가액']].style
                    .format({
                        '평가손익': format_custom,
                        '평가액': format_custom,
                        '수익률(%)': '{:.2f}%'
                    })
                    .map(style_negative_red, subset=['평가손익']),
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.warning(f"선택하신 기간 ({start_date} ~ {end_date})에 해당하는 데이터가 없습니다.")

    with tab2:
        st.title(f"📈 {display_title} 자산 성장 그래프")
        
        if not final_df.empty:
            st.caption(f"📌 조회 기간: {start_date} ~ {end_date}")
            
            timeline = final_df.groupby('기준일자')[['평가액', '원금']].sum().reset_index()
            
            timeline['평가손익'] = timeline['평가액'] - timeline['원금']
            timeline['수익률'] = 0.0
            mask = timeline['원금'] > 0
            timeline.loc[mask, '수익률'] = (timeline.loc[mask, '평가손익'] / timeline.loc[mask, '원금']) * 100

            # 1. 자산 규모
            st.subheader("💸 자산 규모 변동")
            fig_line = px.line(timeline, x='기준일자', y=['평가액', '원금'], markers=True)
            fig_line.update_xaxes(dtick="D1", tickformat="%Y-%m-%d")
            st.plotly_chart(fig_line, use_container_width=True)
            
            # 2. 수익률 추이
            st.subheader("📉 일자별 수익률 추이 (%)")
            fig_roi = px.line(timeline, x='기준일자', y='수익률', markers=True)
            fig_roi.update_traces(texttemplate='%{y:.2f}%', textposition='top center')
            fig_roi.add_hline(y=0, line_dash="dash", line_color="gray", annotation_text="0% (본전)")
            fig_roi.update_xaxes(dtick="D1", tickformat="%Y-%m-%d")
            st.plotly_chart(fig_roi, use_container_width=True)
            
            # 3. 테마별 비중
            st.subheader("🎨 테마별 비중 변화")
            fig_area = px.area(final_df, x='기준일자', y='평가액', color='테마')
            fig_area.update_xaxes(dtick="D1", tickformat="%Y-%m-%d")
            st.plotly_chart(fig_area, use_container_width=True)
        else:
                st.warning(f"선택하신 기간 ({start_date} ~ {end_date})에 해당하는 데이터가 없습니다.")
