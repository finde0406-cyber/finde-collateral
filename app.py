"""
핀드 담보 심사 시스템 v8.0
실전 리스크관리 시스템
"""
import streamlit as st
from config import VERSION, SYSTEM_NAME
from modules import (
    fetch_korean_stock,
    fetch_us_stock,
    analyze_korean_stock,
    analyze_us_stock,
    validate_korean_stock_data,
    validate_us_stock_data,
    save_screening_log,
    export_to_excel
)

st.set_page_config(page_title=SYSTEM_NAME, page_icon="🏦", layout="wide")

# === 사이드바 ===

with st.sidebar:
    st.title("🏦 핀드 담보 심사")
    st.caption(f"KB증권 하이브리드 | v{VERSION}")
    st.markdown("---")
    
    st.header("📖 가이드")
    st.markdown("**국내**: `005930`  \n**해외**: `AAPL`")
    st.markdown("---")
    
    with st.expander("🔴 국내주식 불가 기준"):
        st.markdown("""
        - 관리종목
        - 동전주 (1,000원 미만)
        - 시총 500억 미만
        - 변동성 극심
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

# === 메인 ===

st.title("🏦 핀드 담보 심사 시스템")
st.caption(f"KB증권 하이브리드 계좌운용규칙 | v{VERSION}")

with st.form(key='search_form', clear_on_submit=False):
    c1, c2 = st.columns([3, 1])
    with c1:
        ticker = st.text_input("종목코드/티커", placeholder="005930, AAPL", label_visibility="collapsed")
    with c2:
        search_button = st.form_submit_button("🔍 심사", use_container_width=True)

if search_button and ticker:
    is_korean = ticker.isdigit() and len(ticker) == 6
    
    if is_korean:
        # === 국내주식 ===
        with st.spinner("분석 중..."):
            try:
                # 데이터 수집
                data = fetch_korean_stock(ticker)
                
                # 데이터 검증
                is_valid, message = validate_korean_stock_data(data)
                if not is_valid:
                    st.error(f"❌ {message}")
                    st.info("💡 잠시 후 다시 시도하거나 관리자에게 문의하세요")
                    st.stop()
                
                # 리스크 분석
                analysis = analyze_korean_stock(data)
                
                # 로그 저장
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
                
                # 판정 표시
                if analysis['eligible']:
                    st.success(f"## ✅ {analysis['judgment']} | 위험 등급: {analysis['risk_level']}")
                else:
                    st.error(f"## ⛔ {analysis['judgment']} | 위험 등급: {analysis['risk_level']}")
                
                # 기본 정보
                sector_text = f" | {data.get('sector', 'N/A')}" if data.get('sector') != 'N/A' else ""
                st.markdown(f"**{data['name']}** | {data['market']}{sector_text} | {data['current_price']:,.0f}원 | 시총 {data['market_cap']:,.0f}억 | {analysis['cap_grade']}")
                
                # 52주 정보
                st.markdown(f"📈 **52주 고가**: {data['high_52w']:,.0f}원 | **저가**: {data['low_52w']:,.0f}원 | **변동성**: {analysis['volatility']:.1f}% | **현재 위치**: {analysis['price_position']:.1f}%")
                
                # 담보인정비율
                if analysis['acceptance_ratio'] < 100:
                    st.warning(f"💰 **권장 담보인정비율**: {analysis['acceptance_ratio']}% ({analysis['ratio_reason']})")
                
                # 불가 사유 및 리스크
                if analysis['violations']:
                    st.markdown("### ❌ 담보 불가 사유")
                    for v in analysis['violations']:
                        st.markdown(v)
                    
                    st.markdown("### ⚠️ 주요 리스크")
                    for r in analysis['risk_factors']:
                        st.markdown(f"• {r}")
                    
                    # 심사 의견
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
- 예시: 1억원 평가 → {analysis['acceptance_ratio']*1000000:,.0f}원 인정 → 대출 가능 {analysis['acceptance_ratio']*2000000:,.0f}원

**일일 모니터링 필수**
- 변동성 높아 담보비율 급변 가능
- 추가 담보 요구 가능성

**최종 판정**: **{analysis['judgment']}**

**불가 사유**: {', '.join([v.replace('❌ ', '') for v in analysis['violations'][:2]])}

※ 계좌운용규칙(LTV, 로스컷)은 상품 및 자산규모별로 상이  
※ DART 재무제표 확인 후 담보인정비율 조정 가능성 검토 필요
                    """)
                
                # 엑셀 다운로드
                st.markdown("---")
                if st.button("📥 엑셀로 다운로드"):
                    filename = export_to_excel(ticker, data, analysis)
                    if filename:
                        with open(filename, 'rb') as f:
                            st.download_button(
                                label="⬇️ 파일 다운로드",
                                data=f,
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        st.success(f"✅ {filename} 생성 완료")
                    else:
                        st.error("엑셀 생성 실패")
                
            except Exception as e:
                st.error(f"❌ 시스템 오류: {str(e)}")
                st.error("관리자에게 문의하세요")
    
    else:
        # === 해외주식 ===
        with st.spinner("분석 중..."):
            try:
                # 데이터 수집
                data = fetch_us_stock(ticker)
                
                # 데이터 검증
                is_valid, message = validate_us_stock_data(data)
                if not is_valid:
                    st.error(f"❌ {message}")
                    st.info("💡 잠시 후 다시 시도하거나 관리자에게 문의하세요")
                    st.stop()
                
                # 리스크 분석
                analysis = analyze_us_stock(data)
                
                # 로그 저장
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
                
                # 판정 표시
                if analysis['eligible']:
                    st.success(f"## ✅ {analysis['judgment']} | 위험 등급: {analysis['risk_level']}")
                else:
                    st.error(f"## ⛔ {analysis['judgment']} | 위험 등급: {analysis['risk_level']}")
                
                # 기본 정보
                sector_text = ""
                if data.get('sector') != 'N/A':
                    sector_text = f" | {data['sector']}"
                if data.get('industry') != 'N/A':
                    sector_text += f" - {data['industry']}"
                
                st.markdown(f"**{data['name']}** | {data['exchange']}{sector_text} | ${data['price']:.2f} | {data['mcap_label']} ${data['mcap']:.2f}B | {analysis.get('cap_category', 'N/A')}")
                
                # 52주 정보
                st.markdown(f"📈 **52주 고가**: ${data['high_52w']:.2f} | **저가**: ${data['low_52w']:.2f} | **변동성**: {analysis['volatility']:.1f}% | **현재 위치**: {analysis['price_position']:.1f}%")
                
                # 담보인정비율
                if analysis['acceptance_ratio'] < 100:
                    st.warning(f"💰 **권장 담보인정비율**: {analysis['acceptance_ratio']}% ({analysis['ratio_reason']})")
                
                # 불가 사유 및 리스크
                if analysis['violations']:
                    st.markdown("### ❌ 담보 불가 사유")
                    for v in analysis['violations']:
                        st.markdown(v)
                    
                    st.markdown("### ⚠️ 주요 리스크")
                    for r in analysis['risk_factors']:
                        st.markdown(f"• {r}")
                    
                    # 심사 의견
                    st.markdown("### 💼 심사 의견")
                    st.markdown(f"""
**변동성 리스크**: {'매우 높음' if analysis['volatility'] > 250 else '높음' if analysis['volatility'] > 150 else '보통'}

**현재가 위치**: {analysis['price_position']:.1f}% 지점

**담보인정비율 (권장)**: **{analysis['acceptance_ratio']}%**
- 사유: {analysis['ratio_reason']}
- 예시: $100,000 평가 → ${analysis['acceptance_ratio']*1000:,.0f} 인정

**일일 모니터링 필수**

**최종 판정**: **{analysis['judgment']}**

※ 계좌운용규칙은 상품별로 상이
                    """)
                
                # 엑셀 다운로드
                st.markdown("---")
                if st.button("📥 엑셀로 다운로드"):
                    filename = export_to_excel(ticker, data, analysis)
                    if filename:
                        with open(filename, 'rb') as f:
                            st.download_button(
                                label="⬇️ 파일 다운로드",
                                data=f,
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        st.success(f"✅ {filename} 생성 완료")
                    else:
                        st.error("엑셀 생성 실패")
                
            except Exception as e:
                st.error(f"❌ 시스템 오류: {str(e)}")
                st.error("관리자에게 문의하세요")

elif search_button:
    st.error("❌ 종목코드를 입력하세요")

st.markdown("---")
st.caption(f"ⓒ 2026 FINDE | 리스크 관리 시스템 v{VERSION}")