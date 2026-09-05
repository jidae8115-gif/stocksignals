# 더블비 5분봉 당일 실시간 진단 — KOSPI100 + S&P500, 오늘(또는 가장 최근 거래일) 하루치만
# 목적: 일봉 규칙(BB1 20기간/BB2 44기간)을 그대로 5분봉에 적용해 "장중 언제 신호가 형성되는지" 확인.
# 통계적 승률 백테스트가 아님 — 하루치 데이터라 표본이 극히 적음(참고용 진단 도구).
# 보유규칙: 20기간(5분봉=100분) 이동평균 도달 시 익절, 아니면 당일 장마감까지 보유 후 강제청산.
import argparse
from datetime import datetime

import pandas as pd

import common as c

try:
    import yfinance as yf
except ImportError:
    yf = None


def get_kr_tickers_with_suffix(market="KOSPI", top_n=None):
    """(code, name, yahoo_suffix) 목록. KOSPI는 .KS, KOSDAQ은 .KQ — 야후 파이낸스 규칙."""
    df = c._fetch_krx_listing()
    mkt_map = {"KOSPI": "STK", "KOSDAQ": "KSQ"}
    if market == "ALL":
        df = df[df["MarketId"].isin(mkt_map.values())]
    else:
        df = df[df["MarketId"] == mkt_map[market]]
    if "Marcap" in df.columns:
        df = df.sort_values("Marcap", ascending=False)
    if top_n:
        df = df.head(top_n)
    suffix_map = {"STK": ".KS", "KSQ": ".KQ"}
    return [(row["Code"], row["Name"], suffix_map[row["MarketId"]]) for _, row in df.iterrows()]


def fetch_intraday_5m(yf_ticker):
    df = yf.download(yf_ticker, period="1d", interval="5m", progress=False, auto_adjust=False)
    if df is None or df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.loc[:, ~df.columns.duplicated()]  # 일부 티커(SPAC 등)는 중복 컬럼명이 생겨 이후 계산이 깨짐
    df = df.rename(columns=str.title)
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(df.columns):
        return None
    return df[["Open", "High", "Low", "Close", "Volume"]]


def simulate_intraday_doubleb(df):
    """당일 5분봉 안에서 더블비 신호 → 20기간(5분봉) 도달 시 익절, 아니면 당일 장마감 강제청산."""
    df = c.add_indicators(df)
    trades = []
    in_position_until = -1  # 같은 종목 중복 진입 방지(청산 전까지 재진입 안 함)

    for i in range(50, len(df)):
        if i <= in_position_until:
            continue
        try:
            if not c.signal_doubleb(df, i):
                continue
        except Exception:
            continue

        entry_time = df.index[i]
        entry_price = float(df["Close"].iloc[i])
        sma20 = float(df["SMA20"].iloc[i]) if pd.notna(df["SMA20"].iloc[i]) else None
        atr = float(df["ATR14"].iloc[i]) if pd.notna(df["ATR14"].iloc[i]) else None
        stop, target, rr = c.compute_trade_levels(entry_price, sma20, atr)

        exit_time, exit_price, exit_reason = None, None, "still_open"
        for j in range(i + 1, len(df)):
            close_j = float(df["Close"].iloc[j])
            if close_j >= target:
                exit_time, exit_price, exit_reason = df.index[j], close_j, "target_hit"
                in_position_until = j
                break
            if j == len(df) - 1:
                exit_time, exit_price, exit_reason = df.index[j], close_j, "force_close_eod"
                in_position_until = j

        if exit_time is None:
            exit_time, exit_price, exit_reason = None, None, "still_open"
            in_position_until = len(df) - 1

        trades.append({
            "entry_time": entry_time, "entry_price": entry_price,
            "target": target, "stop_loss": stop, "risk_reward": rr,
            "exit_time": exit_time, "exit_price": exit_price, "exit_reason": exit_reason,
            "return_pct": round((exit_price - entry_price) / entry_price * 100, 2) if exit_price else None,
        })

    return pd.DataFrame(trades)


def main():
    parser = argparse.ArgumentParser(description="더블비 5분봉 당일 실시간 진단 (KOSPI100+S&P500)")
    parser.add_argument("--top-n-kr", type=int, default=0, help="0=전체")
    parser.add_argument("--top-n-us", type=int, default=0, help="0=전체")
    parser.add_argument("--kr-market", choices=["KOSPI", "ALL"], default="ALL", help="ALL=코스피+코스닥")
    parser.add_argument("--us-index", choices=["S&P500", "ALL"], default="ALL", help="ALL=S&P500+나스닥")
    args = parser.parse_args()

    if yf is None:
        print("yfinance가 설치되어 있지 않습니다: pip install yfinance")
        return

    kr_tickers = get_kr_tickers_with_suffix(market=args.kr_market, top_n=args.top_n_kr or None)
    us_tickers = [(code, name, code) for code, name in c.get_us_universe(top_n=args.top_n_us or None, index=args.us_index)]
    print(f"코스피{'+ 코스닥' if args.kr_market == 'ALL' else ''} {len(kr_tickers)}종목, "
          f"S&P500{'+나스닥' if args.us_index == 'ALL' else ''} {len(us_tickers)}종목")

    all_trades = []
    for idx, (code, name, yf_code) in enumerate(kr_tickers):
        if idx % 50 == 0:
            print(f"[KR] {idx}/{len(kr_tickers)} {code} {name}")
        try:
            df = fetch_intraday_5m(yf_code)
            if df is None or len(df) < 51:
                continue
            trades = simulate_intraday_doubleb(df)
            if not trades.empty:
                trades["market"] = "KR"
                trades["code"] = code
                trades["name"] = name
                all_trades.append(trades)
        except Exception as e:
            print(f"  [SKIP] {code} {name}: {e}")
            continue

    for idx, (code, name, yf_code) in enumerate(us_tickers):
        if idx % 50 == 0:
            print(f"[US] {idx}/{len(us_tickers)} {code} {name}")
        try:
            df = fetch_intraday_5m(yf_code)
            if df is None or len(df) < 51:
                continue
            trades = simulate_intraday_doubleb(df)
            if not trades.empty:
                trades["market"] = "US"
                trades["code"] = code
                trades["name"] = name
                all_trades.append(trades)
        except Exception as e:
            print(f"  [SKIP] {code} {name}: {e}")
            continue

    result = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    print(f"\n=== 더블비 5분봉 당일 진단 결과: {len(result)}건 ===")
    if not result.empty:
        cols = ["market", "code", "name", "entry_time", "entry_price", "target", "stop_loss",
                "risk_reward", "exit_time", "exit_price", "exit_reason", "return_pct"]
        print(result[cols].to_string(index=False))
        closed = result[result["exit_reason"] != "still_open"]
        if not closed.empty:
            win_rate = round((closed["return_pct"] > 0).mean() * 100, 2)
            print(f"\n청산 {len(closed)}건 중 승률 {win_rate}% (표본이 하루치라 참고용)")
    else:
        print("오늘(최근 거래일) 5분봉 기준으로는 더블비 신호가 형성되지 않았습니다.")

    tag = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = f"backtest_doubleb_intraday_{tag}.csv"
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
