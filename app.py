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
        
        # 숫자 변환 (괄호 마이너스 처리 포함)
        cols_to_numeric = ['원금', '평가액', '평가손익']
        for col in cols_to_numeric:
            if col in df.columns and df[col].dtype == 'object':
                df[col] = df[col].str.replace(',', '')
                df[col] = df[col].str.replace('(', '-', regex=False).str.replace(')', '', regex=False)
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

st.sidebar.header("⚙️ 메뉴 선택")
menu = st.sidebar.radio("이동할 페이지", ["📊 대시보드 보기", "📝 데이터 입력 도우미"])

st.sidebar.divider()
st.sidebar.header("🔒 접근 권한")
input_password = st.sidebar.text_input("관리자 비밀번호", type="password")

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

        tab1, tab2 = st.tabs(["📊 자산 현황", "📈 성장 추이"])

        with tab1:
            if not final_df.empty:
                latest_date = final_df['기준일자'].max()
                daily_df = final_df[final_df['기준일자'] == latest_date].copy()
                
                st.title(f"📊 {display_title} 자산 현황 ({latest_date.strftime('%Y-%m-%d')})")
                
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
                
                if target_col in daily_df.columns:
                    rank_df = daily_df.groupby(target_col)[['평가손익', '평가액', '원금']].sum().reset_index()
                    rank_df['수익률(%)'] = (rank_df['평가손익'] / rank_df['원금']) * 100
                    rank_df = rank_df.sort_values(by='평가손익', ascending=False)
                    
                    st.dataframe(
                        rank_df[[target_col, '평가손익', '수익률(%)', '평가액']].style.format({
                            '평가손익': '{:,.0f}원',
                            '평가액': '{:,.0f}원',
                            '수익률(%)': '{:.2f}%'
                        }),
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

# ==============================================================================
# [PAGE 2] 데이터 입력 도우미 (업그레이드)
# ==============================================================================
elif menu == "📝 데이터 입력 도우미":
    st.title("📝 간편 데이터 생성기")
    st.info("💡 위쪽 표에서 금액을 수정하면, 아래쪽 표에서 '평가손익'이 자동 계산됩니다.")

    if input_password != ADMIN_PASSWORD:
        st.error("🔒 관리자 비밀번호를 입력해야 사용할 수 있습니다.")
    elif df is not None:
        latest_date = df['기준일자'].max()
        input_df = df[df['기준일자'] == latest_date].copy()
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 1. 입력용 표 (편집 가능)
        st.subheader("1️⃣ 금액 수정 (입력용)")
        # 여기서는 콤마 없이 숫자로 입력해야 에러가 안 납니다.
        # 평가손익은 자동 계산되므로 입력창에서 제외했습니다.
        editable_cols = ['주체', '증권사', '구분', '종목명', '테마', '원금', '평가액']
        
        edited_df = st.data_editor(
            input_df[editable_cols],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "원금": st.column_config.NumberColumn(format="%d"),
                "평가액": st.column_config.NumberColumn(format="%d"),
            }
        )
        
        # 2. 실시간 미리보기 (자동 계산 + 콤마 적용)
        st.subheader("2️⃣ 결과 미리보기 (자동 계산됨)")
        st.caption("👇 위에서 입력한 내용이 여기에 실시간으로 반영됩니다.")
        
        # 평가손익 자동 계산
        edited_df['평가손익'] = edited_df['평가액'] - edited_df['원금']
        
        # 미리보기용 데이터프레임 (콤마 적용하여 보여주기)
        preview_cols = ['종목명', '원금', '평가액', '평가손익']
        st.dataframe(
            edited_df[preview_cols].style.format({
                "원금": "{:,.0f}", 
                "평가액": "{:,.0f}",
                "평가손익": "{:,.0f}" # 마이너스도 자동으로 표시됨
            }),
            use_container_width=True
        )

        st.divider()

        # 3. 최종 생성 버튼
        if st.button("🚀 위 내용으로 데이터 생성하기"):
            final_export_df = edited_df.copy()
            final_export_df.insert(0, '기준일자', today)
            
            # 구글 시트 원본 순서 맞추기
            target_order = ['기준일자', '주체', '증권사', '구분', '종목명', '테마', '원금', '평가액', '평가손익']
            
            try:
                final_export_df = final_export_df[target_order]
                
                st.success("✅ 데이터 생성 완료! 아래 박스 내용을 복사하세요.")
                st.code(final_export_df.to_csv(index=False, header=False, sep='\t'), language='csv')
                st.markdown(f"[👉 구글 시트 바로가기]({FIXED_URL})")
                
            except Exception as e:
                st.error(f"오류 발생: {e}")
