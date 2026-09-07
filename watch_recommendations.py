# 6개 전략(실전 5개 + 더블비) 통합 추천종목 30분 감시봇 — 장시간 아니면 즉시 스킵
# 알림 채널: 텔레그램(신규 신호만, notified_state.json으로 중복 방지) + 대시보드(app.py) —
# 매 실행마다 latest_recommendations.csv + last_scan_recommendations.json 갱신
import os
import traceback
from datetime import datetime

import pandas as pd

import common as c
from scan_recommendations import scan, save_status, STATUS_PATH  # noqa: F401 (STATUS_PATH re-export)


def main():
    kr_active = c.is_market_hours("KR")
    us_active = c.is_market_hours("US")

    if not kr_active and not us_active:
        print(f"{c.now_kst().isoformat()} 장시간 아님 — 스킵")
        return

    print(f"=== watch_recommendations.py 실행 {c.now_kst().isoformat()} (KR={kr_active} US={us_active}) ===")

    try:
        frames = []
        if kr_active:
            frames.append(scan("KR"))
        if us_active:
            frames.append(scan("US"))

        all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        latest_path = os.path.join(c.BASE_DIR, "latest_recommendations.csv")
        all_df.to_csv(latest_path, index=False, encoding="utf-8-sig")
        save_status(len(all_df), kr_active=kr_active, us_active=us_active)

        new_df = c.notify_new_signals(all_df) if not all_df.empty else all_df
        print(f"신호 {len(all_df)}건(신규 {len(new_df)}건 텔레그램 발송) — latest_recommendations.csv 갱신")
    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        print(f"[ERROR] {err_msg}")
        traceback.print_exc()
        save_status(0, kr_active=kr_active, us_active=us_active, error=err_msg)


if __name__ == "__main__":
    main()
