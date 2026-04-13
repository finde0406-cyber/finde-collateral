"""
리스크 분석
"""
from config import KOREAN_STOCK, US_STOCK, ACCEPTANCE_RATIO

def calculate_acceptance_ratio(violations, volatility):
    """담보인정비율 계산"""
    if any('관리종목' in v or '동전주' in v or '시총' in v for v in violations):
        return 0, "상장폐지 위험"
    
    for threshold, ratio in sorted(ACCEPTANCE_RATIO.items(), reverse=True):
        if volatility >= threshold:
            if ratio == 0:
                return 0, f"극심한 변동성 ({threshold}% 이상)"
            else:
                if threshold == 350:
                    desc = "350~400%"
                elif threshold == 300:
                    desc = "300~350%"
                elif threshold == 250:
                    desc = "250~300%"
                elif threshold == 200:
                    desc = "200~250%"
                else:
                    desc = f"{threshold}% 이상"
                return ratio, f"변동성 {desc}"
    
    return 100, "정상 변동성"

def analyze_korean_stock(data):
    """국내주식 리스크 분석"""
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
        violations.append("❌ 관리종목")
        risk_factors.append("상장폐지 가능성")
    
    if current_price < KOREAN_STOCK['min_price']:
        violations.append(f"❌ 동전주 {current_price:,.0f}원")
        risk_factors.append("30일 연속 시 상폐")
    
    min_cap = KOREAN_STOCK['min_market_cap']
    if market_cap < min_cap:
        if market_cap < 100:
            violations.append(f"❌ 극소형주 {market_cap:,.0f}억")
        elif market_cap < 200:
            violations.append(f"❌ 시총 {market_cap:,.0f}억 (2026.7 퇴출)")
        else:
            violations.append(f"❌ 시총 {market_cap:,.0f}억")
        risk_factors.append("유동성 부족")
    
    if data.get('backup_warning'):
        violations.append("❌ 관리종목 확인 불가")
    
    limits = KOREAN_STOCK['volatility_limits']
    
    if market_cap >= 100000:
        cap_grade = "초대형주"
        volatility_limit = limits['mega']
    elif market_cap >= 50000:
        cap_grade = "대형주"
        volatility_limit = limits['large']
    elif market_cap >= 5000:
        cap_grade = "중형주"
        volatility_limit = limits['mid']
    elif market_cap >= min_cap:
        cap_grade = "소형주"
        volatility_limit = limits['small']
    else:
        cap_grade = "극소형주"
        volatility_limit = limits['micro']
    
    if volatility >= volatility_limit and market_cap >= min_cap:
        violations.append(f"❌ 극심한 변동성 {volatility:.1f}% ({cap_grade} {volatility_limit}% 초과)")
        risk_factors.append(f"52주 고가 {data['high_52w']:,.0f}원 / 저가 {data['low_52w']:,.0f}원")
        risk_factors.append(f"현재 위치: {price_position:.1f}%")
        
        if price_position > 80:
            risk_factors.append("고점권 - 하락 위험")
        elif price_position > 60:
            risk_factors.append("중상단 - 조정 가능성")
        elif price_position > 40:
            risk_factors.append("중간 - 양방향 변동")
        elif price_position > 20:
            risk_factors.append("중하단 - 변동성 주의")
        else:
            risk_factors.append("저점권 - 추가 하락 가능")
    
    acceptance_ratio, ratio_reason = calculate_acceptance_ratio(violations, volatility)
    
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

def analyze_us_stock(data):
    """해외주식 리스크 분석"""
    exchange = data['exchange']
    mcap = data['mcap']
    price = data['price']
    quote_type = data['quote_type']
    volume = data.get('volume', 0)
    beta = data.get('beta', 0)
    
    volatility = 0
    price_position = 0
    
    if data['low_52w'] > 0:
        volatility = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
        price_position = ((price - data['low_52w']) / (data['high_52w'] - data['low_52w'])) * 100
    
    violations = []
    risk_factors = []
    
    allowed = US_STOCK['allowed_exchanges']
    
    if "OTC" in exchange.upper():
        violations.append("❌ OTC 장외시장")
    elif "PINK" in exchange.upper():
        violations.append("❌ Pink Sheets")
    elif exchange not in allowed and exchange != "N/A":
        violations.append(f"❌ 비허용 거래소: {exchange}")
    
    if exchange == "NASDAQ":
        if price < 1.0:
            violations.append(f"❌ 나스닥 기준 미달")
        if mcap > 0 and mcap < 0.050:
            violations.append("❌ 나스닥 시총 미달")
    
    if exchange == "NYSE":
        if price < 1.0:
            violations.append("❌ NYSE 저가주")
        if mcap > 0 and mcap < 0.025:
            violations.append("❌ NYSE 시총 미달")
    
    if price < US_STOCK['min_price']:
        violations.append(f"❌ Penny Stock (${price:.2f})")
    
    min_mcap = US_STOCK['min_market_cap']
    if quote_type == "ETF":
        if mcap < 0.1:
            violations.append("❌ 소규모 ETF")
    else:
        if mcap > 0 and mcap < min_mcap:
            violations.append(f"❌ 소형주 (${mcap:.2f}B)")
    
    if quote_type in ["MLP", "ETP"]:
        violations.append("❌ PTP 구조")
    
    if volume > 0 and volume < US_STOCK['min_volume']:
        violations.append("❌ 거래량 부족")
    
    limits = US_STOCK['volatility_limits']
    
    if mcap >= 50:
        cap_category = "초대형주"
        volatility_limit = limits['mega']
    elif mcap >= 10:
        cap_category = "대형주"
        volatility_limit = limits['large']
    elif mcap >= 2:
        cap_category = "중형주"
        volatility_limit = limits['mid']
    elif mcap >= 1:
        cap_category = "소형주"
        volatility_limit = limits['small']
    else:
        cap_category = "극소형주"
        volatility_limit = limits['micro']
    
    if volatility >= volatility_limit:
        violations.append(f"❌ 극심한 변동성 {volatility:.1f}% ({cap_category} {volatility_limit}% 초과)")
        risk_factors.append(f"52주 고가 ${data['high_52w']:.2f} / 저가 ${data['low_52w']:.2f}")
        risk_factors.append(f"현재 위치: {price_position:.1f}%")
        
        if price_position > 80:
            risk_factors.append("고점권 - 하락 위험")
        elif price_position > 60:
            risk_factors.append("중상단 - 조정 가능성")
        elif price_position > 40:
            risk_factors.append("중간 - 양방향 변동")
        elif price_position > 20:
            risk_factors.append("중하단 - 변동성 주의")
        else:
            risk_factors.append("저점권 - 추가 하락 가능")
    
    if beta > US_STOCK['max_beta']:
        violations.append(f"❌ 고베타 {beta:.2f}")
    
    acceptance_ratio, ratio_reason = calculate_acceptance_ratio(violations, volatility)
    
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