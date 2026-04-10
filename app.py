import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="centered")

st.title("🏦 핀드 담보 심사")
st.caption("KB증권 하이브리드 | v6.0 전문가 분석")
st.markdown("---")

# 캐싱 (API 부하 최소화)
@st.cache_data(ttl=3600)
def fetch_korean_stock(ticker):
    """국내주식 데이터 수집 (KRX 우선 → yfinance 백업)"""
    # 1차: FinanceDataReader
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
    
    # 2차: yfinance 백업
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
        
        # ETF vs 주식
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
            'beta': info.get('beta', 0)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def analyze_korean_stock(data):
    """국내주식 전문가 분석"""
    market_cap = data['market_cap']
    current_price = data['current_price']
    dept = data.get('dept', '')
    
    volatility = 0
    if data['low_52w'] > 0:
        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
    
    # 위험 등급 분류
    critical_risks = []  # 🔴 즉시 상폐 위험
    violations = []      # ⛔ 담보 불가
    warnings = []        # ⚠️ 고위험
    
    # === 상장폐지 즉시 위험 (2026년 기준) ===
    
    # 1. 관리종목
    if dept == '관리':
        critical_risks.append("관리종목 지정 (상장폐지 심사 대상)")
    
    # 2. 동전주 (2026년 신설 기준)
    if current_price < 1000:
        if dept == '관리':
            critical_risks.append(f"동전주 {current_price:,.0f}원 + 관리종목 (30일 연속 시 90일 내 상폐)")
        else:
            warnings.append(f"동전주 위험 (현재가 {current_price:,.0f}원, 기준 1,000원)")
    
    # 3. 시가총액 기준 (2026년 7월 강화)
    if market_cap < 100:
        critical_risks.append(f"극소형주 시총 {market_cap:,.0f}억 (즉시 퇴출 대상)")
    elif market_cap < 200:
        violations.append(f"시총 {market_cap:,.0f}억 (2026.7월 코스닥 200억 기준 미달)")
    elif market_cap < 300:
        warnings.append(f"시총 {market_cap:,.0f}억 (향후 300억 기준 예정)")
    
    # 4. 복합 위험 (저가 + 적자 + 시총 조합)
    if current_price < 1000 and market_cap < 300:
        critical_risks.append("저가주 + 소형주 복합 (2026년 퇴출 1순위)")
    
    # 5. 변동성
    if volatility >= 500:
        warnings.append(f"극심한 변동성 {volatility:.0f}% (정상 범위의 5배)")
    elif volatility >= 200:
        warnings.append(f"높은 변동성 {volatility:.0f}%")
    
    # 6. 백업 데이터 사용 시
    if data.get('backup_warning'):
        warnings.append("관리종목 여부 수동 확인 필요 (백업 데이터)")
    
    # === 판정 ===
    if critical_risks:
        judgment = "즉시 상폐 위험"
        risk_level = "🔴 Critical"
        color = "error"
    elif violations:
        judgment = "담보 불가"
        risk_level = "⛔ High"
        color = "error"
    elif warnings:
        judgment = "조건부 (고위험)"
        risk_level = "⚠️ Medium"
        color = "warning"
    else:
        judgment = "담보 가능"
        risk_level = "🟢 Low"
        color = "success"
    
    return {
        'judgment': judgment,
        'risk_level': risk_level,
        'color': color,
        'critical_risks': critical_risks,
        'violations': violations,
        'warnings': warnings,
        'volatility': volatility
    }

def analyze_us_stock(data):
    """해외주식 전문가 분석"""
    exchange = data['exchange']
    mcap = data['mcap']
    quote_type = data['quote_type']
    
    volatility = 0
    if data['low_52w'] > 0:
        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
    
    violations = []
    warnings = []
    
    # === 상장폐지 위험 (미국 기준) ===
    
    # 1. 거래소 (가장 중요)
    allowed_exchanges = ["NYSE", "NASDAQ", "NYSE Arca"]
    
    if "OTC" in exchange.upper():
        violations.append("OTC 장외시장 (상장폐지 후 이동)")
    elif exchange == "Pink Sheets" or "PINK" in exchange.upper():
        violations.append("Pink Sheets (극도로 위험)")
    elif exchange not in allowed_exchanges and exchange != "N/A":
        violations.append(f"비허용 거래소: {exchange}")
    
    # 2. 나스닥 최소 상장 유지 기준
    if exchange == "NASDAQ":
        # 주가 $1 미만 (Bid Price Rule)
        if data['price'] < 1.0:
            violations.append(f"나스닥 최저가 기준 미달 (현재 ${data['price']:.2f}, 기준 $1.00)")
        
        # 시총 $35M 미만 (Minimum Market Value)
        if mcap > 0 and mcap < 0.035:  # $35M = 0.035B
            violations.append(f"나스닥 최소 시총 미달 (${mcap:.3f}B, 기준 $0.035B)")
    
    # 3. NYSE 최소 유지 기준
    if exchange == "NYSE":
        # 주가 지속적으로 낮음
        if data['price'] < 1.0:
            warnings.append(f"NYSE 저가주 위험 (${data['price']:.2f})")
        
        # 시총 매우 낮음
        if mcap > 0 and mcap < 0.015:  # $15M
            violations.append(f"NYSE 최소 시총 미달 (${mcap:.3f}B)")
    
    # 4. Penny Stock (페니스탁)
    if data['price'] < 5.0 and mcap < 0.3:
        warnings.append(f"Penny Stock 해당 (가격 ${data['price']:.2f}, 시총 ${mcap:.2f}B)")
    
    # 5. PTP 구조 (세금 문제)
    if quote_type in ["MLP", "ETP"]:
        violations.append("PTP 구조 (MLP/ETP - K-1 세무 복잡성)")
    
    # 6. 소형 ETF 위험
    if quote_type == "ETF" and mcap < 0.05:  # $50M
        warnings.append(f"소규모 ETF (AUM ${mcap:.2f}B, 청산 위험)")
    
    # 7. 변동성
    if volatility >= 200:
        warnings.append(f"높은 변동성 {volatility:.0f}%")
    
    # 8. 베타 (시장 대비 변동성)
    beta = data.get('beta', 0)
    if beta > 2.0:
        warnings.append(f"고베타 {beta:.1f} (시장 2배 이상 변동)")
    
    # === 판정 ===
    if violations:
        judgment = "담보 불가"
        risk_level = "🔴 High"
        color = "error"
    elif warnings:
        judgment = "조건부 (고위험)"
        risk_level = "⚠️ Medium"
        color = "warning"
    else:
        judgment = "담보 가능"
        risk_level = "🟢 Low"
        color = "success"
    
    return {
        'judgment': judgment,
        'risk_level': risk_level,
        'color': color,
        'violations': violations,
        'warnings': warnings,
        'volatility': volatility
    }

def render_korean_analysis(data, analysis):
    """국내주식 분석 결과 출력"""
    st.markdown("### 📌 기본 정보")
    
    if data.get('source'):
        st.caption(f"📊 데이터 출처: {data['source']}")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("종목명", data['name'])
    c2.metric("시장", data['market'])
    c3.metric("현재가", f"{data['current_price']:,.0f}원")
    c4.metric("시총", f"{data['market_cap']:,.0f}억" if data['market_cap'] > 0 else "-")
    
    st.markdown("---")
    st.markdown(f"### 🎯 판정: {analysis['judgment']}")
    st.markdown(f"**위험 등급**: {analysis['risk_level']}")
    
    # 즉시 위험
    if analysis['critical_risks']:
        st.error("🚨 **즉시 상장폐지 위험**")
        for risk in analysis['critical_risks']:
            st.markdown(f"• {risk}")
        
        st.markdown("---")
        st.markdown("### 💼 전문가 의견")
        st.markdown(f"""
**상장폐지 가능성**: 극히 높음

**2026년 강화 기준**:
- 코스닥 시총 200억 미만 → 즉시 퇴출 대상
- 동전주(1,000원 미만 30일 연속) → 90일 내 미회복 시 상폐
- 관리종목 + 저시총 + 저가 복합 → 퇴출 1순위

**실제 사례**: IHQ, KH필룩스 정리매매 기간 90% 이상 급락

**담보 판정**: 상폐 시 담보가치 전액 손실 위험으로 **담보 인정 불가**

**정리매매**: 상폐 결정 후 7거래일, 30분마다 단일가 체결, 가격제한폭 없음
        """)
    
    # 일반 불가
    elif analysis['violations']:
        st.error("⛔ **담보 인정 불가**")
        for v in analysis['violations']:
            st.markdown(f"• {v}")
        
        st.markdown("---")
        st.markdown("### 💼 전문가 의견")
        st.markdown(f"""
**위험 요소**: 시가총액 기준 미달 또는 향후 기준 강화 시 퇴출 가능

**2026년 7월 시행 예정**: 코스닥 200억, 코스피 300억 기준

**담보 판정**: 리스크 기준 부적합으로 **담보 인정 불가**
        """)
    
    # 조건부
    elif analysis['warnings']:
        st.warning("⚠️ **조건부 담보 인정 (고위험)**")
        for w in analysis['warnings']:
            st.markdown(f"• {w}")
        
        st.markdown("---")
        st.markdown("### 💼 전문가 의견")
        st.markdown(f"""
**위험 요소**: 변동성 극심 또는 향후 기준 강화 시 영향 가능

**담보 조건**: 
- 최대 LTV: 200%
- 로스컷: 130%
- 일일 모니터링 필수

**고객 안내**: 주가 급락 시 자동 반대매매(로스컷) 발생 가능. 담보비율 130% 도달 시 고객 동의 없이 강제 매도
        """)
    
    # 정상
    else:
        st.success("✅ **담보 인정 가능**")
        st.markdown("---")
        st.markdown("### 💼 전문가 의견")
        st.markdown(f"""
**리스크 평가**: 낮음

**담보 조건**:
- 최대 LTV: 200%
- 로스컷: 130%
- 현금인출: 140% 이상

**판정**: 계좌운용규칙 기준 충족, 정상 담보 인정
        """)
    
    # 주가 정보
    if analysis['volatility'] > 0:
        st.markdown("---")
        st.markdown("### 📈 52주 주가")
        p1, p2, p3 = st.columns(3)
        p1.metric("최고", f"{data['high_52w']:,.0f}원")
        p2.metric("최저", f"{data['low_52w']:,.0f}원")
        p3.metric("변동폭", f"{analysis['volatility']:.1f}%")

def render_us_analysis(data, analysis):
    """해외주식 분석 결과 출력"""
    st.markdown("### 📌 기본 정보")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("종목명", data['name'][:15])
    c2.metric("거래소", data['exchange'])
    c3.metric("가격", f"${data['price']:.2f}")
    c4.metric(data['mcap_label'], f"${data['mcap']:.1f}B" if data['mcap'] > 0 else "-")
    
    st.markdown("---")
    st.markdown(f"### 🎯 판정: {analysis['judgment']}")
    st.markdown(f"**위험 등급**: {analysis['risk_level']}")
    
    # 불가
    if analysis['violations']:
        st.error("⛔ **담보 인정 불가**")
        for v in analysis['violations']:
            st.markdown(f"• {v}")
        
        st.markdown("---")
        st.markdown("### 💼 전문가 의견")
        
        if "OTC" in str(analysis['violations']) or "Pink" in str(analysis['violations']):
            st.markdown("""
**OTC/Pink Sheets 위험**:
- 주요 거래소에서 상장폐지 후 이동한 시장
- 규제 최소화, 재무제표 공시 의무 없음
- 유동성 극히 낮고 가격 조작 위험
- 사기 종목 다수 포함

**담보 판정**: 극도로 위험하여 **담보 인정 불가**
            """)
        
        elif "나스닥" in str(analysis['violations']):
            st.markdown("""
**나스닥 상장폐지 기준**:
- Bid Price Rule: 주가 $1.00 미만 30일 연속
- Market Value Rule: 시총 $35M 미만
- 기준 미달 시 180일 유예 후 퇴출

**담보 판정**: 상장폐지 위험으로 **담보 인정 불가**
            """)
        
        elif "PTP" in str(analysis['violations']):
            st.markdown("""
**PTP(MLP/ETP) 구조 문제**:
- K-1 세무서류 발급 (복잡한 세무처리)
- 한국 세법과 충돌 가능성
- 담보 처리 시 세무 이슈 발생

**담보 판정**: 세무 리스크로 **담보 인정 불가**
            """)
        
        else:
            st.markdown("**담보 판정**: 비허용 거래소 또는 리스크 기준 부적합으로 **담보 인정 불가**")
    
    # 조건부
    elif analysis['warnings']:
        st.warning("⚠️ **조건부 담보 인정 (고위험)**")
        for w in analysis['warnings']:
            st.markdown(f"• {w}")
        
        st.markdown("---")
        st.markdown("### 💼 전문가 의견")
        st.markdown(f"""
**위험 요소 분석**:
- Penny Stock: 주가 $5 미만 + 시총 낮음 → 변동성 극심
- 소형 ETF: AUM 낮으면 청산(liquidation) 위험
- 고변동성: 단기간 급락 가능

**담보 조건**:
- 최대 LTV: 200%
- 로스컷: 130%
- 일일 모니터링 필수

**고객 안내**: 변동성이 높아 로스컷 발생 가능성 높음
        """)
    
    # 정상
    else:
        st.success("✅ **담보 인정 가능**")
        st.markdown("---")
        st.markdown("### 💼 전문가 의견")
        st.markdown(f"""
**리스크 평가**: 낮음

**거래소**: {data['exchange']} (주요 거래소 상장)
**섹터**: {data.get('sector', 'N/A')}

**담보 조건**:
- 최대 LTV: 200%
- 로스컷: 130%
- 현금인출: 140% 이상

**판정**: 정상 담보 인정
        """)
    
    # 주가 정보
    if analysis['volatility'] > 0:
        st.markdown("---")
        st.markdown("### 📈 52주 주가")
        p1, p2, p3 = st.columns(3)
        p1.metric("최고", f"${data['high_52w']:.2f}")
        p2.metric("최저", f"${data['low_52w']:.2f}")
        p3.metric("변동폭", f"{analysis['volatility']:.1f}%")

# 사이드바
with st.sidebar:
    st.header("📖 가이드")
    st.markdown("""
    **국내**: `005930` `064800`  
    **해외**: `AAPL` `TSLA` `SOXL`
    """)
    st.markdown("---")
    
    with st.expander("🔴 즉시 상폐 위험"):
        st.markdown("""
        **국내**:
        - 관리종목 + 시총 100억 미만
        - 동전주(1,000원 미만) + 관리종목
        - 저가 + 소형주 복합
        
        **해외**:
        - OTC/Pink Sheets
        - 나스닥 $1 미만
        - 시총 $35M 미만
        """)
    
    with st.expander("⚙️ 2026년 강화 기준"):
        st.markdown("""
        **시행**: 2026년 7월
        
        - 코스닥 시총 200억 미만
        - 동전주 1,000원 미만 30일
        - 미회복 시 90일 내 상폐
        """)
    
    if st.button("🔄 캐시 초기화"):
        st.cache_data.clear()
        st.success("완료!")

# 메인
ticker = st.text_input("종목코드 / 티커", placeholder="예: 005930, AAPL, SOXL")

if st.button("🔍 심사", type="primary", use_container_width=True):
    if not ticker:
        st.error("❌ 종목코드를 입력하세요")
    else:
        is_korean = ticker.isdigit() and len(ticker) == 6
        
        # === 국내주식 ===
        if is_korean:
            st.markdown("## 🇰🇷 국내주식 심사")
            
            with st.spinner("데이터 수집 중..."):
                data = fetch_korean_stock(ticker)
                
                if not data['success']:
                    st.error("❌ 조회 실패")
                    st.warning("⏰ KRX 및 Yahoo Finance 접근 불가. 30분~1시간 후 재시도하세요.")
                    
                    with st.expander("💡 문제 해결"):
                        st.markdown("""
                        **원인**:
                        - API 요청 제한 (Rate Limit)
                        - KRX 서버 일시 장애
                        
                        **해결**:
                        1. 30분~1시간 대기 후 재시도
                        2. 종목코드 6자리 확인 (예: 005930)
                        3. 캐시 초기화 후 재시도
                        """)
                else:
                    analysis = analyze_korean_stock(data)
                    render_korean_analysis(data, analysis)
        
        # === 해외주식 ===
        else:
            st.markdown("## 🌎 해외주식 심사")
            
            with st.spinner("데이터 수집 중..."):
                data = fetch_us_stock(ticker)
                
                if not data['success']:
                    st.error("❌ 조회 실패")
                    st.warning("⏰ Yahoo Finance API 제한. 1시간 후 재시도하세요.")
                    
                    with st.expander("💡 문제 해결"):
                        st.markdown("""
                        **원인**: API 요청 제한 (Rate Limit)
                        
                        **해결**:
                        1. 1시간 대기 후 재시도
                        2. 티커 확인 (예: AAPL, TSLA)
                        3. 캐시 초기화 후 재시도
                        """)
                else:
                    analysis = analyze_us_stock(data)
                    render_us_analysis(data, analysis)

st.markdown("---")
st.caption("ⓒ 2026 Pind | 전문가 리스크 분석")
