# 백테스트 공용 엔진: 신호 발생일 종가 매수 → 손절가 도달 시 즉시 손절, 목표가(20일선 또는
# 손익비 2:1) 도달 시 익절, 최대 N거래일 지나면 강제청산.
# 예전엔 손절 체크가 전혀 없어서(20일선 익절만 확인) 백테스트 승률이 실제 라이브 추적
# (track_recommendations.py, 매일 손절가 체크)보다 부풀려져 있었음 — live와 동일한 규칙으로 수정.
import pandas as pd

import common as c


def simulate_trades(df, signal_fn, hold_days=5):
    trades = []
    n = len(df)
    for i in range(50, n - 1):
        try:
            if not signal_fn(df, i):
                continue
        except Exception:
            continue

        entry_price = float(df["Close"].iloc[i])
        entry_date = df.index[i]
        sma20 = df["SMA20"].iloc[i]
        atr14 = df["ATR14"].iloc[i]
        stop_loss, target, _ = c.compute_trade_levels(
            entry_price,
            float(sma20) if pd.notna(sma20) else None,
            float(atr14) if pd.notna(atr14) else None,
        )

        exit_price = exit_date = exit_reason = None
        for h in range(1, hold_days + 1):
            j = i + h
            if j >= n:
                break
            low_j = float(df["Low"].iloc[j])
            close_j = float(df["Close"].iloc[j])
            if low_j <= stop_loss:
                # 갭하락으로 시가가 이미 손절가 아래면 시가에 체결(손절가보다 더 나쁠 수 있음).
                open_j = float(df["Open"].iloc[j])
                exit_price, exit_date, exit_reason = min(stop_loss, open_j), df.index[j], "stop_loss"
                break
            if close_j >= target:
                exit_price, exit_date, exit_reason = close_j, df.index[j], "take_profit"
                break
            if h == hold_days:
                exit_price, exit_date, exit_reason = close_j, df.index[j], "force_close"

        if exit_price is None:
            continue

        trades.append({
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "return_pct": (exit_price - entry_price) / entry_price * 100,
            "exit_reason": exit_reason,
            "weekday": entry_date.strftime("%A"),
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


def backtest_universe(tickers, market, strategy_key, hold_days=5, require_volume=False,
                       require_liquidity=False, years=3, progress_cb=None):
    """전 종목에 대해 신호→청산 시뮬레이션을 실행하고 개별 거래 내역을 DataFrame으로 반환."""
    spec = c.STRATEGIES[strategy_key]
    all_trades = []
    total = len(tickers)
    for idx, (code, name) in enumerate(tickers):
        if progress_cb:
            progress_cb(idx, total, code, name)

        df = c.fetch_ohlcv(code, days=365 * years + 60)
        if df is None or len(df) < spec["min_bars"] + hold_days:
            continue
        df = c.add_indicators(df)

        def sig(d, i, _spec=spec):
            if require_volume and not c.has_volume_surge(d, i):
                return False
            if require_liquidity and not c.is_liquid(d, market, i):
                return False
            return _spec["signal_fn"](d, i)

        trades = simulate_trades(df, sig, hold_days=hold_days)
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
