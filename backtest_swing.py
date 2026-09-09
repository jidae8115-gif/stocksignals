# 기존 5개 전략 백테스트 (KOSPI100 / S&P500 시총 상위)
import argparse
import os
import sys
from datetime import datetime

import pandas as pd

import common as c
from backtest_core import backtest_universe, summarize

FIVE_STRATEGIES = ["bb_lower", "rsi_oversold", "golden_cross", "new_high_20", "rising_bearish"]

# 코스닥 전용으로 검증된 전략 — KOSPI100/S&P500 유니버스가 아니라 별도 KOSDAQ 유니버스로 백테스트.
KOSDAQ_ONLY_STRATEGIES = ["momentum_continuation_v2"]


def main():
    parser = argparse.ArgumentParser(description="기존 5개 전략 백테스트 (KOSPI100/S&P500)")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--volume-filter", action="store_true", help="거래량 필터 적용 (기본 미적용)")
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    us_tickers = c.get_us_universe(top_n=500, index="S&P500")

    def progress(idx, total, code, name):
        if idx % 20 == 0:
            print(f"  {idx}/{total} {code} {name}", file=sys.stderr)

    kosdaq_tickers = c.get_kr_universe(top_n=200, market="KOSDAQ")

    rows = []
    all_trades = []
    for market, tickers in (("KR", kr_tickers), ("US", us_tickers)):
        for strat in FIVE_STRATEGIES:
            trades = backtest_universe(
                tickers, market, strat, hold_days=args.hold_days,
                require_volume=args.volume_filter, require_liquidity=args.volume_filter,
                years=args.years, progress_cb=progress,
            )
            stat = summarize(trades)
            stat.update({"market": market, "strategy": strat, "strategy_name": c.STRATEGIES[strat]["name"]})
            rows.append(stat)
            if not trades.empty:
                all_trades.append(trades)
            print(f"[{market}] {c.STRATEGIES[strat]['name']}: {stat}")

    for strat in KOSDAQ_ONLY_STRATEGIES:
        trades = backtest_universe(
            kosdaq_tickers, "KR", strat, hold_days=args.hold_days,
            require_volume=False, require_liquidity=True,
            years=args.years, progress_cb=progress,
        )
        stat = summarize(trades)
        stat.update({"market": "KR", "strategy": strat, "strategy_name": c.STRATEGIES[strat]["name"]})
        rows.append(stat)
        if not trades.empty:
            all_trades.append(trades)
        print(f"[KR-KOSDAQ] {c.STRATEGIES[strat]['name']}: {stat}")

    summary_df = pd.DataFrame(rows)[["market", "strategy", "strategy_name", "trades", "win_rate", "avg_return_pct"]]
    print("\n=== 요약 ===")
    print(summary_df.to_string(index=False))

    out_dir = c.BASE_DIR
    tag = c.now_kst().strftime("%Y-%m-%d")
    summary_df.to_csv(os.path.join(out_dir, f"backtest_swing_summary_{tag}.csv"), index=False, encoding="utf-8-sig")
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(
            os.path.join(out_dir, f"backtest_swing_trades_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
