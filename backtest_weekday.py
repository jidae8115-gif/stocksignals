# 요일 효과 분석 (참고용) — 신호 발생 요일(월~금)별 이후 성과 비교
# 일봉 데이터라 장중 시간대 분석은 불가능, 요일 단위만 가능
import argparse
import os
from datetime import datetime

import pandas as pd

import common as c
from backtest_core import backtest_universe

WEEKDAY_KR = {"Monday": "월요일", "Tuesday": "화요일", "Wednesday": "수요일", "Thursday": "목요일", "Friday": "금요일"}


def main():
    parser = argparse.ArgumentParser(description="요일별 성과 분석")
    parser.add_argument("--years", type=int, default=3)
    args = parser.parse_args()

    kr_tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    us_tickers = c.get_us_universe(top_n=500, index="S&P500")

    kr_trades = backtest_universe(kr_tickers, "KR", c.PRODUCTION_STRATEGIES["KR"], years=args.years)
    us_trades = backtest_universe(us_tickers, "US", c.PRODUCTION_STRATEGIES["US"], years=args.years)

    rows = []
    for market, trades in (("한국", kr_trades), ("미국", us_trades)):
        if trades.empty:
            continue
        trades = trades[trades["weekday"].isin(WEEKDAY_KR.keys())]
        grp = trades.groupby("weekday")["return_pct"].agg(
            거래수="count",
            승률=lambda s: round((s > 0).mean() * 100, 2),
            평균수익률=lambda s: round(s.mean(), 2),
        )
        for weekday, r in grp.iterrows():
            rows.append({
                "시장": market, "요일": WEEKDAY_KR[weekday],
                "거래수": int(r["거래수"]), "승률": r["승률"], "평균수익률": r["평균수익률"],
            })

    result_df = pd.DataFrame(rows)
    print("=== 요일별 성과 (README §4 재현) ===")
    print(result_df.to_string(index=False))
    print("\n참고 수준 — 요일별 차이가 크지 않으면 별도 필터로 쓰기엔 근거가 약함.")

    tag = datetime.now().strftime("%Y-%m-%d")
    result_df.to_csv(os.path.join(c.BASE_DIR, f"backtest_weekday_{tag}.csv"), index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
