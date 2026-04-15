"""
핀드 담보 심사 시스템 v8.0
실전 리스크관리 시스템
"""
import streamlit as st
from datetime import datetime, timedelta
from config import VERSION, SYSTEM_NAME
from modules import (
    fetch_korean_stock,
    fetch_us_stock,
    analyze_korean_stock,
    analyze_us_stock,
    validate_korean_stock_data,
    validate_us_stock_data,
    save_screening_log,
    load_rms_from_server,
    save_rms_to_server,
    get_rms_status,
    get_dart_analysis,
    load_holdings_from_server,
    save_holdings_to_server,
    get_holdings_status,
    get_market_cap_krw,
    find_ticker_by_name,
)
from modules.utils import load_screening_history

st.set_page_config(page_title=SYSTEM_NAME, page_icon="🏦", layout="wide")

# ── 앱 시작 시 서버 파일 자동 로드 ──────────────────────────
if 'rms_df' not in st.session_state:
    df_server, meta_server = load_rms_from_server()
    st.session_state['rms_df']          = df_server
    st.session_state['rms_meta']        = meta_server
    st.session_state['rms_filename']    = meta_server['filename']    if meta_server else None
    st.session_state['rms_uploaded_at'] = meta_server['uploaded_at'] if meta_server else None
    st.session_state['rms_total']       = meta_server['total']       if meta_server else 0
    st.session_state['rms_normal']      = meta_server['normal']      if meta_server else 0
    st.session_state['rms_restricted']  = meta_server['restricted']  if meta_server else 0

if 'holdings_df' not in st.session_state:
    df_holdings, meta_holdings = load_holdings_from_server()
    st.session_state['holdings_df']   = df_holdings
    st.session_state['holdings_meta'] = meta_holdings


# ── RMS 상태 표시 헬퍼 ───────────────────────────────────────
def render_rms_result(ticker: str, screen_eligible: bool):
    df_rms = st.session_state.get('rms_df')
    if df_rms is None:
        return

    rms = get_rms_status(ticker, df_rms)
    if not rms['found']:
        st.info("ℹ️ RMS 미등록 종목")
        return

    rms_ok    = (rms['status'] == '정상')
    screen_ok = screen_eligible

    rms_status_text = (
        f"**RMS 상태**: {rms['status']}"
        + (f" ({rms['raw']})" if rms['raw'] else "")
    )

    if screen_ok and rms_ok:
        st.success(f"🟢 {rms_status_text}\n\n✅ RMS 일치 — 정상")
    elif not screen_ok and not rms_ok:
        st.error(f"🔴 {rms_status_text}\n\n✅ RMS 일치 — 협의 불가")
    elif not screen_ok and rms_ok:
        st.error(f"🟢 {rms_status_text}\n\n🚨 불일치 — RMS 매수금지 재설정 검토 필요")
    else:
        st.warning(f"🔴 {rms_status_text}\n\n⚠️ 불일치 — RMS 매수가능 전환 검토 필요")


# ── 보유현황 표시 헬퍼 ───────────────────────────────────────
def render_holdings(ticker: str, is_korean: bool, data: dict, eligible: bool):
    df_holdings = st.session_state.get('holdings_df')
    if df_holdings is None:
        return

    market_cap_krw = get_market_cap_krw(is_korean, data)
    holdings       = get_holdings_status(ticker, df_holdings, market_cap_krw, eligible)

    if not holdings['found']:
        return

    quantity   = holdings['quantity']
    amount     = holdings['amount']
    accounts   = holdings['accounts']
    level      = holdings['warning_level']
    msg        = holdings['warning_msg']

    amount_str = f"{amount/100000000:.2f}억원" if amount >= 100000000 else f"{amount:,.0f}원"

    content = (
        f"**📦 당사 보유현황**\n\n"
        f"계좌수: {accounts}개 | 보유수량: {quantity:,}주 | 보유금액: {amount_str}"
        f"\n\n{msg}"
    )

    if level == 'danger':
        st.error(content)
    elif level == 'caution':
        st.warning(content)
    else:
        st.success(content)


# ── 국내주식 DART 재무 요약 표시 ─────────────────────────────
def render_dart_summary(dart_summary: dict):
    if not dart_summary:
        return

    st.markdown("### 📊 DART 재무 분석")
    year = dart_summary.get('latest_year', '')

    col1, col2, col3, col4 = st.columns(4)

    erosion = dart_summary.get('erosion_rate')
    if erosion is not None:
        if erosion >= 50:
            col1.metric("자본잠식률", f"{erosion:.1f}%", delta="위험", delta_color="inverse")
        elif erosion >= 30:
            col1.metric("자본잠식률", f"{erosion:.1f}%", delta="주의", delta_color="inverse")
        else:
            col1.metric("자본잠식률", f"{erosion:.1f}%", delta="정상", delta_color="normal")
    elif dart_summary.get('equity') is not None and dart_summary['equity'] <= 0:
        col1.metric("자본잠식률", "완전잠식", delta="위험", delta_color="inverse")
    else:
        col1.metric("자본잠식률", "N/A")

    debt_ratio = dart_summary.get('debt_ratio')
    if debt_ratio is not None:
        if debt_ratio >= 300:
            col2.metric("부채비율", f"{debt_ratio:.0f}%", delta="위험", delta_color="inverse")
        elif debt_ratio >= 200:
            col2.metric("부채비율", f"{debt_ratio:.0f}%", delta="주의", delta_color="inverse")
        else:
            col2.metric("부채비율", f"{debt_ratio:.0f}%", delta="정상", delta_color="normal")
    else:
        col2.metric("부채비율", "N/A")

    opinion    = dart_summary.get('audit_opinion', 'N/A')
    audit_year = dart_summary.get('audit_year', '')
    if opinion in ['부적정', '의견거절']:
        col3.metric("감사의견", opinion, delta="즉시불가", delta_color="inverse")
    elif opinion == '한정':
        col3.metric("감사의견", opinion, delta="주의", delta_color="inverse")
    elif opinion == '적정':
        col3.metric("감사의견", f"{opinion} ({audit_year})", delta="정상", delta_color="normal")
    else:
        col3.metric("감사의견", opinion or "N/A")

    loss_years = dart_summary.get('loss_years', [])
    if len(loss_years) >= 3:
        col4.metric("연속 영업손실", f"{len(loss_years)}년", delta="위험", delta_color="inverse")
    elif len(loss_years) == 2:
        col4.metric("연속 영업손실", f"{len(loss_years)}년", delta="주의", delta_color="inverse")
    elif len(loss_years) == 1:
        col4.metric("연속 영업손실", f"{len(loss_years)}년", delta="모니터링", delta_color="inverse")
    else:
        col4.metric("연속 영업손실", "없음", delta="정상", delta_color="normal")

    risk_discs = dart_summary.get('risk_disclosures', [])
    if risk_discs:
        st.markdown("**⚠️ 최근 위험 공시**")
        for disc in risk_discs:
            d = disc['date']
            st.markdown(f"• {d[:4]}.{d[4:6]}.{d[6:]} — {disc['title']}")

    rev_change = dart_summary.get('revenue_change')
    if rev_change is not None and rev_change <= -30:
        st.warning(f"⚠️ 매출 변동: {rev_change:.1f}% ({year}년 기준)")

    st.markdown("---")


# ── 해외주식 재무 요약 표시 ──────────────────────────────────
def render_us_financial_summary(financial_summary: dict, quote_type: str):
    if not financial_summary or quote_type == 'ETF':
        return

    st.markdown("### 📊 재무 분석")

    col1, col2, col3, col4 = st.columns(4)

    d2e = financial_summary.get('debt_to_equity')
    if d2e is not None:
        if d2e >= 300:
            col1.metric("부채비율", f"{d2e:.0f}%", delta="위험", delta_color="inverse")
        elif d2e >= 200:
            col1.metric("부채비율", f"{d2e:.0f}%", delta="주의", delta_color="inverse")
        else:
            col1.metric("부채비율", f"{d2e:.0f}%", delta="정상", delta_color="normal")
    else:
        col1.metric("부채비율", "N/A")

    roe = financial_summary.get('roe')
    if roe is not None:
        if roe < -20:
            col2.metric("ROE", f"{roe:.1f}%", delta="위험", delta_color="inverse")
        elif roe < 0:
            col2.metric("ROE", f"{roe:.1f}%", delta="적자", delta_color="inverse")
        else:
            col2.metric("ROE", f"{roe:.1f}%", delta="정상", delta_color="normal")
    else:
        col2.metric("ROE", "N/A")

    op_margin = financial_summary.get('operating_margins')
    if op_margin is not None:
        if op_margin < -20:
            col3.metric("영업이익률", f"{op_margin:.1f}%", delta="위험", delta_color="inverse")
        elif op_margin < 0:
            col3.metric("영업이익률", f"{op_margin:.1f}%", delta="적자", delta_color="inverse")
        else:
            col3.metric("영업이익률", f"{op_margin:.1f}%", delta="정상", delta_color="normal")
    else:
        col3.metric("영업이익률", "N/A")

    current_ratio = financial_summary.get('current_ratio')
    if current_ratio is not None:
        if current_ratio < 1.0:
            col4.metric("유동비율", f"{current_ratio:.2f}", delta="부족", delta_color="inverse")
        else:
            col4.metric("유동비율", f"{current_ratio:.2f}", delta="정상", delta_color="normal")
    else:
        col4.metric("유동비율", "N/A")

    rev_growth = financial_summary.get('revenue_growth')
    if rev_growth is not None and rev_growth <= -30:
        st.warning(f"⚠️ 매출 성장률 {rev_growth:.1f}% — 급감")

    st.markdown("---")


# ═══════════════════════════════════════════════════════════
# 사이드바
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.title("🏦 핀드 담보 심사")
    st.caption(f"KB증권 하이브리드 | v{VERSION}")
    st.markdown("---")

    st.header("📖 가이드")
    st.markdown("**국내**: `005930` 또는 `삼성전자`  \n**해외**: `AAPL`")
    st.markdown("---")

    with st.expander("🔴 국내주식 불가 기준"):
        st.markdown("""
        - 관리종목
        - 동전주 (1,000원 미만)
        - 시총 500억 미만
        - 완전자본잠식
        - 감사의견 부적정/의견거절
        - 3년 연속 영업손실
        """)

    with st.expander("🔴 해외주식 불가 기준"):
        st.markdown("""
        - OTC/Pink Sheets
        - Penny Stock ($5 미만)
        - 소형주 ($1B 미만)
        - 거래소 기준 미달
        - 완전자본잠식
        - 고베타 (3.0 초과)
        """)

    with st.expander("📊 국내주식 등급"):
        st.markdown("""
        - 초대형주: 10조+
        - 대형주: 5조~10조
        - 중형주: 5천억~5조
        - 소형주: 500억~5천억

        **변동성 한도** (담보인정비율 조정):
        - 초대형/대형: 500%
        - 중형: 300%
        - 소형: 200%
        """)

    with st.expander("📊 담보인정비율"):
        st.markdown("""
        - 400%+: 0%
        - 350~400%: 30%
        - 300~350%: 50%
        - 250~300%: 70%
        - 200~250%: 80%
        - 200% 미만: 100%
        """)

    with st.expander("⚙️ 2026년 강화 기준"):
        st.markdown("""
        **2026년 7월**:
        - 코스닥 200억 미만 퇴출
        - 동전주 30일 연속 상폐
        - 향후 300억 기준 예정
        """)

    if st.button("🔄 캐시 초기화"):
        st.cache_data.clear()
        st.success("완료!")

    st.markdown("---")

    st.header("📂 RMS 파일")
    if st.session_state['rms_uploaded_at']:
        st.success(
            f"✅ 기준일: {st.session_state['rms_uploaded_at']}\n\n"
            f"📄 {st.session_state['rms_filename']}\n\n"
            f"전체 {st.session_state['rms_total']}개 "
            f"| 정상 {st.session_state['rms_normal']} "
            f"| 제한 {st.session_state['rms_restricted']}"
        )
    else:
        st.warning("⚠️ RMS 파일 없음")

    with st.expander("🔄 RMS 긴급 업로드"):
        st.caption("매일 GitHub 업로드가 기본입니다.\n긴급 시에만 사용하세요.")
        rms_uploaded = st.file_uploader(
            "RMS 파일", type=['xlsx'], key="rms_uploader",
            label_visibility="collapsed"
        )
        if rms_uploaded and rms_uploaded.name != st.session_state.get('rms_filename'):
            try:
                meta_new  = save_rms_to_server(rms_uploaded, rms_uploaded.name)
                df_new, _ = load_rms_from_server()
                st.session_state['rms_df']          = df_new
                st.session_state['rms_filename']    = meta_new['filename']
                st.session_state['rms_uploaded_at'] = meta_new['uploaded_at']
                st.session_state['rms_total']       = meta_new['total']
                st.session_state['rms_normal']      = meta_new['normal']
                st.session_state['rms_restricted']  = meta_new['restricted']
                st.success("✅ 업로드 완료")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 업로드 실패: {e}")

    st.markdown("---")

    st.header("📦 보유수량 파일")
    meta_h = st.session_state.get('holdings_meta')
    if meta_h:
        st.success(
            f"✅ 기준월: {meta_h.get('base_date', 'N/A')}\n\n"
            f"📄 {meta_h.get('filename', '')}\n\n"
            f"전체 {meta_h.get('total', 0)}개 종목"
        )
    else:
        st.warning("⚠️ 보유수량 파일 없음")

    with st.expander("🔄 보유수량 업로드"):
        st.caption("월별 1회 GitHub 업로드가 기본입니다.\n긴급 시에만 사용하세요.")
        h_uploaded = st.file_uploader(
            "보유수량 파일", type=['xlsx'], key="holdings_uploader",
            label_visibility="collapsed"
        )
        if h_uploaded:
            try:
                meta_new  = save_holdings_to_server(h_uploaded, h_uploaded.name)
                df_new, _ = load_holdings_from_server()
                st.session_state['holdings_df']   = df_new
                st.session_state['holdings_meta'] = meta_new
                st.success("✅ 업로드 완료")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 업로드 실패: {e}")


# ═══════════════════════════════════════════════════════════
# 메인 — 탭 구조
# ═══════════════════════════════════════════════════════════
st.title("🏦 핀드 담보 심사 시스템")
st.caption(f"KB증권 하이브리드 계좌운용규칙 | v{VERSION}")

tab1, tab2 = st.tabs(["🔍 종목 심사", "📋 심사 이력"])


# ═══════════════════════════════════════════════════════════
# 탭1 — 종목 심사
# ═══════════════════════════════════════════════════════════
with tab1:
    with st.form(key='search_form', clear_on_submit=False):
        col1, col2, col3 = st.columns([2, 1, 3])
        with col1:
            ticker = st.text_input(
                "종목코드/티커",
                placeholder="005930, 삼성전자, AAPL",
                label_visibility="collapsed"
            )
        with col2:
            search_button = st.form_submit_button(
                "🔍 심사",
                use_container_width=True,
                type="primary"
            )

    if search_button and ticker:
        ticker = ticker.strip()

        # 숫자 6자리가 아닌 경우 종목명으로 검색 시도
        if not (ticker.isdigit() and len(ticker) == 6):
            found_ticker = find_ticker_by_name(ticker)
            if found_ticker:
                ticker = found_ticker
            else:
                st.error(f"❌ '{ticker}' 종목을 찾을 수 없습니다. 종목코드로 검색해주세요.")
                ticker = ""

        if ticker:
            is_korean = ticker.isdigit() and len(ticker) == 6

            if is_korean:
                # ── 국내주식 ──────────────────────────────────
                with st.spinner("분석 중..."):
                    try:
                        data     = fetch_korean_stock(ticker)
                        is_valid, message = validate_korean_stock_data(data)

                        if not is_valid:
                            st.error(f"❌ {message}")
                            st.info("💡 잠시 후 다시 시도하거나 관리자에게 문의하세요")
                        else:
                            dart_data = get_dart_analysis(ticker)
                            analysis  = analyze_korean_stock(data, dart_data)

                            save_screening_log(
                                ticker, data['name'], data['market_cap'],
                                analysis['volatility'], analysis['judgment'],
                                analysis['acceptance_ratio'], analysis['violations']
                            )

                            st.markdown("---")

                            col_j, col_r = st.columns(2)
                            with col_j:
                                if analysis['eligible']:
                                    st.success(f"**✅ {analysis['judgment']}**\n\n위험 등급: {analysis['risk_level']}")
                                else:
                                    st.error(f"**⛔ {analysis['judgment']}**\n\n위험 등급: {analysis['risk_level']}")
                            with col_r:
                                render_rms_result(ticker, analysis['eligible'])

                            render_holdings(ticker, True, data, analysis['eligible'])

                            sector_text = f" · {data.get('sector', '')}" if data.get('sector') != 'N/A' else ""
                            ratio_text  = (
                                f"\n💰 담보인정비율 {analysis['acceptance_ratio']}% ({analysis['ratio_reason']})"
                                if analysis['acceptance_ratio'] < 100 else ""
                            )
                            st.info(
                                f"**{data['name']} ({ticker})** | {data['market']} · {analysis['cap_grade']}{sector_text}  \n"
                                f"시총 {data['market_cap']:,.0f}억 | 현재가 {data['current_price']:,.0f}원 | 변동성 {analysis['volatility']:.1f}%  \n"
                                f"52주 {data['high_52w']:,.0f} ~ {data['low_52w']:,.0f}원 (현재 위치 {analysis['price_position']:.1f}%){ratio_text}"
                            )

                            st.markdown("---")

                            if analysis.get('dart_summary'):
                                render_dart_summary(analysis['dart_summary'])

                            if analysis['violations'] or analysis['risk_factors']:
                                col_v1, col_v2 = st.columns(2)
                                with col_v1:
                                    if analysis['violations']:
                                        st.markdown("**❌ 담보 불가 사유**")
                                        for v in analysis['violations']:
                                            st.markdown(f"• {v.replace('❌ ', '')}")
                                with col_v2:
                                    if analysis['risk_factors']:
                                        st.markdown("**⚠️ 주요 리스크**")
                                        for r in analysis['risk_factors']:
                                            st.markdown(f"• {r.replace('⚠️ ', '')}")

                                st.markdown("---")

                                with st.expander("💼 심사 의견 (상세)", expanded=False):
                                    st.markdown(f"""
**변동성 리스크**
- 52주 변동폭 {analysis['volatility']:.1f}% ({analysis['cap_grade']})

**현재가 위치**
- 52주 범위 중 {analysis['price_position']:.1f}% 지점

**담보인정비율 (권장)**
- 권장: **{analysis['acceptance_ratio']}%**
- 사유: {analysis['ratio_reason']}
- 예시: 1억원 평가 → {analysis['acceptance_ratio'] * 1000000:,.0f}원 인정

**일일 모니터링 필수**

※ 계좌운용규칙(LTV, 로스컷)은 상품별로 상이
                                    """)

                    except Exception as e:
                        st.error(f"❌ 시스템 오류: {str(e)}")
                        st.error("관리자에게 문의하세요")

            else:
                # ── 해외주식 ──────────────────────────────────
                with st.spinner("분석 중..."):
                    try:
                        data     = fetch_us_stock(ticker)
                        is_valid, message = validate_us_stock_data(data)

                        if not is_valid:
                            st.error(f"❌ {message}")
                            st.info("💡 잠시 후 다시 시도하거나 관리자에게 문의하세요")
                        else:
                            analysis = analyze_us_stock(data)

                            save_screening_log(
                                ticker, data['name'], data['mcap'],
                                analysis['volatility'], analysis['judgment'],
                                analysis['acceptance_ratio'], analysis['violations']
                            )

                            st.markdown("---")

                            col_j, col_r = st.columns(2)
                            with col_j:
                                if analysis['eligible']:
                                    st.success(f"**✅ {analysis['judgment']}**\n\n위험 등급: {analysis['risk_level']}")
                                else:
                                    st.error(f"**⛔ {analysis['judgment']}**\n\n위험 등급: {analysis['risk_level']}")
                            with col_r:
                                render_rms_result(ticker.upper(), analysis['eligible'])

                            render_holdings(ticker.upper(), False, data, analysis['eligible'])

                            sector_text = ""
                            if data.get('sector') != 'N/A':
                                sector_text += f" · {data['sector']}"
                            if data.get('industry') != 'N/A' and data.get('industry') != data.get('sector'):
                                sector_text += f" · {data['industry']}"

                            mcap_display = f"${data['mcap']:.2f}B" if data['mcap'] > 0 else "조회불가"
                            ratio_text   = (
                                f"\n💰 담보인정비율 {analysis['acceptance_ratio']}% ({analysis['ratio_reason']})"
                                if analysis['acceptance_ratio'] < 100 else ""
                            )
                            st.info(
                                f"**{data['name']} ({ticker.upper()})** | {data['exchange']} · {analysis.get('cap_category', 'N/A')}{sector_text}  \n"
                                f"{data['mcap_label']} {mcap_display} | 현재가 ${data['price']:.2f} | 변동성 {analysis['volatility']:.1f}%  \n"
                                f"52주 ${data['high_52w']:.2f} ~ ${data['low_52w']:.2f} (현재 위치 {analysis['price_position']:.1f}%){ratio_text}"
                            )

                            st.markdown("---")

                            if analysis.get('financial_summary'):
                                render_us_financial_summary(
                                    analysis['financial_summary'],
                                    data.get('quote_type', '')
                                )

                            if analysis['violations'] or analysis['risk_factors']:
                                col_v1, col_v2 = st.columns(2)
                                with col_v1:
                                    if analysis['violations']:
                                        st.markdown("**❌ 담보 불가 사유**")
                                        for v in analysis['violations']:
                                            st.markdown(f"• {v.replace('❌ ', '')}")
                                with col_v2:
                                    if analysis['risk_factors']:
                                        st.markdown("**⚠️ 주요 리스크**")
                                        for r in analysis['risk_factors']:
                                            st.markdown(f"• {r.replace('⚠️ ', '')}")

                                st.markdown("---")

                                with st.expander("💼 심사 의견 (상세)", expanded=False):
                                    st.markdown(f"""
**변동성 리스크**
- 52주 변동폭 {analysis['volatility']:.1f}%

**현재가 위치**
- 52주 범위 중 {analysis['price_position']:.1f}% 지점

**담보인정비율 (권장)**
- 권장: **{analysis['acceptance_ratio']}%**
- 사유: {analysis['ratio_reason']}
- 예시: $100,000 평가 → ${analysis['acceptance_ratio'] * 1000:,.0f} 인정

**일일 모니터링 필수**

※ 계좌운용규칙은 상품별로 상이
                                    """)

                    except Exception as e:
                        st.error(f"❌ 시스템 오류: {str(e)}")
                        st.error("관리자에게 문의하세요")

    elif search_button:
        st.error("❌ 종목코드를 입력하세요")


# ═══════════════════════════════════════════════════════════
# 탭2 — 심사 이력
# ═══════════════════════════════════════════════════════════
with tab2:
    st.markdown("### 📋 심사 이력 조회")

    df_history = load_screening_history()

    if df_history.empty:
        st.info("아직 심사 이력이 없습니다. 종목 심사 탭에서 심사를 진행해주세요.")
    else:
        col_f1, col_f2 = st.columns(2)

        with col_f1:
            period = st.radio(
                "기간",
                ["오늘", "최근 7일", "최근 30일", "전체"],
                horizontal=True
            )

        with col_f2:
            result_filter = st.radio(
                "판정",
                ["전체", "담보 인정 가능", "담보 인정 불가"],
                horizontal=True
            )

        now = datetime.now()
        if period == "오늘":
            df_filtered = df_history[df_history['일시'].dt.date == now.date()]
        elif period == "최근 7일":
            df_filtered = df_history[df_history['일시'] >= now - timedelta(days=7)]
        elif period == "최근 30일":
            df_filtered = df_history[df_history['일시'] >= now - timedelta(days=30)]
        else:
            df_filtered = df_history.copy()

        if result_filter != "전체":
            df_filtered = df_filtered[df_filtered['판정'] == result_filter]

        df_filtered = (
            df_filtered
            .sort_values('일시', ascending=False)
            .drop_duplicates(subset=['종목코드'], keep='first')
            .reset_index(drop=True)
        )

        total      = len(df_filtered)
        eligible   = (df_filtered['판정'] == '담보 인정 가능').sum()
        ineligible = total - eligible

        c1, c2, c3 = st.columns(3)
        c1.metric("전체 종목", f"{total}개")
        c2.metric("담보 가능", f"{eligible}개")
        c3.metric("담보 불가", f"{ineligible}개",
                  delta=f"{ineligible}개" if ineligible > 0 else None,
                  delta_color="inverse")

        st.markdown("---")

        def highlight_judgment(val):
            if val == '담보 인정 가능':
                return 'color: #28a745; font-weight: bold'
            elif val == '담보 인정 불가':
                return 'color: #dc3545; font-weight: bold'
            return ''

        display_cols = ['일시', '종목코드', '종목명', '시총', '변동성', '판정', '담보인정비율', '주요사유']
        df_display = df_filtered[display_cols].copy()
        df_display['일시'] = df_display['일시'].dt.strftime('%Y-%m-%d %H:%M')
        df_display['변동성'] = df_display['변동성'].apply(
            lambda x: f"{float(x):.1f}%" if x != 'N/A' else x
        )

        st.dataframe(
            df_display.style.applymap(highlight_judgment, subset=['판정']),
            use_container_width=True,
            hide_index=True,
            height=500
        )

st.markdown("---")
st.caption(f"ⓒ 2026 FINDE | 리스크 관리 시스템 v{VERSION}")
