# 6개 전략(실전 5개 + 더블비) 통합 추천종목 5분 감시봇 — 장시간 아니면 즉시 스킵
# 알림 채널: 텔레그램(신규 신호만, notified_state.json으로 중복 방지) + 대시보드(app.py) —
# 매 실행마다 latest_recommendations.csv + last_scan_recommendations.json 갱신
import json
import os
import traceback
from datetime import datetime

import pandas as pd

import common as c
import track_recommendations as tr
from scan_recommendations import scan, save_status, STATUS_PATH  # noqa: F401 (STATUS_PATH re-export)


def load_prev_status():
    if not os.path.exists(STATUS_PATH):
        return None
    try:
        with open(STATUS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def notify_if_market_closed_empty(prev_status, kr_active, us_active):
    """직전 실행엔 열려있던 장이 이번 실행엔 닫혔는데, 그날 해당 시장 신호가 하나도
    없었으면 '신호 없음'을 텔레그램으로 알림 — 조용하면 봇이 죽은 건지 진짜 없는 건지
    구분이 안 된다는 피드백에 따라 추가."""
    if prev_status is None:
        return
    latest_path = os.path.join(c.BASE_DIR, "latest_recommendations.csv")
    try:
        df = pd.read_csv(latest_path, dtype={"code": str}) if os.path.exists(latest_path) else pd.DataFrame()
    except Exception:
        df = pd.DataFrame()

    for market, status_key, label in (("KR", "kr_active", "🇰🇷 한국장"), ("US", "us_active", "🇺🇸 미국장")):
        was_active = prev_status.get(status_key)
        is_active = kr_active if market == "KR" else us_active
        if was_active and not is_active:
            has_signal = (not df.empty) and (df["market"] == market).any()
            if not has_signal:
                c.send_telegram(f"📭 {label} 마감 — 오늘 신규 추천 신호 없음.")


def main():
    kr_active = c.is_market_hours("KR")
    us_active = c.is_market_hours("US")

    notify_if_market_closed_empty(load_prev_status(), kr_active, us_active)

    if not kr_active and not us_active:
        print(f"{c.now_kst().isoformat()} 장시간 아님 — 스킵")
        return

    print(f"=== watch_recommendations.py 실행 {c.now_kst().isoformat()} (KR={kr_active} US={us_active}) ===")

    try:
        latest_path = os.path.join(c.BASE_DIR, "latest_recommendations.csv")
        try:
            prev_df = pd.read_csv(latest_path, dtype={"code": str}) if os.path.exists(latest_path) else pd.DataFrame()
        except Exception:
            prev_df = pd.DataFrame()

        # 장이 닫힌 시장은 스캔하지 않으므로, 그 시장의 직전 스캔 결과를 그대로 이어서 보여준다.
        # (안 그러면 예: 한국장 마감 직후 실행에서 US만 다시 써서 KR 신호가 통째로 사라짐)
        frames = []
        if kr_active:
            frames.append(scan("KR"))
        elif not prev_df.empty and "market" in prev_df.columns:
            frames.append(prev_df[prev_df["market"] == "KR"])
        if us_active:
            frames.append(scan("US"))
        elif not prev_df.empty and "market" in prev_df.columns:
            frames.append(prev_df[prev_df["market"] == "US"])

        all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        all_df.to_csv(latest_path, index=False, encoding="utf-8-sig")
        save_status(len(all_df), kr_active=kr_active, us_active=us_active)

        new_df = c.notify_new_signals(all_df) if not all_df.empty else all_df

        # 텔레그램 발송과 같은 시점에 성과추적 로그에도 즉시 기록한다 — 예전엔 로그 기록을
        # TrackRecommendations(15분 주기)의 다음 실행이 latest_recommendations.csv를 다시 읽을
        # 때까지 미뤘는데, 그 사이에 신호가 뜨고 사라지면(예: 골든크로스가 한 스캔만 유지) 텔레그램은
        # 갔지만 로그엔 영영 안 남는 문제가 있었다.
        if not all_df.empty:
            log_df = tr.load_log()
            log_df = tr.append_new_recommendations(log_df, all_df)
            log_df.to_csv(tr.LOG_PATH, index=False, encoding="utf-8-sig")

        print(f"신호 {len(all_df)}건(신규 {len(new_df)}건 텔레그램 발송) — latest_recommendations.csv 갱신")
    except Exception as e:
        err_msg = f"{type(e).__name__}: {e}"
        print(f"[ERROR] {err_msg}")
        traceback.print_exc()
        save_status(0, kr_active=kr_active, us_active=us_active, error=err_msg)


if __name__ == "__main__":
    main()
