"""
유틸리티 함수
"""
import csv
import pandas as pd
from datetime import datetime
from config import LOG_FILE

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
        return False, "조회 실패"
    if data.get('price', 0) <= 0:
        return False, "주가 데이터 없음"
    if data.get('high_52w', 0) <= 0 or data.get('low_52w', 0) <= 0:
        return False, "52주 데이터 없음"
    return True, "정상"

def save_screening_log(ticker, name, market_cap, volatility, judgment, acceptance_ratio, violations):
    """심사 이력 저장"""
    try:
        try:
            with open(LOG_FILE, 'r', encoding='utf-8-sig'):
                pass
        except FileNotFoundError:
            with open(LOG_FILE, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['일시', '종목코드', '종목명', '시총', '변동성', '판정', '담보인정비율', '주요사유'])
        
        with open(LOG_FILE, 'a', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
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
    except:
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
                '현재위치(%)': [f"{analysis['price_position']:.1f}"],
                '등급': [analysis['cap_grade']],
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
    except:
        return None