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
        return False, "조회 실패"
    if data.get('market_cap', 0) <= 0:
        return False, "시총 데이터 없음"
    if data.get('current_price', 0) <= 0:
        return False, "주가 데이터 없음"
    if data.get('high_52w', 0) <= 0 or data.get('low_52w', 0) <= 0:
        return False, "52주 데이터 없음"
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
            writer.writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ticker,
                name,
                f"{market_cap:,.0f}" if market_cap else "N/A",
                f"{volatility:.1f}" if volatility else "N/A",
                judgment,
                acceptance_ratio,
                violations[0].replace('❌ ', '') if violations else '없음'
            ])
    except Exception:
        pass


def load_screening_history() -> pd.DataFrame:
    """심사 이력 로드"""
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame(columns=LOG_HEADER)
    try:
        df = pd.read_csv(LOG_FILE, encoding='utf-8-sig')
        df['일시'] = pd.to_datetime(df['일시'])
        return df
    except Exception:
        return pd.DataFrame(columns=LOG_HEADER)
