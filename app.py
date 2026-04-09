import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="centered")

st.title("🏦 핀드 담보 심사")
st.caption("KB증권 하이브리드 | v4.0 복원")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.header("📖 가이드")
    st.markdown("""
    **국내**: `005930` `064800`  
    **해외**: `AAPL` `SOXL`
    """)

# 메인
ticker = st.text_input("종목코드 / 티커", placeholder="예: 005930, AAPL")

if st.button("🔍 심사", type="primary"):
    if not ticker:
        st.error("❌ 종목코드를 입력하세요")
    else:
        is_korean = ticker.isdigit() and len(ticker) == 6
        
        # === 국내주식 ===
        if is_korean:
            st.markdown("## 🇰🇷 국내주식")
            
            with st.spinner("조회 중..."):
                try:
                    df_krx = fdr.StockListing('KRX')
                    stock_info = df_krx[df_krx['Code'] == ticker]
                    
                    if stock_info.empty:
                        st.error(f"❌ 종목코드 {ticker}를 찾을 수 없습니다.")
                    else:
                        name = stock_info.iloc[0]['Name']
                        market = stock_info.iloc[0]['Market']
                        market_cap = stock_info.iloc[0].get('Marcap', 0) / 100000000
                        
                        df_price = fdr.DataReader(ticker, '2024-01-01')
                        
                        if df_price.empty:
                            st.error("❌ 주가 데이터를 가져올 수 없습니다.")
                        else:
                            current_price = df_price['Close'].iloc[-1]
                            high_52w = df_price['High'].max()
                            low_52w = df_price['Low'].min()
                            
                            volatility = 0
                            if high_52w > 0 and low_52w > 0:
                                volatility = ((high_52w - low_52w) / low_52w) * 100
                            
                            # 기본 정보
                            st.markdown("### 📌 기본 정보")
                            
                            col1, col2, col3, col4 = st.columns(4)
                            col1.metric("종목명", name)
                            col2.metric("시장", market)
                            col3.metric("현재가", f"{current_price:,.0f}원")
                            col4.metric("시총", f"{market_cap:,.0f}억")
                            
                            st.markdown("---")
                            
                            # 판정 로직
                            violations = []
                            warnings = []
                            
                            if stock_info.iloc[0].get('Dept', '') == '관리':
                                violations.append("관리종목 지정")
                            
                            if market_cap < 100:
                                violations.append(f"시가총액 {market_cap:,.0f}억원 (기준: 100억 이상)")
                            
                            if volatility >= 500:
                                warnings.append(f"극심한 변동성 {volatility:.0f}%")
                            elif volatility >= 200:
                                warnings.append(f"높은 변동성 {volatility:.0f}%")
                            
                            # 판정 결과
                            st.markdown("### 🎯 판정")
                            
                            if violations:
                                st.error("⛔ **담보 불가**")
                                st.markdown(f"**불가 사유**: {', '.join(violations)}")
                                st.markdown("**위험 분석**: 🔴 상장폐지 위험 높음, 🔴 급락 위험 높음")
                                st.markdown("**심사 의견**: 담보 인정 불가")
                            elif warnings:
                                st.warning("⚠️ **조건부 가능 (고위험)**")
                                st.markdown(f"**주의 사항**: {', '.join(warnings)}")
                                st.markdown("**위험 분석**: 🔴 급락 위험 매우 높음")
                                st.markdown("**담보 조건**: 일일 모니터링 필수, 로스컷 130%")
                                st.markdown("**심사 의견**: 변동성 극심. 로스컷 발생 시 고객 안내 필수")
                            else:
                                st.success("✅ **담보 가능**")
                                st.markdown("**위험 분석**: 🟢 낮음")
                                st.markdown("**담보 조건**: 최대 LTV 200%, 로스컷 130%")
                                st.markdown("**심사 의견**: 정상 담보 인정")
                            
                            # 주가 정보
                            st.markdown("---")
                            st.markdown("### 📈 52주 주가")
                            
                            p1, p2, p3 = st.columns(3)
                            p1.metric("최고", f"{high_52w:,.0f}원")
                            p2.metric("최저", f"{low_52w:,.0f}원")
                            p3.metric("변동폭", f"{volatility:.1f}%")
                    
                except Exception as e:
                    st.error(f"❌ 오류: {str(e)}")
        
        # === 해외주식 ===
        else:
            st.markdown("## 🌎 해외주식")
            
            with st.spinner("조회 중..."):
                try:
                    stock = yf.Ticker(ticker.upper())
                    info = stock.info
                    hist = stock.history(period="1y")
                    
                    st.markdown("### 📌 기본 정보")
                    
                    name = info.get('longName', info.get('shortName', 'N/A'))
                    exchange_raw = info.get('exchange', 'N/A')
                    price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                    
                    # ETF인 경우 totalAssets(AUM) 사용, 일반 주식은 marketCap 사용
                    quote_type = info.get('quoteType', '')
                    
                    if quote_type == 'ETF':
                        mcap_value = info.get('totalAssets', 0)
                        mcap_label = "AUM"
                        stock_type = "ETF"
                    else:
                        mcap_value = info.get('marketCap', 0)
                        mcap_label = "시총"
                        stock_type = "주식"
                    
                    mcap = mcap_value / 1e9 if mcap_value else 0
                    
                    exchange_map = {
                        'NYQ': 'NYSE', 'NMS': 'NASDAQ', 'NGM': 'NASDAQ',
                        'NAS': 'NASDAQ', 'PCX': 'NYSE Arca', 'NYSEARCA': 'NYSE Arca'
                    }
                    exchange = exchange_map.get(exchange_raw, exchange_raw)
                    
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("종목명", name[:15])
                    col2.metric("거래소", exchange)
                    col3.metric("가격", f"${price:.2f}")
                    col4.metric(mcap_label, f"${mcap:.1f}B")
                    
                    st.markdown("---")
                    
                    violations = []
                    warnings = []
                    
                    allowed = ["NYSE", "NASDAQ", "NYSE Arca"]
                    if exchange not in allowed and exchange != "N/A":
                        violations.append(f"비허용 거래소: {exchange}")
                    if "OTC" in exchange.upper():
                        violations.append("OTC 장외시장")
                    
                    if quote_type != "ETF" and quote_type in ["MLP", "ETP"]:
                        violations.append("PTP 구조")
                    
                    if mcap < 1 and not violations:
                        if quote_type == 'ETF':
                            warnings.append(f"소규모 ETF (AUM ${mcap:.2f}B)")
                        else:
                            warnings.append(f"소형주 (시총 ${mcap:.2f}B)")
                    
                    # 변동성
                    if not hist.empty:
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100 if low > 0 else 0
                        if vol >= 200 and not violations:
                            warnings.append(f"높은 변동성 {vol:.0f}%")
                    else:
                        high = 0
                        low = 0
                        vol = 0
                    
                    st.markdown("### 🎯 판정")
                    
                    if violations:
                        st.error("⛔ **담보 불가**")
                        st.markdown(f"**불가 사유**: {', '.join(violations)}")
                        st.markdown("**위험 분석**: 🔴 높음")
                        st.markdown("**심사 의견**: 비허용 거래소로 담보 인정 불가")
                    elif warnings:
                        st.warning("⚠️ **조건부 가능 (고위험)**")
                        st.markdown(f"**주의 사항**: {', '.join(warnings)}")
                        st.markdown("**위험 분석**: 🔴 급락 위험 높음")
                        st.markdown("**담보 조건**: 일일 모니터링 필수")
                        st.markdown("**심사 의견**: 변동성 높음. 로스컷 위험 안내 필수")
                    else:
                        st.success("✅ **담보 가능**")
                        st.markdown("**위험 분석**: 🟢 낮음")
                        st.markdown("**담보 조건**: 최대 LTV 200%, 로스컷 130%")
                        st.markdown("**심사 의견**: 정상 담보 인정")
                    
                    if not hist.empty:
                        st.markdown("---")
                        st.markdown("### 📈 52주 주가")
                        
                        p1, p2, p3 = st.columns(3)
                        p1.metric("최고", f"${high:.2f}")
                        p2.metric("최저", f"${low:.2f}")
                        p3.metric("변동폭", f"{vol:.1f}%")
                    
                except Exception as e:
                    st.error(f"❌ 오류: {str(e)}")

st.markdown("---")
st.caption("ⓒ 2026 Pind | v4.0")
