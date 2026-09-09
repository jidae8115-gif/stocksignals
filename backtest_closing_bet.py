# 종가베팅 전략 백테스트 — "당일 종가 매수 → 다음날 시가 매도" 1일 홀딩 구조.
# 기존 backtest_core.simulate_trades()(다중일 보유 + 20일선 익절)와 청산 규칙이 근본적으로
# 달라 별도 엔진으로 구현. 유형1(모멘텀연속)/유형2(눌림반등) 두 시그널을 각각 검증.
import argparse
import os
import sys

import pandas as pd

import common as c

CLOSING_BET_KEYS = list(c.CLOSING_BET_STRATEGIES.keys())


def simulate_closing_bet(df, signal_fn):
    """신호일 종가 매수 → 다음 거래일 시가 매도. 손절은 '매수가 밑으로 내려가면 즉시 매도'인데,
    일봉만으로는 장중 손절 시점을 알 수 없으므로 다음날 시가 하나로 손익이 정해지는 구조로 근사
    (시가가 매수가보다 낮으면 그 자체가 손절 실현, 높으면 익절 실현)."""
    trades = []
    n = len(df)
    for i in range(25, n - 1):
        try:
            if not signal_fn(df, i):
                continue
        except Exception:
            continue

        entry_price = float(df["Close"].iloc[i])
        entry_date = df.index[i]
        exit_price = float(df["Open"].iloc[i + 1])
        exit_date = df.index[i + 1]

        trades.append({
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "return_pct": (exit_price - entry_price) / entry_price * 100,
            "exit_reason": "next_day_open",
            "weekday": entry_date.strftime("%A"),
        })
    return pd.DataFrame(trades)


def backtest_universe(tickers, market, strategy_key, years=3, require_volume=False,
                       require_liquidity=False, progress_cb=None):
    spec = c.CLOSING_BET_STRATEGIES[strategy_key]
    all_trades = []
    total = len(tickers)
    for idx, (code, name) in enumerate(tickers):
        if progress_cb:
            progress_cb(idx, total, code, name)

        df = c.fetch_ohlcv(code, days=365 * years + 60)
        if df is None or len(df) < spec["min_bars"] + 1:
            continue
        df = c.add_indicators(df)

        def sig(d, i, _spec=spec):
            if require_volume and not c.has_volume_surge(d, i):
                return False
            if require_liquidity and not c.is_liquid(d, market, i):
                return False
            return _spec["signal_fn"](d, i)

        trades = simulate_closing_bet(df, sig)
        if trades.empty:
            continue
        trades["code"] = code
        trades["name"] = name
        trades["market"] = market
        trades["strategy"] = strategy_key
        all_trades.append(trades)

    if not all_trades:
        return pd.DataFrame()
    return pd.concat(all_trades, ignore_index=True)


def summarize(trades_df):
    if trades_df.empty:
        return {"trades": 0, "win_rate": None, "avg_return_pct": None}
    wins = (trades_df["return_pct"] > 0).sum()
    return {
        "trades": len(trades_df),
        "win_rate": round(wins / len(trades_df) * 100, 2),
        "avg_return_pct": round(trades_df["return_pct"].mean(), 2),
    }


def main():
    parser = argparse.ArgumentParser(description="종가베팅 전략 백테스트 (당일 종가매수/익일 시가매도)")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--kr-market", choices=["KOSPI", "ALL"], default="KOSPI", help="ALL=코스피+코스닥")
    parser.add_argument("--top-n", type=int, default=100)
    parser.add_argument("--volume-filter", action="store_true", help="거래량 급증·유동성 필터 적용")
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(top_n=args.top_n, market=args.kr_market)

    def progress(idx, total, code, name):
        if idx % 20 == 0:
            print(f"  {idx}/{total} {code} {name}", file=sys.stderr)

    rows = []
    all_trades = []
    for strat in CLOSING_BET_KEYS:
        trades = backtest_universe(
            kr_tickers, "KR", strat, years=args.years,
            require_volume=args.volume_filter, require_liquidity=args.volume_filter,
            progress_cb=progress,
        )
        stat = summarize(trades)
        stat.update({"market": "KR", "strategy": strat, "strategy_name": c.CLOSING_BET_STRATEGIES[strat]["name"]})
        rows.append(stat)
        if not trades.empty:
            all_trades.append(trades)
        print(f"[KR] {c.CLOSING_BET_STRATEGIES[strat]['name']}: {stat}")

    summary_df = pd.DataFrame(rows)[["market", "strategy", "strategy_name", "trades", "win_rate", "avg_return_pct"]]
    print("\n=== 요약 ===")
    print(summary_df.to_string(index=False))

    tag = c.now_kst().strftime("%Y-%m-%d")
    summary_df.to_csv(os.path.join(c.BASE_DIR, f"backtest_closing_bet_summary_{tag}.csv"), index=False, encoding="utf-8-sig")
    if all_trades:
        pd.concat(all_trades, ignore_index=True).to_csv(
            os.path.join(c.BASE_DIR, f"backtest_closing_bet_trades_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
