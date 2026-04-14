"""
DART API 연동
- 재무제표 (자본총계, 부채총계, 매출액, 영업이익 최근 3년)
- 감사의견
- 위험 공시 탐지
"""
import requests
from datetime import datetime
from config import DART_API_KEY

BASE_URL = "https://opendart.fss.or.kr/api"

# 위험 키워드 (공시 제목에서 탐지)
RISK_KEYWORDS = [
    '관리종목', '상장폐지', '거래정지', '횡령', '배임',
    '감자', '워크아웃', '법정관리', '회생', '부도',
    '불성실공시', '매출액미달', '자본잠식'
]


def is_available() -> bool:
    """DART API Key 설정 여부 확인"""
    return DART_API_KEY is not None and DART_API_KEY != ""


def fetch_corp_code(stock_code: str):
    """
    종목코드 → DART 고유번호(corp_code) 조회
    """
    try:
        url = f"{BASE_URL}/company.json"
        params = {
            'crtfc_key': DART_API_KEY,
            'stock_code': stock_code
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if data.get('status') == '000':
            return data.get('corp_code')
        return None
    except Exception:
        return None


def fetch_financial_data(corp_code: str) -> list:
    """
    최근 3년 주요 재무 데이터 조회
    반환: [{'year': 2024, 'equity': ..., 'debt': ..., 'revenue': ..., 'op_income': ...}, ...]
    """
    results = []
    current_year = datetime.now().year

    for year in range(current_year - 1, current_year - 4, -1):
        try:
            url = f"{BASE_URL}/fnlttSinglAcnt.json"
            params = {
                'crtfc_key' : DART_API_KEY,
                'corp_code' : corp_code,
                'bsns_year' : str(year),
                'reprt_code': '11011',  # 사업보고서
                'fs_div'    : 'CFS',    # 연결재무제표 우선
            }
            res = requests.get(url, params=params, timeout=10)
            data = res.json()

            # 연결재무제표 없으면 별도재무제표 시도
            if data.get('status') != '000':
                params['fs_div'] = 'OFS'
                res = requests.get(url, params=params, timeout=10)
                data = res.json()

            if data.get('status') != '000':
                continue

            items = data.get('list', [])
            row = {'year': year, 'equity': None, 'debt': None,
                   'revenue': None, 'op_income': None}

            for item in items:
                account = item.get('account_nm', '')
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
                results.append(row)

        except Exception:
            continue

    return results


def fetch_audit_opinion(corp_code: str) -> dict:
    """
    최근 감사의견 조회
    반환: {'opinion': '적정'/'한정'/'부적정'/'의견거절', 'year': 2024}
    """
    try:
        # 감사보고서 공시 검색
        url = f"{BASE_URL}/list.json"
        params = {
            'crtfc_key'  : DART_API_KEY,
            'corp_code'  : corp_code,
            'pblntf_ty'  : 'A',   # 정기공시
            'pblntf_detail_ty': 'A001',  # 사업보고서
            'page_count' : 5,
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if data.get('status') != '000':
            return {'opinion': None, 'year': None}

        disclosures = data.get('list', [])
        if not disclosures:
            return {'opinion': None, 'year': None}

        # 가장 최근 사업보고서의 감사의견 조회
        latest = disclosures[0]
        rcp_no = latest.get('rcept_no')

        url2 = f"{BASE_URL}/fnlttAuditOpinion.json"
        params2 = {
            'crtfc_key': DART_API_KEY,
            'rcept_no' : rcp_no,
        }
        res2 = requests.get(url2, params=params2, timeout=10)
        data2 = res2.json()

        if data2.get('status') == '000' and data2.get('list'):
            opinion_data = data2['list'][0]
            opinion = opinion_data.get('opinion', '')
            year = latest.get('rcept_dt', '')[:4]
            return {'opinion': opinion, 'year': year}

        return {'opinion': None, 'year': None}

    except Exception:
        return {'opinion': None, 'year': None}


def fetch_risk_disclosures(corp_code: str) -> list:
    """
    최근 1년 위험 공시 탐지
    반환: [{'date': '20260101', 'title': '...'}, ...]
    """
    try:
        today = datetime.now()
        bgn_de = f"{today.year - 1}{today.month:02d}{today.day:02d}"
        end_de = today.strftime('%Y%m%d')

        url = f"{BASE_URL}/list.json"
        params = {
            'crtfc_key' : DART_API_KEY,
            'corp_code' : corp_code,
            'bgn_de'    : bgn_de,
            'end_de'    : end_de,
            'page_count': 20,
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        if data.get('status') != '000':
            return []

        risk_list = []
        for item in data.get('list', []):
            title = item.get('report_nm', '')
            if any(kw in title for kw in RISK_KEYWORDS):
                risk_list.append({
                    'date' : item.get('rcept_dt', ''),
                    'title': title
                })

        return risk_list

    except Exception:
        return []


def get_dart_analysis(stock_code: str) -> dict:
    """
    메인 함수 — 종목코드로 DART 전체 분석 실행
    반환: {
        'available': bool,
        'corp_code': str,
        'financial': [...],
        'audit': {...},
        'risk_disclosures': [...],
        'error': str or None
    }
    """
    if not is_available():
        return {'available': False, 'error': 'API Key 미설정'}

    corp_code = fetch_corp_code(stock_code)
    if not corp_code:
        return {'available': True, 'corp_code': None, 'error': '기업 정보 없음',
                'financial': [], 'audit': {}, 'risk_disclosures': []}

    financial        = fetch_financial_data(corp_code)
    audit            = fetch_audit_opinion(corp_code)
    risk_disclosures = fetch_risk_disclosures(corp_code)

    return {
        'available'       : True,
        'corp_code'       : corp_code,
        'financial'       : financial,
        'audit'           : audit,
        'risk_disclosures': risk_disclosures,
        'error'           : None
    }
