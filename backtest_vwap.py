# 단타 - VWAP 되돌림: 진입폭 3종 x 손절 4종 (12조합) (결론: 승률은 높은데 평균≈0(꼬리손실) — README §5)
# 분봉 VWAP이 없어 당일 전형가((고+저+종)/3)를 일봉 VWAP 근사치로 사용
import argparse
import os
from datetime import datetime

import pandas as pd

import common as c
from backtest_daytrade_core import simulate_daytrade, summarize

ENTRY_DEPTHS = [0.003, 0.006, 0.010]  # VWAP 근사치 대비 되돌림 진입폭 3종
STOP_PCTS = [0.005, 0.010, 0.015, 0.020]  # 손절 4종


def make_entry_fn(depth):
    def entry_fn(df, i):
        if i < 1:
            return None
        row = df.iloc[i]
        vwap_approx = (row["High"] + row["Low"] + row["Close"]) / 3
        pullback_price = vwap_approx * (1 - depth)
        if row["Low"] <= pullback_price <= row["High"]:
            return pullback_price
        return None
    return entry_fn


def main():
    parser = argparse.ArgumentParser(description="VWAP 되돌림 단타 백테스트")
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    us_tickers = c.get_us_universe(top_n=500, index="S&P500")

    rows = []
    for market, tickers in (("KR", kr_tickers), ("US", us_tickers)):
        for depth in ENTRY_DEPTHS:
            entry_fn = make_entry_fn(depth)
            for stop_pct in STOP_PCTS:
                all_trades = []
                for code, name in tickers:
                    df = c.fetch_ohlcv(code, days=365 * args.years + 30)
                    if df is None or len(df) < 30:
                        continue
                    df = c.add_indicators(df)
                    trades = simulate_daytrade(df, entry_fn, market, stop_pct=stop_pct)
                    if not trades.empty:
                        all_trades.append(trades)
                combined = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
                stat = summarize(combined)
                stat.update({"market": market, "entry_depth": depth, "stop_pct": stop_pct})
                rows.append(stat)
                print(f"[{market}] 진입폭{depth} 손절{stop_pct}: {stat}")

    result_df = pd.DataFrame(rows)[["market", "entry_depth", "stop_pct", "trades", "win_rate", "avg_return_pct"]]
    print("\n=== VWAP 되돌림 12조합 결과 (수수료 반영) ===")
    print(result_df.to_string(index=False))
    print("결론: 승률은 높게 나와도 평균수익률은 0에 수렴(꼬리손실) — 엣지 없음, 폐기.")

    tag = datetime.now().strftime("%Y-%m-%d")
    result_df.to_csv(os.path.join(c.BASE_DIR, f"daytrade_vwap_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
