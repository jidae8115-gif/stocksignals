# 단타 - 신규 후보 4종: 2일연속하락반등 / 눌림목 / 전고점돌파갭 / 추세지속 (결론: 최고 +0.05%, 폐기 — README §5)
import argparse
import os
from datetime import datetime

import pandas as pd

import common as c
from backtest_daytrade_core import run_over_universe, summarize


def two_day_down_bounce(df, i):
    """2일 연속 하락 마감 다음날 시가 매수 (낙폭과대 반등 기대)."""
    if i < 3:
        return None
    if df["Close"].iloc[i - 3] > df["Close"].iloc[i - 2] > df["Close"].iloc[i - 1]:
        return df["Open"].iloc[i]
    return None


def pullback_entry(df, i):
    """상승추세(20일선 위) 중 5일선까지 눌린 당일 시가 매수."""
    if i < 20:
        return None
    row = df.iloc[i]
    if pd.isna(row["SMA5"]) or pd.isna(row["SMA20"]):
        return None
    uptrend = row["Close"] > row["SMA20"]
    near_sma5 = abs(row["Low"] - row["SMA5"]) / row["SMA5"] < 0.01
    if uptrend and near_sma5:
        return row["Open"]
    return None


def prior_high_breakout_gap(df, i):
    """직전 20일 고점을 갭상승으로 돌파하며 시작하는 날 시가 매수."""
    if i < 21:
        return None
    prior_high = df["High"].iloc[i - 20:i].max()
    open_ = df["Open"].iloc[i]
    if open_ > prior_high:
        return open_
    return None


def trend_continuation(df, i):
    """5일선 > 20일선(상승추세) 지속 중 당일 양봉 시가 매수."""
    if i < 1:
        return None
    row = df.iloc[i]
    if pd.isna(row["SMA5"]) or pd.isna(row["SMA20"]):
        return None
    if row["SMA5"] > row["SMA20"] and row["Close"] > row["Open"]:
        return row["Open"]
    return None


CANDIDATES = [
    ("2일연속하락반등", two_day_down_bounce),
    ("눌림목", pullback_entry),
    ("전고점돌파갭", prior_high_breakout_gap),
    ("추세지속", trend_continuation),
]


def main():
    parser = argparse.ArgumentParser(description="신규 단타 후보 4종 백테스트")
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    us_tickers = c.get_us_universe(top_n=500, index="S&P500")

    rows = []
    for market, tickers in (("KR", kr_tickers), ("US", us_tickers)):
        for name, fn in CANDIDATES:
            trades = run_over_universe(tickers, market, fn, years=args.years)
            stat = summarize(trades)
            stat.update({"market": market, "candidate": name})
            rows.append(stat)
            print(f"[{market}] {name}: {stat}")

    result_df = pd.DataFrame(rows)[["market", "candidate", "trades", "win_rate", "avg_return_pct"]]
    print("\n=== 신규 후보 4종 결과 (수수료 반영) ===")
    print(result_df.to_string(index=False))
    print("결론: 최고 +0.05% 수준 — 엣지 없음, 폐기.")

    tag = c.now_kst().strftime("%Y-%m-%d")
    result_df.to_csv(os.path.join(c.BASE_DIR, f"daytrade_candidates_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
