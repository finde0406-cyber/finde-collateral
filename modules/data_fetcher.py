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


def fetch_us_stock(ticker):
    """
    해외주식 데이터 수집 (Finnhub 기반)
    - 기본 시세: Finnhub quote
    - 기업 정보: Finnhub company profile
    - 52주 고저가: Finnhub candle (1년치)
    - 재무 데이터: Finnhub basic financials
    """
    try:
        client = get_finnhub_client()
        symbol = ticker.strip().upper()

        # ── 1. 기업 프로필 ────────────────────────────────────
        profile = client.company_profile2(symbol=symbol)
        if not profile or not profile.get('name'):
            return {'success': False, 'error': '종목 정보 없음'}

        # ── 2. 실시간 시세 ────────────────────────────────────
        quote = client.quote(symbol)
        if not quote or quote.get('c', 0) == 0:
            return {'success': False, 'error': '시세 조회 실패'}

        current_price = quote.get('c', 0)    # 현재가
        high_day      = quote.get('h', 0)    # 당일 고가
        low_day       = quote.get('l', 0)    # 당일 저가

        # ── 3. 52주 고저가 (기본 재무 지표에서 추출) ──────────
        try:
            metrics_data = client.company_basic_financials(symbol, 'all')
            metrics      = metrics_data.get('metric', {})

            high_52w = metrics.get('52WeekHigh', high_day)
            low_52w  = metrics.get('52WeekLow', low_day)

            # 재무 지표
            debt_to_equity    = metrics.get('totalDebt/totalEquityAnnual')
            return_on_equity  = metrics.get('roeAnnual')
            current_ratio     = metrics.get('currentRatioAnnual')
            operating_margins = metrics.get('operatingMarginAnnual')
            revenue_growth    = metrics.get('revenueGrowthAnnual') or metrics.get('revenueGrowth3Y')
            net_margin        = metrics.get('netProfitMarginAnnual')
            beta              = metrics.get('beta')
            market_cap        = metrics.get('marketCapitalization')  # $M 단위

        except Exception:
            high_52w          = high_day
            low_52w           = low_day
            debt_to_equity    = None
            return_on_equity  = None
            current_ratio     = None
            operating_margins = None
            revenue_growth    = None
            net_margin        = None
            beta              = None
            market_cap        = None

        # 시총: Finnhub은 $M 단위 → $B로 변환
        mcap_b = (market_cap / 1000) if market_cap else 0

        # 거래소 매핑
        exchange_raw = profile.get('exchange', 'N/A')
        exchange_map = {
            'NASDAQ NMS - GLOBAL MARKET' : 'NASDAQ',
            'NASDAQ CAPITAL MARKET'      : 'NASDAQ',
            'NASDAQ GLOBAL SELECT MARKET': 'NASDAQ',
            'NEW YORK STOCK EXCHANGE'    : 'NYSE',
            'NYSE'                       : 'NYSE',
            'NYSE AMERICAN'              : 'NYSE',
            'NYSE ARCA'                  : 'NYSE Arca',
        }
        exchange = exchange_map.get(exchange_raw.upper(), exchange_raw)

        # 종목 유형
        finn_type  = profile.get('finnhubIndustry', 'N/A')
        quote_type = 'ETF' if 'ETF' in finn_type.upper() or 'FUND' in finn_type.upper() else 'EQUITY'

        # ETF는 AUM, 주식은 시총
        if quote_type == 'ETF':
            mcap_label = "AUM"
        else:
            mcap_label = "시총"

        # ROE: Finnhub은 % 단위로 반환 (소수점 아님)
        roe_decimal   = (return_on_equity / 100) if return_on_equity is not None else None
        op_mar_decimal = (operating_margins / 100) if operating_margins is not None else None

        # ── 4. 거래량 (별도 조회) ─────────────────────────────
        try:
            volume_data = client.company_basic_financials(symbol, 'all')
            volume      = volume_data.get('metric', {}).get('10DayAverageTradingVolume', 0)
            if volume:
                volume = int(volume * 1000000)  # M 단위 → 실제 수
            else:
                volume = 0
        except Exception:
            volume = 0

        return {
            'success'          : True,
            'name'             : profile.get('name', symbol),
            'exchange'         : exchange,
            'price'            : current_price,
            'mcap'             : mcap_b,
            'mcap_label'       : mcap_label,
            'quote_type'       : quote_type,
            'high_52w'         : high_52w if high_52w else high_day,
            'low_52w'          : low_52w if low_52w else low_day,
            'sector'           : profile.get('finnhubIndustry', 'N/A'),
            'industry'         : profile.get('finnhubIndustry', 'N/A'),
            'beta'             : beta if beta else 0,
            'volume'           : volume,
            # 재무 데이터
            'debt_to_equity'   : debt_to_equity,
            'return_on_equity' : roe_decimal,
            'current_ratio'    : current_ratio,
            'operating_margins': op_mar_decimal,
            'revenue_growth'   : revenue_growth,
            'total_equity'     : None,  # Finnhub metric에서 직접 제공 안 함
        }

    except Exception as e:
        return {'success': False, 'error': str(e)}
