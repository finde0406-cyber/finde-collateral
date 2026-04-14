"""
리스크 분석
변동성: 담보인정비율만 조정 (불가 판정 없음)
backup_warning: 경고만 표시 (불가 판정 없음)
"""
from config import KOREAN_STOCK, US_STOCK, ACCEPTANCE_RATIO


def calculate_acceptance_ratio(violations, volatility):
    """담보인정비율 계산 - 재무/상폐 위험만 0% 처리"""
    if any('관리종목' in v or '동전주' in v or '시총' in v or
           '자본잠식' in v or '감사의견' in v or '영업손실' in v for v in violations):
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


def analyze_dart_data(dart_data: dict) -> tuple:
    """DART 데이터 분석 → violations, risk_factors, dart_summary 반환"""
    violations   = []
    risk_factors = []
    dart_summary = {}

    if not dart_data or not dart_data.get('available'):
        return violations, risk_factors, dart_summary

    if dart_data.get('error'):
        return violations, risk_factors, dart_summary

    # ── 재무제표 분석 ──────────────────────────────────────
    financial = dart_data.get('financial', [])
    if financial:
        latest    = financial[0]
        equity    = latest.get('equity')
        debt      = latest.get('debt')
        op_income = latest.get('op_income')
        year      = latest.get('year')

        dart_summary['latest_year'] = year

        if equity is not None and debt is not None:
            total_assets = equity + debt
            dart_summary['equity']       = equity
            dart_summary['debt']         = debt
            dart_summary['total_assets'] = total_assets

            # 완전자본잠식 → 담보 불가
            if equity <= 0:
                violations.append(f"❌ 완전자본잠식 ({year}년 자본총계 {equity/100000000:,.0f}억)")
                risk_factors.append("상장폐지 실질심사 대상 가능")
            elif total_assets > 0:
                erosion_rate = (1 - equity / total_assets) * 100
                dart_summary['erosion_rate'] = erosion_rate
                # 자본잠식 50% 이상 → 담보 불가
                if erosion_rate >= 50:
                    violations.append(f"❌ 자본잠식률 {erosion_rate:.1f}% ({year}년) — 관리종목 기준 초과")
                    risk_factors.append("자본잠식 50% 이상 — 관리종목 지정 가능")
                elif erosion_rate >= 30:
                    risk_factors.append(f"⚠️ 자본잠식률 {erosion_rate:.1f}% ({year}년) — 주의 필요")

            # 부채비율 → 경고만
            if equity > 0:
                debt_ratio = (debt / equity) * 100
                dart_summary['debt_ratio'] = debt_ratio
                if debt_ratio >= 300:
                    risk_factors.append(f"⚠️ 부채비율 {debt_ratio:.0f}% ({year}년) — 재무 위험")

        # 영업손실 연속 체크
        if len(financial) >= 2:
            loss_years = [f['year'] for f in financial
                          if f.get('op_income') is not None and f['op_income'] < 0]
            dart_summary['loss_years'] = loss_years
            # 3년 연속 → 담보 불가
            if len(loss_years) >= 3:
                violations.append(f"❌ 3년 연속 영업손실 ({', '.join(map(str, loss_years))})")
                risk_factors.append("상장폐지 실질심사 대상 가능")
            elif len(loss_years) == 2:
                risk_factors.append(f"⚠️ 2년 연속 영업손실 ({', '.join(map(str, loss_years))})")

        # 매출 급감
        if len(financial) >= 2:
            rev_latest = financial[0].get('revenue')
            rev_prev   = financial[1].get('revenue')
            if rev_latest and rev_prev and rev_prev > 0:
                rev_change = (rev_latest - rev_prev) / rev_prev * 100
                dart_summary['revenue_change'] = rev_change
                if rev_change <= -50:
                    violations.append(
                        f"❌ 매출 급감 {rev_change:.1f}% "
                        f"({financial[1]['year']}→{financial[0]['year']})"
                    )
                elif rev_change <= -30:
                    risk_factors.append(
                        f"⚠️ 매출 감소 {rev_change:.1f}% "
                        f"({financial[1]['year']}→{financial[0]['year']})"
                    )

    # ── 감사의견 분석 ──────────────────────────────────────
    audit      = dart_data.get('audit', {})
    opinion    = audit.get('opinion', '')
    audit_year = audit.get('year', '')

    if opinion:
        dart_summary['audit_opinion'] = opinion
        dart_summary['audit_year']    = audit_year

        if any(kw in opinion for kw in ['부적정', '의견거절']):
            violations.append(f"❌ 감사의견 '{opinion}' ({audit_year}년) — 즉시 담보 불가")
            risk_factors.append("감사의견 부적정/의견거절 — 상장폐지 사유")
        elif '한정' in opinion:
            risk_factors.append(f"⚠️ 감사의견 '한정' ({audit_year}년) — 재무 신뢰성 주의")

    # ── 위험 공시 분석 ──────────────────────────────────────
    risk_disclosures = dart_data.get('risk_disclosures', [])
    if risk_disclosures:
        dart_summary['risk_disclosures'] = risk_disclosures
        for disc in risk_disclosures[:3]:
            d = disc['date']
            risk_factors.append(
                f"⚠️ 위험공시: {disc['title']} ({d[:4]}.{d[4:6]}.{d[6:]})"
            )

    return violations, risk_factors, dart_summary


def analyze_korean_stock(data, dart_data=None):
    """국내주식 리스크 분석"""
    market_cap     = data['market_cap']
    current_price  = data['current_price']
    dept           = data.get('dept', '')

    volatility     = 0
    price_position = 0

    if data['low_52w'] > 0:
        volatility     = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
        price_position = ((current_price - data['low_52w']) /
                          (data['high_52w'] - data['low_52w'])) * 100

    violations   = []
    risk_factors = []

    # ── 기본 심사 ───────────────────────────────────────────
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

    # backup_warning → 경고만 표시 (불가 판정 없음)
    if data.get('backup_warning'):
        risk_factors.append("⚠️ 관리종목 실시간 확인 불가 (수동 확인 필요)")

    # ── 시총 등급 분류 ──────────────────────────────────────
    limits = KOREAN_STOCK['volatility_limits']

    if market_cap >= 100000:
        cap_grade        = "초대형주"
        volatility_limit = limits['mega']
    elif market_cap >= 50000:
        cap_grade        = "대형주"
        volatility_limit = limits['large']
    elif market_cap >= 5000:
        cap_grade        = "중형주"
        volatility_limit = limits['mid']
    elif market_cap >= min_cap:
        cap_grade        = "소형주"
        volatility_limit = limits['small']
    else:
        cap_grade        = "극소형주"
        volatility_limit = limits['micro']

    # ── 변동성 → 경고만 표시, 담보인정비율로만 반영 ────────
    if volatility >= volatility_limit and market_cap >= min_cap:
        risk_factors.append(
            f"⚠️ 높은 변동성 {volatility:.1f}% ({cap_grade} 기준 {volatility_limit}%)"
        )
        risk_factors.append(
            f"52주 {data['high_52w']:,.0f}원 ~ {data['low_52w']:,.0f}원 "
            f"(현재 위치 {price_position:.1f}%)"
        )
        if price_position > 80:
            risk_factors.append("고점권 — 하락 위험")
        elif price_position > 60:
            risk_factors.append("중상단 — 조정 가능성")
        elif price_position > 40:
            risk_factors.append("중간 — 양방향 변동")
        elif price_position > 20:
            risk_factors.append("중하단 — 변동성 주의")
        else:
            risk_factors.append("저점권 — 추가 하락 가능")

    # ── DART 데이터 심사 ────────────────────────────────────
    dart_summary = {}
    if dart_data:
        dart_violations, dart_risks, dart_summary = analyze_dart_data(dart_data)
        violations   += dart_violations
        risk_factors += dart_risks

    acceptance_ratio, ratio_reason = calculate_acceptance_ratio(violations, volatility)

    if violations:
        judgment   = "담보 인정 불가"
        risk_level = "🔴 높음"
        eligible   = False
    else:
        judgment   = "담보 인정 가능"
        risk_level = "🟢 낮음"
        eligible   = True

    return {
        'judgment'        : judgment,
        'risk_level'      : risk_level,
        'eligible'        : eligible,
        'violations'      : violations,
        'risk_factors'    : risk_factors,
        'volatility'      : volatility,
        'price_position'  : price_position,
        'cap_grade'       : cap_grade,
        'market_cap'      : market_cap,
        'current_price'   : current_price,
        'acceptance_ratio': acceptance_ratio,
        'ratio_reason'    : ratio_reason,
        'dart_summary'    : dart_summary,
    }


def analyze_us_stock(data):
    """해외주식 리스크 분석"""
    exchange   = data['exchange']
    mcap       = data['mcap']
    price      = data['price']
    quote_type = data['quote_type']
    volume     = data.get('volume', 0)
    beta       = data.get('beta', 0)

    volatility     = 0
    price_position = 0

    if data['low_52w'] > 0:
        volatility     = ((data['high_52w'] - data['low_52w']) / data['low_52w']) * 100
        price_position = ((price - data['low_52w']) /
                          (data['high_52w'] - data['low_52w'])) * 100

    violations   = []
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
            violations.append("❌ 나스닥 기준 미달")
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
        cap_category     = "초대형주"
        volatility_limit = limits['mega']
    elif mcap >= 10:
        cap_category     = "대형주"
        volatility_limit = limits['large']
    elif mcap >= 2:
        cap_category     = "중형주"
        volatility_limit = limits['mid']
    elif mcap >= 1:
        cap_category     = "소형주"
        volatility_limit = limits['small']
    else:
        cap_category     = "극소형주"
        volatility_limit = limits['micro']

    # 변동성 → 경고만 표시
    if volatility >= volatility_limit:
        risk_factors.append(
            f"⚠️ 높은 변동성 {volatility:.1f}% ({cap_category} 기준 {volatility_limit}%)"
        )
        risk_factors.append(
            f"52주 ${data['high_52w']:.2f} ~ ${data['low_52w']:.2f} "
            f"(현재 위치 {price_position:.1f}%)"
        )
        if price_position > 80:
            risk_factors.append("고점권 — 하락 위험")
        elif price_position > 60:
            risk_factors.append("중상단 — 조정 가능성")
        elif price_position > 40:
            risk_factors.append("중간 — 양방향 변동")
        elif price_position > 20:
            risk_factors.append("중하단 — 변동성 주의")
        else:
            risk_factors.append("저점권 — 추가 하락 가능")

    if beta > US_STOCK['max_beta']:
        violations.append(f"❌ 고베타 {beta:.2f}")

    acceptance_ratio, ratio_reason = calculate_acceptance_ratio(violations, volatility)

    if violations:
        judgment   = "담보 인정 불가"
        risk_level = "🔴 높음"
        eligible   = False
    else:
        judgment   = "담보 인정 가능"
        risk_level = "🟢 낮음"
        eligible   = True

    return {
        'judgment'        : judgment,
        'risk_level'      : risk_level,
        'eligible'        : eligible,
        'violations'      : violations,
        'risk_factors'    : risk_factors,
        'volatility'      : volatility,
        'price_position'  : price_position,
        'mcap'            : mcap,
        'price'           : price,
        'quote_type'      : quote_type,
        'cap_category'    : cap_category,
        'acceptance_ratio': acceptance_ratio,
        'ratio_reason'    : ratio_reason,
        'dart_summary'    : {},
    }
