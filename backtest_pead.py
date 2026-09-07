# 단타 - PEAD(실적서프라이즈 이후 드리프트): 미스/소폭비트/대폭비트 x 10일/20일 (결론: 전부 마이너스 — README §5)
# FinanceDataReader에는 실적 캘린더가 없어, 급격한 갭+거래량 급증일을 "실적 발표 반응일" 근사치로 사용
import argparse
import os
from datetime import datetime

import pandas as pd

import common as c

MISS_GAP = -0.03       # 갭 -3% 이하: 미스
SMALL_BEAT_RANGE = (0.03, 0.07)  # 갭 +3~7%: 소폭비트
BIG_BEAT_GAP = 0.07    # 갭 +7% 이상: 대폭비트
VOL_SURGE_MIN = 2.0    # 거래량 20일 평균 대비 2배 이상이어야 "실적 반응"으로 간주
HOLD_DAYS = [10, 20]


def classify_event(df, i):
    if i < 1:
        return None
    prev_close = df["Close"].iloc[i - 1]
    open_ = df["Open"].iloc[i]
    vol_ratio = df["VOL_RATIO"].iloc[i]
    if pd.isna(vol_ratio) or vol_ratio < VOL_SURGE_MIN:
        return None
    gap = (open_ - prev_close) / prev_close
    if gap <= MISS_GAP:
        return "미스"
    if SMALL_BEAT_RANGE[0] <= gap < SMALL_BEAT_RANGE[1]:
        return "소폭비트"
    if gap >= BIG_BEAT_GAP:
        return "대폭비트"
    return None


def scan_events(tickers, market, years, progress_cb=None):
    events = []
    total = len(tickers)
    for idx, (code, name) in enumerate(tickers):
        if progress_cb:
            progress_cb(idx, total, code, name)
        df = c.fetch_ohlcv(code, days=365 * years + 40)
        if df is None or len(df) < 40:
            continue
        df = c.add_indicators(df)
        n = len(df)
        for i in range(20, n - max(HOLD_DAYS) - 1):
            category = classify_event(df, i)
            if category is None:
                continue
            entry_close = df["Close"].iloc[i]
            row = {"code": code, "name": name, "market": market, "category": category, "date": df.index[i]}
            for h in HOLD_DAYS:
                j = i + h
                if j >= n:
                    row[f"return_{h}d"] = None
                    continue
                exit_close = df["Close"].iloc[j]
                row[f"return_{h}d"] = (exit_close - entry_close) / entry_close * 100
            events.append(row)
    return pd.DataFrame(events)


def main():
    parser = argparse.ArgumentParser(description="PEAD(실적서프라이즈 드리프트) 백테스트")
    parser.add_argument("--years", type=int, default=2)
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    us_tickers = c.get_us_universe(top_n=500, index="S&P500")

    def progress(idx, total, code, name):
        if idx % 20 == 0:
            print(f"  {idx}/{total} {code} {name}")

    all_events = []
    for market, tickers in (("KR", kr_tickers), ("US", us_tickers)):
        events = scan_events(tickers, market, args.years, progress_cb=progress)
        if not events.empty:
            all_events.append(events)

    if not all_events:
        print("이벤트가 발견되지 않았습니다.")
        return

    events_df = pd.concat(all_events, ignore_index=True)

    rows = []
    for market in events_df["market"].unique():
        for category in ["미스", "소폭비트", "대폭비트"]:
            sub = events_df[(events_df["market"] == market) & (events_df["category"] == category)]
            if sub.empty:
                continue
            for h in HOLD_DAYS:
                col = f"return_{h}d"
                valid = sub[col].dropna()
                if valid.empty:
                    continue
                rows.append({
                    "market": market, "category": category, "hold_days": h,
                    "trades": len(valid),
                    "win_rate": round((valid > 0).mean() * 100, 2),
                    "avg_return_pct": round(valid.mean(), 2),
                })

    result_df = pd.DataFrame(rows)
    print("\n=== PEAD 결과 (미스/소폭비트/대폭비트 x 10일/20일) ===")
    print(result_df.to_string(index=False))
    print("결론: 전부 마이너스 — 엣지 없음, 폐기.")

    tag = c.now_kst().strftime("%Y-%m-%d")
    result_df.to_csv(os.path.join(c.BASE_DIR, f"daytrade_pead_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
