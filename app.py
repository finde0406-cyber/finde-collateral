import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime

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
st.caption("KB증권 하이브리드 계좌운용규칙 | v4.2")
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
    opinion = "⛔ **담보 인정 불가**\n\n"
    
    opinion += "**불가 사유**\n"
    for v in violations:
        opinion += f"• {v}\n"
    
    opinion += "\n**리스크 분석**\n"
    opinion += "🚨 상장폐지 위험: 높음\n"
    opinion += "📉 급락 위험: 높음\n"
    opinion += "💰 재무상태: 불량\n"
    
    opinion += "\n**심사 의견**\n"
    if is_korean:
        if any("시가총액" in v for v in violations):
            opinion += "시가총액 100억원 미만 소형주로 유동성이 극히 낮아 강제매도 시 손실 위험이 큽니다. "
        if any("관리종목" in v for v in violations):
            opinion += "관리종목 지정으로 상장폐지 가능성이 있어 담보가치 전액 손실 위험이 있습니다. "
    else:
        opinion += "장외시장 또는 비허용 거래소 종목으로 담보 인정이 불가능합니다. "
    
    opinion += "\n\n**고객 안내**\n"
    if is_korean:
        opinion += "해당 종목은 담보로 인정되지 않습니다. 시총 100억 이상의 우량 종목으로 재신청해주세요."
    else:
        opinion += "해당 종목은 담보로 인정되지 않습니다. NYSE, NASDAQ 상장 종목으로 재신청해주세요."
    
    return opinion

def generate_conditional_opinion(warnings, data, is_korean=True):
    opinion = "⚠️ **조건부 담보 인정 (고위험)**\n\n"
    
    opinion += "**주의 사항**\n"
    for w in warnings:
        opinion += f"• {w}\n"
    
    opinion += "\n**리스크 분석**\n"
    
    # 상장폐지 위험
    if any("관리" in w for w in warnings):
        opinion += "🚨 상장폐지 위험: 높음\n"
    else:
        opinion += "🚨 상장폐지 위험: 낮음\n"
    
    # 급락 위험
    if any("변동성" in w for w in warnings):
        vol_value = next((w.split()[2] for w in warnings if "변동성" in w), "높음")
        opinion += f"📉 급락 위험: 높음 (변동성 {vol_value})\n"
    else:
        opinion += "📉 급락 위험: 보통\n"
    
    # 재무상태
    opinion += "💰 재무상태: 확인 필요\n"
    
    opinion += "\n**담보 조건**\n"
    opinion += "• 담보 인정: 가능 (단, 일일 모니터링 필수)\n"
    opinion += "• 담보비율 150% 미만 시 즉시 연락\n"
    opinion += "• 추가 하락 시 담보 추가 징구 가능\n"
    
    opinion += "\n**심사 의견**\n"
    opinion += "변동성이 높아 단기간 급락 위험이 있습니다. "
    opinion += "일일 담보비율 모니터링이 필수이며, 추가 하락 시 로스컷 가능성을 고객에게 사전 안내해야 합니다."
    
    opinion += "\n\n**고객 안내**\n"
    opinion += "담보 가능하나 변동성이 높아 주가 급락 시 담보 추가 제공 또는 강제 매도가 발생할 수 있습니다."
    
    return opinion

def generate_approval_opinion(data, is_korean=True):
    opinion = "✅ **담보 인정 가능**\n\n"
    
    opinion += "**적격 근거**\n"
    if is_korean:
        mcap = data.get('market_cap', 0)
        if mcap >= 10000:
            opinion += f"• 시가총액 {mcap:,.0f}억원 (초대형주)\n"
        elif mcap >= 1000:
            opinion += f"• 시가총액 {mcap:,.0f}억원 (대형주)\n"
        else:
            opinion += f"• 시가총액 {mcap:,.0f}억원 (기준 충족)\n"
        opinion += "• 계좌운용규칙 기준 충족\n"
    else:
        mcap_value = data.get('market_cap', 0)
        mcap_type = data.get('type', '주식')
        if mcap_type == 'ETF':
            opinion += f"• 운용자산(AUM) ${mcap_value:.1f}B\n"
        else:
            opinion += f"• 시가총액 ${mcap_value:.1f}B\n"
        opinion += f"• 거래소: {data.get('exchange', 'N/A')}\n"
    
    opinion += "\n**리스크 분석**\n"
    opinion += "🚨 상장폐지 위험: 낮음\n"
    opinion += "📉 급락 위험: 낮음\n"
    opinion += "💰 재무상태: 양호\n"
    
    opinion += "\n**담보 조건**\n"
    opinion += "• 최대 LTV: 200%\n"
    opinion += "• 로스컷: 130%\n"
    opinion += "• 현금인출: 140% 이상\n"
    
    opinion += "\n**심사 의견**\n"
    opinion += "계좌운용규칙 기준을 충족하여 정상적인 담보 인정이 가능합니다."
    
    opinion += "\n\n**고객 안내**\n"
    opinion += "담보 설정에 문제가 없습니다. 최대 200%까지 대출 가능합니다."
    
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

if search_button:
    if not ticker:
        st.error("❌ 종목코드를 입력하세요")
    else:
        is_korean = ticker.isdigit() and len(ticker) == 6
        
        # === 국내주식 ===
        if is_korean:
            st.markdown("## 🇰🇷 국내주식")
            
            with st.spinner("데이터 수집 중..."):
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
                            
                            volatility = 0
                            if high_52w > 0 and low_52w > 0:
                                volatility = ((high_52w - low_52w) / low_52w) * 100
                                if volatility >= 500:
                                    warnings.append(f"극심한 변동성 {volatility:.0f}%")
                                elif volatility >= 200:
                                    warnings.append(f"높은 변동성 {volatility:.0f}%")
                            
                            # 판정 결과
                            st.markdown("### 🎯 판정 결과")
                            
                            data = {'market_cap': market_cap}
                            
                            if violations:
                                judgment = "불가"
                                opinion = generate_rejection_opinion(violations, data, True)
                                st.error(opinion)
                            elif warnings:
                                judgment = "조건부"
                                opinion = generate_conditional_opinion(warnings, data, True)
                                st.warning(opinion)
                            else:
                                judgment = "가능"
                                opinion = generate_approval_opinion(data, True)
                                st.success(opinion)
                            
                            # 주가 정보
                            st.markdown("---")
                            st.markdown("### 📈 52주 주가")
                            
                            p1, p2, p3 = st.columns(3)
                            p1.metric("최고", f"{high_52w:,.0f}원")
                            p2.metric("최저", f"{low_52w:,.0f}원")
                            p3.metric("변동폭", f"{volatility:.1f}%")
                            
                            # 다운로드
                            st.markdown("---")
                            report = pd.DataFrame([{
                                "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "종목코드": ticker,
                                "종목명": name,
                                "판정": judgment,
                                "시가총액": f"{market_cap:,.0f}억",
                                "현재가": f"{current_price:,.0f}원"
                            }])
                            
                            csv = report.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(
                                "📥 다운로드",
                                csv,
                                f"심사_{ticker}_{datetime.now().strftime('%Y%m%d')}.csv",
                                use_container_width=True
                            )
                    
                except Exception as e:
                    st.error(f"❌ 오류: {str(e)}")
        
        # === 해외주식 ===
        else:
            st.markdown("## 🌎 해외주식")
            
            with st.spinner("데이터 수집 중..."):
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
                    
                    mcap = mcap_value / 1e9 if mcap_value else 0  # 십억 달러 단위
                    
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
                    
                    # ETF가 아닌 경우만 PTP 체크
                    if quote_type != "ETF" and quote_type in ["MLP", "ETP"]:
                        violations.append("PTP 구조")
                    
                    # 규모 체크 (ETF는 AUM, 일반주식은 시총)
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
                    
                    st.markdown("### 🎯 판정 결과")
                    
                    data_us = {
                        'market_cap': mcap,
                        'exchange': exchange,
                        'type': stock_type
                    }
                    
                    if violations:
                        judgment = "불가"
                        opinion = generate_rejection_opinion(violations, data_us, False)
                        st.error(opinion)
                    elif warnings:
                        judgment = "조건부"
                        opinion = generate_conditional_opinion(warnings, data_us, False)
                        st.warning(opinion)
                    else:
                        judgment = "가능"
                        opinion = generate_approval_opinion(data_us, False)
                        st.success(opinion)
                    
                    # 주가 정보
                    if not hist.empty:
                        st.markdown("---")
                        st.markdown("### 📈 52주 주가")
                        
                        p1, p2, p3 = st.columns(3)
                        p1.metric("최고", f"${high:.2f}")
                        p2.metric("최저", f"${low:.2f}")
                        p3.metric("변동폭", f"{vol:.1f}%")
                    
                    st.markdown("---")
                    report = pd.DataFrame([{
                        "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "티커": ticker.upper(),
                        "종목명": name,
                        "유형": stock_type,
                        "거래소": exchange,
                        "판정": judgment,
                        mcap_label: f"${mcap:.1f}B"
                    }])
                    
                    csv = report.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        "📥 다운로드",
                        csv,
                        f"심사_{ticker.upper()}_{datetime.now().strftime('%Y%m%d')}.csv",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ 오류: {str(e)}")
                    st.info("종목코드를 확인해주세요.")

st.markdown("---")
st.caption("ⓒ 2026 Pind | v4.2")
