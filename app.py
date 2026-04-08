import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="wide")

st.title("🏦 핀드 담보 적격성 자동 심사 시스템")
st.caption("KB증권 하이브리드 계좌운용규칙 기준 | v3.0 안정화")
st.markdown("---")

# 사이드바
with st.sidebar:
    st.header("ℹ️ 사용법")
    st.markdown("""
    **국내주식**: 6자리 숫자  
    예) 005930, 127120, 064800
    
    **해외주식**: 영문 티커  
    예) AAPL, TSLA, SOXL
    """)
    st.markdown("---")
    st.info("""
    **국내주식**: 간단한 정보 입력  
    **해외주식**: 완전 자동화
    """)
    
    with st.expander("⚠️ 주요 불가사유"):
        st.markdown("""
        **국내주식**
        - 시가총액 100억 미만
        - 관리종목
        - 거래정지
        
        **해외주식**
        - OTC 장외시장
        - 비허용 거래소
        """)

# 의견 생성 함수들
def generate_rejection_opinion(violations, data, is_korean=True):
    """담보 불가 의견"""
    opinion = "⛔ 담보 설정 불가\n\n"
    
    opinion += "**[불가 사유]**\n"
    for v in violations:
        opinion += f"• {v}\n"
    
    opinion += "\n**[위험도 평가]**\n"
    opinion += "재무 건전성: 🔴 위험\n"
    opinion += "주가 안정성: 🔴 위험\n"
    opinion += "유동성: 🔴 위험\n"
    opinion += "**종합 평가: 🔴 부적격**\n\n"
    
    opinion += "**[리스크관리팀 의견]**\n"
    
    if is_korean:
        if any("시가총액" in v for v in violations):
            opinion += "해당 종목은 시가총액 100억원 미만 소형주로 유동성 위험이 높아 담보 설정이 불가능합니다. "
        if any("관리종목" in v for v in violations):
            opinion += "관리종목으로 지정되어 상장폐지 위험이 있습니다. "
        if any("거래정지" in v for v in violations):
            opinion += "거래정지 상태로 즉시 처분이 불가능합니다. "
    else:
        if any("OTC" in v or "거래소" in v for v in violations):
            opinion += "해당 종목은 장외시장 또는 비허용 거래소에서 거래되어 담보 인정이 불가능합니다. "
    
    opinion += "\n\n**[고객 안내 문구]**\n"
    opinion += '"해당 종목은 당사 계좌운용규칙상 담보로 인정되지 않습니다. '
    
    if is_korean:
        opinion += '시가총액 100억원 이상의 우량 종목으로 재신청 부탁드립니다."'
    else:
        opinion += 'NYSE, NASDAQ 상장 종목 중에서 재신청 부탁드립니다."'
    
    return opinion

def generate_conditional_opinion(warnings, data, is_korean=True):
    """조건부 가능 의견"""
    risk_level = "고위험" if len(warnings) >= 3 else "주의"
    risk_emoji = "🔴" if len(warnings) >= 3 else "🟠"
    max_ltv = "30%" if len(warnings) >= 3 else "40%"
    
    opinion = f"⚠️ 조건부 담보 가능 ({risk_level} - 보수적 관리 필수)\n\n"
    
    opinion += "**[주의 사유]**\n"
    for w in warnings:
        opinion += f"• {w}\n"
    
    opinion += "\n**[위험도 평가]**\n"
    
    if any("자본잠식" in w or "부채" in w for w in warnings):
        opinion += "재무 건전성: 🔴 위험\n"
    else:
        opinion += "재무 건전성: 🟡 보통\n"
    
    if any("변동" in w for w in warnings):
        opinion += "주가 안정성: 🟠 주의\n"
    else:
        opinion += "주가 안정성: 🟡 보통\n"
    
    opinion += "유동성: 🟡 보통\n"
    opinion += f"**종합 평가: {risk_emoji} {risk_level}**\n\n"
    
    opinion += "**[담보 설정 조건]**\n"
    opinion += f"1. 최대 대출비율 {max_ltv} 이하로 제한\n"
    opinion += "2. 담보비율 150% 미만 시 즉시 연락 필수\n"
    opinion += "3. 일일 모니터링 대상 등록\n"
    opinion += "4. 추가 하락 시 담보 추가 징구 가능성 안내\n\n"
    
    opinion += "**[리스크관리팀 의견]**\n"
    
    if any("변동" in w for w in warnings):
        opinion += "주가 변동성이 높아 단기간 급등락 위험이 있습니다. "
    
    if any("자본잠식" in w for w in warnings):
        opinion += "재무 건전성이 취약하여 관리종목 지정 가능성을 주의해야 합니다. "
    
    opinion += f"\n\n보수적 대출비율({max_ltv} 이하) 적용과 정기 모니터링이 필수적입니다.\n\n"
    
    opinion += "**[고객 안내 문구]**\n"
    opinion += f'"해당 종목은 담보 설정이 가능하나, 변동성이 높은 상태입니다. '
    opinion += f'대출한도는 평가금액의 {max_ltv} 이하를 권장하며, '
    opinion += '주가 추가 하락 시 담보 추가 제공 또는 강제 매도가 발생할 수 있습니다."'
    
    return opinion

def generate_approval_opinion(data, is_korean=True):
    """담보 가능 의견"""
    opinion = "✅ 담보 설정 가능\n\n"
    
    opinion += "**[적격 근거]**\n"
    
    if is_korean:
        if data.get('market_cap', 0) >= 10000:
            opinion += f"✓ 시가총액 {data['market_cap']:,.0f}억원 (초대형주)\n"
        elif data.get('market_cap', 0) >= 1000:
            opinion += f"✓ 시가총액 {data['market_cap']:,.0f}억원 (대형주)\n"
        else:
            opinion += f"✓ 시가총액 {data.get('market_cap', 0):,.0f}억원 (기준 충족)\n"
        opinion += "✓ 계좌운용규칙 기준 충족\n"
        
        if not data.get('is_managed', False):
            opinion += "✓ 관리종목 아님\n"
        if not data.get('is_suspended', False):
            opinion += "✓ 거래정지 없음\n"
    else:
        mcap_b = data.get('market_cap', 0)
        opinion += f"✓ 시가총액 ${mcap_b:.1f}B\n"
        opinion += f"✓ 거래소: {data.get('exchange', 'N/A')}\n"
        opinion += "✓ 주요 거래소 상장\n"
    
    opinion += "\n**[위험도 평가]**\n"
    opinion += "재무 건전성: 🟢 양호\n"
    opinion += "주가 안정성: 🟢 안정\n"
    opinion += "유동성: 🟢 우수\n"
    opinion += "**종합 평가: 🟢 우량**\n\n"
    
    opinion += "**[담보 설정 조건]**\n"
    opinion += "• 최대 대출비율: 계좌평가금액의 200% 이내\n"
    opinion += "• 자동반대매매(로스컷): 130%\n"
    opinion += "• 현금인출 가능: 140% 이상\n\n"
    
    opinion += "**[리스크관리팀 의견]**\n"
    opinion += "계좌운용규칙 기준을 충족하여 정상적인 담보 설정이 가능합니다.\n\n"
    
    opinion += "**[고객 안내 문구]**\n"
    opinion += '"해당 종목은 담보 설정에 문제가 없습니다. 계좌평가금액의 최대 200%까지 대출 가능합니다."'
    
    return opinion

# 메인
ticker = st.text_input("**종목코드 / 티커 입력**", placeholder="005930 또는 AAPL")

if st.button("🔍 심사 시작", type="primary", use_container_width=True):
    if not ticker:
        st.error("❌ 종목코드를 입력하세요")
    else:
        is_korean = ticker.isdigit() and len(ticker) == 6
        
        # === 국내주식 ===
        if is_korean:
            st.markdown("## 🇰🇷 국내주식 심사")
            st.info("💡 정확한 심사를 위해 아래 정보를 입력해주세요 (네이버 금융, 다음 금융 등에서 확인 가능)")
            
            with st.form("korean_stock_form"):
                st.markdown("### 📝 기본 정보")
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    stock_name = st.text_input("종목명", placeholder="예: 삼성전자")
                with col_b:
                    current_price = st.number_input("현재가 (원)", min_value=0, value=0, step=100)
                with col_c:
                    market_cap = st.number_input("시가총액 (억원)", min_value=0, value=0, step=10)
                
                st.markdown("### ⚠️ 위험 요소 체크")
                
                col_d, col_e, col_f = st.columns(3)
                with col_d:
                    is_managed = st.checkbox("관리종목")
                with col_e:
                    is_suspended = st.checkbox("거래정지")
                with col_f:
                    is_delisting = st.checkbox("정리매매")
                
                st.markdown("### 📊 52주 주가 (선택사항)")
                
                col_g, col_h = st.columns(2)
                with col_g:
                    high_52w = st.number_input("52주 최고 (원)", min_value=0, value=0, step=100)
                with col_h:
                    low_52w = st.number_input("52주 최저 (원)", min_value=0, value=0, step=100)
                
                submit = st.form_submit_button("✅ 판정 실행", use_container_width=True)
                
                if submit:
                    # 기본 정보 표시
                    st.markdown("---")
                    st.markdown("### 📌 심사 정보")
                    info_cols = st.columns(4)
                    info_cols[0].metric("종목코드", ticker)
                    info_cols[1].metric("종목명", stock_name if stock_name else "-")
                    info_cols[2].metric("현재가", f"{current_price:,}원")
                    info_cols[3].metric("시가총액", f"{market_cap:,}억")
                    
                    st.markdown("---")
                    
                    # 판정 로직
                    violations = []
                    warnings = []
                    
                    # 1차: 절대 불가
                    if is_managed:
                        violations.append("관리종목 지정")
                    if is_suspended:
                        violations.append("거래정지")
                    if is_delisting:
                        violations.append("정리매매")
                    if market_cap < 100:
                        violations.append(f"시가총액 {market_cap:,}억원 (기준: 100억 이상)")
                    
                    # 2차: 변동성
                    volatility = 0
                    if high_52w > 0 and low_52w > 0:
                        volatility = ((high_52w - low_52w) / low_52w) * 100
                        if volatility >= 500:
                            warnings.append(f"극심한 변동성 {volatility:.0f}%")
                        elif volatility >= 200:
                            warnings.append(f"높은 변동성 {volatility:.0f}%")
                    
                    # 최종 판정
                    st.markdown("### 🎯 판정 결과")
                    
                    data = {
                        'market_cap': market_cap,
                        'is_managed': is_managed,
                        'is_suspended': is_suspended
                    }
                    
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
                    if high_52w > 0 or low_52w > 0:
                        st.markdown("---")
                        st.markdown("### 📈 주가 정보 (52주)")
                        p1, p2, p3 = st.columns(3)
                        p1.metric("최고가", f"{high_52w:,}원")
                        p2.metric("최저가", f"{low_52w:,}원")
                        if volatility > 0:
                            p3.metric("변동폭", f"{volatility:.1f}%")
                    
                    # 다운로드
                    st.markdown("---")
                    report = pd.DataFrame([{
                        "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "종목코드": ticker,
                        "종목명": stock_name,
                        "판정": judgment,
                        "시가총액": f"{market_cap:,}억",
                        "현재가": f"{current_price:,}원",
                        "불가사유": ", ".join(violations) if violations else "-",
                        "주의사항": ", ".join(warnings) if warnings else "-"
                    }])
                    
                    csv = report.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        "📥 심사 결과 다운로드",
                        csv,
                        f"핀드_담보심사_{ticker}_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv",
                        use_container_width=True
                    )
        
        # === 해외주식 (완전 자동) ===
        else:
            st.markdown("## 🌎 해외주식 자동 심사")
            
            with st.spinner("📡 Yahoo Finance에서 데이터 수집 중..."):
                try:
                    stock = yf.Ticker(ticker.upper())
                    info = stock.info
                    hist = stock.history(period="1y")
                    
                    # 기본 정보
                    st.markdown("### 📌 기본 정보")
                    
                    name = info.get('longName', info.get('shortName', 'N/A'))
                    exchange_raw = info.get('exchange', 'N/A')
                    price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                    mcap = info.get('marketCap', 0) / 1e9
                    
                    # 거래소 정리 (yfinance 코드 → 실제 거래소명)
                    exchange_map = {
                        'NYQ': 'NYSE',
                        'NMS': 'NASDAQ',
                        'NGM': 'NASDAQ',
                        'NAS': 'NASDAQ',
                        'PCX': 'NYSE Arca',
                        'NYSEARCA': 'NYSE Arca',
                        'NASDAQ': 'NASDAQ',
                        'NYSE': 'NYSE'
                    }
                    exchange = exchange_map.get(exchange_raw, exchange_raw)
                    
                    info_cols = st.columns(5)
                    info_cols[0].metric("티커", ticker.upper())
                    info_cols[1].metric("종목명", name[:25])
                    info_cols[2].metric("거래소", exchange)
                    info_cols[3].metric("가격", f"${price:.2f}")
                    info_cols[4].metric("시가총액", f"${mcap:.1f}B")
                    
                    st.markdown("---")
                    
                    # 판정 로직
                    violations = []
                    warnings = []
                    
                    # 허용 거래소 (실제 거래소명 기준)
                    allowed_exchanges = ["NYSE", "NASDAQ", "NYSE Arca"]
                    
                    if exchange not in allowed_exchanges and exchange != "N/A":
                        violations.append(f"비허용 거래소: {exchange}")
                    
                    if "OTC" in exchange.upper():
                        violations.append("OTC 장외시장 거래")
                    
                    # PTP 체크
                    quote_type = info.get('quoteType', '')
                    if quote_type in ["MLP", "ETP"]:
                        violations.append("PTP(Partnership) 구조")
                    
                    # 시가총액 경고
                    if mcap < 1 and not violations:
                        warnings.append(f"시가총액 ${mcap:.2f}B (소형주)")
                    
                    # 변동성
                    if not hist.empty:
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100 if low > 0 else 0
                        if vol >= 200 and not violations:
                            warnings.append(f"높은 변동성 {vol:.0f}%")
                    
                    # 최종 판정
                    st.markdown("### 🎯 판정 결과")
                    
                    data_us = {
                        'market_cap': mcap,
                        'exchange': exchange,
                        'name': name
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
                        st.markdown("### 📈 주가 정보 (52주)")
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100 if low > 0 else 0
                        
                        p1, p2, p3 = st.columns(3)
                        p1.metric("최고가", f"${high:.2f}")
                        p2.metric("최저가", f"${low:.2f}")
                        p3.metric("변동폭", f"{vol:.1f}%")
                    
                    # 다운로드
                    st.markdown("---")
                    report = pd.DataFrame([{
                        "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "티커": ticker.upper(),
                        "종목명": name,
                        "거래소": exchange,
                        "판정": judgment,
                        "시가총액": f"${mcap:.1f}B",
                        "불가사유": ", ".join(violations) if violations else "-",
                        "주의사항": ", ".join(warnings) if warnings else "-"
                    }])
                    
                    csv = report.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        "📥 심사 결과 다운로드",
                        csv,
                        f"핀드_담보심사_{ticker.upper()}_{datetime.now().strftime('%Y%m%d')}.csv",
                        "text/csv",
                        use_container_width=True
                    )
                    
                except Exception as e:
                    st.error(f"❌ 조회 실패: {str(e)}")
                    st.info("💡 티커를 다시 확인해주세요. 예: AAPL, TSLA, SOXL")

st.markdown("---")
st.caption("ⓒ 2026 Pind Inc. | v3.0 안정화 버전")
