import streamlit as st
import yfinance as yf
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime
import time

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="centered")

st.title("🏦 핀드 담보 심사")
st.caption("KB증권 하이브리드 계좌운용규칙 | v7.0 보수적 리스크 관리")
st.markdown("---")

# === 데이터 수집 함수 ===

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

# === 국내주식 리스크 분석 (보수적) ===

def analyze_korean_stock(data):
    """
    국내주식 보수적 리스크 분석
    원칙: 의심스러우면 불가, 리스크 관리 최우선
    """
    market_cap = data['market_cap']
    current_price = data['current_price']
    dept = data.get('dept', '')
    market = data['market']
    
    volatility = 0
    if data['low_52w'] > 0:
        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
    
    violations = []  # 담보 불가 사유
    risk_factors = []  # 리스크 요인 (참고)
    
    # === 절대 불가 기준 (하나라도 해당하면 불가) ===
    
    # 1. 관리종목 → 무조건 불가
    if dept == '관리':
        violations.append("❌ 관리종목 지정 (상장폐지 심사 대상)")
        risk_factors.append("상장폐지 가능성 극히 높음")
    
    # 2. 동전주 (1,000원 미만) → 무조건 불가
    if current_price < 1000:
        violations.append(f"❌ 동전주 {current_price:,.0f}원 (2026년 기준: 1,000원 미만 30일 연속 시 상폐)")
        risk_factors.append("30일 연속 시 관리종목 → 90일 내 미회복 시 상장폐지")
    
    # 3. 시총 500억 미만 → 무조건 불가 (안전 마진)
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
    
    # 4. 백업 데이터 사용 시 관리종목 확인 불가 → 불가
    if data.get('backup_warning'):
        violations.append("❌ 관리종목 여부 확인 불가 (백업 데이터 사용)")
        risk_factors.append("KRX 데이터 없어 관리종목 지정 여부 미확인")
    
    # 5. 변동성 극심 (시총별 차등, 보수적)
    if market_cap >= 10000:  # 1조 이상 대형주
        cap_grade = "대형주"
        volatility_limit = 500
    elif market_cap >= 1000:  # 1,000억~1조 중형주
        cap_grade = "중형주"
        volatility_limit = 300
    elif market_cap >= 500:  # 500억~1,000억 소형주
        cap_grade = "소형주"
        volatility_limit = 200
    else:
        cap_grade = "극소형주"
        volatility_limit = 150
    
    if volatility >= volatility_limit and market_cap >= 500:
        violations.append(f"❌ 극심한 변동성 {volatility:.0f}% ({cap_grade} 기준 {volatility_limit}% 초과)")
        risk_factors.append("단기간 급락으로 로스컷 가능성 높음")
    
    # === 시총 등급 (10조 이상은 초대형주) ===
    if market_cap >= 100000:
        cap_grade = "초대형주"
    
    # === 최종 판정 ===
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
        'cap_grade': cap_grade,
        'market_cap': market_cap,
        'current_price': current_price
    }

# === 해외주식 리스크 분석 (보수적) ===

def analyze_us_stock(data):
    """
    해외주식 보수적 리스크 분석
    원칙: 고위험은 무조건 불가, 리스크관리 최우선
    """
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
    
    # === 절대 불가 기준 ===
    
    # 1. 거래소 (NYSE, NASDAQ, NYSE Arca만 허용)
    allowed_exchanges = ["NYSE", "NASDAQ", "NYSE Arca"]
    
    if "OTC" in exchange.upper():
        violations.append("❌ OTC 장외시장 (상장폐지 후 이동, 규제 없음)")
        risk_factors.append("유동성 극히 낮고 가격 조작 위험, 사기 종목 다수")
    elif "PINK" in exchange.upper() or exchange == "Pink Sheets":
        violations.append("❌ Pink Sheets (극도로 위험한 장외시장)")
        risk_factors.append("공시 의무 없음, 사기 가능성 매우 높음")
    elif exchange not in allowed_exchanges and exchange != "N/A":
        violations.append(f"❌ 비허용 거래소: {exchange}")
        risk_factors.append("당사 허용 거래소 아님 (NYSE, NASDAQ, NYSE Arca만 허용)")
    
    # 2. 나스닥 상장폐지 기준 미달
    if exchange == "NASDAQ":
        if price < 1.0:
            violations.append(f"❌ 나스닥 Bid Price Rule 미달 (현재 ${price:.2f}, 기준 $1.00)")
            risk_factors.append("30일 연속 미달 시 180일 유예 → 퇴출")
        
        if mcap > 0 and mcap < 0.050:  # $50M (보수적, 실제는 $35M)
            violations.append(f"❌ 나스닥 시총 기준 미달 (현재 ${mcap:.3f}B, 안전 기준 $0.05B)")
            risk_factors.append("상장폐지 위험 (실제 기준 $35M이나 안전 마진 고려)")
    
    # 3. NYSE 상장폐지 기준
    if exchange == "NYSE":
        if price < 1.0:
            violations.append(f"❌ NYSE 저가주 위험 (현재 ${price:.2f})")
            risk_factors.append("지속적 저가 시 상장폐지 심사 대상")
        
        if mcap > 0 and mcap < 0.025:  # $25M (보수적, 실제는 $15M)
            violations.append(f"❌ NYSE 시총 기준 미달 (현재 ${mcap:.3f}B)")
            risk_factors.append("상장폐지 위험")
    
    # 4. Penny Stock (매우 위험)
    if price < 5.0:
        violations.append(f"❌ Penny Stock (가격 ${price:.2f}, 기준 $5.00 미만)")
        risk_factors.append("변동성 극심, 가격 조작 위험, 유동성 낮음")
    
    # 5. 소형주/소형 ETF (시총 기준 보수적)
    if quote_type == "ETF":
        if mcap < 0.1:  # AUM $100M 미만
            violations.append(f"❌ 소규모 ETF (AUM ${mcap:.3f}B, 안전 기준 $0.1B)")
            risk_factors.append("청산(liquidation) 위험, 유동성 부족")
    else:
        if mcap > 0 and mcap < 1.0:  # $1B 미만 (보수적)
            violations.append(f"❌ 소형주 (시총 ${mcap:.2f}B, 안전 기준 $1.0B)")
            risk_factors.append("유동성 부족, 변동성 높음")
    
    # 6. PTP 구조 (MLP, ETP)
    if quote_type in ["MLP", "ETP"]:
        violations.append("❌ PTP 구조 (MLP/ETP)")
        risk_factors.append("K-1 세무서류 발급, 한국 세법 충돌, 담보 처리 시 복잡")
    
    # 7. 거래량 부족
    if volume > 0 and volume < 100000:  # 일평균 10만주 미만
        violations.append(f"❌ 거래량 부족 (평균 {volume:,}주/일)")
        risk_factors.append("로스컷 시 매도 어려움, 슬리피지 발생")
    
    # 8. 변동성 (보수적 기준)
    if mcap >= 10:  # $10B 이상
        volatility_limit = 300
    elif mcap >= 1:  # $1B~$10B
        volatility_limit = 200
    else:
        volatility_limit = 150
    
    if volatility >= volatility_limit:
        violations.append(f"❌ 극심한 변동성 {volatility:.0f}% (기준 {volatility_limit}% 초과)")
        risk_factors.append("단기간 급락 위험")
    
    # 9. 고베타 (시장 대비 2배 이상 변동)
    beta = data.get('beta', 0)
    if beta > 2.0:
        violations.append(f"❌ 고베타 {beta:.2f} (시장 대비 2배 이상 변동)")
        risk_factors.append("시장 하락 시 2배 이상 급락 가능")
    
    # === 최종 판정 ===
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
        'mcap': mcap,
        'price': price,
        'quote_type': quote_type
    }

# === 결과 출력 함수 ===

def render_korean_analysis(data, analysis):
    """국내주식 심사 결과 출력"""
    
    # 기본 정보
    st.markdown("### 📌 기본 정보")
    if data.get('source'):
        st.caption(f"📊 데이터 출처: {data['source']}")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("종목명", data['name'])
    col2.metric("시장", data['market'])
    col3.metric("현재가", f"{data['current_price']:,.0f}원")
    col4.metric("시총", f"{data['market_cap']:,.0f}억")
    
    st.caption(f"💎 시총 등급: {analysis['cap_grade']}")
    
    st.markdown("---")
    
    # 판정 결과
    if analysis['eligible']:
        st.success(f"### ✅ {analysis['judgment']}")
    else:
        st.error(f"### ⛔ {analysis['judgment']}")
    
    st.markdown(f"**위험 등급**: {analysis['risk_level']}")
    
    # 불가 사유
    if analysis['violations']:
        st.markdown("---")
        st.markdown("### ❌ 담보 불가 사유")
        for v in analysis['violations']:
            st.markdown(v)
        
        st.markdown("---")
        st.markdown("### ⚠️ 주요 리스크")
        for r in analysis['risk_factors']:
            st.markdown(f"• {r}")
        
        st.markdown("---")
        st.markdown("### 💼 심사 의견")
        
        st.markdown(f"""
**회사 리스크 평가**: 담보 부적격

**시가총액**: {analysis['market_cap']:,.0f}억원  
**현재가**: {analysis['current_price']:,.0f}원  
**변동성**: {analysis['volatility']:.1f}%

**상장폐지 위험도**: 높음

**2026년 7월 강화 기준**:
- 코스닥 시총 200억 미만 → 즉시 퇴출
- 동전주 (1,000원 미만 30일) → 90일 내 상폐
- 향후 300억 이상으로 추가 강화 예정

**실제 상폐 사례**: IHQ, KH필룩스 정리매매 기간 90% 이상 급락

**담보 설정 시 리스크**:
1. 상장폐지 시 담보가치 전액 손실
2. 정리매매 7거래일, 가격제한폭 없음
3. 로스컷 시 매도 자체 불가능할 수 있음
4. 회사 손실 → 회사 존속 위협

**최종 판정**: **담보 인정 불가**

**근거**: 상장폐지 위험, 유동성 부족, 리스크관리 최우선
        """)
    
    else:
        st.markdown("---")
        st.markdown("### 💼 심사 의견")
        
        st.markdown(f"""
**회사 리스크 평가**: 담보 적격

**시총 등급**: {analysis['cap_grade']}  
**시가총액**: {analysis['market_cap']:,.0f}억원  
**현재가**: {analysis['current_price']:,.0f}원  
**변동성**: {analysis['volatility']:.1f}%

**적격 근거**:
✓ 시가총액 500억 이상 (2026년 기준 충족 + 안전 마진)  
✓ 주가 1,000원 이상 (동전주 아님)  
✓ 관리종목 미지정  
✓ 변동성 정상 범위

**담보 조건**:
- 최대 대출비율(LTV): 200%
- 로스컷: 130%
- 현금인출 가능: 140% 이상
- 일일 담보비율 모니터링

**최종 판정**: **담보 인정 가능**

**고객 안내**: 담보비율 130% 도달 시 고객 동의 없이 자동 반대매매 실행
        """)
    
    # 주가 정보
    if analysis['volatility'] > 0:
        st.markdown("---")
        st.markdown("### 📈 52주 주가 분석")
        p1, p2, p3 = st.columns(3)
        p1.metric("최고가", f"{data['high_52w']:,.0f}원")
        p2.metric("최저가", f"{data['low_52w']:,.0f}원")
        p3.metric("변동폭", f"{analysis['volatility']:.1f}%")

def render_us_analysis(data, analysis):
    """해외주식 심사 결과 출력"""
    
    # 기본 정보
    st.markdown("### 📌 기본 정보")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("종목명", data['name'])
    col2.metric("거래소", data['exchange'])
    col3.metric("가격", f"${data['price']:.2f}")
    col4.metric(data['mcap_label'], f"${data['mcap']:.2f}B")
    
    if data.get('sector') != 'N/A':
        st.caption(f"🏢 섹터: {data['sector']}")
    
    st.markdown("---")
    
    # 판정 결과
    if analysis['eligible']:
        st.success(f"### ✅ {analysis['judgment']}")
    else:
        st.error(f"### ⛔ {analysis['judgment']}")
    
    st.markdown(f"**위험 등급**: {analysis['risk_level']}")
    
    # 불가 사유
    if analysis['violations']:
        st.markdown("---")
        st.markdown("### ❌ 담보 불가 사유")
        for v in analysis['violations']:
            st.markdown(v)
        
        st.markdown("---")
        st.markdown("### ⚠️ 주요 리스크")
        for r in analysis['risk_factors']:
            st.markdown(f"• {r}")
        
        st.markdown("---")
        st.markdown("### 💼 심사 의견")
        
        violation_text = ' '.join(analysis['violations'])
        
        if "OTC" in violation_text or "Pink" in violation_text:
            st.markdown(f"""
**회사 리스크 평가**: 극도로 위험

**OTC/Pink Sheets 장외시장**:
- 주요 거래소에서 상장폐지된 종목들이 이동하는 시장
- SEC 규제 거의 없음, 공시 의무 없음
- 재무제표 신뢰성 없음
- 유동성 극히 낮음 (매도 자체 불가능)
- 가격 조작, 사기 종목 다수 포함

**실제 위험**:
- 담보가치 급락 시 손실 회수 불가
- 로스컷 실행 불가능 (매수자 없음)
- 회사 손실 직결 → 존속 위협

**최종 판정**: **담보 인정 불가**
            """)
        
        elif "나스닥" in violation_text or "NYSE" in violation_text:
            st.markdown(f"""
**회사 리스크 평가**: 상장폐지 위험

**상장폐지 기준**:
- 나스닥 Bid Price Rule: $1.00 미만 30일 연속
- 나스닥 시총: $35M 미만
- NYSE 시총: $15M 미만
- 180일 유예 후 퇴출

**현재 상태**:
- 가격: ${analysis['price']:.2f}
- 시총: ${analysis['mcap']:.3f}B

**위험**:
- 상장폐지 시 OTC 이동 → 유동성 소멸
- 담보가치 전액 손실 가능
- 회사 손실 직결

**최종 판정**: **담보 인정 불가**
            """)
        
        elif "Penny Stock" in violation_text:
            st.markdown(f"""
**회사 리스크 평가**: 극심한 변동성

**Penny Stock (가격 $5 미만)**:
- 변동성 극심 (하루 20~50% 등락 가능)
- 가격 조작 위험
- 유동성 낮음
- SEC 규제 강화 대상

**담보 리스크**:
- 단기간 급락으로 로스컷 빈발
- 로스컷 시 슬리피지 발생
- 회사 손실 가능성 높음

**최종 판정**: **담보 인정 불가**
            """)
        
        elif "PTP" in violation_text:
            st.markdown(f"""
**회사 리스크 평가**: 세무 리스크

**PTP 구조 (MLP, ETP)**:
- Partnership 형태 (법인 아님)
- K-1 세무서류 발급 (1099가 아님)
- 한국 세법과 충돌 가능성
- 담보 처리 시 세무 복잡성

**운영 리스크**:
- 세무 처리 복잡
- 고객 민원 가능성
- 법률 리스크

**최종 판정**: **담보 인정 불가**
            """)
        
        else:
            st.markdown(f"""
**회사 리스크 평가**: 담보 부적격

**가격**: ${analysis['price']:.2f}  
**시총**: ${analysis['mcap']:.2f}B  
**변동성**: {analysis['volatility']:.1f}%

**위험 요소**:
- 유동성 부족
- 변동성 극심
- 로스컷 시 손실 가능성

**최종 판정**: **담보 인정 불가**

**근거**: 리스크관리 최우선, 손실 위험 차단
            """)
    
    else:
        st.markdown("---")
        st.markdown("### 💼 심사 의견")
        
        st.markdown(f"""
**회사 리스크 평가**: 담보 적격

**거래소**: {data['exchange']} (주요 거래소)  
**가격**: ${analysis['price']:.2f}  
**시총/AUM**: ${analysis['mcap']:.2f}B  
**변동성**: {analysis['volatility']:.1f}%

**적격 근거**:
✓ NYSE, NASDAQ, NYSE Arca 상장  
✓ 가격 $5.00 이상  
✓ 시총 $1.0B 이상 (안전 마진)  
✓ 변동성 정상 범위  
✓ 거래량 충분

**담보 조건**:
- 최대 대출비율(LTV): 200%
- 로스컷: 130%
- 현금인출 가능: 140% 이상
- 일일 담보비율 모니터링

**최종 판정**: **담보 인정 가능**

**고객 안내**: 환율 변동 위험 별도, 담보비율 130% 도달 시 자동 반대매매
        """)
    
    # 주가 정보
    if analysis['volatility'] > 0:
        st.markdown("---")
        st.markdown("### 📈 52주 주가 분석")
        p1, p2, p3 = st.columns(3)
        p1.metric("최고가", f"${data['high_52w']:.2f}")
        p2.metric("최저가", f"${data['low_52w']:.2f}")
        p3.metric("변동폭", f"{analysis['volatility']:.1f}%")

# === 사이드바 ===

with st.sidebar:
    st.header("📖 가이드")
    st.markdown("""
    **국내**: `005930` (삼성전자)  
    **해외**: `AAPL` (애플)
    """)
    st.markdown("---")
    
    st.error("### ⚠️ 보수적 리스크 관리")
    st.markdown("""
    **원칙**: 리스크관리 최우선
    
    **의심스러우면 → 불가**  
    **애매하면 → 불가**  
    **위험 가능성 있으면 → 불가**
    
    ✅ **100% 안전한 종목만** 담보 인정
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

# === 메인 ===

ticker = st.text_input("종목코드 / 티커", placeholder="예: 005930 (삼성전자), AAPL (애플)")

if st.button("🔍 심사 시작", type="primary", use_container_width=True):
    if not ticker:
        st.error("❌ 종목코드를 입력하세요")
    else:
        is_korean = ticker.isdigit() and len(ticker) == 6
        
        # 국내주식
        if is_korean:
            st.markdown("## 🇰🇷 국내주식 담보 심사")
            st.markdown("**원칙**: 회사 안전 최우선 / 의심스러우면 불가")
            st.markdown("---")
            
            with st.spinner("종목 분석 중..."):
                data = fetch_korean_stock(ticker)
                
                if not data['success']:
                    st.error("❌ 종목 데이터 조회 실패")
                    st.warning("⏰ 30분~1시간 후 재시도하세요")
                    
                    with st.expander("💡 문제 해결"):
                        st.markdown("""
                        **원인**:
                        - KRX 서버 일시 장애
                        - API 요청 제한
                        
                        **해결**:
                        1. 30분~1시간 대기
                        2. 종목코드 6자리 확인 (예: 005930)
                        3. 캐시 초기화 후 재시도
                        """)
                else:
                    analysis = analyze_korean_stock(data)
                    render_korean_analysis(data, analysis)
        
        # 해외주식
        else:
            st.markdown("## 🌎 해외주식 담보 심사")
            st.markdown("**원칙**: 회사 안전 최우선 / 고위험은 무조건 불가")
            st.markdown("---")
            
            with st.spinner("종목 분석 중..."):
                data = fetch_us_stock(ticker)
                
                if not data['success']:
                    st.error("❌ 종목 데이터 조회 실패")
                    st.warning("⏰ 1시간 후 재시도하세요")
                    
                    with st.expander("💡 문제 해결"):
                        st.markdown("""
                        **원인**:
                        - Yahoo Finance API 제한
                        
                        **해결**:
                        1. 1시간 대기
                        2. 티커 확인 (예: AAPL, TSLA)
                        3. 캐시 초기화 후 재시도
                        """)
                else:
                    analysis = analyze_us_stock(data)
                    render_us_analysis(data, analysis)

st.markdown("---")
st.caption("ⓒ 2026 Pind | 보수적 리스크 관리 시스템 v7.0")
