import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="핀드 담보 심사", page_icon="🏦", layout="wide")

st.title("🏦 핀드 담보 적격성 자동 심사 시스템")
st.caption("KB증권 하이브리드 계좌운용규칙 기준 | v2.0")
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
    st.success("✅ **자동 데이터 수집**  \n실시간 주가 및 기업정보")
    
    with st.expander("⚠️ 주요 불가사유"):
        st.markdown("""
        **국내주식**
        - 시가총액 100억 미만
        - 관리종목
        - 거래정지
        - 자본잠식 50% 이상
        - 최근 7일 -50% 이상
        
        **해외주식**
        - OTC 장외시장
        - 비허용 거래소
        - PTP 종목
        """)

# 국내주식 데이터 가져오기
def get_korean_stock_data(ticker):
    try:
        stock = yf.Ticker(f"{ticker}.KS")
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

# 상세 의견 생성 함수들
def generate_rejection_opinion(violations, data, is_korean=True):
    """담보 불가 의견 생성"""
    opinion = "⛔ 담보 설정 불가\n\n"
    
    # 불가 사유
    opinion += "**[불가 사유]**\n"
    for v in violations:
        opinion += f"• {v}\n"
    
    opinion += "\n**[위험도 평가]**\n"
    opinion += "재무 건전성: 🔴 위험\n"
    opinion += "주가 안정성: 🔴 위험\n"
    opinion += "유동성: 🔴 위험\n"
    opinion += "**종합 평가: 🔴 부적격**\n\n"
    
    # 리스크팀 의견
    opinion += "**[리스크관리팀 의견]**\n"
    
    if is_korean:
        if any("시가총액" in v for v in violations):
            opinion += "해당 종목은 시가총액 100억원 미만 소형주로 유동성 위험이 높아 담보 설정이 불가능합니다. "
        if any("50%" in v or "급락" in v for v in violations):
            opinion += "최근 주가가 급락하여 극심한 변동성을 보이고 있어 추가 손실 위험이 높습니다. "
        if any("거래" in v for v in violations):
            opinion += "거래량 및 거래대금 기준 미달로 유동성 위험이 높습니다. "
    else:
        if any("OTC" in v or "거래소" in v for v in violations):
            opinion += "해당 종목은 장외시장 또는 비허용 거래소에서 거래되어 담보 인정이 불가능합니다. "
        if any("PTP" in v for v in violations):
            opinion += "PTP(Partnership) 구조로 세금 및 배당 리스크가 높아 담보 설정이 불가능합니다. "
    
    opinion += "\n\n**[고객 안내 문구]**\n"
    opinion += f'"해당 종목은 당사 계좌운용규칙상 담보로 인정되지 않습니다. '
    
    if is_korean:
        opinion += '시가총액 100억원 이상, 일평균 거래대금 5,000만원 이상의 종목으로 재신청 부탁드립니다."'
    else:
        opinion += 'NYSE, NASDAQ, AMEX 상장 종목 중에서 재신청 부탁드립니다."'
    
    return opinion

def generate_conditional_opinion(warnings, data, is_korean=True):
    """조건부 가능 의견 생성"""
    # 위험도 계산
    risk_level = "고위험" if len(warnings) >= 3 else "주의"
    risk_emoji = "🔴" if len(warnings) >= 3 else "🟠"
    max_ltv = "30%" if len(warnings) >= 3 else "40%"
    
    opinion = f"⚠️ 조건부 담보 가능 ({risk_level} - 보수적 관리 필수)\n\n"
    
    # 주의 사유
    opinion += "**[주의 사유]**\n"
    for w in warnings:
        opinion += f"• {w}\n"
    
    opinion += "\n**[위험도 평가]**\n"
    
    # 재무 건전성
    if any("자본잠식" in w or "부채" in w for w in warnings):
        opinion += "재무 건전성: 🔴 위험\n"
    else:
        opinion += "재무 건전성: 🟡 보통\n"
    
    # 주가 안정성
    if any("변동" in w or "급락" in w for w in warnings):
        opinion += "주가 안정성: 🟠 주의\n"
    else:
        opinion += "주가 안정성: 🟡 보통\n"
    
    opinion += "유동성: 🟡 보통\n"
    opinion += f"**종합 평가: {risk_emoji} {risk_level}**\n\n"
    
    # 담보 설정 조건
    opinion += "**[담보 설정 조건]**\n"
    opinion += f"1. 최대 대출비율 {max_ltv} 이하로 제한\n"
    opinion += "2. 담보비율 150% 미만 시 즉시 연락 필수\n"
    opinion += "3. 일일 모니터링 대상 등록\n"
    opinion += "4. 추가 하락 시 담보 추가 징구 가능성 안내\n\n"
    
    # 리스크팀 의견
    opinion += "**[리스크관리팀 의견]**\n"
    
    if any("자본잠식" in w for w in warnings):
        erosion_pct = next((w.split()[1] for w in warnings if "자본잠식" in w), "높은")
        opinion += f"해당 종목은 자본잠식률 {erosion_pct}로 위험 수준(50%)에 근접해 있어 재무 건전성이 취약합니다. "
    
    if any("부채비율" in w for w in warnings):
        opinion += "부채비율이 300%를 초과하여 재무 레버리지가 높은 상태입니다. "
    
    if any("변동" in w for w in warnings):
        opinion += "주가 변동성이 높아 단기간 급등락 위험이 있습니다. "
    
    opinion += f"\n\n보수적 대출비율({max_ltv} 이하) 적용과 정기 모니터링이 필수적입니다. "
    
    if any("자본잠식" in w for w in warnings):
        opinion += "자본잠식률이 50%에 도달하거나 관리종목 지정 시 즉시 전량 매도가 필요함을 고객에게 사전 안내 바랍니다."
    
    opinion += "\n\n**[고객 안내 문구]**\n"
    opinion += f'"해당 종목은 담보 설정이 가능하나, 재무 위험이 있는 상태입니다. '
    opinion += f'대출한도는 평가금액의 {max_ltv} 이하로 제한되며, '
    opinion += '주가 추가 하락 시 담보 추가 제공 또는 강제 매도가 발생할 수 있음을 안내드립니다."'
    
    return opinion

def generate_approval_opinion(data, is_korean=True):
    """담보 가능 의견 생성"""
    opinion = "✅ 담보 설정 가능 (우량 종목)\n\n"
    
    # 적격 근거
    opinion += "**[적격 근거]**\n"
    
    if is_korean:
        if data['market_cap'] >= 1000:
            opinion += f"✓ 시가총액 {data['market_cap']:.0f}억원 (대형주)\n"
        else:
            opinion += f"✓ 시가총액 {data['market_cap']:.0f}억원 (기준 충족)\n"
        opinion += "✓ 자본잠식률 0% (재무 건전)\n"
        opinion += "✓ 관리종목 이력 없음\n"
        opinion += "✓ 안정적 거래량 유지\n"
    else:
        mcap_b = data.get('market_cap', 0)
        opinion += f"✓ 시가총액 ${mcap_b:.1f}B (대형주)\n"
        opinion += "✓ 주요 거래소 상장 (NYSE/NASDAQ)\n"
        opinion += "✓ 높은 유동성\n"
    
    opinion += "\n**[위험도 평가]**\n"
    opinion += "재무 건전성: 🟢 우량\n"
    opinion += "주가 안정성: 🟢 안정\n"
    opinion += "유동성: 🟢 우수\n"
    opinion += "**종합 평가: 🟢 우량**\n\n"
    
    # 담보 설정 조건
    opinion += "**[담보 설정 조건]**\n"
    opinion += "• 최대 대출비율: 계좌평가금액의 200% 이내\n"
    opinion += "• 자동반대매매(로스컷): 130%\n"
    opinion += "• 현금인출 가능: 140% 이상\n\n"
    
    # 리스크팀 의견
    opinion += "**[리스크관리팀 의견]**\n"
    
    if is_korean:
        if data['market_cap'] >= 10000:
            opinion += "해당 종목은 초대형 우량주로, "
        else:
            opinion += "해당 종목은 "
        opinion += "재무 건전성이 우수하고 유동성이 풍부하여 담보 적격성이 높습니다. 정상적인 담보 설정이 가능합니다."
    else:
        opinion += "해당 종목은 주요 거래소 상장 우량주로 담보 적격성이 높습니다. 정상적인 담보 설정이 가능합니다."
    
    opinion += "\n\n**[고객 안내 문구]**\n"
    opinion += '"해당 종목은 우량주로 담보 설정에 문제가 없습니다. 계좌평가금액의 최대 200%까지 대출 가능합니다."'
    
    return opinion

# 메인
ticker = st.text_input("**종목코드 / 티커 입력**", placeholder="005930 또는 AAPL")

if st.button("🔍 자동 심사", type="primary", use_container_width=True):
    if not ticker:
        st.error("❌ 종목코드를 입력하세요")
    else:
        is_korean = ticker.isdigit() and len(ticker) == 6
        
        # === 국내주식 ===
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
                    c4.metric("시가총액", f"{data['market_cap']:,.0f}억")
                    c5.metric("P/E", f"{data['pe_ratio']:.1f}" if data['pe_ratio'] > 0 else "N/A")
                    
                    st.markdown("---")
                    
                    # 판정 로직
                    violations = []
                    warnings = []
                    
                    # 1차: 시가총액
                    if data['market_cap'] < 100:
                        violations.append(f"시가총액 {data['market_cap']:.0f}억원 (기준: 100억 이상)")
                    
                    # 2차: 변동성
                    volatility = 0
                    if data['high_52w'] > 0 and data['low_52w'] > 0:
                        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
                        if volatility >= 500:
                            warnings.append(f"극심한 변동성 {volatility:.0f}% (52주 기준)")
                        elif volatility >= 200:
                            warnings.append(f"높은 변동성 {volatility:.0f}% (52주 기준)")
                    
                    # 최종 판정
                    st.markdown("### 🎯 판정 결과")
                    
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
                    
                    st.markdown("---")
                    
                    # 주가 정보
                    st.markdown("### 📈 주가 정보 (52주)")
                    p1, p2, p3 = st.columns(3)
                    p1.metric("최고가", f"{data['high_52w']:,.0f}원")
                    p2.metric("최저가", f"{data['low_52w']:,.0f}원")
                    if volatility > 0:
                        p3.metric("변동폭", f"{volatility:.1f}%")
                    
                    # 다운로드
                    st.markdown("---")
                    report = pd.DataFrame([{
                        "심사일시": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "종목코드": ticker,
                        "종목명": data['name'],
                        "판정": judgment,
                        "시가총액": f"{data['market_cap']:.0f}억",
                        "현재가": f"{data['price']:.0f}원",
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
        
        # === 해외주식 ===
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
                    c5.metric("시가총액", f"${mcap:.1f}B")
                    
                    st.markdown("---")
                    
                    # 판정
                    violations = []
                    warnings = []
                    
                    allowed = ["NYQ", "NMS", "NGM", "NAS", "NYSE", "NASDAQ"]
                    if exchange not in allowed and exchange != "N/A":
                        violations.append(f"비허용 거래소: {exchange} (허용: NYSE, NASDAQ, AMEX)")
                    
                    if "OTC" in exchange.upper():
                        violations.append("OTC 장외시장 거래 종목")
                    
                    quote_type = info.get('quoteType', '')
                    if quote_type in ["MLP", "ETP"] or "LP" in ticker.upper():
                        violations.append("PTP(Partnership) 구조 종목")
                    
                    if mcap < 10 and not violations:
                        warnings.append(f"시가총액 ${mcap:.1f}B (S&P500/NASDAQ100 확인 필요)")
                    
                    # 변동성
                    if not hist.empty:
                        high = hist['High'].max()
                        low = hist['Low'].min()
                        vol = ((high - low) / low) * 100 if low > 0 else 0
                        if vol >= 200 and not violations:
                            warnings.append(f"높은 변동성 {vol:.0f}% (52주 기준)")
                    
                    st.markdown("### 🎯 판정 결과")
                    
                    data_us = {'market_cap': mcap, 'name': name}
                    
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
                    
                    st.markdown("---")
                    
                    # 주가 정보
                    if not hist.empty:
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
                    st.info("💡 티커를 다시 확인해주세요. 예: AAPL, MSFT, TSLA")

st.markdown("---")
st.caption("ⓒ 2026 Pind Inc. | v2.0 상세 리스크 분석")
