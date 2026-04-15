"""
유틸리티 함수
"""
import os
import csv
import pandas as pd
from datetime import datetime

# data 폴더에 저장
DATA_DIR   = "data"
LOG_FILE   = os.path.join(DATA_DIR, "screening_history.csv")
LOG_HEADER = ['일시', '종목코드', '종목명', '시총', '변동성', '판정', '담보인정비율', '주요사유']


def validate_korean_stock_data(data):
    """국내주식 데이터 검증"""
    if not data.get('success'):
        return False, data.get('error', '조회 실패')
    return True, "정상"


def validate_us_stock_data(data):
    """해외주식 데이터 검증"""
    if not data.get('success'):
        return False, data.get('error', '조회 실패')
    if data.get('price', 0) <= 0:
        return False, "주가 데이터 없음"
    if data.get('high_52w', 0) <= 0:
        return False, "52주 데이터 없음"
    return True, "정상"


def save_screening_log(ticker, name, market_cap, volatility, judgment, acceptance_ratio, violations):
    """심사 이력 저장 — data/screening_history.csv"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)

        # 헤더 없으면 생성
        write_header = not os.path.exists(LOG_FILE)

        with open(LOG_FILE, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(LOG_HEADER)
            # 국내주식 종목코드 앞자리 0 유지
            ticker_str = str(ticker).zfill(6) if str(ticker).isdigit() else ticker

            from datetime import timezone, timedelta
            kst     = timezone(timedelta(hours=9))
            now_kst = datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")

            writer.writerow([
                now_kst,
                ticker_str,
                name,
                f"{market_cap:,.0f}" if market_cap else "N/A",
                f"{volatility:.1f}" if volatility else "N/A",
                judgment,
                acceptance_ratio,
                violations[0].replace('❌ ', '') if violations else '없음'
            ])
    except Exception:
        pass

def export_to_excel(ticker, data, analysis):
    """엑셀 내보내기"""
    try:
        is_korean = ticker.isdigit() and len(ticker) == 6

        if is_korean:
            df = pd.DataFrame({
                '종목코드': [ticker],
                '종목명': [data['name']],
                '시장': [data['market']],
                '업종': [data.get('sector', 'N/A')],
                '시총(억)': [f"{data['market_cap']:,.0f}"],
                '현재가': [f"{data['current_price']:,.0f}"],
                '52주고가': [f"{data['high_52w']:,.0f}"],
                '52주저가': [f"{data['low_52w']:,.0f}"],
                '변동성(%)': [f"{analysis['volatility']:.1f}"],
                '담보인정비율(%)': [analysis['acceptance_ratio']],
                '판정': [analysis['judgment']],
                '주요사유': [', '.join([v.replace('❌ ', '') for v in analysis['violations']]) if analysis['violations'] else '없음']
            })
        else:
            df = pd.DataFrame({
                '티커': [ticker],
                '종목명': [data['name']],
                '거래소': [data['exchange']],
                '시총($B)': [f"{data['mcap']:.2f}"],
                '현재가($)': [f"{data['price']:.2f}"],
                '변동성(%)': [f"{analysis['volatility']:.1f}"],
                '담보인정비율(%)': [analysis['acceptance_ratio']],
                '판정': [analysis['judgment']]
            })

        filename = f"심사_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(filename, index=False, engine='openpyxl')
        return filename
    except Exception:
        return None
def load_screening_history() -> pd.DataFrame:
    """심사 이력 로드"""
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame(columns=LOG_HEADER)
    try:
        df = pd.read_csv(LOG_FILE, encoding='utf-8-sig', dtype={'종목코드': str})
        df['일시'] = pd.to_datetime(df['일시'])
        return df
    except Exception:
        return pd.DataFrame(columns=LOG_HEADER)
