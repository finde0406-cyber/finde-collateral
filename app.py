import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="wide")

st.markdown("""
<style>
    .main > div {padding-top: 2rem;}
    h1 {font-size: 2rem !important; margin-bottom: 0.5rem !important;}
</style>
""", unsafe_allow_html=True)

st.title("🏦 핀드 담보 적격성 자동 심사")
st.caption("KB증권 하이브리드 계좌운용규칙 기준 | v4.0 완전 자동화")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.header("📖 사용 가이드")
    st.markdown("""
    **국내주식**: 6자리 숫자  
    `005930` `127120` `064800`
    
    **해외주식**: 영문 티커  
    `AAPL` `TSLA` `SOXL`
    """)
    st.markdown("---")
    st.success("**완전 자동화**\n국내/해외 모두 자동")
    
    with st.expander("⚠️ 불가사유"):
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
    opinion = "⛔ 담보 설정 불가\n\n"
    opinion += "**[불가 사유]**\n"
    for v in violations:
        opinion += f"• {v}\n"
    opinion += "\n**[위험도 평가]**\n"
    opinion += "재무 건전성: 🔴 위험\n주가 안정성: 🔴 위험\n유동성: 🔴 위험\n"
    opinion += "**종합 평가: 🔴 부적격**\n\n"
    opinion += "**[리스크관리팀 의견]**\n"
    if is_korean:
        if any("시가총액" in v for v in violations):
            opinion += "시가총액 100억원 미만 소형주로 유동성 위험이 높아 담보 설정이 불가능합니다. "
        if any("관리종목" in v for v in violations):
            opinion += "관리종목으로 지정되어 상장폐지 위험이 있습니다. "
    else:
        if any("OTC" in v or "거래소" in v for v in violations):
            opinion += "장외시장 또는 비허용 거래소에서 거래되어 담보 인정이 불가능합니다. "
    opinion += "\n\n**[고객 안내 문구]**\n"
    opinion += '"해당 종목은 당사 계좌운용규칙상 담보로 인정되지 않습니다."'
    return opinion

def generate_conditional_opinion(warnings, data, is_korean=True):
    risk_level = "고위험" if len(warnings) >= 3 else "주의"
    risk_emoji = "🔴" if len(warnings) >= 3 else "🟠"
    max_ltv = "30%" if len(warnings) >= 3 else "40%"
    opinion = f"⚠️ 조건부 담보 가능 ({risk_level})\n\n"
    opinion += "**[주의 사유]**\n"
    for w in warnings:
        opinion += f"• {w}\n"
    opinion += "\n**[위험도 평가]**\n"
    opinion += "재무 건전성: 🟡 보통\n주가 안정성: 🟠 주의\n유동성: 🟡 보통\n"
    opinion += f"**종합 평가: {risk_emoji} {risk_level}**\n\n"
    opinion += "**[담보 설정 조건]**\n"
    opinion += f"1. 최대 대출비율 {max_ltv} 이하\n2. 담보비율 150% 미만 시 즉시 연락\n"
    opinion += "3. 일일 모니터링 대상\n\n"
    opinion += "**[리스크관리팀 의견]**\n"
    opinion += f"보수적 대출비율({max_ltv} 이하) 적용과 정기 모니터링이 필수입니다.\n\n"
    opinion += "**[고객 안내 문구]**\n"
    opinion += f'"담보 가능하나 대출한도는 평가금액의 {max_ltv} 이하를 권장합니다."'
    return opinion

def generate_approval_opinion(data, is_korean=True):
    opinion = "✅ 담보 설정 가능\n\n**[적격 근거]**\n"
    if is_korean:
        mcap = data.get('market_cap', 0)
        if mcap >= 10000:
            opinion += f"✓ 시가총액 {mcap:,.0f}억원 (초대형주)\n"
        elif mcap >= 1000:
            opinion += f"✓ 시가총액 {mcap:,.0f}억원 (대형주)\n"
        else:
            opinion += f"✓ 시가총액 {mcap:,.0f}억원 (기준 충족)\n"
        opinion += "✓ 계좌운용규칙 기준 충족\n"
    else:
        mcap_b = data.get('market_cap', 0)
        opinion += f"✓ 시가총액 ${mcap_b:.1f}B\n"
        opinion += f"✓ 거래소: {data.get('exchange', 'N/A')}\n"
    opinion += "\n**[위험도 평가]**\n"
    opinion += "재무 건전성: 🟢 양호\n주가 안정성: 🟢 안정\n유동성: 🟢 우수\n"
    opinion += "**종합 평가: 🟢 우량**\n\n"
    opinion += "**[담보 설정 조건]**\n"
    opinion += "• 최대 대출비율: 200% 이내\n• 로스컷: 130%\n• 현금인출: 140% 이상\n\n"
    opinion += "**[리스크관리팀 의견]**\n"
    opinion += "계좌운용규칙 기준을 충족하여 정상 담보 설정이 가능합니다.\n\n"
    opinion += "**[고객 안내 문구]**\n"
    opinion += '"담보 설정에 문제가 없습니다. 최대 200%까지 대출 가능합니다."'
    return opinion

# 메인
col1, col2 = st.columns([4, 1])
with col1:
    ticker = st.text_input("종목코드 / 티커", placeholder="예: 005930, AAPL, SOXL")
with col2:
    st.write("")
    search_button = st.button("🔍 심사", type="primary")

if search_button:
    if not ticker:
        st.error("❌ 종목코드를 입력하세요")
    else:
        is_korean = ticker.isdigit() and len(ticker) == 6
        
        # === 국내주식 (완전 자동화) ===
        if is_korean:
            st.markdown("## 🇰🇷 국내주식 자동 심사")
            
            with st.spinner("📡 KRX 데이터 수집 중..."):
                try:
                    # KRX 전체 종목 리스트 가져오기
                    df_krx = fdr.StockListing('KRX')
                    stock_info = df_krx[df_krx['Code'] == ticker]
                    
                    if stock_info.empty:
                        st.error(f"❌ 종목코드 {ticker}를 찾을 수 없습니다.")
                    else:
                        # 기본 정보
                        name = stock_info.iloc[0]['Name']
                        market = stock_info.iloc[0]['Market']
                        sector = stock_info.iloc[0].get('Sector', '-')
                        
                        # 시가총액 (억원 단위)
                        market_cap = stock_info.iloc[0].get('Marcap', 0) / 100000000
                        
                        # 주가 데이터
                        df_price = fdr.DataReader(ticker, '2024-01-01')
                        
                        if df_price.empty:
                            st.error("❌ 주가 데이터를 가져올 수 없습니다.")
                        else:
                            current_price = df_price['Close'].iloc[-1]
                            high_52w = df_price['High'].max()
                            low_52w = df_price['Low'].min()
                            
                            # 기본 정보 표시
                            st.markdown("### 📌 기본 정보")
                            c1, c2, c3, c4, c5 = st.columns(5)
                            c1.metric("종목코드", ticker)
                            c2.metric("종목명", name)
                            c3.metric("시장", market)
                            c4.metric("현재가", f"{current_price:,.0f}원")
                            c5.metric("시총", f"{market_cap:,.0f}억")
                            
                            st.markdown("---")
                            
                            # 판정 로직
                            violations = []
                            warnings = []
                            
                            # 관리종목 체크 (Dept 컬럼이 '관리'면 관리종목)
                            if stock_info.iloc[0].get('Dept', '') == '관리':
                                violations.append("관리종목 지정")
                            
                            # 시가총액
                            if market_cap < 100:
                                violations.append(f"시가총액 {market_cap:,.0f}억원 (기준: 100억 이상)")
                            
                            # 변동성
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
                            st.markdown("### 📈 주가 정보")
                            p1, p2, p3 = st.columns(3)
                            p1.metric("52주 최고", f"{high_52w:,.0f}원")
                            p2.metric("52주 최저", f"{low_52w:,.0f}원")
                            p3.metric("변동폭", f"{volatility:.1f}%")
                            
                            # 다운로드
                            st.markdown("---")
                            report = pd.DataFrame([{
                                "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                "종목코드": ticker,
                                "종목명": name,
                                "시장": market,
                                "판정": judgment,
                                "시가총액": f"{market_cap:,.0f}억",
                                "현재가": f"{current_price:,.0f}원"
                            }])
                            
                            csv = report.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(
                                "📥 결과 다운로드",
                                csv,
                                f"핀드_심사_{ticker}_{datetime.now().strftime('%Y%m%d')}.csv",
                                "text/csv",
                                use_container_width=True
                            )
                    
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")
                    st.info("💡 종목코드를 확인하세요. 예: 005930 (삼성전자)")
        
        # === 해외주식 ===
        else:
            st.markdown("## 🌎 해외주식 자동 심사")
            
            with st.spinner("📡 Yahoo Finance 데이터 수집 중..."):
                try:
                    stock = yf.Ticker(ticker.upper())
                    info = stock.info
                    hist = stock.history(period="1y")
                    
                    st.markdown("### 📌 기본 정보")
                    
                    name = info.get('longName', info.get('shortName', 'N/A'))
                    exchange_raw = info.get('exchange', 'N/A')
                    price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                    mcap = info.get('marketCap', 0) / 1e9
                    
                    exchange_map = {
                        'NYQ': 'NYSE', 'NMS': 'NASDAQ', 'NGM': 'NASDAQ',
                        'NAS': 'NASDAQ', 'PCX': 'NYSE Arca', 'NYSEARCA': 'NYSE Arca'
                    }
                    exchange = exchange_map.get(exchange_raw, exchange_raw)
                    
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("티커", ticker.upper())
                    c2.metric("종목명", name[:20])
                    c3.metric("거래소", exchange)
                    c4.metric("가격", f"${price:.2f}")
                    c5.metric("시총", f"${mcap:.1f}B")
                    
                    st.markdown("---")
                    
                    violations = []
                    warnings = []
                    
                    allowed = ["NYSE", "NASDAQ", "NYSE Arca"]
                    if exchange not in allowed and exchange != "N/A":
                        violations.append(f"비허용 거래소: {exchange}")
                    if "OTC" in exchange.upper():
                        violations.append("OTC 장외시장")
                    
                    quote_type = info.get('quoteType', '')
                    if quote_type in ["MLP", "ETP"]:
                        violations.append("PTP 구조")
                    
                    if mcap < 1 and not violations:
                        warnings.append(f"시총 ${mcap:.2f}B (소형주)")
                    
                    if not hist.empty:
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100 if low > 0 else 0
                        if vol >= 200 and not violations:
                            warnings.append(f"높은 변동성 {vol:.0f}%")
                    
                    st.markdown("### 🎯 판정 결과")
                    
                    data_us = {'market_cap': mcap, 'exchange': exchange}
                    
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
                    
                    if not hist.empty:
                        st.markdown("---")
                        st.markdown("### 📈 주가 정보")
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100 if low > 0 else 0
                        
                        p1, p2, p3 = st.columns(3)
                        p1.metric("52주 최고", f"${high:.2f}")
                        p2.metric("52주 최저", f"${low:.2f}")
                        p3.metric("변동폭", f"{vol:.1f}%")
                    
                    st.markdown("---")
                    report = pd.DataFrame([{
                        "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "티커": ticker.upper(),
                        "종목명": name,
                        "거래소": exchange,
                        "판정": judgment,
                        "시가총액": f"${mcap:.1f}B"
                    }])
                    
                    csv = report.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        "📥 결과 다운로드",
                        csv,
                        f"핀드_심사_{ticker.upper()}_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ 조회 실패: {str(e)}")

st.markdown("---")
st.caption("ⓒ 2026 Pind Inc. | v4.0 완전 자동화")
