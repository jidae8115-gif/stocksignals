# 전체 유니버스(코스피+코스닥 / S&P500+나스닥) 6개 전략 재검증
import argparse
import os
import sys
from datetime import datetime

import pandas as pd

import common as c
from backtest_core import backtest_universe, summarize

SIX_STRATEGIES = ["doubleb", "rsi_oversold", "bb_lower", "golden_cross", "new_high_20", "rising_bearish"]


def main():
    parser = argparse.ArgumentParser(description="전체 시장 6개 전략 백테스트")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--hold-days", type=int, default=5)
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(market="ALL")
    us_tickers = c.get_us_universe(index="ALL")
    print(f"코스피+코스닥 {len(kr_tickers)}종목, S&P500+나스닥 {len(us_tickers)}종목")

    def progress(idx, total, code, name):
        if idx % 50 == 0:
            print(f"  {idx}/{total} {code} {name}", file=sys.stderr)

    rows = []
    for market, tickers, label in (("KR", kr_tickers, "코스피+코스닥"), ("US", us_tickers, "S&P500+나스닥")):
        for strat in SIX_STRATEGIES:
            trades = backtest_universe(
                tickers, market, strat, hold_days=args.hold_days,
                require_volume=False, require_liquidity=False,
                years=args.years, progress_cb=progress,
            )
            stat = summarize(trades)
            stat.update({"market": label, "strategy": strat, "strategy_name": c.STRATEGIES[strat]["name"]})
            rows.append(stat)
            print(f"[{label}] {c.STRATEGIES[strat]['name']}: {stat}")

    summary_df = pd.DataFrame(rows)[["market", "strategy", "strategy_name", "trades", "win_rate", "avg_return_pct"]]
    summary_df = summary_df.sort_values(["market", "win_rate"], ascending=[True, False])
    print("\n=== 전체 유니버스 백테스트 요약 (README §3 재현) ===")
    print(summary_df.to_string(index=False))

    tag = c.now_kst().strftime("%Y-%m-%d")
    summary_df.to_csv(os.path.join(c.BASE_DIR, f"backtest_full_universe_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
