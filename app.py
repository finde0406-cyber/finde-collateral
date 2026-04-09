import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="centered")

st.title("🏦 핀드 담보 심사")
st.caption("KB증권 하이브리드 | v5.4")
st.markdown("---")

# 캐싱 함수
@st.cache_data(ttl=3600)
def get_krx_stock(ticker):
    """국내주식 - KRX 우선, yfinance 백업"""
    
    # 1차: FinanceDataReader (KRX)
    try:
        df_krx = fdr.StockListing('KRX')
        stock_info = df_krx[df_krx['Code'] == ticker]
        
        if not stock_info.empty:
            df_price = fdr.DataReader(ticker, '2024-01-01')
            
            return {
                'source': 'KRX',
                'name': stock_info.iloc[0]['Name'],
                'market': stock_info.iloc[0]['Market'],
                'market_cap': stock_info.iloc[0].get('Marcap', 0) / 100000000,
                'dept': stock_info.iloc[0].get('Dept', ''),
                'current_price': df_price['Close'].iloc[-1],
                'high_52w': df_price['High'].max(),
                'low_52w': df_price['Low'].min()
            }
    except Exception as e:
        # KRX 실패 시 계속 진행
        pass
    
    # 2차: yfinance (백업)
    try:
        # KOSPI 시도
        for suffix, market_name in [('.KS', 'KOSPI'), ('.KQ', 'KOSDAQ')]:
            stock = yf.Ticker(f"{ticker}{suffix}")
            info = stock.info
            
            if info and info.get('regularMarketPrice'):
                hist = stock.history(period="1y")
                
                if not hist.empty:
                    mcap_raw = info.get('marketCap', 0)
                    
                    return {
                        'source': 'Yahoo Finance',
                        'name': info.get('shortName', ticker),
                        'market': market_name,
                        'market_cap': mcap_raw / 100000000 if mcap_raw else 0,
                        'dept': '',  # yfinance에는 관리종목 정보 없음
                        'current_price': hist['Close'].iloc[-1],
                        'high_52w': hist['High'].max(),
                        'low_52w': hist['Low'].min(),
                        'warning': '관리종목 여부 수동 확인 필요'
                    }
    except:
        pass
    
    return {'error': 'KRX와 Yahoo Finance 모두 조회 실패'}

@st.cache_data(ttl=3600)
def get_us_stock(ticker):
    """해외주식"""
    try:
        time.sleep(1)
        
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        hist = stock.history(period="1y")
        
        quote_type = info.get('quoteType', '')
        
        if quote_type == 'ETF':
            mcap_value = info.get('totalAssets', 0)
            mcap_label = "AUM"
        else:
            mcap_value = info.get('marketCap', 0)
            mcap_label = "시총"
        
        exchange_map = {
            'NYQ': 'NYSE', 'NMS': 'NASDAQ', 'NGM': 'NASDAQ',
            'NAS': 'NASDAQ', 'PCX': 'NYSE Arca', 'NYSEARCA': 'NYSE Arca'
        }
        
        return {
            'name': info.get('longName', info.get('shortName', ticker.upper())),
            'exchange': exchange_map.get(info.get('exchange', 'N/A'), info.get('exchange', 'N/A')),
            'price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
            'mcap': mcap_value / 1e9 if mcap_value else 0,
            'mcap_label': mcap_label,
            'high_52w': hist['High'].max() if not hist.empty else 0,
            'low_52w': hist['Low'].min() if not hist.empty else 0
        }
    except Exception as e:
        return {'error': str(e)}

# 사이드바
with st.sidebar:
    st.header("📖 가이드")
    st.markdown("**국내**: `005930`  \n**해외**: `AAPL` `SOXL`")
    st.markdown("---")
    
    if st.button("🔄 캐시 초기화"):
        st.cache_data.clear()
        st.success("완료!")

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
                data = get_krx_stock(ticker)
                
                if 'error' in data:
                    st.error(f"❌ 조회 실패")
                    st.warning("⏰ KRX 서버 접근 불가 + Yahoo Finance도 실패")
                    
                    with st.expander("💡 원인 및 해결책"):
                        st.markdown("""
                        **원인**:
                        - KRX 서버가 Streamlit Cloud IP 차단
                        - Yahoo Finance도 일시적 제한
                        
                        **해결책**:
                        1. **30분~1시간 대기** 후 재시도
                        2. 로컬에서 실행 (본인 PC)
                        3. 한국투자증권 API 사용 (장기적)
                        
                        **확인 사항**:
                        - 종목코드 6자리 확인: `005930`
                        - 네트워크 연결 확인
                        """)
                else:
                    # 데이터 소스 표시
                    if data.get('source') == 'Yahoo Finance':
                        st.info(f"ℹ️ 데이터 소스: {data['source']} (KRX 접근 불가로 백업 사용)")
                    
                    # 기본 정보
                    st.markdown("### 📌 기본 정보")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("종목명", data['name'])
                    c2.metric("시장", data['market'])
                    c3.metric("현재가", f"{data['current_price']:,.0f}원")
                    
                    if data['market_cap'] > 0:
                        c4.metric("시총", f"{data['market_cap']:,.0f}억")
                    else:
                        c4.metric("시총", "-")
                    
                    st.markdown("---")
                    
                    # 변동성
                    if data['low_52w'] > 0:
                        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
                    else:
                        volatility = 0
                    
                    # 판정
                    violations = []
                    warnings = []
                    
                    # 관리종목 (KRX에만 있음)
                    if data.get('dept') == '관리':
                        violations.append("관리종목")
                    
                    # 백업 소스 사용 시 경고
                    if data.get('warning'):
                        warnings.append(data['warning'])
                    
                    # 시총
                    if data['market_cap'] > 0 and data['market_cap'] < 100:
                        violations.append(f"시총 {data['market_cap']:,.0f}억")
                    elif data['market_cap'] == 0:
                        warnings.append("시총 정보 없음 (확인 필요)")
                    
                    # 변동성
                    if volatility >= 500:
                        warnings.append(f"극심한 변동성 {volatility:.0f}%")
                    elif volatility >= 200:
                        warnings.append(f"높은 변동성 {volatility:.0f}%")
                    
                    # 결과
                    st.markdown("### 🎯 판정")
                    
                    if violations:
                        st.error("⛔ **담보 불가**")
                        st.markdown(f"**불가 사유**: {', '.join(violations)}")
                        st.markdown("**위험**: 🔴 상장폐지 위험 높음")
                        st.markdown("**의견**: 담보 인정 불가")
                    elif warnings:
                        st.warning("⚠️ **조건부 가능 (주의)**")
                        st.markdown(f"**주의**: {', '.join(warnings)}")
                        st.markdown("**위험**: 🟠 급락 위험")
                        st.markdown("**조건**: 일일 모니터링 필수, 로스컷 130%")
                        st.markdown("**의견**: 주의 필요. 일일 모니터링 필수")
                    else:
                        st.success("✅ **담보 가능**")
                        st.markdown("**위험**: 🟢 낮음")
                        st.markdown("**조건**: 최대 LTV 200%, 로스컷 130%")
                        st.markdown("**의견**: 정상 담보 인정")
                    
                    # 주가
                    if volatility > 0:
                        st.markdown("---")
                        st.markdown("### 📈 52주 주가")
                        p1, p2, p3 = st.columns(3)
                        p1.metric("최고", f"{data['high_52w']:,.0f}원")
                        p2.metric("최저", f"{data['low_52w']:,.0f}원")
                        p3.metric("변동폭", f"{volatility:.1f}%")
        
        # === 해외주식 ===
        else:
            st.markdown("## 🌎 해외주식")
            
            with st.spinner("조회 중..."):
                data = get_us_stock(ticker)
                
                if 'error' in data:
                    st.error(f"❌ 조회 실패")
                    st.warning("⏰ Yahoo Finance API 제한. 1시간 후 재시도하세요.")
                else:
                    st.markdown("### 📌 기본 정보")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("종목명", data['name'][:15])
                    c2.metric("거래소", data['exchange'])
                    c3.metric("가격", f"${data['price']:.2f}")
                    c4.metric(data['mcap_label'], f"${data['mcap']:.1f}B")
                    
                    st.markdown("---")
                    
                    # 변동성
                    if data['high_52w'] > 0 and data['low_52w'] > 0:
                        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
                    else:
                        volatility = 0
                    
                    # 판정
                    violations = []
                    warnings = []
                    
                    allowed = ["NYSE", "NASDAQ", "NYSE Arca"]
                    if data['exchange'] not in allowed and data['exchange'] != "N/A":
                        violations.append(f"비허용 거래소: {data['exchange']}")
                    if "OTC" in data['exchange'].upper():
                        violations.append("OTC 장외시장")
                    if volatility >= 200:
                        warnings.append(f"높은 변동성 {volatility:.0f}%")
                    
                    # 결과
                    st.markdown("### 🎯 판정")
                    
                    if violations:
                        st.error("⛔ **담보 불가**")
                        st.markdown(f"**불가 사유**: {', '.join(violations)}")
                        st.markdown("**의견**: 비허용 거래소로 담보 인정 불가")
                    elif warnings:
                        st.warning("⚠️ **조건부 가능 (고위험)**")
                        st.markdown(f"**주의**: {', '.join(warnings)}")
                        st.markdown("**조건**: 일일 모니터링 필수")
                        st.markdown("**의견**: 변동성 높음. 로스컷 위험 안내 필수")
                    else:
                        st.success("✅ **담보 가능**")
                        st.markdown("**조건**: 최대 LTV 200%, 로스컷 130%")
                        st.markdown("**의견**: 정상 담보 인정")
                    
                    if volatility > 0:
                        st.markdown("---")
                        st.markdown("### 📈 52주 주가")
                        p1, p2, p3 = st.columns(3)
                        p1.metric("최고", f"${data['high_52w']:.2f}")
                        p2.metric("최저", f"${data['low_52w']:.2f}")
                        p3.metric("변동폭", f"{volatility:.1f}%")

st.markdown("---")
st.caption("ⓒ 2026 Pind | KRX 백업 추가")
