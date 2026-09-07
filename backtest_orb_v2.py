# 단타 - ORB(Opening Range Breakout): 손절無 + 손절 1.0R/1.5R/2.0R (결론: 전부 마이너스 — README §5)
# 분봉 데이터가 없어 시가 대비 +0.5% 를 "오프닝 레인지 상단" 근사치로 사용
import argparse
import os
from datetime import datetime

import pandas as pd

import common as c
from backtest_daytrade_core import run_over_universe, summarize

OPENING_RANGE_PCT = 0.005  # 시가 대비 +0.5%를 오프닝 레인지 상단 근사치로 사용
R_UNIT = OPENING_RANGE_PCT  # 리스크 단위(R) = 진입가 - 시가


def orb_entry(df, i):
    open_ = df["Open"].iloc[i]
    high = df["High"].iloc[i]
    breakout_price = open_ * (1 + OPENING_RANGE_PCT)
    if high >= breakout_price:
        return breakout_price
    return None


def main():
    parser = argparse.ArgumentParser(description="ORB 단타 백테스트")
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    us_tickers = c.get_us_universe(top_n=500, index="S&P500")

    variants = [("손절無", None), ("손절1.0R", 1.0 * R_UNIT), ("손절1.5R", 1.5 * R_UNIT), ("손절2.0R", 2.0 * R_UNIT)]

    rows = []
    for market, tickers in (("KR", kr_tickers), ("US", us_tickers)):
        for label, stop_pct in variants:
            trades = run_over_universe(tickers, market, orb_entry, stop_pct=stop_pct, years=args.years)
            stat = summarize(trades)
            stat.update({"market": market, "variant": label})
            rows.append(stat)
            print(f"[{market}] {label}: {stat}")

    result_df = pd.DataFrame(rows)[["market", "variant", "trades", "win_rate", "avg_return_pct"]]
    print("\n=== ORB 결과 (수수료 반영) ===")
    print(result_df.to_string(index=False))
    print("결론: 전부 마이너스 — 엣지 없음, 폐기.")

    tag = c.now_kst().strftime("%Y-%m-%d")
    result_df.to_csv(os.path.join(c.BASE_DIR, f"daytrade_orb_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
