"""
보유종목 수량 관리 모듈
- A열(index 0): 기준년
- B열(index 1): 기준월
- C열(index 2): 기준일
- D열(index 3): 국가
- H열(index 7): 종목코드
- I열(index 8): 종목명
- K열(index 10): 계좌수
- L열(index 11): 보유수량
- M열(index 12): 보유금액 (원화)
"""
import os
import json
import pandas as pd
from datetime import datetime
from config import USD_KRW, HKD_KRW, CNY_KRW

DATA_DIR      = "data"
HOLDINGS_FILE = os.path.join(DATA_DIR, "holdings_latest.xlsx")
HOLDINGS_META = os.path.join(DATA_DIR, "holdings_meta.json")


def parse_holdings_excel(file) -> pd.DataFrame:
    """보유수량 엑셀 파싱"""
    df_raw = pd.read_excel(file, header=0, dtype=str)
    df_raw = df_raw.fillna("")

    if df_raw.shape[1] < 13:
        raise ValueError(f"열 개수 부족: {df_raw.shape[1]}열 (최소 13열 필요)")

    df = pd.DataFrame()
    df['국가']      = df_raw.iloc[:, 3].str.strip()
    df['종목코드']  = df_raw.iloc[:, 7].str.strip()
    df['종목명']    = df_raw.iloc[:, 8].str.strip()
    df['계좌수']    = df_raw.iloc[:, 10].str.strip()
    df['보유수량']  = df_raw.iloc[:, 11].str.strip()
    df['보유금액']  = df_raw.iloc[:, 12].str.strip()

    # 빈 종목코드 제거
    df = df[df['종목코드'] != ''].reset_index(drop=True)

    # 숫자 변환 (쉼표 제거)
    for col in ['계좌수', '보유수량', '보유금액']:
        df[col] = pd.to_numeric(
            df[col].str.replace(',', '').str.replace(' ', ''),
            errors='coerce'
        ).fillna(0)

    return df[['종목코드', '종목명', '국가', '계좌수', '보유수량', '보유금액']]


def load_holdings_from_server() -> tuple:
    """서버(GitHub)에 저장된 보유수량 파일 로드"""
    if not os.path.exists(HOLDINGS_FILE):
        return None, None

    try:
        df = parse_holdings_excel(HOLDINGS_FILE)

        if os.path.exists(HOLDINGS_META):
            with open(HOLDINGS_META, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        else:
            mtime = os.path.getmtime(HOLDINGS_FILE)
            dt    = datetime.fromtimestamp(mtime)
            meta  = {
                'filename'  : 'holdings_latest.xlsx',
                'base_date' : dt.strftime('%Y-%m'),
                'total'     : len(df),
            }

        return df, meta

    except Exception:
        return None, None


def save_holdings_to_server(uploaded_file, original_filename: str) -> dict:
    """업로드한 보유수량 파일을 서버에 저장"""
    os.makedirs(DATA_DIR, exist_ok=True)

    df = parse_holdings_excel(uploaded_file)
    df.to_excel(HOLDINGS_FILE, index=False)

    from datetime import timezone, timedelta
    kst     = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst).strftime('%Y-%m-%d %H:%M')

    meta = {
        'filename'  : original_filename,
        'base_date' : now_kst[:7],
        'uploaded_at': now_kst,
        'total'     : len(df),
    }
    with open(HOLDINGS_META, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False)

    return meta


def get_holdings_status(ticker: str, df_holdings: pd.DataFrame,
                        market_cap_krw: float, eligible: bool) -> dict:
    """
    단건 심사용 — 해당 종목 보유현황 + 경고 메시지 반환
    market_cap_krw: 시총 (원화 기준)
    eligible: 담보 가능 여부
    반환: {
        'found': bool,
        'quantity': int,
        'amount': float,
        'accounts': int,
        'name': str,
        'warning_level': 'danger'/'caution'/'normal'/None,
        'warning_msg': str
    }
    """
    if df_holdings is None or df_holdings.empty:
        return {'found': False}

    ticker_clean = ticker.strip().upper()

    # 1차: 그대로 조회
    match = df_holdings[df_holdings['종목코드'].str.strip().str.upper() == ticker_clean]

    # 2차: A 붙여서 조회 (한국 6자리 숫자인 경우)
    if match.empty and ticker_clean.isdigit() and len(ticker_clean) == 6:
        match = df_holdings[df_holdings['종목코드'].str.strip().str.upper() == 'A' + ticker_clean]

    if match.empty:
        return {'found': False}

    row      = match.iloc[0]
    quantity = int(row['보유수량'])
    amount   = float(row['보유금액'])
    accounts = int(row['계좌수'])
    name     = row['종목명']

    # 경고 메시지 판별
    warning_level = None
    warning_msg   = ""

    if not eligible:
        # 담보 불가 종목인데 보유 있음
        warning_level = 'danger'
        warning_msg   = "🚨 리스크 종목 보유 중 — 추가 담보 설정 금지"

    elif market_cap_krw > 0:
        # 시총 1% 초과 여부
        limit_1pct = market_cap_krw * 0.01
        if amount >= limit_1pct:
            warning_level = 'danger'
            warning_msg   = f"🚨 시총 1% 초과 보유 ({amount/100000000:.1f}억 / 한도 {limit_1pct/100000000:.1f}억) — 집중 리스크 주의"
        elif amount >= 100000000:
            warning_level = 'caution'
            warning_msg   = f"⚠️ 동일 종목 집중 보유 ({amount/100000000:.1f}억) — 추가 설정 주의"
        else:
            warning_level = 'normal'
            warning_msg   = f"✅ 보유 중 — 정상 범위 ({amount/100000000:.2f}억)"

    else:
        # 시총 데이터 없을 때 금액 기준만 적용
        if amount >= 100000000:
            warning_level = 'caution'
            warning_msg   = f"⚠️ 동일 종목 집중 보유 ({amount/100000000:.1f}억) — 추가 설정 주의"
        else:
            warning_level = 'normal'
            warning_msg   = f"✅ 보유 중 — 정상 범위 ({amount/100000000:.2f}억)"

    return {
        'found'        : True,
        'quantity'     : quantity,
        'amount'       : amount,
        'accounts'     : accounts,
        'name'         : name,
        'warning_level': warning_level,
        'warning_msg'  : warning_msg,
    }


def get_market_cap_krw(is_korean: bool, data: dict) -> float:
    """
    시총을 원화로 변환
    국내: 시총(억원) → 원
    해외: 시총($B) → 원
    """
    if is_korean:
        mcap_eok = data.get('market_cap', 0)
        return mcap_eok * 100000000  # 억원 → 원

    else:
        mcap_b   = data.get('mcap', 0)
        country  = data.get('exchange', '')
        if 'HK' in country.upper():
            return mcap_b * 1e9 * HKD_KRW
        elif 'CN' in country.upper():
            return mcap_b * 1e9 * CNY_KRW
        else:
            return mcap_b * 1e9 * USD_KRW
