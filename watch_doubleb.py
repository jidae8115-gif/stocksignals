# 더블비(Double B) 30분 감시봇 — 장시간(한국 09:00~15:30 / 미국 22:00~06:30) 아니면 즉시 스킵
# 실측 스캔시간(KOSPI100+S&P500, 600종목) 약 2.9분 — 30분 주기면 약 10배 여유
# 알림 채널: 텔레그램 대신 대시보드(app.py) — 매 실행마다 latest_doubleb.csv + last_scan_doubleb.json 갱신
import json
import os
import traceback
from datetime import datetime

import pandas as pd

import common as c
from scan_doubleb import scan

STATUS_PATH = os.path.join(c.BASE_DIR, "last_scan_doubleb.json")


def save_status(kr_active, us_active, count, error=None):
    status = {
        "last_run": c.now_kst().isoformat(),
        "kr_active": kr_active,
        "us_active": us_active,
        "signal_count": count,
        "error": error,
    }
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def main():
    kr_active = c.is_market_hours("KR")
    us_active = c.is_market_hours("US")

    if not kr_active and not us_active:
        print(f"{c.now_kst().isoformat()} 장시간 아님 — 스킵")
        return

    print(f"=== watch_doubleb.py 실행 {c.now_kst().isoformat()} (KR={kr_active} US={us_active}) ===")

    try:
        frames = []
        if kr_active:
            frames.append(scan("KR"))
        if us_active:
            frames.append(scan("US"))

        all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        latest_path = os.path.join(c.BASE_DIR, "latest_doubleb.csv")
        all_df.to_csv(latest_path, index=False, encoding="utf-8-sig")
        save_status(kr_active, us_active, len(all_df))

        print(f"신호 {len(all_df)}건 — {latest_path} 갱신 (대시보드에서 확인 가능)")
    except Exception as e:
        # 스캔 실패해도 대시보드가 "마지막 성공 몇 시간 전"으로 조용히 낡는 대신
        # 에러 사유를 상태 파일에 남겨 대시보드에서 바로 보이게 한다.
        err_msg = f"{type(e).__name__}: {e}"
        print(f"[ERROR] {err_msg}")
        traceback.print_exc()
        save_status(kr_active, us_active, 0, error=err_msg)


if __name__ == "__main__":
    main()
