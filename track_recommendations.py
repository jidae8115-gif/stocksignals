# 추천종목 성과 추적 — latest_recommendations.csv의 신규 신호를 recommendations_log.csv에 누적하고,
# 기존 보유중(OPEN) 건은 현재가/현재수익률을 갱신하며 목표가·손절가 도달 또는 5거래일 강제청산 여부를 판정.
# backtest_core.simulate_trades()와 동일한 보유규칙(최대 5거래일)에 손절가 도달 조건만 추가.
import os
from datetime import datetime

import pandas as pd

import common as c

LOG_PATH = os.path.join(c.BASE_DIR, "recommendations_log.csv")
LOG_COLUMNS = [
    "date", "market", "code", "name", "strategy", "strategy_name",
    "buy_price", "target", "stop_loss", "risk_reward",
    "backtest_win_rate", "backtest_avg_return",
    "status", "current_price", "current_return_pct",
    "exit_date", "exit_price", "realized_return_pct", "last_checked",
]


def load_log():
    if os.path.exists(LOG_PATH):
        return pd.read_csv(LOG_PATH, dtype={"code": str})
    return pd.DataFrame(columns=LOG_COLUMNS)


def append_new_recommendations(log_df, latest_df):
    if latest_df is None or latest_df.empty:
        return log_df

    existing_keys = set()
    if not log_df.empty:
        existing_keys = set(zip(log_df["date"], log_df["market"], log_df["code"], log_df["strategy"]))

    new_rows = []
    for _, row in latest_df.iterrows():
        key = (row["date"], row["market"], row["code"], row["strategy"])
        if key in existing_keys:
            continue
        new_rows.append({
            "date": row["date"], "market": row["market"], "code": row["code"], "name": row["name"],
            "strategy": row["strategy"], "strategy_name": row["strategy_name"],
            "buy_price": row["buy_price"], "target": row["target"], "stop_loss": row["stop_loss"],
            "risk_reward": row["risk_reward"],
            "backtest_win_rate": row.get("backtest_win_rate"), "backtest_avg_return": row.get("backtest_avg_return"),
            "status": "OPEN", "current_price": row["buy_price"], "current_return_pct": 0.0,
            "exit_date": None, "exit_price": None, "realized_return_pct": None,
            "last_checked": c.now_kst().isoformat(),
        })

    if new_rows:
        new_df = pd.DataFrame(new_rows, columns=LOG_COLUMNS)
        log_df = new_df if log_df.empty else pd.concat([log_df, new_df], ignore_index=True)
    return log_df


def update_open_positions(log_df):
    if log_df.empty:
        return log_df

    open_idx = log_df.index[log_df["status"] == "OPEN"]
    for idx in open_idx:
        row = log_df.loc[idx]
        df = c.fetch_ohlcv(row["code"], days=30)
        if df is None:
            continue

        entry_date = pd.to_datetime(row["date"])
        forward = df[df.index > entry_date]
        if forward.empty:
            continue

        target, stop = float(row["target"]), float(row["stop_loss"])
        status, exit_date, exit_price = "OPEN", None, None

        for h, (dt, r) in enumerate(forward.iterrows(), start=1):
            if r["Low"] <= stop:
                status, exit_date, exit_price = "STOP_HIT", dt, stop
                break
            if r["Close"] >= target:
                status, exit_date, exit_price = "TARGET_HIT", dt, target
                break
            if h >= 5:
                status, exit_date, exit_price = "FORCE_CLOSED", dt, float(r["Close"])
                break

        last_close = float(df["Close"].iloc[-1])
        log_df.at[idx, "current_price"] = last_close
        log_df.at[idx, "current_return_pct"] = round((last_close - row["buy_price"]) / row["buy_price"] * 100, 2)
        log_df.at[idx, "last_checked"] = c.now_kst().isoformat()

        if status != "OPEN":
            log_df.at[idx, "status"] = status
            log_df.at[idx, "exit_date"] = exit_date.strftime("%Y-%m-%d")
            log_df.at[idx, "exit_price"] = exit_price
            log_df.at[idx, "realized_return_pct"] = round((exit_price - row["buy_price"]) / row["buy_price"] * 100, 2)

    return log_df


def main():
    log_df = load_log()

    latest_path = os.path.join(c.BASE_DIR, "latest_recommendations.csv")
    latest_df = pd.read_csv(latest_path, dtype={"code": str}) if os.path.exists(latest_path) else None

    log_df = append_new_recommendations(log_df, latest_df)
    log_df = update_open_positions(log_df)
    log_df.to_csv(LOG_PATH, index=False, encoding="utf-8-sig")

    open_n = int((log_df["status"] == "OPEN").sum()) if not log_df.empty else 0
    closed = log_df[log_df["status"] != "OPEN"] if not log_df.empty else log_df
    win_n = int((closed["status"] == "TARGET_HIT").sum()) if not closed.empty else 0
    print(f"추적 로그 갱신: 총 {len(log_df)}건 (OPEN {open_n}건, 청산 {len(closed)}건 중 목표달성 {win_n}건)")
    print(f"저장: {LOG_PATH}")

    import drive_sync
    folder_id = c.CONFIG.get("google_drive", {}).get("folder_id", "")
    sheet_title = c.CONFIG.get("google_drive", {}).get("sheet_title", "StockSignals 추천종목 추적")
    if folder_id:
        ok, info = drive_sync.sync_log(log_df, folder_id, sheet_title)
        print(("구글드라이브 동기화 성공: " if ok else "구글드라이브 동기화 스킵: ") + str(info))


if __name__ == "__main__":
    main()
