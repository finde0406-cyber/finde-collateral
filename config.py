"""
핀드 담보 심사 시스템 설정
"""

VERSION = "8.0"
SYSTEM_NAME = "핀드 담보 심사 시스템"

# DART API
DART_API_KEY = "2a943c8700adfcb64e1e1500318e480ad2684bf5"
FINNHUB_API_KEY = "d7etdh1r01qi33g7j9j0d7etdh1r01qi33g7j9jg"

# 국내주식 기준
KOREAN_STOCK = {
    'min_price': 1000,
    'min_market_cap': 500,
    'volatility_limits': {
        'mega': 500,
        'large': 500,
        'mid': 300,
        'small': 200,
        'micro': 150
    }
}

# 해외주식 기준
US_STOCK = {
    'min_price': 5.0,
    'min_market_cap': 1.0,
    'min_volume': 100000,
    'max_beta': 3.0,
    'allowed_exchanges': ['NYSE', 'NASDAQ', 'NYSE Arca'],
    'volatility_limits': {
        'mega': 300,
        'large': 250,
        'mid': 200,
        'small': 150,
        'micro': 100
    }
}

# 담보인정비율
ACCEPTANCE_RATIO = {
    400: 0,
    350: 30,
    300: 50,
    250: 70,
    200: 80,
    0: 100
}

CACHE_TTL = 3600
LOG_FILE = "screening_history.csv"

# 환율 (월별 수동 업데이트)
USD_KRW = 1450
HKD_KRW = 186
CNY_KRW = 200
