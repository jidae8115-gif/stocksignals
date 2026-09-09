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

# 종가베팅-모멘텀연속(코스닥)은 코스닥에서만 검증된 전략이라 코스피/미국 스캔에서는 제외하고
# 코스닥 전용 스캔에서만 적용한다.
_KOSDAQ_ONLY = "momentum_continuation_v2"
KOSPI_STRATEGIES = [k for k in c.STRATEGIES.keys() if k != _KOSDAQ_ONLY]
US_STRATEGIES = KOSPI_STRATEGIES
KOSDAQ_STRATEGIES = [_KOSDAQ_ONLY]
ALL_STRATEGIES = list(c.STRATEGIES.keys())  # scan_signals.py 등 기존 참조 호환용


def scan(market):
    def make_progress(label):
        def progress(idx, total, code, name):
            if idx % 50 == 0:
                print(f"  [{label}] {idx}/{total} {code} {name}", file=sys.stderr)
        return progress

    if market == "KR":
        kospi_tickers = c.get_kr_universe(top_n=100, market="KOSPI")
        kosdaq_tickers = c.get_kr_universe(top_n=150, market="KOSDAQ")
        kospi_df = c.build_signals(kospi_tickers, "KR", strategy_keys=KOSPI_STRATEGIES, progress_cb=make_progress("KR-KOSPI"))
        kosdaq_df = c.build_signals(kosdaq_tickers, "KR", strategy_keys=KOSDAQ_STRATEGIES, progress_cb=make_progress("KR-KOSDAQ"))
        return pd.concat([kospi_df, kosdaq_df], ignore_index=True)

    tickers = c.get_us_universe(top_n=500, index="S&P500")
    return c.build_signals(tickers, market, strategy_keys=US_STRATEGIES, progress_cb=make_progress("US"))


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
