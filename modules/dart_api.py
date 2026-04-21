"""
DART API 연동
- 정식님 PC의 로컬 서버를 통해 DART 데이터 조회
- IP 문제 완전 해결
"""
import requests
from config import DART_API_KEY

# 정식님 PC ngrok 주소 (PC 재시작 시 변경 필요)
DART_LOCAL_SERVER = "https://mutiny-shakily-legroom.ngrok-free.dev"

RISK_KEYWORDS = [
    '관리종목', '상장폐지', '거래정지', '횡령', '배임',
    '감자', '워크아웃', '법정관리', '회생', '부도',
    '불성실공시', '매출액미달', '자본잠식'
]


def is_available() -> bool:
    return DART_API_KEY is not None and DART_API_KEY != ""


def get_dart_analysis(stock_code: str) -> dict:
    """메인 함수 — 로컬 서버를 통해 DART 전체 분석"""
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
        res = requests.get(
            f"{DART_LOCAL_SERVER}/dart",
            params={'code': stock_code},
            headers={'ngrok-skip-browser-warning': '1'},
            timeout=30
        )

        if res.status_code != 200:
            return {**empty, 'error': f'서버 오류 ({res.status_code})'}

        data = res.json()

        if data.get('error') and data['error'] != None:
            return {**empty, 'error': data['error']}

        return {
            'available'       : True,
            'corp_code'       : data.get('corp_code'),
            'financial'       : data.get('financial', []),
            'audit'           : data.get('audit', {}),
            'risk_disclosures': data.get('risk_disclosures', []),
            'error'           : None
        }

    except requests.exceptions.ConnectionError:
        return {**empty, 'error': 'PC 서버 연결 실패 (dart_server.py 실행 확인)'}
    except requests.exceptions.Timeout:
        return {**empty, 'error': 'PC 서버 응답 시간 초과'}
    except Exception as e:
        return {**empty, 'error': str(e)}
