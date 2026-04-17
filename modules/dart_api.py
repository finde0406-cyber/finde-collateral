"""
DART API 연동
- 재무제표 (최근 2년)
- 감사의견
- 위험 공시 탐지
"""
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from config import DART_API_KEY

BASE_URL      = "https://opendart.fss.or.kr/api"
_xml_cache    = None  # corpCode.xml 메모리 캐시
RISK_KEYWORDS = [
    '관리종목', '상장폐지', '거래정지', '횡령', '배임',
    '감자', '워크아웃', '법정관리', '회생', '부도',
    '불성실공시', '매출액미달', '자본잠식'
]


def is_available() -> bool:
    return DART_API_KEY is not None and DART_API_KEY != ""


def fetch_corp_code(stock_code: str):
    import zipfile
    import xml.etree.ElementTree as ET
    import io

    global _xml_cache
    code = str(stock_code).zfill(6)

    try:
        if _xml_cache is None:
            res = requests.get(
                f"{BASE_URL}/corpCode.xml",
                params={'crtfc_key': DART_API_KEY},
                timeout=30
            )
            if res.status_code != 200:
                return None
            # ZIP이면 압축 해제, 아니면 직접 사용
            try:
                with zipfile.ZipFile(io.BytesIO(res.content)) as z:
                    _xml_cache = z.read('CORPCODE.xml')
            except zipfile.BadZipFile:
                _xml_cache = res.content

        root = ET.fromstring(_xml_cache)
        for item in root.findall('.//list'):
            if item.findtext('stock_code', '').strip() == code:
                return item.findtext('corp_code', '').strip()
        return None

    except Exception as e:
        _xml_cache = None
        import streamlit as st
        st.error(f"DART 에러: {str(e)}")
        return None

def fetch_financial_year(corp_code: str, year: int):
    """특정 연도 재무데이터 조회"""
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
                     'capital': None, 'revenue': None, 'op_income': None}

            for item in items:
                account    = item.get('account_nm', '')
                amount_str = item.get('thstrm_amount', '').replace(',', '').replace(' ', '')
                try:
                    amount = int(amount_str) if amount_str and amount_str != '-' else None
                except ValueError:
                    amount = None

                if account == '자본금':
                    row['capital'] = amount
                elif '자본총계' in account:
                    row['equity'] = amount
                elif '부채총계' in account:
                    row['debt'] = amount
                elif account in ['매출액', '수익(매출액)']:
                    row['revenue'] = amount
                elif '영업이익' in account:
                    row['op_income'] = amount

            if any(v is not None for v in [row['equity'], row['debt']]):
                return row
        except Exception as e:
            import streamlit as st
            st.error(f"재무데이터 에러: {str(e)}")
            continue
    return None


def fetch_financial_data(corp_code: str) -> list:
    """최근 2년 재무데이터 병렬 조회"""
    current_year = datetime.now().year
    years        = [current_year - 1, current_year - 2]

    results = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(fetch_financial_year, corp_code, y): y for y in years}
        for future in futures:
            result = future.result()
            if result:
                results.append(result)

    return sorted(results, key=lambda x: x['year'], reverse=True)


def fetch_audit_opinion(corp_code: str) -> dict:
    """최근 감사의견 조회"""
    try:
        res  = requests.get(
            f"{BASE_URL}/list.json",
            params={
                'crtfc_key'        : DART_API_KEY,
                'corp_code'        : corp_code,
                'pblntf_ty'        : 'A',
                'pblntf_detail_ty' : 'A001',
                'page_count'       : 3,
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
            return {
                'opinion': data2['list'][0].get('opinion', ''),
                'year'   : latest.get('rcept_dt', '')[:4]
            }
        return {'opinion': None, 'year': None}
    except Exception:
        return {'opinion': None, 'year': None}


def fetch_risk_disclosures(corp_code: str) -> list:
    """최근 1년 위험 공시 탐지"""
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


def get_dart_analysis(stock_code: str) -> dict:
    """메인 함수 — DART 전체 분석"""
    empty = {
        'available'       : True,
        'corp_code'       : None,
        'error'           : 'DART 조회 실패',
        'financial'       : [],
        'audit'           : {},
        'risk_disclosures': []
    }

    if not is_available():
        return {'available': False, 'error': 'API Key 미설정'}

    try:
        corp_code = fetch_corp_code(stock_code)
        if not corp_code:
            return {**empty, 'error': '기업 정보 없음'}

        with ThreadPoolExecutor(max_workers=3) as executor:
            f_financial = executor.submit(fetch_financial_data, corp_code)
            f_audit     = executor.submit(fetch_audit_opinion, corp_code)
            f_risk      = executor.submit(fetch_risk_disclosures, corp_code)

            financial        = f_financial.result(timeout=10)
            audit            = f_audit.result(timeout=10)
            risk_disclosures = f_risk.result(timeout=10)

        return {
            'available'       : True,
            'corp_code'       : corp_code,
            'financial'       : financial,
            'audit'           : audit,
            'risk_disclosures': risk_disclosures,
            'error'           : None
        }

    except Exception:
        return empty
