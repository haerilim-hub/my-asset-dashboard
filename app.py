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

# 사이드바 메뉴 구성
st.sidebar.header("⚙️ 메뉴 선택")
menu = st.sidebar.radio("이동할 페이지", ["📊 대시보드 보기", "📝 데이터 입력 도우미"])

st.sidebar.divider()
st.sidebar.header("🔒 접근 권한")
input_password = st.sidebar.text_input("관리자 비밀번호", type="password")

# 데이터 로드
df, error_msg = load_data(FIXED_URL)

# ==============================================================================
# [PAGE 1] 대시보드 보기 (기존 기능)
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
# [PAGE 2] 데이터 입력 도우미 (새로운 기능)
# ==============================================================================
elif menu == "📝 데이터 입력 도우미":
    st.title("📝 간편 데이터 생성기")
    st.info("💡 가장 최근 데이터를 불러옵니다. 금액만 수정하면 '오늘자 데이터'를 만들어 드립니다.")

    # 관리자만 접근 가능
    if input_password != ADMIN_PASSWORD:
        st.error("🔒 관리자 비밀번호를 입력해야 사용할 수 있습니다.")
    elif df is not None:
        # 1. 가장 최근 데이터 불러오기
        latest_date = df['기준일자'].max()
        input_df = df[df['기준일자'] == latest_date].copy()
        
        # 2. 날짜 컬럼은 오늘 날짜로 변경할 준비
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 3. 사용자에게 보여줄(수정할) 컬럼만 추리기
        # (원금이나 종목명은 잘 안 바뀌니까 그대로 두고, '평가액'만 수정하게 유도)
        editable_cols = ['주체', '증권사', '구분', '종목명', '테마', '원금', '평가액']
        
        st.subheader(f"1️⃣ {latest_date.date()} 기준 보유 종목입니다. 금액을 최신화하세요.")
        st.caption("👇 아래 표의 숫자를 클릭해서 수정할 수 있습니다. (행 추가/삭제도 가능)")
        
        # ★ 데이터 에디터 (여기서 엑셀처럼 수정 가능)
        edited_df = st.data_editor(
            input_df[editable_cols],
            num_rows="dynamic", # 행 추가/삭제 가능
            use_container_width=True,
            column_config={
                "원금": st.column_config.NumberColumn(format="%d"),
                "평가액": st.column_config.NumberColumn(format="%d"),
            }
        )
        
        # 4. 결과 생성 버튼
        if st.button("🚀 오늘 날짜로 데이터 생성하기"):
            # 계산 로직: 평가손익 = 평가액 - 원금
            edited_df['평가손익'] = edited_df['평가액'] - edited_df['원금']
            
            # 기준일자 컬럼 맨 앞에 추가
            final_export_df = edited_df.copy()
            final_export_df.insert(0, '기준일자', today)
            
            # 구글 시트 원본 순서대로 컬럼 정렬 (중요!)
            # 기준일자, 주체, 증권사, 구분, 종목명, 테마, 원금, 평가액, 평가손익
            target_order = ['기준일자', '주체', '증권사', '구분', '종목명', '테마', '원금', '평가액', '평가손익']
            
            # 혹시 컬럼이 다 있는지 확인
            try:
                final_export_df = final_export_df[target_order]
                
                st.subheader("2️⃣ 아래 내용을 복사해서 구글 시트에 붙여넣으세요!")
                st.code(final_export_df.to_csv(index=False, header=False, sep='\t'), language='csv')
                
                st.success(f"✅ 총 {len(final_export_df)}개의 데이터가 생성되었습니다. 위 박스 오른쪽 위의 '복사' 버튼을 누르세요!")
                st.markdown(f"[👉 구글 시트 바로가기]({FIXED_URL})")
                
            except Exception as e:
                st.error(f"컬럼 생성 중 오류가 났습니다. 원본 시트 양식과 맞는지 확인해주세요. ({e})")
