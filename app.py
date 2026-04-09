import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="centered")

st.title("🏦 핀드 담보 심사")
st.caption("KB증권 하이브리드 | v5.2")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.header("📖 가이드")
    st.markdown("**국내**: `005930`  \n**해외**: `AAPL`")
    st.markdown("---")
    with st.expander("불가사유"):
        st.markdown("**국내**: 시총 100억 미만, 관리종목  \n**해외**: OTC, 비허용 거래소")

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
                    # KRX 데이터
                    df_krx = fdr.StockListing('KRX')
                    stock_info = df_krx[df_krx['Code'] == ticker]
                    
                    if stock_info.empty:
                        st.error(f"❌ {ticker} 조회 실패")
                    else:
                        name = stock_info.iloc[0]['Name']
                        market = stock_info.iloc[0]['Market']
                        market_cap = stock_info.iloc[0].get('Marcap', 0) / 100000000
                        
                        # 주가 데이터
                        df_price = fdr.DataReader(ticker, '2024-01-01')
                        current_price = df_price['Close'].iloc[-1]
                        high_52w = df_price['High'].max()
                        low_52w = df_price['Low'].min()
                        volatility = ((high_52w - low_52w) / low_52w) * 100
                        
                        # 기본 정보
                        st.markdown("### 📌 기본 정보")
                        c1, c2, c3, c4 = st.columns(4)
                        c1.metric("종목명", name)
                        c2.metric("시장", market)
                        c3.metric("현재가", f"{current_price:,.0f}원")
                        c4.metric("시총", f"{market_cap:,.0f}억")
                        
                        st.markdown("---")
                        
                        # 판정
                        violations = []
                        warnings = []
                        
                        if stock_info.iloc[0].get('Dept', '') == '관리':
                            violations.append("관리종목")
                        
                        if market_cap < 100:
                            violations.append(f"시총 {market_cap:,.0f}억")
                        
                        if volatility >= 500:
                            warnings.append(f"변동성 {volatility:.0f}%")
                        elif volatility >= 200:
                            warnings.append(f"변동성 {volatility:.0f}%")
                        
                        # 결과
                        st.markdown("### 🎯 판정")
                        
                        if violations:
                            st.error("⛔ **담보 불가**")
                            st.markdown(f"**불가 사유**: {', '.join(violations)}")
                            st.markdown("**위험**: 🔴 상장폐지 위험 높음, 🔴 급락 위험 높음")
                            st.markdown("**의견**: 시총 100억 미만 또는 관리종목으로 담보 인정 불가")
                        elif warnings:
                            st.warning("⚠️ **조건부 가능**")
                            st.markdown(f"**주의**: {', '.join(warnings)}")
                            st.markdown("**위험**: 🟠 급락 위험 높음, 🟡 모니터링 필요")
                            st.markdown("**조건**: 일일 모니터링 필수, 로스컷 130%")
                            st.markdown("**의견**: 변동성이 높아 급락 위험 있음. 일일 모니터링 필수")
                        else:
                            st.success("✅ **담보 가능**")
                            st.markdown("**위험**: 🟢 낮음, 🟢 안정적")
                            st.markdown("**조건**: LTV 200%, 로스컷 130%")
                            st.markdown("**의견**: 정상 담보 인정 가능")
                        
                        st.markdown("---")
                        st.markdown("### 📈 주가 (52주)")
                        p1, p2, p3 = st.columns(3)
                        p1.metric("최고", f"{high_52w:,.0f}원")
                        p2.metric("최저", f"{low_52w:,.0f}원")
                        p3.metric("변동폭", f"{volatility:.1f}%")
                    
                except Exception as e:
                    st.error(f"❌ 오류: {str(e)}")
                    st.info("KRX 서버 일시 오류일 수 있습니다. 잠시 후 재시도해주세요.")
        
        # === 해외주식 ===
        else:
            st.markdown("## 🌎 해외주식")
            
            with st.spinner("조회 중..."):
                try:
                    stock = yf.Ticker(ticker.upper())
                    info = stock.info
                    hist = stock.history(period="1y")
                    
                    name = info.get('longName', info.get('shortName', ticker.upper()))
                    exchange_raw = info.get('exchange', 'N/A')
                    price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                    
                    # ETF vs 주식
                    quote_type = info.get('quoteType', '')
                    if quote_type == 'ETF':
                        mcap_value = info.get('totalAssets', 0)
                        mcap_label = "AUM"
                    else:
                        mcap_value = info.get('marketCap', 0)
                        mcap_label = "시총"
                    
                    mcap = mcap_value / 1e9 if mcap_value else 0
                    
                    # 거래소
                    exchange_map = {
                        'NYQ': 'NYSE', 'NMS': 'NASDAQ', 'NGM': 'NASDAQ',
                        'NAS': 'NASDAQ', 'PCX': 'NYSE Arca', 'NYSEARCA': 'NYSE Arca'
                    }
                    exchange = exchange_map.get(exchange_raw, exchange_raw)
                    
                    # 변동성
                    if not hist.empty:
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100 if low > 0 else 0
                    else:
                        high = low = vol = 0
                    
                    # 기본 정보
                    st.markdown("### 📌 기본 정보")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("종목명", name[:15])
                    c2.metric("거래소", exchange)
                    c3.metric("가격", f"${price:.2f}")
                    c4.metric(mcap_label, f"${mcap:.1f}B")
                    
                    st.markdown("---")
                    
                    # 판정
                    violations = []
                    warnings = []
                    
                    allowed = ["NYSE", "NASDAQ", "NYSE Arca"]
                    if exchange not in allowed and exchange != "N/A":
                        violations.append(f"거래소: {exchange}")
                    
                    if "OTC" in exchange.upper():
                        violations.append("OTC")
                    
                    if vol >= 200:
                        warnings.append(f"변동성 {vol:.0f}%")
                    
                    # 결과
                    st.markdown("### 🎯 판정")
                    
                    if violations:
                        st.error("⛔ **담보 불가**")
                        st.markdown(f"**불가 사유**: {', '.join(violations)}")
                        st.markdown("**위험**: 🔴 높음")
                        st.markdown("**의견**: 비허용 거래소로 담보 인정 불가")
                    elif warnings:
                        st.warning("⚠️ **조건부 가능**")
                        st.markdown(f"**주의**: {', '.join(warnings)}")
                        st.markdown("**위험**: 🟠 급락 위험 높음")
                        st.markdown("**조건**: 일일 모니터링 필수")
                        st.markdown("**의견**: 변동성 높음. 일일 모니터링 필수")
                    else:
                        st.success("✅ **담보 가능**")
                        st.markdown("**위험**: 🟢 낮음")
                        st.markdown("**조건**: LTV 200%, 로스컷 130%")
                        st.markdown("**의견**: 정상 담보 인정 가능")
                    
                    if not hist.empty:
                        st.markdown("---")
                        st.markdown("### 📈 주가 (52주)")
                        p1, p2, p3 = st.columns(3)
                        p1.metric("최고", f"${high:.2f}")
                        p2.metric("최저", f"${low:.2f}")
                        p3.metric("변동폭", f"{vol:.1f}%")
                
                except Exception as e:
                    st.error(f"❌ 오류: {str(e)}")
                    st.info("Yahoo Finance 일시 오류일 수 있습니다. 잠시 후 재시도해주세요.")

st.markdown("---")
st.caption("ⓒ 2026 Pind")
