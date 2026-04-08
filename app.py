import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import time

# 페이지 설정
st.set_page_config(
    page_title="핀드 담보 적격성 자동 심사 시스템",
    page_icon="🏦",
    layout="wide"
)

# CSS 스타일
st.markdown("""
<style>
.big-font {
    font-size:20px !important;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# 제목
st.title("🏦 핀드 담보 적격성 자동 심사 시스템")
st.markdown("**KB증권 하이브리드 계좌운용규칙 기준**")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.header("📊 시스템 정보")
    st.info("""
    **버전**: v1.0  
    **업데이트**: 2026-04-08  
    **규칙 기준**: KB증권 하이브리드
    """)
    
    st.markdown("---")
    st.header("ℹ️ 사용 가이드")
    st.markdown("""
    1. 종목코드 또는 티커 입력
    2. 시장 선택 (자동 감지)
    3. [심사 시작] 버튼 클릭
    4. 결과 확인 및 다운로드
    
    **국내주식 예시**:  
    - 005930 (삼성전자)  
    - 127120 (제이에스링크)
    
    **해외주식 예시**:  
    - AAPL (애플)  
    - TSLA (테슬라)
    """)
    
    st.markdown("---")
    st.header("⚠️ 주요 불가 사유")
    with st.expander("국내주식"):
        st.markdown("""
        - 비상장 주식
        - 관리종목
        - 거래정지 예정
        - 시가총액 100억 미만
        - 액면가 100% 이하
        - 최근 7일간 -50% 이상
        - 정리매매종목
        """)
    
    with st.expander("해외주식"):
        st.markdown("""
        - 비상장 주식
        - PTP 종목
        - S&P500/NASDAQ100 미포함
        - OTC 시장
        """)

# 메인 화면
col1, col2 = st.columns([3, 1])

with col1:
    ticker_input = st.text_input(
        "**종목코드 또는 티커 입력**",
        placeholder="예: 005930, AAPL",
        help="국내주식: 6자리 숫자 / 해외주식: 영문 티커"
    )

with col2:
    market_type = st.selectbox(
        "**시장 구분**",
        ["자동 감지", "국내 주식", "해외 주식"]
    )

if st.button("🔍 심사 시작", type="primary", use_container_width=True):
    if not ticker_input:
        st.error("❌ 종목코드를 입력해주세요.")
    else:
        # 시장 자동 감지
        is_korean = ticker_input.isdigit() and len(ticker_input) == 6
        
        if market_type == "국내 주식" or (market_type == "자동 감지" and is_korean):
            # 국내 주식 심사
            st.markdown("## 🇰🇷 국내 주식 심사 결과")
            
            with st.spinner("📡 데이터 수집 중..."):
                time.sleep(0.5)
                
                # TODO: 실제 API 연동 필요
                # 현재는 더미 데이터로 작동
                stock_data = {
                    "종목코드": ticker_input,
                    "종목명": "조회 중...",
                    "시장": "KOSPI/KOSDAQ",
                    "현재가": "-",
                    "시가총액": "-",
                }
                
                # 기본 정보
                st.markdown("### 📌 기본 정보")
                info_cols = st.columns(5)
                with info_cols[0]:
                    st.metric("종목코드", stock_data["종목코드"])
                with info_cols[1]:
                    st.metric("종목명", stock_data["종목명"])
                with info_cols[2]:
                    st.metric("시장", stock_data["시장"])
                with info_cols[3]:
                    st.metric("현재가", stock_data["현재가"])
                with info_cols[4]:
                    st.metric("시가총액", stock_data["시가총액"])
                
                st.markdown("---")
                
                # 판정 로직
                violations = []
                warnings = []
                
                # [예시] 1차 필터: 절대 불가 조건
                # TODO: 실제 데이터로 교체 필요
                is_unlisted = False
                is_managed = False
                is_suspended = False
                market_cap_billion = 1000  # 예시: 1조원
                
                if is_unlisted:
                    violations.append("비상장 주식")
                if is_managed:
                    violations.append("관리종목")
                if is_suspended:
                    violations.append("거래정지")
                if market_cap_billion < 100:
                    violations.append(f"시가총액 {market_cap_billion}억원 (100억 미만)")
                
                # [예시] 2차 필터: 재무 리스크
                capital_erosion = 0
                debt_ratio = 80
                consecutive_losses = 0
                
                if capital_erosion >= 50:
                    violations.append(f"자본잠식 {capital_erosion}%")
                elif capital_erosion >= 30:
                    warnings.append(f"자본잠식 {capital_erosion}% → LTV 20% 이하 권장")
                
                if debt_ratio >= 300:
                    warnings.append(f"부채비율 {debt_ratio}% → LTV 30% 이하 권장")
                
                if consecutive_losses >= 3:
                    violations.append("3년 연속 당기순손실")
                
                # [예시] 3차 필터: 주가 변동성
                price_52w_high = 100000
                price_52w_low = 80000
                volatility_ratio = ((price_52w_high - price_52w_low) / price_52w_low) * 100
                
                if volatility_ratio >= 500:
                    warnings.append(f"극심한 변동성 {volatility_ratio:.0f}% → LTV 20% 이하 권장")
                elif volatility_ratio >= 200:
                    warnings.append(f"높은 변동성 {volatility_ratio:.0f}% → LTV 40% 이하 권장")
                
                # 최종 판정
                st.markdown("### 🎯 최종 판정")
                
                if violations:
                    st.error("### ✕ **담보 설정 불가**")
                    st.markdown("#### ⚠️ 불가 사유")
                    for v in violations:
                        st.markdown(f"- {v}")
                    recommended_ltv = "N/A"
                    judgment = "불가"
                    color = "red"
                    
                elif warnings:
                    st.warning("### △ **조건부 담보 설정 가능**")
                    st.markdown("#### ⚠️ 주의사항")
                    for w in warnings:
                        st.markdown(f"- {w}")
                    recommended_ltv = "20~40%"
                    judgment = "조건부"
                    color = "orange"
                    
                else:
                    st.success("### ○ **담보 설정 가능**")
                    st.markdown("✅ 계좌운용규칙 충족")
                    recommended_ltv = "60~80%"
                    judgment = "가능"
                    color = "green"
                
                st.markdown("---")
                
                # 재무 지표
                st.markdown("### 💰 재무 지표")
                fin_cols = st.columns(4)
                with fin_cols[0]:
                    st.metric("자본잠식률", f"{capital_erosion}%")
                with fin_cols[1]:
                    st.metric("부채비율", f"{debt_ratio}%")
                with fin_cols[2]:
                    st.metric("최근 3년 영업이익", "흑자/흑자/흑자")
                with fin_cols[3]:
                    st.metric("권장 LTV", recommended_ltv, delta=None, delta_color="off")
                
                st.markdown("---")
                
                # 주가 변동성
                st.markdown("### 📈 주가 변동성")
                vol_cols = st.columns(3)
                with vol_cols[0]:
                    st.metric("52주 최고가", f"{price_52w_high:,}원")
                with vol_cols[1]:
                    st.metric("52주 최저가", f"{price_52w_low:,}원")
                with vol_cols[2]:
                    st.metric("변동폭", f"{volatility_ratio:.1f}%")
                
                st.markdown("---")
                
                # 관리자 의견
                st.markdown("### 📝 리스크 관리팀 의견")
                if judgment == "불가":
                    opinion = "⛔ 담보로 절대 받지 말 것. 계좌운용규칙 명백히 위반."
                    st.error(opinion)
                elif judgment == "조건부":
                    opinion = "⚠️ 보수적 LTV 적용 필수. 정기 모니터링 및 추가 담보 징구 준비 필요."
                    st.warning(opinion)
                else:
                    opinion = "✅ 우량 종목. 정상적인 담보 설정 가능."
                    st.success(opinion)
                
                # 다운로드
                st.markdown("---")
                report_data = {
                    "심사일시": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                    "종목코드": [stock_data["종목코드"]],
                    "종목명": [stock_data["종목명"]],
                    "시장": [stock_data["시장"]],
                    "판정": [judgment],
                    "권장LTV": [recommended_ltv],
                    "불가사유": [", ".join(violations) if violations else "없음"],
                    "주의사항": [", ".join(warnings) if warnings else "없음"],
                    "자본잠식률": [f"{capital_erosion}%"],
                    "부채비율": [f"{debt_ratio}%"],
                    "52주변동폭": [f"{volatility_ratio:.1f}%"],
                    "리스크관리팀의견": [opinion]
                }
                
                df_report = pd.DataFrame(report_data)
                
                csv = df_report.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 심사 결과 다운로드 (CSV)",
                    data=csv,
                    file_name=f"핀드_담보심사_{ticker_input}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
        else:  # 해외 주식
            st.markdown("## 🌎 해외 주식 심사 결과")
            
            with st.spinner("📡 데이터 수집 중 (Yahoo Finance API)..."):
                try:
                    # yfinance로 실제 데이터 가져오기
                    stock = yf.Ticker(ticker_input.upper())
                    info = stock.info
                    hist = stock.history(period="1y")
                    
                    # 기본 정보
                    st.markdown("### 📌 기본 정보")
                    info_cols = st.columns(5)
                    with info_cols[0]:
                        st.metric("티커", ticker_input.upper())
                    with info_cols[1]:
                        st.metric("종목명", info.get("longName", "N/A")[:20])
                    with info_cols[2]:
                        exchange = info.get("exchange", "N/A")
                        st.metric("거래소", exchange)
                    with info_cols[3]:
                        price = info.get("currentPrice", info.get("regularMarketPrice", 0))
                        st.metric("현재가", f"${price:.2f}")
                    with info_cols[4]:
                        market_cap = info.get("marketCap", 0) / 1e9
                        st.metric("시가총액", f"${market_cap:.1f}B")
                    
                    st.markdown("---")
                    
                    # 판정 로직
                    violations = []
                    warnings = []
                    
                    # 1차: 거래소 확인
                    allowed_exchanges = ["NYQ", "NMS", "NGM", "PCX", "NAS"]
                    if exchange not in allowed_exchanges and exchange != "N/A":
                        violations.append(f"허용되지 않은 거래소 ({exchange})")
                    
                    # 2차: S&P500 / NASDAQ100 확인 (간이 판정)
                    # 실제로는 별도 리스트 확인 필요
                    is_large_cap = market_cap > 10  # 100억 달러 이상
                    if not is_large_cap:
                        warnings.append(f"시가총액 ${market_cap:.1f}B - S&P500/NASDAQ100 확인 필요")
                    
                    # PTP 확인 (더미)
                    quote_type = info.get("quoteType", "")
                    if "LP" in ticker_input.upper() or quote_type == "MLP":
                        violations.append("PTP (Publicly Traded Partnership) 가능성")
                    
                    # 최종 판정
                    st.markdown("### 🎯 최종 판정")
                    
                    if violations:
                        st.error("### ✕ **담보 설정 불가**")
                        st.markdown("#### ⚠️ 불가 사유")
                        for v in violations:
                            st.markdown(f"- {v}")
                        recommended_ltv = "N/A"
                        judgment = "불가"
                    elif warnings:
                        st.warning("### △ **조건부 담보 설정 가능**")
                        st.markdown("#### ⚠️ 주의사항")
                        for w in warnings:
                            st.markdown(f"- {w}")
                        recommended_ltv = "40~60%"
                        judgment = "조건부"
                    else:
                        st.success("### ○ **담보 설정 가능**")
                        st.markdown("✅ S&P500/NASDAQ100 대형주 (추정)")
                        recommended_ltv = "60~70%"
                        judgment = "가능"
                    
                    st.markdown("---")
                    
                    # 기업 정보
                    st.markdown("### 💰 기업 정보")
                    comp_cols = st.columns(4)
                    with comp_cols[0]:
                        st.metric("섹터", info.get("sector", "N/A"))
                    with comp_cols[1]:
                        st.metric("산업", info.get("industry", "N/A")[:20])
                    with comp_cols[2]:
                        pe_ratio = info.get("trailingPE", "N/A")
                        pe_text = f"{pe_ratio:.2f}" if isinstance(pe_ratio, (int, float)) else "N/A"
                        st.metric("P/E Ratio", pe_text)
                    with comp_cols[3]:
                        st.metric("권장 LTV", recommended_ltv)
                    
                    st.markdown("---")
                    
                    # 주가 정보
                    if not hist.empty:
                        st.markdown("### 📈 주가 정보 (52주)")
                        price_high = hist['High'].max()
                        price_low = hist['Low'].min()
                        volatility = ((price_high - price_low) / price_low) * 100
                        
                        price_cols = st.columns(3)
                        with price_cols[0]:
                            st.metric("52주 최고가", f"${price_high:.2f}")
                        with price_cols[1]:
                            st.metric("52주 최저가", f"${price_low:.2f}")
                        with price_cols[2]:
                            st.metric("변동폭", f"{volatility:.1f}%")
                        
                        st.markdown("---")
                    
                    # 관리자 의견
                    st.markdown("### 📝 리스크 관리팀 의견")
                    if judgment == "불가":
                        opinion = "⛔ 계좌운용규칙 위반. 담보 설정 불가."
                        st.error(opinion)
                    elif judgment == "조건부":
                        opinion = "⚠️ S&P500/NASDAQ100 편입 여부 재확인 필요. 확인 후 담보 설정."
                        st.warning(opinion)
                    else:
                        opinion = "✅ 대형 우량주. 정상 담보 설정 가능."
                        st.success(opinion)
                    
                    # 다운로드
                    st.markdown("---")
                    report_data = {
                        "심사일시": [datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                        "티커": [ticker_input.upper()],
                        "종목명": [info.get("longName", "N/A")],
                        "거래소": [exchange],
                        "판정": [judgment],
                        "권장LTV": [recommended_ltv],
                        "불가사유": [", ".join(violations) if violations else "없음"],
                        "주의사항": [", ".join(warnings) if warnings else "없음"],
                        "시가총액_B": [f"${market_cap:.1f}"],
                        "리스크관리팀의견": [opinion]
                    }
                    
                    df_report = pd.DataFrame(report_data)
                    csv = df_report.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 심사 결과 다운로드 (CSV)",
                        data=csv,
                        file_name=f"핀드_담보심사_{ticker_input.upper()}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ 데이터 조회 실패: {str(e)}")
                    st.info("💡 종목 티커를 다시 확인해주세요. 예: AAPL, MSFT, TSLA")

# 하단 정보
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: gray; font-size: 12px;'>
<b>핀드 담보 적격성 자동 심사 시스템 v1.0</b><br>
계좌운용규칙 기준: KB증권 하이브리드 | 업데이트: 2026-04-08<br>
문의: risk@pind.co.kr | ⓒ 2026 Pind Inc.
</div>
""", unsafe_allow_html=True)