"""
핀드 담보 심사 시스템 v8.0
실전 리스크관리 시스템
"""
import streamlit as st
from datetime import datetime
from config import VERSION, SYSTEM_NAME
from modules import (
    fetch_korean_stock,
    fetch_us_stock,
    analyze_korean_stock,
    analyze_us_stock,
    validate_korean_stock_data,
    validate_us_stock_data,
    save_screening_log,
    export_to_excel,
    parse_rms_excel,
    get_rms_status,
    get_dart_analysis,
)

st.set_page_config(page_title=SYSTEM_NAME, page_icon="🏦", layout="wide")

# ── session_state 초기화 ─────────────────────────────────────
if 'rms_df' not in st.session_state:
    st.session_state['rms_df']          = None
    st.session_state['rms_filename']    = None
    st.session_state['rms_uploaded_at'] = None
    st.session_state['rms_total']       = 0
    st.session_state['rms_normal']      = 0
    st.session_state['rms_restricted']  = 0


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


# ── DART 재무 요약 표시 헬퍼 ────────────────────────────────
def render_dart_summary(dart_summary: dict):
    """DART 재무 요약 박스 표시"""
    if not dart_summary:
        return

    st.markdown("### 📊 DART 재무 분석")

    year = dart_summary.get('latest_year', '')

    col1, col2, col3, col4 = st.columns(4)

    # 자본잠식률
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

    # 부채비율
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

    # 감사의견
    opinion = dart_summary.get('audit_opinion', 'N/A')
    audit_year = dart_summary.get('audit_year', '')
    if opinion in ['부적정', '의견거절']:
        col3.metric("감사의견", opinion, delta="즉시불가", delta_color="inverse")
    elif opinion == '한정':
        col3.metric("감사의견", opinion, delta="주의", delta_color="inverse")
    elif opinion == '적정':
        col3.metric("감사의견", f"{opinion} ({audit_year})", delta="정상", delta_color="normal")
    else:
        col3.metric("감사의견", opinion or "N/A")

    # 영업손실 연속
    loss_years = dart_summary.get('loss_years', [])
    if len(loss_years) >= 3:
        col4.metric("연속 영업손실", f"{len(loss_years)}년", delta="위험", delta_color="inverse")
    elif len(loss_years) == 2:
        col4.metric("연속 영업손실", f"{len(loss_years)}년", delta="주의", delta_color="inverse")
    elif len(loss_years) == 1:
        col4.metric("연속 영업손실", f"{len(loss_years)}년", delta="모니터링", delta_color="inverse")
    else:
        col4.metric("연속 영업손실", "없음", delta="정상", delta_color="normal")

    # 위험 공시
    risk_discs = dart_summary.get('risk_disclosures', [])
    if risk_discs:
        st.markdown("**⚠️ 최근 위험 공시**")
        for disc in risk_discs:
            date_str = disc['date']
            formatted = f"{date_str[:4]}.{date_str[4:6]}.{date_str[6:]}"
            st.markdown(f"• {formatted} — {disc['title']}")

    # 매출 변동
    rev_change = dart_summary.get('revenue_change')
    if rev_change is not None and rev_change <= -30:
        st.warning(f"⚠️ 매출 변동: {rev_change:.1f}% ({year}년 기준)")

    st.markdown("---")


# ═══════════════════════════════════════════════════════════
# 사이드바
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.title("🏦 핀드 담보 심사")
    st.caption(f"KB증권 하이브리드 | v{VERSION}")
    st.markdown("---")

    # ── RMS 파일 업로드 ──────────────────────────────────────
    st.header("📂 RMS 파일")

    if st.session_state['rms_uploaded_at']:
        st.success(
            f"✅ 업로드: {st.session_state['rms_uploaded_at']}\n\n"
            f"📄 {st.session_state['rms_filename']}\n\n"
            f"전체 {st.session_state['rms_total']}개 "
            f"| 정상 {st.session_state['rms_normal']} "
            f"| 제한 {st.session_state['rms_restricted']}"
        )
    else:
        st.warning("⚠️ RMS 파일 미업로드")

    uploaded = st.file_uploader(
        "RMS일별종목관리현황_YYYYMMDD.xlsx",
        type=['xlsx'],
        label_visibility="collapsed"
    )

    if uploaded and uploaded.name != st.session_state.get('rms_filename'):
        try:
            df_rms = parse_rms_excel(uploaded)
            from datetime import timezone, timedelta
            kst     = timezone(timedelta(hours=9))
            now_kst = datetime.now(kst).strftime('%Y-%m-%d %H:%M')
            st.session_state['rms_df']          = df_rms
            st.session_state['rms_filename']    = uploaded.name
            st.session_state['rms_uploaded_at'] = now_kst
            st.session_state['rms_total']       = len(df_rms)
            st.session_state['rms_normal']      = int((df_rms['RMS상태'] == '정상').sum())
            st.session_state['rms_restricted']  = int((df_rms['RMS상태'] != '정상').sum())
            st.rerun()
        except Exception as e:
            st.error(f"❌ 업로드 실패: {e}")

    st.markdown("---")

    # ── 심사 기준 안내 ────────────────────────────────────────
    st.header("📖 가이드")
    st.markdown("**국내**: `005930`  \n**해외**: `AAPL`")
    st.markdown("---")

    with st.expander("🔴 국내주식 불가 기준"):
        st.markdown("""
        - 관리종목
        - 동전주 (1,000원 미만)
        - 시총 500억 미만
        - 변동성 극심
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
        - 변동성 극심
        """)

    with st.expander("📊 국내주식 등급"):
        st.markdown("""
        **시총 순위 기준 (근사치)**:
        - 초대형주: 10조+
        - 대형주: 5조~10조 (상위 100위)
        - 중형주: 5천억~5조 (상위 300위)
        - 소형주: 500억~5천억 (301위+)

        **변동성 한도**:
        - 초대형/대형: 500%
        - 중형: 300%
        - 소형: 200%
        """)

    with st.expander("📊 담보인정비율"):
        st.markdown("""
        **변동성 기준**:
        - 400%+: 0%
        - 350~400%: 30%
        - 300~350%: 50%
        - 250~300%: 70%
        - 200~250%: 80%
        - 200% 미만: 100%

        **예시**:
        평가 1억원 × 70% = 7천만원 인정
        → 대출 가능 1.4억원 (LTV 200%)
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


# ═══════════════════════════════════════════════════════════
# 메인
# ═══════════════════════════════════════════════════════════
st.title("🏦 핀드 담보 심사 시스템")
st.caption(f"KB증권 하이브리드 계좌운용규칙 | v{VERSION}")

with st.form(key='search_form', clear_on_submit=False):
    col1, col2, col3 = st.columns([2, 1, 3])
    with col1:
        ticker = st.text_input(
            "종목코드/티커",
            placeholder="005930, AAPL",
            label_visibility="collapsed"
        )
    with col2:
        search_button = st.form_submit_button(
            "🔍 심사",
            use_container_width=True,
            type="primary"
        )

if search_button and ticker:
    is_korean = ticker.isdigit() and len(ticker) == 6

    if is_korean:
        # ── 국내주식 ──────────────────────────────────────────
        with st.spinner("분석 중..."):
            try:
                data = fetch_korean_stock(ticker)
                is_valid, message = validate_korean_stock_data(data)
                if not is_valid:
                    st.error(f"❌ {message}")
                    st.info("💡 잠시 후 다시 시도하거나 관리자에게 문의하세요")
                    st.stop()

                # DART 분석 (국내주식만)
                dart_data = get_dart_analysis(ticker)

                analysis = analyze_korean_stock(data, dart_data)

                save_screening_log(
                    ticker,
                    data['name'],
                    data['market_cap'],
                    analysis['volatility'],
                    analysis['judgment'],
                    analysis['acceptance_ratio'],
                    analysis['violations']
                )

                st.markdown("---")

                # 판정 + RMS 상태 나란히
                col_j, col_r = st.columns(2)
                with col_j:
                    if analysis['eligible']:
                        st.success(f"**✅ {analysis['judgment']}**\n\n위험 등급: {analysis['risk_level']}")
                    else:
                        st.error(f"**⛔ {analysis['judgment']}**\n\n위험 등급: {analysis['risk_level']}")
                with col_r:
                    render_rms_result(ticker, analysis['eligible'])

                # 통합 정보 박스
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

                # DART 재무 요약
                if analysis.get('dart_summary'):
                    render_dart_summary(analysis['dart_summary'])

                # 불가 사유 및 리스크
                if analysis['violations']:
                    col_v1, col_v2 = st.columns(2)
                    with col_v1:
                        st.markdown("**❌ 담보 불가 사유**")
                        for v in analysis['violations']:
                            st.markdown(f"• {v.replace('❌ ', '')}")
                    with col_v2:
                        st.markdown("**⚠️ 주요 리스크**")
                        for r in analysis['risk_factors']:
                            st.markdown(f"• {r}")

                    st.markdown("---")

                    with st.expander("💼 심사 의견 (상세)", expanded=False):
                        st.markdown(f"""
**변동성 리스크**
- 52주 변동폭 {analysis['volatility']:.1f}%는 {analysis['cap_grade']}로서 {'매우 높은' if analysis['volatility'] > 300 else '높은'} 수준

**현재가 위치**
- 52주 범위 중 {analysis['price_position']:.1f}% 지점
- 최고가 대비 {100 - analysis['price_position']:.1f}% 하락 여력
- 최저가 대비 {analysis['price_position']:.1f}% 상승한 상태

**담보인정비율 (권장)**
- 권장: **{analysis['acceptance_ratio']}%**
- 사유: {analysis['ratio_reason']}
- 예시: 1억원 평가 → {analysis['acceptance_ratio'] * 1000000:,.0f}원 인정

**일일 모니터링 필수**

※ 계좌운용규칙(LTV, 로스컷)은 상품별로 상이
※ DART 재무제표 확인 후 조정 가능성 검토
                        """)

                st.markdown("---")
                col_d1, col_d2, col_d3 = st.columns([1, 1, 2])
                with col_d1:
                    if st.button("📥 엑셀로 다운로드", use_container_width=True):
                        filename = export_to_excel(ticker, data, analysis)
                        if filename:
                            with open(filename, 'rb') as f:
                                st.download_button(
                                    label="⬇️ 파일 다운로드",
                                    data=f,
                                    file_name=filename,
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True
                                )
                            st.success("✅ 생성 완료")
                        else:
                            st.error("생성 실패")

            except Exception as e:
                st.error(f"❌ 시스템 오류: {str(e)}")
                st.error("관리자에게 문의하세요")

    else:
        # ── 해외주식 ──────────────────────────────────────────
        with st.spinner("분석 중..."):
            try:
                data = fetch_us_stock(ticker)
                is_valid, message = validate_us_stock_data(data)
                if not is_valid:
                    st.error(f"❌ {message}")
                    st.info("💡 잠시 후 다시 시도하거나 관리자에게 문의하세요")
                    st.stop()

                analysis = analyze_us_stock(data)

                save_screening_log(
                    ticker,
                    data['name'],
                    data['mcap'],
                    analysis['volatility'],
                    analysis['judgment'],
                    analysis['acceptance_ratio'],
                    analysis['violations']
                )

                st.markdown("---")

                # 판정 + RMS 상태 나란히
                col_j, col_r = st.columns(2)
                with col_j:
                    if analysis['eligible']:
                        st.success(f"**✅ {analysis['judgment']}**\n\n위험 등급: {analysis['risk_level']}")
                    else:
                        st.error(f"**⛔ {analysis['judgment']}**\n\n위험 등급: {analysis['risk_level']}")
                with col_r:
                    render_rms_result(ticker.upper(), analysis['eligible'])

                # 통합 정보 박스
                sector_text = ""
                if data.get('sector') != 'N/A':
                    sector_text += f" · {data['sector']}"
                if data.get('industry') != 'N/A':
                    sector_text += f" · {data['industry']}"

                ratio_text = (
                    f"\n💰 담보인정비율 {analysis['acceptance_ratio']}% ({analysis['ratio_reason']})"
                    if analysis['acceptance_ratio'] < 100 else ""
                )
                st.info(
                    f"**{data['name']} ({ticker.upper()})** | {data['exchange']} · {analysis.get('cap_category', 'N/A')}{sector_text}  \n"
                    f"{data['mcap_label']} ${data['mcap']:.2f}B | 현재가 ${data['price']:.2f} | 변동성 {analysis['volatility']:.1f}%  \n"
                    f"52주 ${data['high_52w']:.2f} ~ ${data['low_52w']:.2f} (현재 위치 {analysis['price_position']:.1f}%){ratio_text}"
                )

                st.markdown("---")

                if analysis['violations']:
                    col_v1, col_v2 = st.columns(2)
                    with col_v1:
                        st.markdown("**❌ 담보 불가 사유**")
                        for v in analysis['violations']:
                            st.markdown(f"• {v.replace('❌ ', '')}")
                    with col_v2:
                        st.markdown("**⚠️ 주요 리스크**")
                        for r in analysis['risk_factors']:
                            st.markdown(f"• {r}")

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

                st.markdown("---")
                col_d1, col_d2, col_d3 = st.columns([1, 1, 2])
                with col_d1:
                    if st.button("📥 엑셀로 다운로드", use_container_width=True):
                        filename = export_to_excel(ticker, data, analysis)
                        if filename:
                            with open(filename, 'rb') as f:
                                st.download_button(
                                    label="⬇️ 파일 다운로드",
                                    data=f,
                                    file_name=filename,
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True
                                )
                            st.success("✅ 생성 완료")
                        else:
                            st.error("생성 실패")

            except Exception as e:
                st.error(f"❌ 시스템 오류: {str(e)}")
                st.error("관리자에게 문의하세요")

elif search_button:
    st.error("❌ 종목코드를 입력하세요")

st.markdown("---")
st.caption(f"ⓒ 2026 FINDE | 리스크 관리 시스템 v{VERSION}")
