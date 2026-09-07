# 5개 전략 전체 스캔 (전략 선택 가능)
import argparse
import os
import sys
from datetime import datetime

import pandas as pd

import common as c


def main():
    parser = argparse.ArgumentParser(description="전략 선택형 전체 스캔")
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=list(c.STRATEGIES.keys()),
        choices=list(c.STRATEGIES.keys()),
        help="스캔할 전략 키 (기본: 전체)",
    )
    parser.add_argument("--market", choices=["KR", "US", "ALL"], default="ALL")
    parser.add_argument("--top-n", type=int, default=100, help="시총 상위 N종목만 (기본 100)")
    parser.add_argument("--no-volume-filter", action="store_true")
    parser.add_argument("--no-liquidity-filter", action="store_true")
    args = parser.parse_args()

    def progress(idx, total, code, name):
        if idx % 30 == 0:
            print(f"  {idx}/{total} {code} {name}", file=sys.stderr)

    frames = []
    if args.market in ("KR", "ALL"):
        kr_tickers = c.get_kr_universe(top_n=args.top_n, market="KOSPI")
        frames.append(c.build_signals(
            kr_tickers, "KR", strategy_keys=args.strategies,
            require_volume=not args.no_volume_filter,
            require_liquidity=not args.no_liquidity_filter,
            progress_cb=progress,
        ))
    if args.market in ("US", "ALL"):
        us_tickers = c.get_us_universe(top_n=args.top_n, index="S&P500")
        frames.append(c.build_signals(
            us_tickers, "US", strategy_keys=args.strategies,
            require_volume=not args.no_volume_filter,
            require_liquidity=not args.no_liquidity_filter,
            progress_cb=progress,
        ))

    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    print(f"\n총 {len(result)}건 신호 발생")
    if not result.empty:
        print(result.groupby("strategy_name").size().to_string())
        print()
        print(result.to_string(index=False))

    out_path = os.path.join(c.BASE_DIR, "history", f"scan_signals_{c.now_kst().strftime('%Y-%m-%d_%H%M')}.csv")
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
