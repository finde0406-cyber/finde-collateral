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
    .risk-box {
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        border-left: 4px solid;
    }
    .risk-critical {border-left-color: #ff4b4b; background-color: #fff5f5;}
    .risk-warning {border-left-color: #ffa500; background-color: #fff8e1;}
    .risk-safe {border-left-color: #00c853; background-color: #f1f8f4;}
</style>
""", unsafe_allow_html=True)

st.title("🏦 핀드 담보 심사")
st.caption("KB증권 하이브리드 계좌운용규칙 | v5.0")
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
    
    # 정량 지표
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
    
    opinion += "\n"
    
    # 불가 사유
    opinion += "### ❌ 불가 사유\n"
    for v in violations:
        opinion += f"• {v}\n"
    
    opinion += "\n"
    
    # 위험 분석
    opinion += "### 🚨 위험 분석\n"
    opinion += "| 항목 | 평가 |\n"
    opinion += "|------|------|\n"
    opinion += "| 상장폐지 위험 | 🔴 **높음** |\n"
    opinion += "| 급락 위험 | 🔴 **높음** |\n"
    opinion += "| 유동성 위험 | 🔴 **높음** |\n"
    
    opinion += "\n"
    
    # 심사 의견
    opinion += "### 💼 심사 의견\n"
    if is_korean:
        if any("시가총액" in v for v in violations):
            opinion += "**시가총액 100억원 미만**으로 유동성이 극히 낮습니다. 로스컷 상황 시 호가창이 얇아 슬리피지(체결가격 불리)가 크게 발생할 수 있으며, 최악의 경우 매도 자체가 불가능할 수 있습니다.\n\n"
        
        if any("관리종목" in v for v in violations):
            opinion += "**관리종목 지정**으로 상장폐지 심사 대상입니다. 상장폐지 시 담보가치가 전액 소멸되어 원금 전액 손실이 발생합니다.\n\n"
    else:
        if any("OTC" in v or "거래소" in v for v in violations):
            opinion += "**장외시장(OTC)** 또는 **비허용 거래소** 종목입니다. 유동성이 낮고 가격 조작 위험이 있어 담보로 인정할 수 없습니다.\n\n"
    
    opinion += "**결론**: 담보 인정 불가\n"
    
    opinion += "\n"
    
    # 고객 안내
    opinion += "### 📢 고객 안내\n"
    if is_korean:
        opinion += "> 해당 종목은 당사 리스크 기준에 부적합하여 담보로 인정되지 않습니다. **시가총액 100억원 이상**의 우량 종목으로 재신청 부탁드립니다."
    else:
        opinion += "> 해당 종목은 당사 리스크 기준에 부적합하여 담보로 인정되지 않습니다. **NYSE, NASDAQ 상장 종목**으로 재신청 부탁드립니다."
    
    return opinion

def generate_conditional_opinion(warnings, data, is_korean=True):
    opinion = ""
    
    # 정량 지표
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
    
    # 변동성 정보
    volatility = data.get('volatility', 0)
    if volatility > 0:
        opinion += f"• **52주 변동폭**: {volatility:.1f}%\n"
    
    opinion += "\n"
    
    # 주의 사항
    opinion += "### ⚠️ 주의 사항\n"
    for w in warnings:
        opinion += f"• {w}\n"
    
    opinion += "\n"
    
    # 위험 분석
    opinion += "### 🔍 위험 분석\n"
    opinion += "| 항목 | 평가 | 비고 |\n"
    opinion += "|------|------|------|\n"
    
    # 상장폐지 위험
    if any("관리" in w for w in warnings):
        opinion += "| 상장폐지 위험 | 🔴 **높음** | 관리종목 지정 |\n"
    else:
        opinion += "| 상장폐지 위험 | 🟢 낮음 | 정상 종목 |\n"
    
    # 급락 위험
    if volatility >= 500:
        opinion += f"| 급락 위험 | 🔴 **매우 높음** | 변동성 {volatility:.0f}% |\n"
    elif volatility >= 200:
        opinion += f"| 급락 위험 | 🟠 **높음** | 변동성 {volatility:.0f}% |\n"
    else:
        opinion += "| 급락 위험 | 🟡 보통 | - |\n"
    
    # 유동성
    opinion += "| 유동성 | 🟡 보통 | 시총 기준 충족 |\n"
    
    opinion += "\n"
    
    # 담보 조건
    opinion += "### 📋 담보 조건\n"
    opinion += "```\n"
    opinion += "✓ 담보 인정: 가능 (고위험 등급)\n"
    opinion += "✓ 최대 LTV: 200%\n"
    opinion += "✓ 로스컷: 130%\n"
    opinion += "✓ 일일 모니터링: 필수\n"
    opinion += "```\n"
    
    opinion += "\n"
    
    # 심사 의견
    opinion += "### 💼 심사 의견\n"
    
    if volatility >= 500:
        opinion += f"**극심한 변동성({volatility:.0f}%)**으로 단기간 급락 위험이 매우 높습니다. "
    elif volatility >= 200:
        opinion += f"**높은 변동성({volatility:.0f}%)**으로 단기간 급락 위험이 있습니다. "
    
    opinion += "담보비율이 로스컷 기준(130%)에 근접하거나 도달할 경우 **자동 반대매매**가 즉시 실행됩니다.\n\n"
    
    opinion += "변동성이 큰 종목 특성상 하루에도 10-20% 등락이 가능하므로, 고객에게 **로스컷 위험**을 명확히 안내해야 합니다.\n\n"
    
    opinion += "**결론**: 조건부 담보 인정 (일일 모니터링 필수)\n"
    
    opinion += "\n"
    
    # 고객 안내
    opinion += "### 📢 고객 안내\n"
    opinion += "> 담보 설정은 가능하나 **변동성이 매우 높은 종목**입니다. 주가 급락 시 **자동 반대매매(로스컷)**가 발생할 수 있으며, 이 경우 고객님의 동의 없이 강제 매도됩니다. 신중한 투자 판단 부탁드립니다."
    
    return opinion

def generate_approval_opinion(data, is_korean=True):
    opinion = ""
    
    # 정량 지표
    opinion += "### 📊 정량 지표\n"
    if is_korean:
        mcap = data.get('market_cap', 0)
        opinion += f"• **시가총액**: {mcap:,.0f}억원\n"
        if mcap >= 10000:
            opinion += f"• **등급**: 초대형주 (10조 이상)\n"
        elif mcap >= 1000:
            opinion += f"• **등급**: 대형주 (1조 이상)\n"
        else:
            opinion += f"• **등급**: 중형주\n"
        opinion += f"• **시장**: {data.get('market', 'N/A')}\n"
        opinion += f"• **현재가**: {data.get('price', 0):,.0f}원\n"
    else:
        mcap = data.get('market_cap', 0)
        stock_type = data.get('type', '주식')
        if stock_type == 'ETF':
            opinion += f"• **운용자산(AUM)**: ${mcap:.1f}B\n"
            opinion += f"• **유형**: ETF\n"
        else:
            opinion += f"• **시가총액**: ${mcap:.1f}B\n"
            opinion += f"• **유형**: 주식\n"
        opinion += f"• **거래소**: {data.get('exchange', 'N/A')}\n"
        opinion += f"• **현재가**: ${data.get('price', 0):.2f}\n"
    
    volatility = data.get('volatility', 0)
    if volatility > 0:
        opinion += f"• **52주 변동폭**: {volatility:.1f}%\n"
    
    opinion += "\n"
    
    # 적격 근거
    opinion += "### ✅ 적격 근거\n"
    if is_korean:
        opinion += "• 시가총액 100억원 이상 기준 충족\n"
        opinion += "• 관리종목 미지정\n"
        opinion += "• 정상 거래 중\n"
    else:
        opinion += "• 주요 거래소 상장 (NYSE/NASDAQ/NYSE Arca)\n"
        opinion += "• 정상 거래 중\n"
        if data.get('type') == 'ETF':
            opinion += "• 충분한 운용자산 (AUM)\n"
        else:
            opinion += "• 적정 시가총액\n"
    
    opinion += "\n"
    
    # 위험 분석
    opinion += "### 🔍 위험 분석\n"
    opinion += "| 항목 | 평가 | 비고 |\n"
    opinion += "|------|------|------|\n"
    opinion += "| 상장폐지 위험 | 🟢 낮음 | 정상 종목 |\n"
    
    if volatility >= 100:
        opinion += f"| 급락 위험 | 🟡 보통 | 변동성 {volatility:.0f}% |\n"
    else:
        opinion += "| 급락 위험 | 🟢 낮음 | 안정적 |\n"
    
    opinion += "| 유동성 | 🟢 우수 | 충분한 거래량 |\n"
    
    opinion += "\n"
    
    # 담보 조건
    opinion += "### 📋 담보 조건\n"
    opinion += "```\n"
    opinion += "✓ 담보 인정: 가능 (정상 등급)\n"
    opinion += "✓ 최대 LTV: 200%\n"
    opinion += "✓ 로스컷: 130%\n"
    opinion += "✓ 현금인출: 140% 이상\n"
    opinion += "```\n"
    
    opinion += "\n"
    
    # 심사 의견
    opinion += "### 💼 심사 의견\n"
    opinion += "계좌운용규칙의 모든 기준을 충족하는 우량 종목입니다. "
    
    if is_korean:
        mcap = data.get('market_cap', 0)
        if mcap >= 10000:
            opinion += "초대형주로 유동성이 풍부하고 가격 안정성이 높아 담보가치가 우수합니다.\n\n"
        elif mcap >= 1000:
            opinion += "대형주로 적정 유동성을 보유하고 있어 담보로 적합합니다.\n\n"
        else:
            opinion += "담보 설정에 문제가 없습니다.\n\n"
    else:
        opinion += "주요 거래소 상장 종목으로 담보 설정에 문제가 없습니다.\n\n"
    
    opinion += "**결론**: 정상 담보 인정\n"
    
    opinion += "\n"
    
    # 고객 안내
    opinion += "### 📢 고객 안내\n"
    opinion += "> 담보 설정에 문제가 없습니다. 계좌평가금액의 **최대 200%**까지 대출 가능하며, 담보비율 **130% 도달 시 자동 반대매매**가 실행됩니다."
    
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
            st.markdown("## 🇰🇷 국내주식 심사")
            
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
                            st.markdown("---")
                            
                            data = {
                                'market_cap': market_cap,
                                'market': market,
                                'price': current_price,
                                'volatility': volatility
                            }
                            
                            if violations:
                                st.error("⛔ **담보 인정 불가**")
                                judgment = "불가"
                                opinion = generate_rejection_opinion(violations, data, True)
                                st.markdown(opinion)
                            elif warnings:
                                st.warning("⚠️ **조건부 담보 인정 (고위험)**")
                                judgment = "조건부"
                                opinion = generate_conditional_opinion(warnings, data, True)
                                st.markdown(opinion)
                            else:
                                st.success("✅ **담보 인정 가능**")
                                judgment = "가능"
                                opinion = generate_approval_opinion(data, True)
                                st.markdown(opinion)
                            
                            # 다운로드
                            st.markdown("---")
                            report = pd.DataFrame([{
                                "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "종목코드": ticker,
                                "종목명": name,
                                "판정": judgment,
                                "시가총액": f"{market_cap:,.0f}억",
                                "현재가": f"{current_price:,.0f}원",
                                "변동성": f"{volatility:.1f}%"
                            }])
                            
                            csv = report.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(
                                "📥 심사결과 다운로드",
                                csv,
                                f"심사_{ticker}_{datetime.now().strftime('%Y%m%d')}.csv",
                                use_container_width=True
                            )
                    
                except Exception as e:
                    st.error(f"❌ 오류: {str(e)}")
        
        # === 해외주식 ===
        else:
            st.markdown("## 🌎 해외주식 심사")
            
            with st.spinner("데이터 수집 중..."):
                try:
                    stock = yf.Ticker(ticker.upper())
                    info = stock.info
                    hist = stock.history(period="1y")
                    
                    name = info.get('longName', info.get('shortName', 'N/A'))
                    exchange_raw = info.get('exchange', 'N/A')
                    price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                    
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
                    
                    # 변동성
                    if not hist.empty:
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100 if low > 0 else 0
                    else:
                        high = 0
                        low = 0
                        vol = 0
                    
                    # 기본 정보
                    st.markdown("### 📌 기본 정보")
                    
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
                    
                    if vol >= 200 and not violations:
                        warnings.append(f"높은 변동성 {vol:.0f}%")
                    
                    # 판정 결과
                    st.markdown("---")
                    
                    data_us = {
                        'market_cap': mcap,
                        'exchange': exchange,
                        'type': stock_type,
                        'price': price,
                        'volatility': vol
                    }
                    
                    if violations:
                        st.error("⛔ **담보 인정 불가**")
                        judgment = "불가"
                        opinion = generate_rejection_opinion(violations, data_us, False)
                        st.markdown(opinion)
                    elif warnings:
                        st.warning("⚠️ **조건부 담보 인정 (고위험)**")
                        judgment = "조건부"
                        opinion = generate_conditional_opinion(warnings, data_us, False)
                        st.markdown(opinion)
                    else:
                        st.success("✅ **담보 인정 가능**")
                        judgment = "가능"
                        opinion = generate_approval_opinion(data_us, False)
                        st.markdown(opinion)
                    
                    # 다운로드
                    st.markdown("---")
                    report = pd.DataFrame([{
                        "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "티커": ticker.upper(),
                        "종목명": name,
                        "유형": stock_type,
                        "거래소": exchange,
                        "판정": judgment,
                        mcap_label: f"${mcap:.1f}B",
                        "변동성": f"{vol:.1f}%"
                    }])
                    
                    csv = report.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        "📥 심사결과 다운로드",
                        csv,
                        f"심사_{ticker.upper()}_{datetime.now().strftime('%Y%m%d')}.csv",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ 오류: {str(e)}")
                    st.info("종목코드를 확인해주세요.")

st.markdown("---")
st.caption("ⓒ 2026 Pind | v5.0 고도화")
