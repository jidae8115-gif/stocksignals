# 더블비(Double B) 볼린저밴드 실전 신호 스캔 + 텔레그램 알림
# README §2 실험 결과 표본은 작지만(34~53건) 성적이 제일 좋아 사용자 판단으로 편입.
# KOSPI100 + S&P500 범위로 스캔 (나스닥 전체까지 포함하면 1회 스캔에 25~30분 걸려 30분 주기 감시에 부적합)
import argparse
import json
import os
import sys
import time
from datetime import datetime

import pandas as pd

import common as c

STATUS_PATH = os.path.join(c.BASE_DIR, "last_scan_doubleb.json")


def scan(market):
    if market == "KR":
        tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    else:
        tickers = c.get_us_universe(top_n=500, index="S&P500")

    def progress(idx, total, code, name):
        if idx % 50 == 0:
            print(f"  [{market}] {idx}/{total} {code} {name}", file=sys.stderr)

    return c.build_signals(tickers, market, strategy_keys=["doubleb"], progress_cb=progress)


def main():
    parser = argparse.ArgumentParser(description="더블비 실전 신호 스캔")
    parser.add_argument("--no-notify", action="store_true", help="텔레그램 알림 생략")
    args = parser.parse_args()

    t0 = time.time()
    print(f"=== scan_doubleb.py 실행 {c.now_kst().isoformat()} ===")

    kr_df = scan("KR")
    us_df = scan("US")
    all_df = pd.concat([kr_df, us_df], ignore_index=True)
    elapsed = time.time() - t0

    print(f"KR(더블비): {len(kr_df)}건, US(더블비): {len(us_df)}건, 소요시간: {elapsed:.1f}초")
    if not all_df.empty:
        print(all_df.to_string(index=False))
    else:
        print("오늘 신호 없음")

    if not args.no_notify and not all_df.empty:
        new_df = c.notify_new_signals(all_df)
        print(f"신규 알림 발송: {len(new_df)}건")

    latest_path = os.path.join(c.BASE_DIR, "latest_doubleb.csv")
    all_df.to_csv(latest_path, index=False, encoding="utf-8-sig")
    print(f"저장: {latest_path}")

    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "last_run": c.now_kst().isoformat(),
            "kr_active": True, "us_active": True,
            "signal_count": len(all_df),
        }, f, ensure_ascii=False, indent=2)

    print(f"[TIMING] 총 소요시간 {elapsed:.1f}초 ({elapsed/60:.1f}분)")


if __name__ == "__main__":
    main()
