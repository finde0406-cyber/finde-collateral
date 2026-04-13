"""
주식 데이터 수집
"""
import yfinance as yf
import FinanceDataReader as fdr
import time

def fetch_korean_stock(ticker):
    """국내주식 데이터 수집"""
    try:
        df_krx = fdr.StockListing('KRX')
        stock_info = df_krx[df_krx['Code'] == ticker]
        
        if not stock_info.empty:
            df_price = fdr.DataReader(ticker, '2024-01-01')
            
            return {
                'source': 'KRX',
                'success': True,
                'name': stock_info.iloc[0]['Name'],
                'market': stock_info.iloc[0]['Market'],
                'sector': stock_info.iloc[0].get('Sector', 'N/A'),
                'market_cap': stock_info.iloc[0].get('Marcap', 0) / 100000000,
                'dept': stock_info.iloc[0].get('Dept', ''),
                'current_price': df_price['Close'].iloc[-1],
                'high_52w': df_price['High'].max(),
                'low_52w': df_price['Low'].min()
            }
    except:
        pass
    
    try:
        time.sleep(1)
        for suffix, market_name in [('.KS', 'KOSPI'), ('.KQ', 'KOSDAQ')]:
            stock = yf.Ticker(f"{ticker}{suffix}")
            info = stock.info
            
            if info and info.get('regularMarketPrice'):
                hist = stock.history(period="1y")
                if not hist.empty:
                    mcap_raw = info.get('marketCap', 0)
                    return {
                        'source': 'Yahoo Finance',
                        'success': True,
                        'name': info.get('shortName', ticker),
                        'market': market_name,
                        'sector': info.get('sector', 'N/A'),
                        'market_cap': mcap_raw / 100000000 if mcap_raw else 0,
                        'dept': '',
                        'current_price': hist['Close'].iloc[-1],
                        'high_52w': hist['High'].max(),
                        'low_52w': hist['Low'].min(),
                        'backup_warning': True
                    }
    except:
        pass
    
    return {'success': False, 'error': '데이터 조회 실패'}

def fetch_us_stock(ticker):
    """해외주식 데이터 수집"""
    try:
        time.sleep(1)
        stock = yf.Ticker(ticker.upper())
        info = stock.info
        hist = stock.history(period="1y")
        
        if not info or not info.get('regularMarketPrice'):
            return {'success': False, 'error': '종목 정보 없음'}
        
        quote_type = info.get('quoteType', '')
        
        if quote_type == 'ETF':
            mcap_value = info.get('totalAssets', 0)
            mcap_label = "AUM"
        else:
            mcap_value = info.get('marketCap', 0)
            mcap_label = "시총"
        
        exchange_map = {
            'NYQ': 'NYSE', 'NMS': 'NASDAQ', 'NGM': 'NASDAQ',
            'NAS': 'NASDAQ', 'PCX': 'NYSE Arca', 'NYSEARCA': 'NYSE Arca'
        }
        
        return {
            'success': True,
            'name': info.get('longName', info.get('shortName', ticker.upper())),
            'exchange': exchange_map.get(info.get('exchange', 'N/A'), info.get('exchange', 'N/A')),
            'price': info.get('currentPrice', info.get('regularMarketPrice', 0)),
            'mcap': mcap_value / 1e9 if mcap_value else 0,
            'mcap_label': mcap_label,
            'quote_type': quote_type,
            'high_52w': hist['High'].max() if not hist.empty else 0,
            'low_52w': hist['Low'].min() if not hist.empty else 0,
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'beta': info.get('beta', 0),
            'volume': info.get('averageVolume', 0)
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}