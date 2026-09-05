# 전체 시장(S&P500+나스닥) 상승음봉 스캔
import os
import sys
from datetime import datetime

import common as c


def main():
    tickers = c.get_us_universe(index="ALL")
    print(f"S&P500+나스닥 전체 {len(tickers)}종목 스캔 시작")

    def progress(idx, total, code, name):
        if idx % 200 == 0:
            print(f"  {idx}/{total} {code} {name}", file=sys.stderr)

    result = c.build_signals(tickers, "US", strategy_keys=["rising_bearish"], progress_cb=progress)
    print(f"\n상승음봉 신호: {len(result)}건")
    if not result.empty:
        print(result.to_string(index=False))

    out_path = os.path.join(c.BASE_DIR, "history", f"rising_bearish_us_{datetime.now().strftime('%Y-%m-%d')}.csv")
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"저장: {out_path}")


if __name__ == "__main__":
    main()
