# 구글 드라이브 자동 동기화 — 서비스 계정으로 추천종목 추적 시트를 매번 최신 상태로 갱신
# 설정 방법: DRIVE_SETUP.md 참고. 서비스계정 키(service_account.json) 없으면 조용히 스킵.
import io
import os

import pandas as pd

import common as c

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload
except ImportError:
    Credentials = None

SCOPES = ["https://www.googleapis.com/auth/drive"]
SERVICE_ACCOUNT_PATH = os.path.join(c.BASE_DIR, "service_account.json")

COLUMN_LABELS = {
    "date": "추천일", "market": "시장", "code": "종목코드", "name": "종목명",
    "strategy_name": "전략", "buy_price": "매수가", "target": "목표가", "stop_loss": "손절가",
    "risk_reward": "손익비", "backtest_win_rate": "백테스트승률(%)",
    "backtest_avg_return": "백테스트평균수익률(%)", "status": "상태",
    "current_price": "현재가", "current_return_pct": "현재수익률(%)",
    "exit_date": "청산일", "exit_price": "청산가", "realized_return_pct": "실현수익률(%)",
    "last_checked": "마지막확인",
}
COLUMN_ORDER = list(COLUMN_LABELS.keys())


def is_configured():
    return Credentials is not None and os.path.exists(SERVICE_ACCOUNT_PATH)


def _build_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def _prepare_csv_bytes(log_df):
    df = log_df.copy()
    num_cols = ["buy_price", "target", "stop_loss", "current_price", "current_return_pct",
                "exit_price", "realized_return_pct", "risk_reward", "backtest_win_rate", "backtest_avg_return"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").round(2)
    for col in COLUMN_ORDER:
        if col not in df.columns:
            df[col] = None
    df = df[COLUMN_ORDER].rename(columns=COLUMN_LABELS)
    return df.to_csv(index=False).encode("utf-8")


def sync_log(log_df, folder_id, title="StockSignals 추천종목 추적"):
    """log_df를 folder_id 폴더의 구글시트로 동기화. update_file이 내용 변경을 지원하지 않아
    개인 구글 계정에서는 서비스 계정이 저장용량 할당량 0이라 새 파일을 만들 수 없음 — 그래서
    삭제 후 재생성 대신, 기존 파일(사용자 계정으로 최초 1회 생성)의 내용만 덮어쓴다.
    내용 교체는 파일 소유권이 바뀌지 않아 서비스 계정 저장용량을 쓰지 않는다."""
    if not is_configured():
        return False, "서비스 계정 미설정 — DRIVE_SETUP.md 참고 (service_account.json 없음)"
    if log_df is None or log_df.empty:
        return False, "추적 로그가 비어있어 스킵"

    service = _build_service()
    csv_bytes = _prepare_csv_bytes(log_df)
    media = MediaIoBaseUpload(io.BytesIO(csv_bytes), mimetype="text/csv", resumable=False)

    existing = service.files().list(
        q=f"name='{title}' and '{folder_id}' in parents and trashed=false",
        fields="files(id, webViewLink)",
    ).execute().get("files", [])

    if existing:
        file_id = existing[0]["id"]
        updated = service.files().update(fileId=file_id, media_body=media, fields="id,webViewLink").execute()
        return True, updated.get("webViewLink", file_id)

    file_metadata = {"name": title, "parents": [folder_id], "mimeType": "application/vnd.google-apps.spreadsheet"}
    try:
        created = service.files().create(body=file_metadata, media_body=media, fields="id,webViewLink").execute()
        return True, created.get("webViewLink", created.get("id"))
    except Exception as e:
        return False, (
            f"기존 시트가 없고 서비스 계정은 새 파일을 못 만듭니다 (저장용량 할당량 0) — "
            f"사용자 계정으로 '{title}' 시트를 폴더에 한 번 만들어주세요. 원본 에러: {e}"
        )


if __name__ == "__main__":
    from track_recommendations import load_log

    folder_id = c.CONFIG.get("google_drive", {}).get("folder_id", "")
    if not folder_id:
        print("config.json의 google_drive.folder_id가 비어있습니다.")
    else:
        ok, info = sync_log(load_log(), folder_id, c.CONFIG.get("google_drive", {}).get("sheet_title", "StockSignals 추천종목 추적"))
        print(("성공: " if ok else "스킵/실패: ") + str(info))
