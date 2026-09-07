# 30분 감시봇 — 장시간(한국 09:00~15:30 / 미국 22:00~06:30) 아니면 즉시 스킵
import sys
from datetime import datetime

import pandas as pd

import common as c
from find_entries import scan


def main():
    kr_active = c.is_market_hours("KR")
    us_active = c.is_market_hours("US")

    if not kr_active and not us_active:
        print(f"{c.now_kst().isoformat()} 장시간 아님 — 스킵")
        return

    print(f"=== watch_signals.py 실행 {c.now_kst().isoformat()} (KR={kr_active} US={us_active}) ===")

    frames = []
    if kr_active:
        frames.append(scan("KR"))
    if us_active:
        frames.append(scan("US"))

    all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if all_df.empty:
        print("신호 없음")
        return

    new_df = c.notify_new_signals(all_df)
    print(f"신규 알림: {len(new_df)}건 / 전체 감지: {len(all_df)}건")


if __name__ == "__main__":
    main()
