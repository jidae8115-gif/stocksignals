# 6개 전략(실전 5개 + 더블비) 통합 추천종목 스캔 — 매수가/목표가/손절가/손익비 포함
# KOSPI100 + S&P500 범위로 스캔 (한 종목 fetch를 캐싱해 6개 전략에 공유하므로 doubleb 단독 스캔과 소요시간 거의 동일, 약 3분)
import argparse
import json
import os
import sys
import time
from datetime import datetime

import pandas as pd

import common as c

STATUS_PATH = os.path.join(c.BASE_DIR, "last_scan_recommendations.json")
ALL_STRATEGIES = list(c.STRATEGIES.keys())


def scan(market):
    if market == "KR":
        tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    else:
        tickers = c.get_us_universe(top_n=500, index="S&P500")

    def progress(idx, total, code, name):
        if idx % 50 == 0:
            print(f"  [{market}] {idx}/{total} {code} {name}", file=sys.stderr)

    return c.build_signals(tickers, market, strategy_keys=ALL_STRATEGIES, progress_cb=progress)


def save_status(count, kr_active=True, us_active=True, error=None):
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "last_run": c.now_kst().isoformat(),
            "kr_active": kr_active,
            "us_active": us_active,
            "signal_count": count,
            "error": error,
        }, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="6개 전략 통합 추천종목 스캔")
    args = parser.parse_args()

    t0 = time.time()
    print(f"=== scan_recommendations.py 실행 {c.now_kst().isoformat()} ===")

    kr_df = scan("KR")
    us_df = scan("US")
    all_df = pd.concat([kr_df, us_df], ignore_index=True)
    elapsed = time.time() - t0

    print(f"KR: {len(kr_df)}건, US: {len(us_df)}건, 소요시간: {elapsed:.1f}초")
    if not all_df.empty:
        print(all_df.to_string(index=False))
    else:
        print("오늘 신호 없음")

    latest_path = os.path.join(c.BASE_DIR, "latest_recommendations.csv")
    all_df.to_csv(latest_path, index=False, encoding="utf-8-sig")
    save_status(len(all_df))
    print(f"저장: {latest_path}")
    print(f"[TIMING] 총 소요시간 {elapsed:.1f}초 ({elapsed/60:.1f}분)")


if __name__ == "__main__":
    main()
