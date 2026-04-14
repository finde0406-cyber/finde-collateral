"""
RMS 일별 종목관리현황 모듈
- G열(index 6): 종목코드
- J열(index 9): 종목상태 (빈칸=정상, 값있음=제한)
- 한국: A+6자리 숫자
- 중국: 6자리 숫자
- 홍콩: 5자리 숫자
- 미국: 영문 티커
"""
import json
import os
import pandas as pd
from datetime import datetime

# 저장 경로
DATA_DIR  = "data"
RMS_FILE  = os.path.join(DATA_DIR, "rms_latest.xlsx")
META_FILE = os.path.join(DATA_DIR, "rms_meta.json")


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def detect_country(code: str) -> str:
    """종목코드로 국가 감지"""
    code = str(code).strip()
    if code.upper().startswith('A') and len(code) == 7 and code[1:].isdigit():
        return '한국'
    if code.isdigit() and len(code) == 5:
        return '홍콩'
    if code.isdigit() and len(code) == 6:
        return '중국'
    return '미국'


def get_clean_code(code: str, country: str) -> str:
    """심사용 코드 반환 - 한국은 A 제거"""
    if country == '한국':
        return code[1:]  # A000660 → 000660
    return code


def parse_rms_excel(file) -> pd.DataFrame:
    """
    RMS 엑셀 파싱
    G열(index 6): 종목코드
    J열(index 9): 종목상태
    반환: DataFrame {종목코드_원본, 종목코드, 국가, RMS상태, RMS상태원문}
    """
    df_raw = pd.read_excel(file, header=0, dtype=str)
    df_raw = df_raw.fillna("")

    if df_raw.shape[1] < 10:
        raise ValueError(f"열 개수 부족: {df_raw.shape[1]}열 (최소 10열 필요)")

    df = pd.DataFrame()
    df['종목코드_원본'] = df_raw.iloc[:, 6].str.strip()
    df['RMS상태원문']   = df_raw.iloc[:, 9].str.strip()

    # 빈 종목코드 제거
    df = df[df['종목코드_원본'] != ''].reset_index(drop=True)

    df['국가']    = df['종목코드_원본'].apply(detect_country)
    df['종목코드'] = df.apply(
        lambda r: get_clean_code(r['종목코드_원본'], r['국가']), axis=1
    )
    df['RMS상태'] = df['RMS상태원문'].apply(
        lambda x: '정상' if x == '' else f'제한({x})'
    )

    return df[['종목코드_원본', '종목코드', '국가', 'RMS상태', 'RMS상태원문']]


def save_rms_data(uploaded_file, original_filename: str) -> dict:
    """
    RMS 파일 서버 저장
    반환: meta 딕셔너리
    """
    _ensure_data_dir()

    df = parse_rms_excel(uploaded_file)

    # 파싱된 데이터 저장
    df.to_excel(RMS_FILE, index=False)

    # 메타 저장
    meta = {
        'filename'    : original_filename,
        'uploaded_at' : datetime.now().strftime('%Y-%m-%d %H:%M'),
        'total'       : len(df),
        'normal'      : int((df['RMS상태'] == '정상').sum()),
        'restricted'  : int((df['RMS상태'] != '정상').sum()),
    }
    with open(META_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False)

    return meta


def load_rms_data() -> tuple:
    """
    저장된 RMS 데이터 로드
    반환: (DataFrame or None, meta dict or None)
    """
    if not os.path.exists(RMS_FILE) or not os.path.exists(META_FILE):
        return None, None

    try:
        df = pd.read_excel(RMS_FILE, dtype=str).fillna("")
        with open(META_FILE, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        return df, meta
    except Exception:
        return None, None


def get_rms_status(ticker: str, df_rms: pd.DataFrame) -> dict:
    """
    단건 심사 결과 화면용 — 해당 종목의 RMS 상태 반환
    ticker: 사용자 입력 코드 (한국 6자리, 미국 영문 등 — A 접두어 없음)
    반환: {'found': bool, 'status': str, 'raw': str}
    """
    if df_rms is None or df_rms.empty:
        return {'found': False, 'status': '', 'raw': ''}

    match = df_rms[df_rms['종목코드'].str.upper() == ticker.strip().upper()]

    if match.empty:
        return {'found': False, 'status': '', 'raw': ''}

    row = match.iloc[0]
    return {
        'found' : True,
        'status': row['RMS상태'],
        'raw'   : row['RMS상태원문']
    }
