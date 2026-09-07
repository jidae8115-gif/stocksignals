# 더블비(Double B) 볼린저밴드 백테스트 — BB1(20,종가) + BB2(44,시가) 동시 하단 하회
import argparse
import os
import sys
from datetime import datetime

import pandas as pd

import common as c
from backtest_core import backtest_universe, summarize


def run(market, tickers, volume_filter, years, hold_days, progress_cb):
    trades = backtest_universe(
        tickers, market, "doubleb", hold_days=hold_days,
        require_volume=volume_filter, require_liquidity=volume_filter,
        years=years, progress_cb=progress_cb,
    )
    return trades, summarize(trades)


def main():
    parser = argparse.ArgumentParser(description="더블비 볼린저밴드 백테스트")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--hold-days", type=int, default=5)
    parser.add_argument("--top-n-kr", type=int, default=100)
    parser.add_argument("--top-n-us", type=int, default=500)
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(top_n=args.top_n_kr, market="KOSPI")
    us_tickers = c.get_us_universe(top_n=args.top_n_us, index="ALL")

    def progress(idx, total, code, name):
        if idx % 20 == 0:
            print(f"  {idx}/{total} {code} {name}", file=sys.stderr)

    rows = []
    all_trades = []
    for market, tickers, label in (("KR", kr_tickers, "KOSPI100"), ("US", us_tickers, "S&P500+나스닥")):
        for volume_filter in (False, True):
            trades, stat = run(market, tickers, volume_filter, args.years, args.hold_days, progress)
            stat.update({
                "market": market, "universe": label,
                "volume_filter": "적용" if volume_filter else "미적용",
            })
            rows.append(stat)
            if not trades.empty:
                trades["volume_filter"] = volume_filter
                all_trades.append(trades)
            print(f"[{label}] 거래량필터 {stat['volume_filter']}: {stat}")

    summary_df = pd.DataFrame(rows)[["market", "universe", "volume_filter", "trades", "win_rate", "avg_return_pct"]]
    print("\n=== 더블비 백테스트 요약 (README §2 재현) ===")
    print(summary_df.to_string(index=False))

    tag = c.now_kst().strftime("%Y-%m-%d")
    summary_df.to_csv(os.path.join(c.BASE_DIR, f"backtest_doubleb_summary_{tag}.csv"), index=False, encoding="utf-8-sig")
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(
            os.path.join(c.BASE_DIR, f"backtest_doubleb_trades_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
