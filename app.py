import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="wide")

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
                'sector': stock_info.iloc[0].get('Sector', 'N/A'),
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
                        'sector': info.get('sector', 'N/A'),
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
            'industry': info.get('industry', 'N/A'),
            'beta': info.get('beta', 0),
            'volume': info.get('averageVolume', 0)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

# === 담보인정비율 계산 함수 ===

def calculate_acceptance_ratio(violations, volatility, cap_grade):
    """담보인정비율 계산"""
    
    if any('관리종목' in v or '동전주' in v or '시총' in v for v in violations):
        return 0, "상장폐지 위험"
    
    if volatility >= 400:
        return 0, "극심한 변동성 (400% 이상)"
    elif volatility >= 350:
        return 30, "매우 높은 변동성 (350% 이상)"
    elif volatility >= 300:
        return 50, "높은 변동성 (300% 이상)"
    elif volatility >= 250:
        return 70, "중상위 변동성 (250% 이상)"
    elif volatility >= 200:
        return 80, "중위 변동성 (200% 이상)"
    else:
        return 100, "정상 변동성"

# === 국내주식 리스크 분석 ===

def analyze_korean_stock(data):
    """국내주식 보수적 리스크 분석"""
    market_cap = data['market_cap']
    current_price = data['current_price']
    dept = data.get('dept', '')
    
    volatility = 0
    price_position = 0
    
    if data['low_52w'] > 0:
        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
        price_position = ((current_price - data['low_52w']) / (data['high_52w'] - data['low_52w'])) * 100
    
    violations = []
    risk_factors = []
    
    if dept == '관리':
        violations.append("❌ 관리종목 지정 (상장폐지 심사 대상)")
        risk_factors.append("상장폐지 가능성 극히 높음")
    
    if current_price < 1000:
        violations.append(f"❌ 동전주 {current_price:,.0f}원 (2026년 기준: 1,000원 미만 30일 연속 시 상폐)")
        risk_factors.append("30일 연속 시 관리종목 → 90일 내 미회복 시 상장폐지")
    
    if market_cap < 500:
        if market_cap < 100:
            violations.append(f"❌ 극소형주 시총 {market_cap:,.0f}억 (유동성 극히 낮음)")
            risk_factors.append("로스컷 시 매도 자체 불가능할 수 있음")
        elif market_cap < 200:
            violations.append(f"❌ 시총 {market_cap:,.0f}억 (2026.7월 코스닥 200억 기준 미달)")
            risk_factors.append("2026년 7월 즉시 퇴출 대상")
        else:
            violations.append(f"❌ 시총 {market_cap:,.0f}억 (향후 300억 기준 강화 예정, 안전 마진 부족)")
            risk_factors.append("향후 기준 강화 시 퇴출 가능")
    
    if data.get('backup_warning'):
        violations.append("❌ 관리종목 여부 확인 불가 (백업 데이터 사용)")
        risk_factors.append("KRX 데이터 없어 관리종목 지정 여부 미확인")
    
    # 시총 등급 (순위 기준 근사치)
    if market_cap >= 100000:
        cap_grade = "초대형주"
        volatility_limit = 500
    elif market_cap >= 50000:
        cap_grade = "대형주"
        volatility_limit = 500
    elif market_cap >= 5000:
        cap_grade = "중형주"
        volatility_limit = 300
    elif market_cap >= 500:
        cap_grade = "소형주"
        volatility_limit = 200
    else:
        cap_grade = "극소형주"
        volatility_limit = 150
    
    # 변동성 체크
    if volatility >= volatility_limit and market_cap >= 500:
        violations.append(f"❌ 극심한 변동성 {volatility:.1f}% ({cap_grade} 기준 {volatility_limit}% 초과)")
        risk_factors.append(f"52주 최고가 {data['high_52w']:,.0f}원 / 최저가 {data['low_52w']:,.0f}원")
        risk_factors.append(f"현재가 위치: 52주 범위 중 {price_position:.1f}% 지점")
        
        if price_position > 80:
            risk_factors.append("고점권 위치 - 하락 위험 높음")
        elif price_position > 60:
            risk_factors.append("중상단 위치 - 조정 가능성 있음")
        elif price_position > 40:
            risk_factors.append("중간 위치 - 양방향 변동 가능")
        elif price_position > 20:
            risk_factors.append("중하단 위치 - 상승 여력 있으나 변동성 주의")
        else:
            risk_factors.append("저점권 위치 - 상승 여력 있으나 추가 하락 가능성도 존재")
    
    # 담보인정비율
    acceptance_ratio, ratio_reason = calculate_acceptance_ratio(violations, volatility, cap_grade)
    
    # 최종 판정
    if violations:
        judgment = "담보 인정 불가"
        risk_level = "🔴 높음"
        eligible = False
    else:
        judgment = "담보 인정 가능"
        risk_level = "🟢 낮음"
        eligible = True
    
    return {
        'judgment': judgment,
        'risk_level': risk_level,
        'eligible': eligible,
        'violations': violations,
        'risk_factors': risk_factors,
        'volatility': volatility,
        'price_position': price_position,
        'cap_grade': cap_grade,
        'market_cap': market_cap,
        'current_price': current_price,
        'acceptance_ratio': acceptance_ratio,
        'ratio_reason': ratio_reason
    }

# === 해외주식 리스크 분석 ===

def analyze_us_stock(data):
    """해외주식 보수적 리스크 분석"""
    exchange = data['exchange']
    mcap = data['mcap']
    price = data['price']
    quote_type = data['quote_type']
    volume = data.get('volume', 0)
    
    volatility = 0
    price_position = 0
    
    if data['low_52w'] > 0:
        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
        price_position = ((price - data['low_52w']) / (data['high_52w'] - data['low_52w'])) * 100
    
    violations = []
    risk_factors = []
    
    allowed_exchanges = ["NYSE", "NASDAQ", "NYSE Arca"]
    
    if "OTC" in exchange.upper():
        violations.append("❌ OTC 장외시장")
        risk_factors.append("유동성 극히 낮고 가격 조작 위험")
    elif "PINK" in exchange.upper():
        violations.append("❌ Pink Sheets")
        risk_factors.append("공시 의무 없음")
    elif exchange not in allowed_exchanges and exchange != "N/A":
        violations.append(f"❌ 비허용 거래소: {exchange}")
        risk_factors.append("NYSE, NASDAQ만 허용")
    
    if exchange == "NASDAQ":
        if price < 1.0:
            violations.append(f"❌ 나스닥 기준 미달 (${price:.2f})")
            risk_factors.append("180일 유예 → 퇴출")
        if mcap > 0 and mcap < 0.050:
            violations.append(f"❌ 나스닥 시총 미달")
            risk_factors.append("상장폐지 위험")
    
    if exchange == "NYSE":
        if price < 1.0:
            violations.append(f"❌ NYSE 저가주")
            risk_factors.append("상장폐지 심사 대상")
        if mcap > 0 and mcap < 0.025:
            violations.append(f"❌ NYSE 시총 미달")
            risk_factors.append("상장폐지 위험")
    
    if price < 5.0:
        violations.append(f"❌ Penny Stock (${price:.2f})")
        risk_factors.append("변동성 극심, 가격 조작 위험")
    
    if quote_type == "ETF":
        if mcap < 0.1:
            violations.append(f"❌ 소규모 ETF")
            risk_factors.append("청산 위험")
    else:
        if mcap > 0 and mcap < 1.0:
            violations.append(f"❌ 소형주 (${mcap:.2f}B)")
            risk_factors.append("유동성 부족")
    
    if quote_type in ["MLP", "ETP"]:
        violations.append("❌ PTP 구조")
        risk_factors.append("K-1 세무 복잡")
    
    if volume > 0 and volume < 100000:
        violations.append(f"❌ 거래량 부족")
        risk_factors.append("매도 어려움")
    
    if mcap >= 50:
        cap_category = "초대형주"
        volatility_limit = 300
    elif mcap >= 10:
        cap_category = "대형주"
        volatility_limit = 250
    elif mcap >= 2:
        cap_category = "중형주"
        volatility_limit = 200
    elif mcap >= 1:
        cap_category = "소형주"
        volatility_limit = 150
    else:
        cap_category = "극소형주"
        volatility_limit = 100
    
    if volatility >= volatility_limit:
        violations.append(f"❌ 극심한 변동성 {volatility:.1f}% ({cap_category} 기준 {volatility_limit}% 초과)")
        risk_factors.append(f"52주 최고가 ${data['high_52w']:.2f} / 최저가 ${data['low_52w']:.2f}")
        risk_factors.append(f"현재가 위치: {price_position:.1f}% 지점")
        
        if price_position > 80:
            risk_factors.append("고점권 - 하락 위험")
        elif price_position > 60:
            risk_factors.append("중상단 - 조정 가능성")
        elif price_position > 40:
            risk_factors.append("중간 - 양방향 변동")
        elif price_position > 20:
            risk_factors.append("중하단 - 변동성 주의")
        else:
            risk_factors.append("저점권 - 추가 하락 가능성")
    
    beta = data.get('beta', 0)
    if beta > 3.0:
        violations.append(f"❌ 고베타 {beta:.2f}")
        risk_factors.append("시장 대비 3배 변동")
    
    acceptance_ratio, ratio_reason = calculate_acceptance_ratio(violations, volatility, cap_category)
    
    if violations:
        judgment = "담보 인정 불가"
        risk_level = "🔴 높음"
        eligible = False
    else:
        judgment = "담보 인정 가능"
        risk_level = "🟢 낮음"
        eligible = True
    
    return {
        'judgment': judgment,
        'risk_level': risk_level,
        'eligible': eligible,
        'violations': violations,
        'risk_factors': risk_factors,
        'volatility': volatility,
        'price_position': price_position,
        'mcap': mcap,
        'price': price,
        'quote_type': quote_type,
        'cap_category': cap_category,
        'acceptance_ratio': acceptance_ratio,
        'ratio_reason': ratio_reason
    }

# === 사이드바 (간소화) ===

with st.sidebar:
    st.title("🏦 핀드 담보 심사")
    st.caption("KB증권 하이브리드 | v7.3")
    st.markdown("---")
    
    st.header("📖 가이드")
    st.markdown("**국내**: `005930`  \n**해외**: `AAPL`")
    st.markdown("---")
    
    with st.expander("🔴 국내주식 불가 기준"):
        st.markdown("""
        **절대 불가**:
        - 관리종목
        - 동전주 (1,000원 미만)
        - 시총 500억 미만
        - 변동성 극심
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
    
    with st.expander("📊 국내주식 등급 기준"):
        st.markdown("""
        **시총 순위 기준** (근사치):
        - 초대형주: 10조 이상
        - 대형주: 5조~10조 (상위 100위권)
        - 중형주: 5,000억~5조 (상위 300위권)
        - 소형주: 500억~5,000억 (301위 이하)
        
        **변동성 기준**:
        - 초대형/대형주: 500% 초과 불가
        - 중형주: 300% 초과 불가
        - 소형주: 200% 초과 불가
        """)
    
    with st.expander("📊 담보인정비율 기준"):
        st.markdown("""
        **변동성 기준 차등 적용**:
        - 400% 이상: 0% (담보 불가)
        - 350~400%: 30%
        - 300~350%: 50%
        - 250~300%: 70%
        - 200~250%: 80%
        - 200% 미만: 100%
        
        **예시**:
        - 평가 1억원, 인정비율 70%
        - 실제 담보가치 7,000만원
        - 대출 가능 1.4억원 (LTV 200%)
        """)
    
    with st.expander("⚙️ 2026년 강화 기준"):
        st.markdown("""
        **2026년 7월 시행**:
        - 코스닥 시총 200억 미만 퇴출
        - 동전주 (1,000원 미만 30일) 상폐
        - 향후 300억 이상 강화 예정
        """)
    
    if st.button("🔄 캐시 초기화"):
        st.cache_data.clear()
        st.success("완료!")

# === 메인 ===

st.title("🏦 핀드 담보 심사")
st.caption("KB증권 하이브리드 계좌운용규칙 | v7.3")

with st.form(key='search_form', clear_on_submit=False):
    c1, c2, c3, c4 = st.columns([3, 1, 6, 1])
    with c1:
        ticker = st.text_input("종목코드/티커", placeholder="005930, AAPL", label_visibility="collapsed")
    with c2:
        search_button = st.form_submit_button("🔍 심사", use_container_width=True)

if search_button and ticker:
    is_korean = ticker.isdigit() and len(ticker) == 6
    
    if is_korean:
        with st.spinner("분석 중..."):
            data = fetch_korean_stock(ticker)
            
            if data['success']:
                analysis = analyze_korean_stock(data)
                
                st.markdown("---")
                
                if analysis['eligible']:
                    st.success(f"## ✅ {analysis['judgment']} | 위험 등급: {analysis['risk_level']}")
                else:
                    st.error(f"## ⛔ {analysis['judgment']} | 위험 등급: {analysis['risk_level']}")
                
                sector_text = f" | {data.get('sector', 'N/A')}" if data.get('sector') != 'N/A' else ""
                st.markdown(f"**{data['name']}** | {data['market']}{sector_text} | {data['current_price']:,.0f}원 | 시총 {data['market_cap']:,.0f}억 | {analysis['cap_grade']}")
                
                st.markdown(f"📈 **52주 고가**: {data['high_52w']:,.0f}원 | **저가**: {data['low_52w']:,.0f}원 | **변동성**: {analysis['volatility']:.1f}% | **현재 위치**: {analysis['price_position']:.1f}%")
                
                if analysis['acceptance_ratio'] < 100:
                    st.warning(f"💰 **권장 담보인정비율**: {analysis['acceptance_ratio']}% ({analysis['ratio_reason']})")
                
                if analysis['violations']:
                    st.markdown("### ❌ 담보 불가 사유")
                    for v in analysis['violations']:
                        st.markdown(v)
                    
                    st.markdown("### ⚠️ 주요 리스크")
                    for r in analysis['risk_factors']:
                        st.markdown(f"• {r}")
                    
                    st.markdown("### 💼 심사 의견")
                    
                    st.markdown(f"""
**변동성 리스크**: {'매우 높음' if analysis['volatility'] > 300 else '높음' if analysis['volatility'] > 200 else '보통'}
- 52주 변동폭 {analysis['volatility']:.1f}%는 {analysis['cap_grade']}로서 {'매우 높은' if analysis['volatility'] > 300 else '높은'} 수준

**현재가 위치**: {analysis['price_position']:.1f}% 지점
- 최고가 대비 {100 - analysis['price_position']:.1f}% 하락 여력
- 최저가 대비 {analysis['price_position']:.1f}% 상승한 상태

**담보 설정 시 리스크 관리**:

**종목별 담보인정비율 (권장)** 🔥
- **권장 인정비율: {analysis['acceptance_ratio']}%**
- 사유: {analysis['ratio_reason']}
- 실제 담보가치 = 평가금액 × {analysis['acceptance_ratio']}%
- 예시: 1억원 평가 → {analysis['acceptance_ratio']*1000000:,.0f}원 인정 → 대출 가능 {analysis['acceptance_ratio']*2000000:,.0f}원 (LTV 200% 기준)

**일일 모니터링 필수**
- 변동성 높아 담보비율 급변 가능
- 추가 담보 요구 가능성 있음

**최종 판정**: **담보 인정 불가**

**불가 사유**: {', '.join([v.replace('❌ ', '') for v in analysis['violations'][:2]])}

※ 계좌운용규칙(LTV, 로스컷, 인출비율)은 상품 및 자산규모별로 상이하므로 별도 확인 필요  
※ DART 재무제표 확인 후 담보인정비율 조정 가능성 검토 필요
                    """)
                
            else:
                st.error("❌ 조회 실패 - 30분 후 재시도")
    
    else:
        with st.spinner("분석 중..."):
            data = fetch_us_stock(ticker)
            
            if data['success']:
                analysis = analyze_us_stock(data)
                
                st.markdown("---")
                
                if analysis['eligible']:
                    st.success(f"## ✅ {analysis['judgment']} | 위험 등급: {analysis['risk_level']}")
                else:
                    st.error(f"## ⛔ {analysis['judgment']} | 위험 등급: {analysis['risk_level']}")
                
                sector_text = ""
                if data.get('sector') != 'N/A':
                    sector_text = f" | {data['sector']}"
                if data.get('industry') != 'N/A':
                    sector_text += f" - {data['industry']}"
                
                st.markdown(f"**{data['name']}** | {data['exchange']}{sector_text} | ${data['price']:.2f} | {data['mcap_label']} ${data['mcap']:.2f}B | {analysis.get('cap_category', 'N/A')}")
                
                st.markdown(f"📈 **52주 고가**: ${data['high_52w']:.2f} | **저가**: ${data['low_52w']:.2f} | **변동성**: {analysis['volatility']:.1f}% | **현재 위치**: {analysis['price_position']:.1f}%")
                
                if analysis['acceptance_ratio'] < 100:
                    st.warning(f"💰 **권장 담보인정비율**: {analysis['acceptance_ratio']}% ({analysis['ratio_reason']})")
                
                if analysis['violations']:
                    st.markdown("### ❌ 담보 불가 사유")
                    for v in analysis['violations']:
                        st.markdown(v)
                    
                    st.markdown("### ⚠️ 주요 리스크")
                    for r in analysis['risk_factors']:
                        st.markdown(f"• {r}")
                    
                    st.markdown("### 💼 심사 의견")
                    st.markdown(f"""
**변동성 리스크**: {'매우 높음' if analysis['volatility'] > 250 else '높음' if analysis['volatility'] > 150 else '보통'}

**현재가 위치**: {analysis['price_position']:.1f}% 지점

**담보인정비율 (권장)**: **{analysis['acceptance_ratio']}%**
- 사유: {analysis['ratio_reason']}
- 예시: $100,000 평가 → ${analysis['acceptance_ratio']*1000:,.0f} 인정

**일일 모니터링 필수**

**최종 판정**: **담보 인정 불가**

※ 계좌운용규칙은 상품별로 상이하므로 별도 확인 필요
                    """)
            else:
                st.error("❌ 조회 실패 - 1시간 후 재시도")

elif search_button:
    st.error("❌ 종목코드를 입력하세요")

st.markdown("---")
st.caption("ⓒ 2026 FINDE | 리스크 관리 시스템 v7.3")
