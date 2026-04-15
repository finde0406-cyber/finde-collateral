"""
RMS 일별 종목관리현황 모듈
- D열(index 3): 국가
- H열(index 7): 종목코드
- J열(index 9): 종목상태 (빈칸=정상, 값있음=제한)
- 한국: A+6자리 숫자
- 중국: 6자리 숫자
- 홍콩: 5자리 숫자
- 미국: 영문 티커
"""
import os
import json
import pandas as pd
from datetime import datetime

# 서버 저장 경로
DATA_DIR  = "data"
RMS_FILE  = os.path.join(DATA_DIR, "rms_latest.xlsx")
META_FILE = os.path.join(DATA_DIR, "rms_meta.json")


def get_clean_code(code: str, country: str) -> str:
    """심사용 코드 반환 - 한국은 A 제거"""
    code = str(code).strip()
    if country == '한국' and code.upper().startswith('A'):
        return code[1:]  # A006800 → 006800
    return code


def parse_rms_excel(file) -> pd.DataFrame:
    """
    RMS 엑셀 파싱
    D열(index 3): 국가
    H열(index 7): 종목코드
    J열(index 9): 종목상태
    """
    df_raw = pd.read_excel(file, header=0, dtype=str)
    df_raw = df_raw.fillna("")

    if df_raw.shape[1] < 10:
        raise ValueError(f"열 개수 부족: {df_raw.shape[1]}열 (최소 10열 필요)")

    df = pd.DataFrame()
    df['국가']          = df_raw.iloc[:, 3].str.strip()
    df['종목코드_원본'] = df_raw.iloc[:, 7].str.strip()
    df['RMS상태원문']   = df_raw.iloc[:, 9].str.strip()

    # 빈 종목코드 제거
    df = df[df['종목코드_원본'] != ''].reset_index(drop=True)

    df['종목코드'] = df.apply(
        lambda r: get_clean_code(r['종목코드_원본'], r['국가']), axis=1
    )
    df['RMS상태'] = df['RMS상태원문'].apply(
        lambda x: '정상' if x == '' else f'제한({x})'
    )

    return df[['종목코드_원본', '종목코드', '국가', 'RMS상태', 'RMS상태원문']]


def load_rms_from_server() -> tuple:
    """
    서버(GitHub)에 저장된 RMS 파일 로드
    반환: (DataFrame or None, meta dict or None)
    """
    if not os.path.exists(RMS_FILE):
        return None, None

    try:
        df = parse_rms_excel(RMS_FILE)

        # 메타 파일이 있으면 로드, 없으면 파일 수정일 기준으로 생성
        if os.path.exists(META_FILE):
            with open(META_FILE, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        else:
            from datetime import timezone, timedelta
            kst   = timezone(timedelta(hours=9))
            mtime = os.path.getmtime(RMS_FILE)
            dt    = datetime.fromtimestamp(mtime, tz=kst)
            meta  = {
                'filename'    : 'rms_latest.xlsx',
                'uploaded_at' : dt.strftime('%Y-%m-%d %H:%M'),
                'total'       : len(df),
                'normal'      : int((df['RMS상태'] == '정상').sum()),
                'restricted'  : int((df['RMS상태'] != '정상').sum()),
            }

        return df, meta

    except Exception:
        return None, None


def save_rms_to_server(uploaded_file, original_filename: str) -> dict:
    """
    업로드한 RMS 파일을 서버에 저장
    (앱 내 업로드 버튼 사용 시)
    반환: meta 딕셔너리
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    df = parse_rms_excel(uploaded_file)

    # 파일 저장
    df.to_excel(RMS_FILE, index=False)

    # 메타 저장
    from datetime import timezone, timedelta
    kst     = timezone(timedelta(hours=9))
    now_kst = datetime.now(kst).strftime('%Y-%m-%d %H:%M')

    meta = {
        'filename'    : original_filename,
        'uploaded_at' : now_kst,
        'total'       : len(df),
        'normal'      : int((df['RMS상태'] == '정상').sum()),
        'restricted'  : int((df['RMS상태'] != '정상').sum()),
    }
    with open(META_FILE, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False)

    return meta


def get_rms_status(ticker: str, df_rms: pd.DataFrame) -> dict:
    """
    단건 심사용 — 해당 종목의 RMS 상태 반환
    ticker: 사용자 입력 코드 (A 접두어 없음)
    """
    if df_rms is None or df_rms.empty:
        return {'found': False, 'status': '', 'raw': ''}

    ticker_clean = ticker.strip().upper()

    # 1차: 종목코드(A 제거된 코드)로 조회
    match = df_rms[df_rms['종목코드'].str.strip().str.upper() == ticker_clean]

    # 2차: A 붙여서 원본 조회 (한국 6자리)
    if match.empty and ticker_clean.isdigit() and len(ticker_clean) == 6:
        match = df_rms[df_rms['종목코드_원본'].str.strip().str.upper() == 'A' + ticker_clean]

    if match.empty:
        return {'found': False, 'status': '', 'raw': ''}

    row = match.iloc[0]
    return {
        'found' : True,
        'status': row['RMS상태'],
        'raw'   : row['RMS상태원문']
    }
