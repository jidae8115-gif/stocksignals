# 실전 2개 전략 스캔 (승률 1위만): KR 볼린저밴드 하단터치 / US RSI 과매도
import argparse
import os
import sys
from datetime import datetime

import pandas as pd

import common as c


def scan(market):
    strategy_key = c.PRODUCTION_STRATEGIES[market]
    if market == "KR":
        tickers = c.get_kr_universe(top_n=100, market="KOSPI")
    else:
        tickers = c.get_us_universe(top_n=500, index="S&P500")

    def progress(idx, total, code, name):
        if idx % 20 == 0:
            print(f"  [{market}] {idx}/{total} {code} {name}", file=sys.stderr)

    return c.build_signals(tickers, market, strategy_keys=[strategy_key], progress_cb=progress)


def main():
    parser = argparse.ArgumentParser(description="실전 2개 전략(승률 1위) 스캔")
    parser.add_argument("--no-notify", action="store_true", help="텔레그램 알림 생략")
    parser.add_argument("--backup", action="store_true", help="history/ 폴더에 날짜별 백업 저장")
    args = parser.parse_args()

    print(f"=== find_entries.py 실행 {datetime.now().isoformat()} ===")

    kr_df = scan("KR")
    us_df = scan("US")
    all_df = pd.concat([kr_df, us_df], ignore_index=True)

    print(f"KR({c.STRATEGIES[c.PRODUCTION_STRATEGIES['KR']]['name']}): {len(kr_df)}건")
    print(f"US({c.STRATEGIES[c.PRODUCTION_STRATEGIES['US']]['name']}): {len(us_df)}건")

    if not all_df.empty:
        print(all_df.to_string(index=False))

    if args.backup:
        today = datetime.now().strftime("%Y-%m-%d")
        out_path = os.path.join(c.BASE_DIR, "history", f"find_entries_{today}.csv")
        all_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"백업 저장: {out_path}")

    if not args.no_notify and not all_df.empty:
        new_df = c.notify_new_signals(all_df)
        print(f"신규 알림 발송: {len(new_df)}건")

    latest_path = os.path.join(c.BASE_DIR, "latest_entries.csv")
    all_df.to_csv(latest_path, index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()
