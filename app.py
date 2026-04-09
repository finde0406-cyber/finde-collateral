import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="centered")

st.markdown("""
<style>
    .main > div {padding-top: 1rem;}
    h1 {font-size: 1.8rem !important; margin-bottom: 0.3rem !important;}
    .stTextInput > div > div > input {font-size: 1rem;}
    [data-testid="stMetricValue"] {font-size: 1.2rem;}
</style>
""", unsafe_allow_html=True)

st.title("🏦 핀드 담보 심사")
st.caption("KB증권 하이브리드 계좌운용규칙 | v5.1")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.header("📖 가이드")
    st.markdown("""
    **국내**: `005930` `064800`  
    **해외**: `AAPL` `SOXL`
    """)
    st.markdown("---")
    st.success("완전 자동화")
    
    with st.expander("불가사유"):
        st.markdown("""
        **국내**
        • 시총 100억 미만
        • 관리종목
        
        **해외**
        • OTC 장외시장
        • 비허용 거래소
        """)

# 의견 생성 함수들
def generate_rejection_opinion(violations, data, is_korean=True):
    opinion = ""
    
    opinion += "### 📊 정량 지표\n"
    if is_korean:
        opinion += f"• **시가총액**: {data.get('market_cap', 0):,.0f}억원\n"
        opinion += f"• **시장**: {data.get('market', 'N/A')}\n"
    else:
        mcap = data.get('market_cap', 0)
        stock_type = data.get('type', '주식')
        if stock_type == 'ETF':
            opinion += f"• **운용자산(AUM)**: ${mcap:.1f}B\n"
        else:
            opinion += f"• **시가총액**: ${mcap:.1f}B\n"
        opinion += f"• **거래소**: {data.get('exchange', 'N/A')}\n"
    
    opinion += "\n### ❌ 불가 사유\n"
    for v in violations:
        opinion += f"• {v}\n"
    
    opinion += "\n### 🚨 위험 분석\n"
    opinion += "| 항목 | 평가 |\n|------|------|\n"
    opinion += "| 상장폐지 위험 | 🔴 **높음** |\n"
    opinion += "| 급락 위험 | 🔴 **높음** |\n"
    opinion += "| 유동성 위험 | 🔴 **높음** |\n"
    
    opinion += "\n### 💼 심사 의견\n"
    if is_korean:
        if any("시가총액" in v for v in violations):
            opinion += "시가총액 100억원 미만으로 유동성이 극히 낮습니다. 로스컷 시 슬리피지가 크게 발생할 수 있습니다.\n\n"
        if any("관리종목" in v for v in violations):
            opinion += "관리종목 지정으로 상장폐지 가능성이 있어 담보가치 전액 소멸 위험이 있습니다.\n\n"
    else:
        opinion += "장외시장 또는 비허용 거래소 종목으로 담보로 인정할 수 없습니다.\n\n"
    
    opinion += "**결론**: 담보 인정 불가\n"
    
    opinion += "\n### 📢 고객 안내\n"
    if is_korean:
        opinion += "> 해당 종목은 리스크 기준 부적합으로 담보 인정이 불가능합니다. 시가총액 100억원 이상 종목으로 재신청해주세요."
    else:
        opinion += "> 해당 종목은 리스크 기준 부적합으로 담보 인정이 불가능합니다. NYSE, NASDAQ 상장 종목으로 재신청해주세요."
    
    return opinion

def generate_conditional_opinion(warnings, data, is_korean=True):
    opinion = ""
    
    opinion += "### 📊 정량 지표\n"
    if is_korean:
        opinion += f"• **시가총액**: {data.get('market_cap', 0):,.0f}억원\n"
        opinion += f"• **시장**: {data.get('market', 'N/A')}\n"
        opinion += f"• **현재가**: {data.get('price', 0):,.0f}원\n"
    else:
        mcap = data.get('market_cap', 0)
        stock_type = data.get('type', '주식')
        if stock_type == 'ETF':
            opinion += f"• **운용자산(AUM)**: ${mcap:.1f}B\n"
        else:
            opinion += f"• **시가총액**: ${mcap:.1f}B\n"
        opinion += f"• **거래소**: {data.get('exchange', 'N/A')}\n"
        opinion += f"• **현재가**: ${data.get('price', 0):.2f}\n"
    
    volatility = data.get('volatility', 0)
    if volatility > 0:
        opinion += f"• **52주 변동폭**: {volatility:.1f}%\n"
    
    opinion += "\n### ⚠️ 주의 사항\n"
    for w in warnings:
        opinion += f"• {w}\n"
    
    opinion += "\n### 🔍 위험 분석\n"
    opinion += "| 항목 | 평가 | 비고 |\n|------|------|------|\n"
    
    if any("관리" in w for w in warnings):
        opinion += "| 상장폐지 위험 | 🔴 **높음** | 관리종목 |\n"
    else:
        opinion += "| 상장폐지 위험 | 🟢 낮음 | 정상 종목 |\n"
    
    if volatility >= 500:
        opinion += f"| 급락 위험 | 🔴 **매우 높음** | 변동성 {volatility:.0f}% |\n"
    elif volatility >= 200:
        opinion += f"| 급락 위험 | 🟠 **높음** | 변동성 {volatility:.0f}% |\n"
    else:
        opinion += "| 급락 위험 | 🟡 보통 | - |\n"
    
    opinion += "| 유동성 | 🟡 보통 | 시총 기준 충족 |\n"
    
    opinion += "\n### 📋 담보 조건\n```\n"
    opinion += "✓ 담보 인정: 가능 (고위험 등급)\n"
    opinion += "✓ 최대 LTV: 200%\n"
    opinion += "✓ 로스컷: 130%\n"
    opinion += "✓ 일일 모니터링: 필수\n```\n"
    
    opinion += "\n### 💼 심사 의견\n"
    if volatility >= 500:
        opinion += f"극심한 변동성({volatility:.0f}%)으로 단기간 급락 위험이 매우 높습니다. "
    elif volatility >= 200:
        opinion += f"높은 변동성({volatility:.0f}%)으로 단기간 급락 위험이 있습니다. "
    
    opinion += "담보비율 130% 도달 시 자동 반대매매가 즉시 실행됩니다.\n\n**결론**: 조건부 담보 인정 (일일 모니터링 필수)\n"
    
    opinion += "\n### 📢 고객 안내\n"
    opinion += "> 담보 가능하나 변동성이 높은 종목입니다. 주가 급락 시 자동 반대매매(로스컷)가 발생할 수 있습니다."
    
    return opinion

def generate_approval_opinion(data, is_korean=True):
    opinion = ""
    
    opinion += "### 📊 정량 지표\n"
    if is_korean:
        mcap = data.get('market_cap', 0)
        opinion += f"• **시가총액**: {mcap:,.0f}억원\n"
        if mcap >= 10000:
            opinion += f"• **등급**: 초대형주\n"
        elif mcap >= 1000:
            opinion += f"• **등급**: 대형주\n"
        else:
            opinion += f"• **등급**: 중형주\n"
        opinion += f"• **시장**: {data.get('market', 'N/A')}\n"
        opinion += f"• **현재가**: {data.get('price', 0):,.0f}원\n"
    else:
        mcap = data.get('market_cap', 0)
        stock_type = data.get('type', '주식')
        if stock_type == 'ETF':
            opinion += f"• **운용자산(AUM)**: ${mcap:.1f}B\n"
        else:
            opinion += f"• **시가총액**: ${mcap:.1f}B\n"
        opinion += f"• **거래소**: {data.get('exchange', 'N/A')}\n"
        opinion += f"• **현재가**: ${data.get('price', 0):.2f}\n"
    
    volatility = data.get('volatility', 0)
    if volatility > 0:
        opinion += f"• **52주 변동폭**: {volatility:.1f}%\n"
    
    opinion += "\n### ✅ 적격 근거\n"
    if is_korean:
        opinion += "• 시가총액 100억원 이상\n• 관리종목 미지정\n• 정상 거래 중\n"
    else:
        opinion += "• 주요 거래소 상장\n• 정상 거래 중\n"
    
    opinion += "\n### 🔍 위험 분석\n"
    opinion += "| 항목 | 평가 | 비고 |\n|------|------|------|\n"
    opinion += "| 상장폐지 위험 | 🟢 낮음 | 정상 종목 |\n"
    
    if volatility >= 100:
        opinion += f"| 급락 위험 | 🟡 보통 | 변동성 {volatility:.0f}% |\n"
    else:
        opinion += "| 급락 위험 | 🟢 낮음 | 안정적 |\n"
    
    opinion += "| 유동성 | 🟢 우수 | 충분한 거래량 |\n"
    
    opinion += "\n### 📋 담보 조건\n```\n"
    opinion += "✓ 담보 인정: 가능 (정상 등급)\n"
    opinion += "✓ 최대 LTV: 200%\n"
    opinion += "✓ 로스컷: 130%\n"
    opinion += "✓ 현금인출: 140% 이상\n```\n"
    
    opinion += "\n### 💼 심사 의견\n"
    opinion += "계좌운용규칙 기준을 충족하는 우량 종목입니다. 정상 담보 설정이 가능합니다.\n\n**결론**: 정상 담보 인정\n"
    
    opinion += "\n### 📢 고객 안내\n"
    opinion += "> 담보 설정에 문제가 없습니다. 최대 200%까지 대출 가능합니다."
    
    return opinion

# 메인
ticker = st.text_input(
    "종목코드 / 티커",
    placeholder="예: 005930, AAPL, SOXL",
    key="ticker_input"
)

col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    search_button = st.button("🔍 심사", type="primary", use_container_width=True)

if search_button and ticker:
    is_korean = ticker.isdigit() and len(ticker) == 6
    
    # === 국내주식 ===
    if is_korean:
        st.markdown("## 🇰🇷 국내주식 심사")
        
        with st.spinner("데이터 수집 중..."):
            data_source = None
            stock_data = None
            
            # 1차: FinanceDataReader
            try:
                df_krx = fdr.StockListing('KRX')
                stock_info = df_krx[df_krx['Code'] == ticker]
                
                if not stock_info.empty:
                    df_price = fdr.DataReader(ticker, '2024-01-01')
                    if not df_price.empty:
                        data_source = "KRX"
                        stock_data = {
                            'name': stock_info.iloc[0]['Name'],
                            'market': stock_info.iloc[0]['Market'],
                            'market_cap': stock_info.iloc[0].get('Marcap', 0) / 100000000,
                            'dept': stock_info.iloc[0].get('Dept', ''),
                            'price_data': df_price
                        }
            except:
                st.warning("⚠️ KRX 접근 실패 - 백업 시도 중...")
            
            # 2차: yfinance
            if not stock_data:
                try:
                    for suffix in ['.KS', '.KQ']:
                        stock_yf = yf.Ticker(f"{ticker}{suffix}")
                        info = stock_yf.info
                        if info and info.get('regularMarketPrice'):
                            hist = stock_yf.history(period="1y")
                            if not hist.empty:
                                data_source = f"Yahoo Finance"
                                mcap_raw = info.get('marketCap', 0)
                                stock_data = {
                                    'name': info.get('shortName', ticker),
                                    'market': 'KOSPI' if suffix == '.KS' else 'KOSDAQ',
                                    'market_cap': mcap_raw / 100000000 if mcap_raw else 0,
                                    'dept': '',
                                    'price_data': hist
                                }
                                st.info(f"ℹ️ 백업 데이터 소스 사용")
                                break
                except:
                    pass
            
            if not stock_data:
                st.error(f"❌ {ticker} 데이터를 가져올 수 없습니다.")
            else:
                try:
                    name = stock_data['name']
                    market = stock_data['market']
                    market_cap = stock_data['market_cap']
                    df_price = stock_data['price_data']
                    
                    current_price = df_price['Close'].iloc[-1]
                    high_52w = df_price['High'].max()
                    low_52w = df_price['Low'].min()
                    volatility = ((high_52w - low_52w) / low_52w) * 100 if low_52w > 0 else 0
                    
                    st.markdown("### 📌 기본 정보")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("종목명", name)
                    col2.metric("시장", market)
                    col3.metric("현재가", f"{current_price:,.0f}원")
                    col4.metric("시총", f"{market_cap:,.0f}억" if market_cap > 0 else "-")
                    
                    st.markdown("---")
                    
                    violations = []
                    warnings = []
                    
                    if stock_data['dept'] == '관리':
                        violations.append("관리종목 지정")
                    
                    if market_cap > 0 and market_cap < 100:
                        violations.append(f"시가총액 {market_cap:,.0f}억원")
                    elif market_cap == 0:
                        warnings.append("시가총액 정보 없음")
                    
                    if volatility >= 500:
                        warnings.append(f"극심한 변동성 {volatility:.0f}%")
                    elif volatility >= 200:
                        warnings.append(f"높은 변동성 {volatility:.0f}%")
                    
                    if data_source == "Yahoo Finance":
                        warnings.append("관리종목 여부 확인 필요")
                    
                    st.markdown("---")
                    
                    data = {'market_cap': market_cap, 'market': market, 'price': current_price, 'volatility': volatility}
                    
                    if violations:
                        st.error("⛔ **담보 인정 불가**")
                        st.markdown(generate_rejection_opinion(violations, data, True))
                    elif warnings:
                        st.warning("⚠️ **조건부 담보 인정**")
                        st.markdown(generate_conditional_opinion(warnings, data, True))
                    else:
                        st.success("✅ **담보 인정 가능**")
                        st.markdown(generate_approval_opinion(data, True))
                    
                    if data_source:
                        st.caption(f"📊 데이터: {data_source}")
                    
                except Exception as e:
                    st.error(f"❌ 처리 오류: {str(e)}")
    
    # === 해외주식 ===
    else:
        st.markdown("## 🌎 해외주식 심사")
        
        with st.spinner("데이터 수집 중..."):
            data_source = None
            stock_data = None
            
            # 1차: yfinance
            try:
                stock = yf.Ticker(ticker.upper())
                info = stock.info
                if info and len(info) > 5 and info.get('regularMarketPrice'):
                    hist = stock.history(period="1y")
                    data_source = "Yahoo Finance"
                    stock_data = {
                        'name': info.get('longName', info.get('shortName', ticker.upper())),
                        'exchange': info.get('exchange', 'N/A'),
                        'price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
                        'quote_type': info.get('quoteType', ''),
                        'mcap_value': info.get('totalAssets', 0) if info.get('quoteType') == 'ETF' else info.get('marketCap', 0),
                        'hist': hist
                    }
            except:
                st.warning("⚠️ Yahoo Finance 실패 - 백업 시도...")
                time.sleep(1)
            
            # 2차: FinanceDataReader
            if not stock_data:
                try:
                    df_price = fdr.DataReader(ticker.upper(), '2024-01-01')
                    if not df_price.empty:
                        data_source = "FinanceDataReader"
                        stock_data = {
                            'name': ticker.upper(),
                            'exchange': 'Unknown',
                            'price': df_price['Close'].iloc[-1],
                            'quote_type': '',
                            'mcap_value': 0,
                            'hist': df_price
                        }
                        st.info("ℹ️ 백업 데이터 소스 사용")
                except:
                    pass
            
            if not stock_data:
                st.error(f"❌ {ticker} 데이터를 가져올 수 없습니다.")
            else:
                try:
                    name = stock_data['name']
                    exchange_raw = stock_data['exchange']
                    price = stock_data['price']
                    quote_type = stock_data['quote_type']
                    mcap_value = stock_data['mcap_value']
                    hist = stock_data['hist']
                    
                    stock_type = "ETF" if quote_type == 'ETF' else "주식"
                    mcap_label = "AUM" if quote_type == 'ETF' else "시총"
                    mcap = mcap_value / 1e9 if mcap_value else 0
                    
                    exchange_map = {'NYQ': 'NYSE', 'NMS': 'NASDAQ', 'NGM': 'NASDAQ', 'NAS': 'NASDAQ', 'PCX': 'NYSE Arca', 'NYSEARCA': 'NYSE Arca'}
                    exchange = exchange_map.get(exchange_raw, exchange_raw)
                    
                    if not hist.empty:
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100 if low > 0 else 0
                    else:
                        vol = 0
                    
                    st.markdown("### 📌 기본 정보")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("종목명", name[:15])
                    col2.metric("거래소", exchange if exchange != "Unknown" else "-")
                    col3.metric("가격", f"${price:.2f}")
                    col4.metric(mcap_label, f"${mcap:.1f}B" if mcap > 0 else "-")
                    
                    st.markdown("---")
                    
                    violations = []
                    warnings = []
                    
                    if exchange not in ["Unknown", "N/A"]:
                        allowed = ["NYSE", "NASDAQ", "NYSE Arca"]
                        if exchange not in allowed:
                            violations.append(f"비허용 거래소: {exchange}")
                        if "OTC" in exchange.upper():
                            violations.append("OTC 장외시장")
                    
                    if quote_type not in ["ETF", ""] and quote_type in ["MLP", "ETP"]:
                        violations.append("PTP 구조")
                    
                    if mcap > 0 and mcap < 1:
                        warnings.append(f"소형주 (${mcap:.2f}B)")
                    
                    if vol >= 200:
                        warnings.append(f"높은 변동성 {vol:.0f}%")
                    
                    if data_source == "FinanceDataReader":
                        warnings.append("일부 정보 제한")
                    
                    st.markdown("---")
                    
                    data_us = {'market_cap': mcap, 'exchange': exchange, 'type': stock_type, 'price': price, 'volatility': vol}
                    
                    if violations:
                        st.error("⛔ **담보 인정 불가**")
                        st.markdown(generate_rejection_opinion(violations, data_us, False))
                    elif warnings:
                        st.warning("⚠️ **조건부 담보 인정**")
                        st.markdown(generate_conditional_opinion(warnings, data_us, False))
                    else:
                        st.success("✅ **담보 인정 가능**")
                        st.markdown(generate_approval_opinion(data_us, False))
                    
                    if data_source:
                        st.caption(f"📊 데이터: {data_source}")
                    
                except Exception as e:
                    st.error(f"❌ 처리 오류: {str(e)}")

elif search_button and not ticker:
    st.error("❌ 종목코드를 입력하세요")

st.markdown("---")
st.caption("ⓒ 2026 Pind | v5.1")
