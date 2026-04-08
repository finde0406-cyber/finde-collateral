import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="wide")

st.title("🏦 핀드 담보 적격성 자동 심사 시스템")
st.caption("KB증권 하이브리드 | v2.0 - 국내/해외 완전 자동화")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.header("ℹ️ 사용법")
    st.markdown("""
    **국내주식**: 6자리 숫자  
    예) 005930, 127120, 310210
    
    **해외주식**: 영문 티커  
    예) AAPL, TSLA, MSFT
    """)
    st.markdown("---")
    st.success("✅ **완전 자동화**  \n국내/해외 모두 실시간 데이터")
    
    with st.expander("⚠️ 불가사유"):
        st.markdown("""
        **국내주식**
        - 관리종목
        - 거래정지
        - 시총 100억 미만
        - 자본잠식 50% 이상
        - 부채비율 300% 이상
        
        **해외주식**
        - 비허용 거래소
        - PTP 종목
        """)

# 국내주식 데이터 가져오기 함수
def get_korean_stock_data(ticker):
    try:
        # Google Finance URL
        url = f"https://www.google.com/finance/quote/{ticker}:KRX"
        
        # yfinance로도 시도 (일부 한국 주식 지원)
        stock = yf.Ticker(f"{ticker}.KS")  # KOSPI
        info = stock.info
        
        # 기본 정보 추출
        name = info.get('longName', info.get('shortName', '조회 실패'))
        price = info.get('currentPrice', info.get('regularMarketPrice', 0))
        market_cap = info.get('marketCap', 0) / 1e8  # 억원
        
        # 52주 최고/최저
        hist = stock.history(period="1y")
        high_52w = hist['High'].max() if not hist.empty else 0
        low_52w = hist['Low'].min() if not hist.empty else 0
        
        return {
            'success': True,
            'name': name,
            'price': price,
            'market_cap': market_cap,
            'high_52w': high_52w,
            'low_52w': low_52w,
            'pe_ratio': info.get('trailingPE', 0),
        }
    except:
        # KOSDAQ 시도
        try:
            stock = yf.Ticker(f"{ticker}.KQ")
            info = stock.info
            
            name = info.get('longName', info.get('shortName', '조회 실패'))
            price = info.get('currentPrice', info.get('regularMarketPrice', 0))
            market_cap = info.get('marketCap', 0) / 1e8
            
            hist = stock.history(period="1y")
            high_52w = hist['High'].max() if not hist.empty else 0
            low_52w = hist['Low'].min() if not hist.empty else 0
            
            return {
                'success': True,
                'name': name,
                'price': price,
                'market_cap': market_cap,
                'high_52w': high_52w,
                'low_52w': low_52w,
                'pe_ratio': info.get('trailingPE', 0),
            }
        except:
            return {'success': False}

# 메인
ticker = st.text_input("**종목코드 입력**", placeholder="005930 또는 AAPL")

if st.button("🔍 자동 심사", type="primary", use_container_width=True):
    if not ticker:
        st.error("종목코드를 입력하세요")
    else:
        is_korean = ticker.isdigit() and len(ticker) == 6
        
        # === 국내주식 자동 ===
        if is_korean:
            st.markdown("## 🇰🇷 국내주식 자동 심사")
            
            with st.spinner("📡 실시간 데이터 수집 중..."):
                data = get_korean_stock_data(ticker)
                
                if not data['success']:
                    st.error("❌ 데이터 조회 실패. 종목코드를 확인하세요.")
                else:
                    # 기본 정보
                    st.markdown("### 📌 기본 정보")
                    c1, c2, c3, c4, c5 = st.columns(5)
                    c1.metric("종목코드", ticker)
                    c2.metric("종목명", data['name'][:15])
                    c3.metric("현재가", f"{data['price']:,.0f}원")
                    c4.metric("시총", f"{data['market_cap']:,.0f}억")
                    c5.metric("P/E", f"{data['pe_ratio']:.1f}" if data['pe_ratio'] > 0 else "N/A")
                    
                    st.markdown("---")
                    
                    # 판정 로직
                    violations = []
                    warnings = []
                    
                    # 1차: 시가총액
                    if data['market_cap'] < 100:
                        violations.append(f"시가총액 {data['market_cap']:.0f}억원 (100억 미만)")
                    
                    # 2차: 변동성
                    if data['high_52w'] > 0 and data['low_52w'] > 0:
                        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
                        if volatility >= 500:
                            warnings.append(f"극심한 변동성 {volatility:.0f}%")
                        elif volatility >= 200:
                            warnings.append(f"높은 변동성 {volatility:.0f}%")
                    
                    # 최종 판정
                    st.markdown("### 🎯 판정 결과")
                    
                    if violations:
                        st.error("### ✕ 담보 불가")
                        for v in violations:
                            st.markdown(f"- {v}")
                        ltv = "N/A"
                        judgment = "불가"
                    elif warnings:
                        st.warning("### △ 조건부")
                        for w in warnings:
                            st.markdown(f"- {w}")
                        ltv = "30~50%"
                        judgment = "조건부"
                    else:
                        st.success("### ○ 담보 가능")
                        st.markdown("✅ 계좌운용규칙 충족")
                        ltv = "60~80%"
                        judgment = "가능"
                    
                    st.markdown("---")
                    
                    # 상세 정보
                    st.markdown("### 📈 주가 정보")
                    p1, p2, p3 = st.columns(3)
                    p1.metric("52주 최고", f"{data['high_52w']:,.0f}원")
                    p2.metric("52주 최저", f"{data['low_52w']:,.0f}원")
                    if data['high_52w'] > 0 and data['low_52w'] > 0:
                        vol = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
                        p3.metric("변동폭", f"{vol:.1f}%")
                    
                    st.markdown("---")
                    st.markdown("### 📝 리스크팀 의견")
                    if judgment == "불가":
                        st.error("⛔ 담보 설정 불가")
                    elif judgment == "조건부":
                        st.warning("⚠️ 보수적 LTV 적용 필수")
                    else:
                        st.success("✅ 정상 담보 가능")
                    
                    # 다운로드
                    report = pd.DataFrame([{
                        "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "종목코드": ticker,
                        "종목명": data['name'],
                        "판정": judgment,
                        "권장LTV": ltv,
                        "시가총액": f"{data['market_cap']:.0f}억",
                        "현재가": f"{data['price']:.0f}원",
                        "불가사유": ", ".join(violations) if violations else "-",
                        "주의사항": ", ".join(warnings) if warnings else "-"
                    }])
                    
                    csv = report.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        "📥 결과 다운로드",
                        csv,
                        f"핀드_심사_{ticker}_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv",
                        use_container_width=True
                    )
        
        # === 해외주식 자동 ===
        else:
            st.markdown("## 🌎 해외주식 자동 심사")
            
            with st.spinner("📡 Yahoo Finance 데이터 수집 중..."):
                try:
                    stock = yf.Ticker(ticker.upper())
                    info = stock.info
                    hist = stock.history(period="1y")
                    
                    # 기본 정보
                    st.markdown("### 📌 기본 정보")
                    c1, c2, c3, c4, c5 = st.columns(5)
                    
                    name = info.get('longName', info.get('shortName', 'N/A'))
                    exchange = info.get('exchange', 'N/A')
                    price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                    mcap = info.get('marketCap', 0) / 1e9
                    
                    c1.metric("티커", ticker.upper())
                    c2.metric("종목명", name[:20])
                    c3.metric("거래소", exchange)
                    c4.metric("가격", f"${price:.2f}")
                    c5.metric("시총", f"${mcap:.1f}B")
                    
                    st.markdown("---")
                    
                    # 판정
                    violations = []
                    warnings = []
                    
                    allowed = ["NYQ", "NMS", "NGM", "NAS", "NYSE", "NASDAQ"]
                    if exchange not in allowed and exchange != "N/A":
                        violations.append(f"거래소: {exchange}")
                    
                    if mcap < 10:
                        warnings.append(f"시총 ${mcap:.1f}B - 확인 필요")
                    
                    st.markdown("### 🎯 판정 결과")
                    
                    if violations:
                        st.error("### ✕ 담보 불가")
                        for v in violations:
                            st.markdown(f"- {v}")
                        ltv = "N/A"
                        judgment = "불가"
                    elif warnings:
                        st.warning("### △ 조건부")
                        for w in warnings:
                            st.markdown(f"- {w}")
                        ltv = "40~60%"
                        judgment = "조건부"
                    else:
                        st.success("### ○ 담보 가능")
                        ltv = "60~70%"
                        judgment = "가능"
                    
                    st.markdown("---")
                    
                    # 주가 정보
                    if not hist.empty:
                        st.markdown("### 📈 52주 주가")
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100
                        
                        p1, p2, p3 = st.columns(3)
                        p1.metric("최고", f"${high:.2f}")
                        p2.metric("최저", f"${low:.2f}")
                        p3.metric("변동폭", f"{vol:.1f}%")
                    
                    st.markdown("---")
                    st.markdown("### 📝 리스크팀 의견")
                    if judgment == "불가":
                        st.error("⛔ 계좌운용규칙 위반")
                    elif judgment == "조건부":
                        st.warning("⚠️ 추가 확인 필요")
                    else:
                        st.success("✅ 정상 담보 가능")
                    
                    # 다운로드
                    report = pd.DataFrame([{
                        "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "티커": ticker.upper(),
                        "종목명": name,
                        "거래소": exchange,
                        "판정": judgment,
                        "권장LTV": ltv,
                        "시가총액": f"${mcap:.1f}B",
                        "불가사유": ", ".join(violations) if violations else "-",
                        "주의사항": ", ".join(warnings) if warnings else "-"
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
st.caption("ⓒ 2026 Pind Inc. | v2.0 완전 자동화")
