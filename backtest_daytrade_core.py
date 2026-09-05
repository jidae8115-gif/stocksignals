# 단타 백테스트 공용 엔진
# 주의: FinanceDataReader는 일봉만 제공하므로 장중 분봉 대신 당일 O/H/L/C로 근사 시뮬레이션한다.
# (저가가 손절가에 먼저 닿았다고 보수적으로 가정 — 틱 데이터 없이는 정확한 체결 순서를 알 수 없음)
import pandas as pd

FEES = {"KR": 0.0030, "US": 0.0010}  # 왕복 수수료+세금 근사치


def simulate_daytrade(df, entry_fn, market, stop_pct=None, target_pct=None):
    """entry_fn(df, i) -> entry_price(float) or None. 당일 매수·당일 청산(스캘핑/데이트레이드)."""
    trades = []
    fee = FEES.get(market, 0.002)
    for i in range(20, len(df)):
        entry = entry_fn(df, i)
        if entry is None:
            continue

        row = df.iloc[i]
        low, high, close = row["Low"], row["High"], row["Close"]
        exit_price, exit_reason = close, "close"

        if stop_pct is not None:
            stop_price = entry * (1 - stop_pct)
            if low <= stop_price:
                exit_price, exit_reason = stop_price, f"stop_{stop_pct}R"

        if target_pct is not None and exit_reason == "close":
            target_price = entry * (1 + target_pct)
            if high >= target_price:
                exit_price, exit_reason = target_price, f"target_{target_pct}"

        ret_pct = ((exit_price - entry) / entry - fee) * 100
        trades.append({
            "date": df.index[i],
            "entry_price": entry,
            "exit_price": exit_price,
            "return_pct": ret_pct,
            "exit_reason": exit_reason,
        })
    return pd.DataFrame(trades)


def summarize(trades_df):
    if trades_df.empty:
        return {"trades": 0, "win_rate": None, "avg_return_pct": None}
    wins = (trades_df["return_pct"] > 0).sum()
    return {
        "trades": len(trades_df),
        "win_rate": round(wins / len(trades_df) * 100, 2),
        "avg_return_pct": round(trades_df["return_pct"].mean(), 2),
    }


def run_over_universe(tickers, market, entry_fn, stop_pct=None, target_pct=None, years=2, progress_cb=None):
    import common as c
    all_trades = []
    total = len(tickers)
    for idx, (code, name) in enumerate(tickers):
        if progress_cb:
            progress_cb(idx, total, code, name)
        df = c.fetch_ohlcv(code, days=365 * years + 30)
        if df is None or len(df) < 30:
            continue
        df = c.add_indicators(df)
        trades = simulate_daytrade(df, entry_fn, market, stop_pct=stop_pct, target_pct=target_pct)
        if trades.empty:
            continue
        trades["code"] = code
        trades["name"] = name
        all_trades.append(trades)
    if not all_trades:
        return pd.DataFrame()
    return pd.concat(all_trades, ignore_index=True)
