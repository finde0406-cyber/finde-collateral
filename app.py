import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="wide")

# CSS로 높이 조정
st.markdown("""
<style>
    .main {padding-top: 1rem;}
    [data-testid="stSidebar"] {min-width: 250px; max-width: 250px;}
</style>
""", unsafe_allow_html=True)

st.title("🏦 핀드 담보 심사")
st.caption("KB증권 하이브리드 계좌운용규칙 | v7.2 보수적 리스크 관리")
st.markdown("---")

# === 데이터 수집 함수 (동일) ===

@st.cache_data(ttl=3600)
def fetch_korean_stock(ticker):
    """국내주식 데이터 수집"""
    try:
        df_krx = fdr.StockListing('KRX')
        stock_info = df_krx[df_krx['Code'] == ticker]
        
        if not stock_info.empty:
            df_price = fdr.DataReader(ticker, '2024-01-01')
            
            return {
                'source': 'KRX',
                'success': True,
                'name': stock_info.iloc[0]['Name'],
                'market': stock_info.iloc[0]['Market'],
                'market_cap': stock_info.iloc[0].get('Marcap', 0) / 100000000,
                'dept': stock_info.iloc[0].get('Dept', ''),
                'current_price': df_price['Close'].iloc[-1],
                'high_52w': df_price['High'].max(),
                'low_52w': df_price['Low'].min()
            }
    except:
        pass
    
    try:
        time.sleep(1)
        for suffix, market_name in [('.KS', 'KOSPI'), ('.KQ', 'KOSDAQ')]:
            stock = yf.Ticker(f"{ticker}{suffix}")
            info = stock.info
            
            if info and info.get('regularMarketPrice'):
                hist = stock.history(period="1y")
                if not hist.empty:
                    mcap_raw = info.get('marketCap', 0)
                    return {
                        'source': 'Yahoo Finance (백업)',
                        'success': True,
                        'name': info.get('shortName', ticker),
                        'market': market_name,
                        'market_cap': mcap_raw / 100000000 if mcap_raw else 0,
                        'dept': '',
                        'current_price': hist['Close'].iloc[-1],
                        'high_52w': hist['High'].max(),
                        'low_52w': hist['Low'].min(),
                        'backup_warning': True
                    }
    except:
        pass
    
    return {'success': False, 'error': 'KRX 및 Yahoo Finance 접근 실패'}

@st.cache_data(ttl=3600)
def fetch_us_stock(ticker):
    """해외주식 데이터 수집"""
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        hist = stock.history(period="1y")
        
        if not info or not info.get('regularMarketPrice'):
            return {'success': False, 'error': '종목 정보 없음'}
        
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
            'success': True,
            'name': info.get('longName', info.get('shortName', ticker.upper())),
            'exchange': exchange_map.get(info.get('exchange', 'N/A'), info.get('exchange', 'N/A')),
            'price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
            'mcap': mcap_value / 1e9 if mcap_value else 0,
            'mcap_label': mcap_label,
            'quote_type': quote_type,
            'high_52w': hist['High'].max() if not hist.empty else 0,
            'low_52w': hist['Low'].min() if not hist.empty else 0,
            'sector': info.get('sector', 'N/A'),
            'beta': info.get('beta', 0),
            'volume': info.get('averageVolume', 0)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

# === 리스크 분석 함수 (동일) ===

def analyze_korean_stock(data):
    """국내주식 보수적 리스크 분석"""
    market_cap = data['market_cap']
    current_price = data['current_price']
    dept = data.get('dept', '')
    
    volatility = 0
    if data['low_52w'] > 0:
        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
    
    violations = []
    risk_factors = []
    
    if dept == '관리':
        violations.append("관리종목 지정")
        risk_factors.append("상장폐지 가능성 극히 높음")
    
    if current_price < 1000:
        violations.append(f"동전주 {current_price:,.0f}원")
        risk_factors.append("30일 연속 시 90일 내 상폐")
    
    if market_cap < 500:
        if market_cap < 100:
            violations.append(f"극소형주 시총 {market_cap:,.0f}억")
            risk_factors.append("로스컷 시 매도 불가능")
        elif market_cap < 200:
            violations.append(f"시총 {market_cap:,.0f}억 (2026년 기준 미달)")
            risk_factors.append("2026.7월 즉시 퇴출")
        else:
            violations.append(f"시총 {market_cap:,.0f}억 (안전 마진 부족)")
            risk_factors.append("향후 기준 강화 시 퇴출")
    
    if data.get('backup_warning'):
        violations.append("관리종목 여부 확인 불가")
        risk_factors.append("KRX 데이터 없음")
    
    if market_cap >= 100000:
        cap_grade = "초대형주"
        volatility_limit = 500
    elif market_cap >= 10000:
        cap_grade = "대형주"
        volatility_limit = 500
    elif market_cap >= 1000:
        cap_grade = "중형주"
        volatility_limit = 300
    elif market_cap >= 500:
        cap_grade = "소형주"
        volatility_limit = 200
    else:
        cap_grade = "극소형주"
        volatility_limit = 150
    
    if volatility >= volatility_limit and market_cap >= 500:
        violations.append(f"극심한 변동성 {volatility:.0f}%")
        risk_factors.append("단기 급락으로 로스컷 가능성")
    
    if violations:
        judgment = "담보 인정 불가"
        risk_level = "높음"
        eligible = False
    else:
        judgment = "담보 인정 가능"
        risk_level = "낮음"
        eligible = True
    
    return {
        'judgment': judgment,
        'risk_level': risk_level,
        'eligible': eligible,
        'violations': violations,
        'risk_factors': risk_factors,
        'volatility': volatility,
        'cap_grade': cap_grade,
        'market_cap': market_cap,
        'current_price': current_price
    }

def analyze_us_stock(data):
    """해외주식 보수적 리스크 분석"""
    exchange = data['exchange']
    mcap = data['mcap']
    price = data['price']
    quote_type = data['quote_type']
    volume = data.get('volume', 0)
    
    volatility = 0
    if data['low_52w'] > 0:
        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
    
    violations = []
    risk_factors = []
    
    allowed_exchanges = ["NYSE", "NASDAQ", "NYSE Arca"]
    
    if "OTC" in exchange.upper():
        violations.append("OTC 장외시장")
        risk_factors.append("가격 조작, 사기 종목 다수")
    elif "PINK" in exchange.upper():
        violations.append("Pink Sheets")
        risk_factors.append("공시 의무 없음")
    elif exchange not in allowed_exchanges and exchange != "N/A":
        violations.append(f"비허용 거래소: {exchange}")
        risk_factors.append("NYSE, NASDAQ만 허용")
    
    if exchange == "NASDAQ":
        if price < 1.0:
            violations.append(f"나스닥 기준 미달 (${price:.2f})")
            risk_factors.append("180일 유예 → 퇴출")
        if mcap > 0 and mcap < 0.050:
            violations.append(f"나스닥 시총 미달")
            risk_factors.append("상장폐지 위험")
    
    if exchange == "NYSE":
        if price < 1.0:
            violations.append(f"NYSE 저가주")
            risk_factors.append("상장폐지 심사 대상")
        if mcap > 0 and mcap < 0.025:
            violations.append(f"NYSE 시총 미달")
            risk_factors.append("상장폐지 위험")
    
    if price < 5.0:
        violations.append(f"Penny Stock (${price:.2f})")
        risk_factors.append("변동성 극심, 가격 조작")
    
    if quote_type == "ETF":
        if mcap < 0.1:
            violations.append(f"소규모 ETF")
            risk_factors.append("청산 위험")
    else:
        if mcap > 0 and mcap < 1.0:
            violations.append(f"소형주 (${mcap:.2f}B)")
            risk_factors.append("유동성 부족")
    
    if quote_type in ["MLP", "ETP"]:
        violations.append("PTP 구조")
        risk_factors.append("K-1 세무 복잡")
    
    if volume > 0 and volume < 100000:
        violations.append(f"거래량 부족")
        risk_factors.append("매도 어려움")
    
    if mcap >= 10:
        volatility_limit = 300
    elif mcap >= 1:
        volatility_limit = 200
    else:
        volatility_limit = 150
    
    if volatility >= volatility_limit:
        violations.append(f"극심한 변동성 {volatility:.0f}%")
        risk_factors.append("단기 급락 위험")
    
    beta = data.get('beta', 0)
    if beta > 2.0:
        violations.append(f"고베타 {beta:.2f}")
        risk_factors.append("시장 대비 2배 변동")
    
    if violations:
        judgment = "담보 인정 불가"
        risk_level = "높음"
        eligible = False
    else:
        judgment = "담보 인정 가능"
        risk_level = "낮음"
        eligible = True
    
    return {
        'judgment': judgment,
        'risk_level': risk_level,
        'eligible': eligible,
        'violations': violations,
        'risk_factors': risk_factors,
        'volatility': volatility,
        'mcap': mcap,
        'price': price,
        'quote_type': quote_type
    }

# === 결과 출력 (간결화) ===

def render_korean_result(data, analysis):
    """국내주식 결과 (우측 표시)"""
    
    st.markdown("### 📌 기본 정보")
    st.text(f"종목명: {data['name']}")
    st.text(f"시장: {data['market']}")
    st.text(f"현재가: {data['current_price']:,.0f}원")
    st.text(f"시총: {data['market_cap']:,.0f}억")
    st.caption(f"💎 {analysis['cap_grade']}")
    
    st.markdown("---")
    
    if analysis['eligible']:
        st.success(f"### ✅ {analysis['judgment']}")
        st.markdown(f"**위험 등급**: 🟢 {analysis['risk_level']}")
    else:
        st.error(f"### ⛔ {analysis['judgment']}")
        st.markdown(f"**위험 등급**: 🔴 {analysis['risk_level']}")
    
    if analysis['violations']:
        st.markdown("### ❌ 불가 사유")
        for v in analysis['violations']:
            st.markdown(f"• {v}")
        
        st.markdown("### ⚠️ 주요 리스크")
        for r in analysis['risk_factors']:
            st.markdown(f"• {r}")
    
    st.markdown("---")
    st.markdown("### 📈 52주 주가")
    st.text(f"최고: {data['high_52w']:,.0f}원")
    st.text(f"최저: {data['low_52w']:,.0f}원")
    st.text(f"변동폭: {analysis['volatility']:.1f}%")

def render_us_result(data, analysis):
    """해외주식 결과 (우측 표시)"""
    
    st.markdown("### 📌 기본 정보")
    st.text(f"종목명: {data['name']}")
    st.text(f"거래소: {data['exchange']}")
    st.text(f"가격: ${data['price']:.2f}")
    st.text(f"{data['mcap_label']}: ${data['mcap']:.2f}B")
    
    st.markdown("---")
    
    if analysis['eligible']:
        st.success(f"### ✅ {analysis['judgment']}")
        st.markdown(f"**위험 등급**: 🟢 {analysis['risk_level']}")
    else:
        st.error(f"### ⛔ {analysis['judgment']}")
        st.markdown(f"**위험 등급**: 🔴 {analysis['risk_level']}")
    
    if analysis['violations']:
        st.markdown("### ❌ 불가 사유")
        for v in analysis['violations']:
            st.markdown(f"• {v}")
        
        st.markdown("### ⚠️ 주요 리스크")
        for r in analysis['risk_factors']:
            st.markdown(f"• {r}")
    
    st.markdown("---")
    st.markdown("### 📈 52주 주가")
    st.text(f"최고: ${data['high_52w']:.2f}")
    st.text(f"최저: ${data['low_52w']:.2f}")
    st.text(f"변동폭: {analysis['volatility']:.1f}%")

# === 사이드바 (고정) ===

with st.sidebar:
    st.header("📖 가이드")
    st.markdown("""
    **국내**: `005930`  
    **해외**: `AAPL`
    """)
    st.markdown("---")
    
    st.error("### ⚠️ 보수적 리스크 관리")
    st.markdown("""
    **원칙**: 리스크관리 최우선
    
    **의심스러우면 → 불가**  
    **애매하면 → 불가**  
    **위험 가능성 → 불가**
    
    ✅ **100% 안전만** 담보 인정
    """)
    
    st.markdown("---")
    
    with st.expander("🔴 국내주식 불가 기준"):
        st.markdown("""
        **절대 불가**:
        - 관리종목
        - 동전주 (1,000원 미만)
        - 시총 500억 미만
        - 변동성 극심
        - 관리종목 확인 불가
        """)
    
    with st.expander("🔴 해외주식 불가 기준"):
        st.markdown("""
        **절대 불가**:
        - OTC/Pink Sheets
        - Penny Stock ($5 미만)
        - 소형주 ($1B 미만)
        - 나스닥/NYSE 기준 미달
        - PTP 구조 (MLP/ETP)
        - 거래량 부족
        - 변동성 극심
        """)
    
    with st.expander("⚙️ 2026년 강화 기준"):
        st.markdown("""
        **2026년 7월 시행**:
        - 코스닥 시총 200억 미만 퇴출
        - 동전주 (1,000원 미만 30일) 상폐
        - 향후 300억 이상 강화 예정
        
        **당사 기준 (안전 마진)**:
        - 시총 500억 이상만 인정
        """)
    
    if st.button("🔄 캐시 초기화"):
        st.cache_data.clear()
        st.success("완료!")

# === 메인 (좌우 분할) ===

left_main, right_main = st.columns([1, 2])

with left_main:
    st.markdown("### 종목코드 / 티커")
    ticker = st.text_input("", placeholder="예: 005930, AAPL", label_visibility="collapsed")
    
    if st.button("🔍 심사 시작", type="primary", use_container_width=True):
        if not ticker:
            st.error("❌ 종목코드 입력")
        else:
            # 세션에 저장
            st.session_state['ticker'] = ticker
            st.session_state['search_clicked'] = True

with right_main:
    if 'search_clicked' in st.session_state and st.session_state['search_clicked']:
        ticker = st.session_state['ticker']
        is_korean = ticker.isdigit() and len(ticker) == 6
        
        if is_korean:
            st.markdown("## 🇰🇷 국내주식 담보 심사")
            
            with st.spinner("분석 중..."):
                data = fetch_korean_stock(ticker)
                
                if not data['success']:
                    st.error("❌ 조회 실패")
                    st.warning("⏰ 30분 후 재시도")
                else:
                    analysis = analyze_korean_stock(data)
                    render_korean_result(data, analysis)
        
        else:
            st.markdown("## 🌎 해외주식 담보 심사")
            
            with st.spinner("분석 중..."):
                data = fetch_us_stock(ticker)
                
                if not data['success']:
                    st.error("❌ 조회 실패")
                    st.warning("⏰ 1시간 후 재시도")
                else:
                    analysis = analyze_us_stock(data)
                    render_us_result(data, analysis)
    else:
        st.info("👈 좌측에서 종목코드를 입력하고 심사를 시작하세요")

st.markdown("---")
st.caption("ⓒ 2026 FINDE | 리스크 관리 시스템 v7.2 | 2단 레이아웃")
