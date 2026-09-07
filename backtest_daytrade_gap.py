# 단타 - 갭매매: 갭상승추종 / 갭하락반등 (결론: 엣지 없음, 폐기 — README §5)
import argparse
import os
from datetime import datetime

import pandas as pd

import common as c
from backtest_daytrade_core import run_over_universe, summarize

GAP_THRESHOLD = 0.02  # 2% 갭


def gap_up_follow(df, i):
    """전일 종가 대비 2%+ 갭상승 출발 → 당일 상승 추종 매수(시가 매수)."""
    if i < 1:
        return None
    prev_close = df["Close"].iloc[i - 1]
    open_ = df["Open"].iloc[i]
    if open_ >= prev_close * (1 + GAP_THRESHOLD):
        return open_
    return None


def gap_down_bounce(df, i):
    """전일 종가 대비 2%+ 갭하락 출발 → 낙폭과대 반등 기대 매수(시가 매수)."""
    if i < 1:
        return None
    prev_close = df["Close"].iloc[i - 1]
    open_ = df["Open"].iloc[i]
    if open_ <= prev_close * (1 - GAP_THRESHOLD):
        return open_
    return None


def main():
    parser = argparse.ArgumentParser(description="갭매매 단타 백테스트")
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    us_tickers = c.get_us_universe(top_n=500, index="S&P500")

    rows = []
    for market, tickers in (("KR", kr_tickers), ("US", us_tickers)):
        for name, fn in (("갭상승추종", gap_up_follow), ("갭하락반등", gap_down_bounce)):
            trades = run_over_universe(tickers, market, fn, years=args.years)
            stat = summarize(trades)
            stat.update({"market": market, "type": name})
            rows.append(stat)
            print(f"[{market}] {name}: {stat}")

    result_df = pd.DataFrame(rows)[["market", "type", "trades", "win_rate", "avg_return_pct"]]
    print("\n=== 갭매매 결과 (수수료 반영) ===")
    print(result_df.to_string(index=False))
    print("결론: 최고 수익률도 거의 0에 가까움 — 엣지 없음, 폐기.")

    tag = c.now_kst().strftime("%Y-%m-%d")
    result_df.to_csv(os.path.join(c.BASE_DIR, f"daytrade_gap_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
