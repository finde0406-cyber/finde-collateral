"""
주식 데이터 수집
- 국내주식: FinanceDataReader (기존 유지)
- 해외주식: Finnhub (yfinance 대체)
"""
import time
import finnhub
import FinanceDataReader as fdr
import yfinance as yf
from config import FINNHUB_API_KEY

# Finnhub 클라이언트 초기화
_finnhub_client = None

def get_finnhub_client():
    global _finnhub_client
    if _finnhub_client is None:
        _finnhub_client = finnhub.Client(api_key=FINNHUB_API_KEY)
    return _finnhub_client


def fetch_korean_stock(ticker):
    """국내주식 데이터 수집"""
    try:
        df_krx     = fdr.StockListing('KRX')
        stock_info = df_krx[df_krx['Code'] == ticker]

        if not stock_info.empty:
            df_price = fdr.DataReader(ticker, '2024-01-01')

            return {
                'source'       : 'KRX',
                'success'      : True,
                'name'         : stock_info.iloc[0]['Name'],
                'market'       : stock_info.iloc[0]['Market'],
                'sector'       : stock_info.iloc[0].get('Sector', 'N/A'),
                'market_cap'   : stock_info.iloc[0].get('Marcap', 0) / 100000000,
                'dept'         : stock_info.iloc[0].get('Dept', ''),
                'current_price': df_price['Close'].iloc[-1],
                'high_52w'     : df_price['High'].max(),
                'low_52w'      : df_price['Low'].min()
            }
    except Exception:
        pass

    try:
        time.sleep(1)
        for suffix, market_name in [('.KS', 'KOSPI'), ('.KQ', 'KOSDAQ')]:
            stock = yf.Ticker(f"{ticker}{suffix}")
            info  = stock.info

            if info and info.get('regularMarketPrice'):
                hist = stock.history(period="1y")
                if not hist.empty:
                    mcap_raw = info.get('marketCap', 0)
                    return {
                        'source'        : 'Yahoo Finance',
                        'success'       : True,
                        'name'          : info.get('shortName', ticker),
                        'market'        : market_name,
                        'sector'        : info.get('sector', 'N/A'),
                        'market_cap'    : mcap_raw / 100000000 if mcap_raw else 0,
                        'dept'          : '',
                        'current_price' : hist['Close'].iloc[-1],
                        'high_52w'      : hist['High'].max(),
                        'low_52w'       : hist['Low'].min(),
                        'backup_warning': True
                    }
    except Exception:
        pass

    return {'success': False, 'error': '데이터 조회 실패'}


# 거래소 매핑
EXCHANGE_MAP = {
    'NASDAQ NMS - GLOBAL MARKET'  : 'NASDAQ',
    'NASDAQ CAPITAL MARKET'       : 'NASDAQ',
    'NASDAQ GLOBAL SELECT MARKET' : 'NASDAQ',
    'NASDAQ'                      : 'NASDAQ',
    'NEW YORK STOCK EXCHANGE'     : 'NYSE',
    'NYSE'                        : 'NYSE',
    'NYSE AMERICAN'               : 'NYSE',
    'NYSE ARCA'                   : 'NYSE Arca',
    'BATS'                        : 'NYSE Arca',
    'CBOE BZX'                    : 'NYSE Arca',
    'CBOE'                        : 'NYSE Arca',
}

# ETF 판별 키워드
ETF_KEYWORDS = [
    'ETF', 'FUND', 'TRUST', 'PROSHARES', 'DIREXION',
    'ISHARES', 'INVESCO', 'SPDR', 'VANGUARD', 'SCHWAB'
]


def _is_etf(symbol: str, industry: str) -> bool:
    """ETF 여부 판별"""
    s = symbol.upper()
    i = industry.upper() if industry else ''
    return any(kw in s or kw in i for kw in ETF_KEYWORDS)


def fetch_us_stock(ticker):
    """
    해외주식 데이터 수집 (Finnhub 기반)
    프로필 없는 ETF도 시세+재무지표로 처리
    """
    try:
        client = get_finnhub_client()
        symbol = ticker.strip().upper()

        # ── 1. 시세 조회 (가장 먼저 — 종목 존재 여부 확인) ───
        quote = client.quote(symbol)
        if not quote or quote.get('c', 0) == 0:
            return {'success': False, 'error': '종목 정보 없음 (시세 조회 실패)'}

        current_price = quote.get('c', 0)
        high_day      = quote.get('h', 0)
        low_day       = quote.get('l', 0)

        # ── 2. 기업 프로필 (없어도 계속 진행) ────────────────
        try:
            profile = client.company_profile2(symbol=symbol)
        except Exception:
            profile = {}

        name         = profile.get('name', symbol) if profile else symbol
        exchange_raw = profile.get('exchange', '') if profile else ''
        industry     = profile.get('finnhubIndustry', 'N/A') if profile else 'N/A'

        exchange   = EXCHANGE_MAP.get(exchange_raw.upper(), exchange_raw) if exchange_raw else 'NASDAQ'
        quote_type = 'ETF' if _is_etf(symbol, industry) else 'EQUITY'
        mcap_label = 'AUM' if quote_type == 'ETF' else '시총'

        # ── 3. 재무 지표 ──────────────────────────────────────
        try:
            metrics_data = client.company_basic_financials(symbol, 'all')
            metrics      = metrics_data.get('metric', {}) if metrics_data else {}

            high_52w          = metrics.get('52WeekHigh') or high_day
            low_52w           = metrics.get('52WeekLow') or low_day
            debt_to_equity    = metrics.get('totalDebt/totalEquityAnnual')
            return_on_equity  = metrics.get('roeAnnual')
            current_ratio     = metrics.get('currentRatioAnnual')
            operating_margins = metrics.get('operatingMarginAnnual')
            revenue_growth    = metrics.get('revenueGrowthAnnual') or metrics.get('revenueGrowth3Y')
            beta              = metrics.get('beta')
            market_cap_m = metrics.get('marketCapitalization')  # $M 단위

            # ETF는 AUM 별도 조회
            if quote_type == 'ETF' and not market_cap_m:
                try:
                    etf_profile = client.etf_profile(symbol)
                    if etf_profile and etf_profile.get('aum'):
                        market_cap_m = etf_profile['aum'] / 1000000  # $ → $M
                except Exception:
                    pass
            volume_m          = metrics.get('10DayAverageTradingVolume')  # M 단위

        except Exception:
            high_52w          = high_day
            low_52w           = low_day
            debt_to_equity    = None
            return_on_equity  = None
            current_ratio     = None
            operating_margins = None
            revenue_growth    = None
            beta              = None
            market_cap_m      = None
            volume_m          = None

        # 단위 변환
        mcap_b = (market_cap_m / 1000) if market_cap_m else 0
        volume = int(volume_m * 1000000) if volume_m else 0

        # ROE, 영업이익률: Finnhub은 % 단위 → 소수점으로 변환
        roe_decimal    = (return_on_equity  / 100) if return_on_equity  is not None else None
        op_mar_decimal = (operating_margins / 100) if operating_margins is not None else None

        return {
            'success'          : True,
            'name'             : name,
            'exchange'         : exchange,
            'price'            : current_price,
            'mcap'             : mcap_b,
            'mcap_label'       : mcap_label,
            'quote_type'       : quote_type,
            'high_52w'         : high_52w,
            'low_52w'          : low_52w,
            'sector'           : industry,
            'industry'         : industry,
            'beta'             : beta if beta else 0,
            'volume'           : volume,
            # 재무 데이터
            'debt_to_equity'   : debt_to_equity,
            'return_on_equity' : roe_decimal,
            'current_ratio'    : current_ratio,
            'operating_margins': op_mar_decimal,
            'revenue_growth'   : revenue_growth,
            'total_equity'     : None,
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}
