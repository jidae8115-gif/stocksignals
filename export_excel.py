# 결과 엑셀 내보내기 — 최신 스캔/백테스트 CSV들을 시트별로 모아 하나의 xlsx로 저장
import argparse
import glob
import os
from datetime import datetime

import pandas as pd

import common as c

PATTERNS = {
    "실전신호": "latest_entries.csv",
    "전체스캔": "history/scan_signals_*.csv",
    "백테스트_5전략": "backtest_swing_summary_*.csv",
    "백테스트_더블비": "backtest_doubleb_summary_*.csv",
    "백테스트_전체유니버스": "backtest_full_universe_*.csv",
    "백테스트_요일효과": "backtest_weekday_*.csv",
}


def latest_file(pattern):
    matches = sorted(glob.glob(os.path.join(c.BASE_DIR, pattern)))
    return matches[-1] if matches else None


def main():
    parser = argparse.ArgumentParser(description="스캔/백테스트 결과를 엑셀로 내보내기")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    out_path = args.out or os.path.join(
        c.BASE_DIR, f"stocksignals_export_{c.now_kst().strftime('%Y-%m-%d_%H%M')}.xlsx"
    )

    sheets_written = 0
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for sheet_name, pattern in PATTERNS.items():
            path = latest_file(pattern)
            if path is None:
                print(f"[스킵] {sheet_name}: 해당 파일 없음 ({pattern})")
                continue
            df = pd.read_csv(path)
            df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
            sheets_written += 1
            print(f"[포함] {sheet_name} <- {os.path.basename(path)} ({len(df)}행)")

    if sheets_written == 0:
        print("내보낼 데이터가 없습니다. 먼저 scan/backtest 스크립트를 실행하세요.")
        os.remove(out_path) if os.path.exists(out_path) else None
        return

    print(f"\n저장 완료: {out_path}")


if __name__ == "__main__":
    main()
