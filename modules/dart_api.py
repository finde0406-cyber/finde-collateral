"""
DART API 연동
- 재무제표 (최근 2년으로 단축 - 속도 개선)
- 감사의견
- 위험 공시 탐지
- st.cache_data로 캐싱 (같은 종목 재조회 시 즉시 반환)
"""
import requests
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from config import DART_API_KEY

BASE_URL = "https://opendart.fss.or.kr/api"

RISK_KEYWORDS = [
    '관리종목', '상장폐지', '거래정지', '횡령', '배임',
    '감자', '워크아웃', '법정관리', '회생', '부도',
    '불성실공시', '매출액미달', '자본잠식'
]


def is_available() -> bool:
    return DART_API_KEY is not None and DART_API_KEY != ""


def fetch_corp_code(stock_code: str):
    """종목코드 → DART 고유번호 조회 (1시간 캐시)"""
    try:
        # 종목코드 6자리 보장 (앞자리 0 유지)
        code = str(stock_code).zfill(6)
        res  = requests.get(
            f"{BASE_URL}/company.json",
            params={'crtfc_key': DART_API_KEY, 'stock_code': code},
            timeout=5
        )
        data = res.json()
        if data.get('status') == '000':
            return data.get('corp_code')
        # 상태 코드 확인용 (디버그 후 제거)
        import streamlit as st
        st.write(f"DART 응답: {data}")
        print(f"DART corp_code 응답: status={data.get('status')}, message={data.get('message')}, code={code}")
        return None
    except Exception:
        return None


@st.cache_data(ttl=3600)
def fetch_financial_year(corp_code: str, year: int):
    """특정 연도 재무데이터 조회 (1시간 캐시)"""
    for fs_div in ['CFS', 'OFS']:
        try:
            res  = requests.get(
                f"{BASE_URL}/fnlttSinglAcnt.json",
                params={
                    'crtfc_key' : DART_API_KEY,
                    'corp_code' : corp_code,
                    'bsns_year' : str(year),
                    'reprt_code': '11011',
                    'fs_div'    : fs_div,
                },
                timeout=5
            )
            data = res.json()
            if data.get('status') != '000':
                continue

            items = data.get('list', [])
            row   = {'year': year, 'equity': None, 'debt': None,
                     'revenue': None, 'op_income': None}

            for item in items:
                account    = item.get('account_nm', '')
                amount_str = item.get('thstrm_amount', '').replace(',', '').replace(' ', '')
                try:
                    amount = int(amount_str) if amount_str and amount_str != '-' else None
                except ValueError:
                    amount = None

                if '자본총계' in account:
                    row['equity'] = amount
                elif '부채총계' in account:
                    row['debt'] = amount
                elif account in ['매출액', '수익(매출액)']:
                    row['revenue'] = amount
                elif '영업이익' in account:
                    row['op_income'] = amount

            if any(v is not None for v in [row['equity'], row['debt']]):
                return row
        except Exception:
            continue
    return None


@st.cache_data(ttl=3600)
def fetch_financial_data(corp_code: str) -> list:
    """최근 2년 재무데이터 병렬 조회 (1시간 캐시)"""
    current_year = datetime.now().year
    years        = [current_year - 1, current_year - 2]

    results = []
    # 병렬 조회로 속도 개선
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(fetch_financial_year, corp_code, y): y for y in years}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    return sorted(results, key=lambda x: x['year'], reverse=True)


@st.cache_data(ttl=3600)
def fetch_audit_opinion(corp_code: str) -> dict:
    """최근 감사의견 조회 (1시간 캐시)"""
    try:
        res  = requests.get(
            f"{BASE_URL}/list.json",
            params={
                'crtfc_key'          : DART_API_KEY,
                'corp_code'          : corp_code,
                'pblntf_ty'          : 'A',
                'pblntf_detail_ty'   : 'A001',
                'page_count'         : 3,
            },
            timeout=5
        )
        data = res.json()

        if data.get('status') != '000' or not data.get('list'):
            return {'opinion': None, 'year': None}

        latest = data['list'][0]
        rcp_no = latest.get('rcept_no')

        res2  = requests.get(
            f"{BASE_URL}/fnlttAuditOpinion.json",
            params={'crtfc_key': DART_API_KEY, 'rcept_no': rcp_no},
            timeout=5
        )
        data2 = res2.json()

        if data2.get('status') == '000' and data2.get('list'):
            opinion_data = data2['list'][0]
            return {
                'opinion': opinion_data.get('opinion', ''),
                'year'   : latest.get('rcept_dt', '')[:4]
            }
        return {'opinion': None, 'year': None}
    except Exception:
        return {'opinion': None, 'year': None}


@st.cache_data(ttl=3600)
def fetch_risk_disclosures(corp_code: str) -> list:
    """최근 1년 위험 공시 탐지 (1시간 캐시)"""
    try:
        today  = datetime.now()
        bgn_de = f"{today.year - 1}{today.month:02d}{today.day:02d}"
        end_de = today.strftime('%Y%m%d')

        res  = requests.get(
            f"{BASE_URL}/list.json",
            params={
                'crtfc_key' : DART_API_KEY,
                'corp_code' : corp_code,
                'bgn_de'    : bgn_de,
                'end_de'    : end_de,
                'page_count': 20,
            },
            timeout=5
        )
        data = res.json()

        if data.get('status') != '000':
            return []

        return [
            {'date': item.get('rcept_dt', ''), 'title': item.get('report_nm', '')}
            for item in data.get('list', [])
            if any(kw in item.get('report_nm', '') for kw in RISK_KEYWORDS)
        ]
    except Exception:
        return []


@st.cache_data(ttl=3600)
def get_dart_analysis(stock_code: str) -> dict:
    """
    메인 함수 — DART 전체 분석 (1시간 캐시)
    재무/감사/공시 병렬 조회로 속도 개선
    """
    if not is_available():
        return {'available': False, 'error': 'API Key 미설정'}

    corp_code = fetch_corp_code(stock_code)
    if not corp_code:
        return {
            'available'       : True,
            'corp_code'       : None,
            'error'           : '기업 정보 없음',
            'financial'       : [],
            'audit'           : {},
            'risk_disclosures': []
        }

    # 재무/감사/공시 병렬 조회
    with ThreadPoolExecutor(max_workers=3) as executor:
        f_financial = executor.submit(fetch_financial_data, corp_code)
        f_audit     = executor.submit(fetch_audit_opinion, corp_code)
        f_risk      = executor.submit(fetch_risk_disclosures, corp_code)

        financial        = f_financial.result()
        audit            = f_audit.result()
        risk_disclosures = f_risk.result()

    return {
        'available'       : True,
        'corp_code'       : corp_code,
        'financial'       : financial,
        'audit'           : audit,
        'risk_disclosures': risk_disclosures,
        'error'           : None
    }
