# Streamlit 대시보드 — streamlit run app.py 로 실행, localhost:8501
# 주의: 실행 중 common.py/app.py 를 수정하면 재시작 전까지 반영되지 않는다(모듈 캐시)
import glob
import json
import os
import subprocess
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

import common as c

st.set_page_config(page_title="StockSignals 대시보드", layout="wide")


def latest_file(pattern):
    matches = sorted(glob.glob(os.path.join(c.BASE_DIR, pattern)))
    return matches[-1] if matches else None


def load_csv(pattern):
    path = latest_file(pattern)
    if path is None:
        return None, None
    return pd.read_csv(path), path


st.title("StockSignals 대시보드")

tab_reco, tab_track, tab_signals, tab_backtest, tab_config = st.tabs(
    ["추천종목", "성과추적", "실전 신호", "백테스트 결과", "설정"]
)

with tab_reco:
    st.subheader("추천종목 (6개 전략 통합)")
    st.caption(
        "KOSPI100+S&P500 매 30분 자동 스캔(RecommendationsWatch 작업스케줄러, 장시간 아니면 스킵) — "
        "볼린저밴드 하단터치/RSI과매도/골든크로스/20일신고가돌파/상승음봉(실전 5개) + 더블비(표본부족으로 미편입, 참고용). "
        "매수가는 신호일 종가, 손절가는 진입가-1.5×ATR(14), 목표가는 20일선(위에 있을 때) 또는 손익비 2:1 기준. "
        "백테스트승률/평균수익률은 최근 backtest_swing.py·backtest_doubleb.py 실행 결과(같은 시장·전략)에서 가져옴 — "
        "backtest_*.py를 다시 돌리면 최신 수치로 갱신됨."
    )
    st.caption(
        f"🇰🇷 한국 매수 시간대: {c.BUY_WINDOW['KR']}  ·  🇺🇸 미국 매수 시간대: {c.BUY_WINDOW['US']}"
    )

    col_refresh, col_scan = st.columns(2)
    if col_refresh.button("화면 새로고침"):
        st.rerun()
    if col_scan.button("지금 스캔 실행 (약 3분)"):
        with st.spinner("KOSPI100+S&P500 6개 전략 스캔 중..."):
            subprocess.run(
                [sys.executable, "scan_recommendations.py"],
                cwd=c.BASE_DIR, check=False,
            )
        st.rerun()

    status_path = os.path.join(c.BASE_DIR, "last_scan_recommendations.json")
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)
        last_run = datetime.fromisoformat(status["last_run"])
        age_min = (c.now_kst() - last_run).total_seconds() / 60
        col1, col2, col3 = st.columns(3)
        col1.metric("마지막 스캔", last_run.strftime("%H:%M:%S"), f"{age_min:.0f}분 전")
        col2.metric("한국장 활성", "예" if status.get("kr_active") else "아니오")
        col3.metric("미국장 활성", "예" if status.get("us_active") else "아니오")
        if status.get("error"):
            st.error(f"마지막 스캔 실패: {status['error']}")
        if age_min > 45:
            st.warning("마지막 스캔이 45분 이상 지났습니다 — RecommendationsWatch 작업스케줄러가 도는 중인지 확인하세요.")
    else:
        st.info("아직 스캔 기록이 없습니다. watch_recommendations.py 또는 scan_recommendations.py를 먼저 실행하세요.")

    df_reco, path_reco = load_csv("latest_recommendations.csv")
    if df_reco is None or df_reco.empty:
        st.info("현재 신호 없음.")
    else:
        strategy_opts = sorted(df_reco["strategy_name"].unique())
        chosen = st.multiselect("전략 필터", options=strategy_opts, default=strategy_opts)
        shown = df_reco[df_reco["strategy_name"].isin(chosen)] if chosen else df_reco
        st.dataframe(
            shown[["date", "market", "code", "name", "strategy_name",
                   "buy_price", "target", "stop_loss", "risk_reward",
                   "backtest_win_rate", "backtest_avg_return", "buy_window"]]
            .rename(columns={
                "strategy_name": "전략", "buy_price": "매수가", "target": "목표가",
                "stop_loss": "손절가", "risk_reward": "손익비",
                "backtest_win_rate": "백테스트승률(%)", "backtest_avg_return": "백테스트평균수익률(%)",
                "buy_window": "매수 시간대",
            }),
            use_container_width=True,
        )

with tab_track:
    st.subheader("성과추적 — 추천종목이 실제로 어떻게 됐는지")
    st.caption(
        "추천된 순간부터 현재가·현재수익률을 계속 추적. 목표가 도달(TARGET_HIT)/손절가 도달(STOP_HIT)/"
        "5거래일 강제청산(FORCE_CLOSED) 중 하나가 발생하면 청산 처리, 아직이면 OPEN으로 계속 갱신. "
        "매일 자동 갱신하려면 track_recommendations.py를 스케줄러에 추가하세요(아직 수동 실행만 지원)."
    )

    if st.button("지금 추적 갱신"):
        with st.spinner("보유중 종목 현재가 조회 및 상태 갱신 중..."):
            subprocess.run([sys.executable, "track_recommendations.py"], cwd=c.BASE_DIR, check=False)
        st.rerun()

    df_log, path_log = load_csv("recommendations_log.csv")
    if df_log is None or df_log.empty:
        st.info("아직 추적 기록이 없습니다. 추천종목이 1건 이상 나온 뒤 추적을 갱신하세요.")
    else:
        open_n = int((df_log["status"] == "OPEN").sum())
        closed = df_log[df_log["status"] != "OPEN"]
        target_n = int((closed["status"] == "TARGET_HIT").sum())
        stop_n = int((closed["status"] == "STOP_HIT").sum())
        force_n = int((closed["status"] == "FORCE_CLOSED").sum())

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("보유중 (OPEN)", open_n)
        col2.metric("목표달성", target_n)
        col3.metric("손절", stop_n)
        col4.metric("강제청산", force_n)
        if len(closed) > 0:
            realized_win_rate = round(target_n / len(closed) * 100, 1)
            st.metric("실현 승률 (청산건 기준)", f"{realized_win_rate}%")

        status_opts = sorted(df_log["status"].unique())
        chosen_status = st.multiselect("상태 필터", options=status_opts, default=status_opts)
        shown_log = df_log[df_log["status"].isin(chosen_status)] if chosen_status else df_log
        st.dataframe(
            shown_log[["date", "market", "code", "name", "strategy_name", "status",
                       "buy_price", "current_price", "current_return_pct",
                       "target", "stop_loss", "exit_date", "exit_price", "realized_return_pct"]]
            .rename(columns={
                "strategy_name": "전략", "status": "상태", "buy_price": "매수가",
                "current_price": "현재가", "current_return_pct": "현재수익률(%)",
                "target": "목표가", "stop_loss": "손절가", "exit_date": "청산일",
                "exit_price": "청산가", "realized_return_pct": "실현수익률(%)",
            }),
            use_container_width=True,
        )

with tab_signals:
    st.subheader("최신 실전 신호 (find_entries.py)")
    df, path = load_csv("latest_entries.csv")
    if df is None:
        st.info("아직 find_entries.py 실행 결과가 없습니다.")
    else:
        st.caption(f"출처: {os.path.basename(path)}")
        st.dataframe(df, use_container_width=True)

    st.subheader("전체 전략 스캔 (scan_signals.py)")
    df2, path2 = load_csv("history/scan_signals_*.csv")
    if df2 is None:
        st.info("아직 scan_signals.py 실행 결과가 없습니다.")
    else:
        st.caption(f"출처: {os.path.basename(path2)}")
        strategy_filter = st.multiselect(
            "전략 필터", options=sorted(df2["strategy_name"].unique()) if not df2.empty else []
        )
        shown = df2[df2["strategy_name"].isin(strategy_filter)] if strategy_filter else df2
        st.dataframe(shown, use_container_width=True)

with tab_backtest:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("5개 전략 백테스트 (KOSPI100/S&P500)")
        df3, path3 = load_csv("backtest_swing_summary_*.csv")
        if df3 is None:
            st.info("backtest_swing.py 를 먼저 실행하세요.")
        else:
            st.caption(f"출처: {os.path.basename(path3)}")
            st.dataframe(df3, use_container_width=True)

        st.subheader("더블비 볼린저밴드")
        df4, path4 = load_csv("backtest_doubleb_summary_*.csv")
        if df4 is None:
            st.info("backtest_doubleb.py 를 먼저 실행하세요.")
        else:
            st.caption(f"출처: {os.path.basename(path4)}")
            st.dataframe(df4, use_container_width=True)

    with col2:
        st.subheader("전체 유니버스 6개 전략")
        df5, path5 = load_csv("backtest_full_universe_*.csv")
        if df5 is None:
            st.info("backtest_full_universe.py 를 먼저 실행하세요.")
        else:
            st.caption(f"출처: {os.path.basename(path5)}")
            st.dataframe(df5, use_container_width=True)

        st.subheader("요일 효과 (참고용)")
        df6, path6 = load_csv("backtest_weekday_*.csv")
        if df6 is None:
            st.info("backtest_weekday.py 를 먼저 실행하세요.")
        else:
            st.caption(f"출처: {os.path.basename(path6)}")
            st.dataframe(df6, use_container_width=True)

with tab_config:
    st.subheader("config.json 수정")
    cfg = c.load_config()
    with st.form("config_form"):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**계좌**")
            balance_krw = st.number_input("계좌 잔고 (KRW)", value=cfg["account"]["balance_krw"], step=1000000)
            balance_usd = st.number_input("계좌 잔고 (USD)", value=cfg["account"]["balance_usd"], step=1000)
            st.markdown("**리스크**")
            max_position_pct = st.number_input("최대 포지션 비율(%)", value=cfg["risk"]["max_position_pct"])
            st.markdown("**필터**")
            vol_min_ratio = st.number_input("거래량 배수 필터", value=cfg["volume_filter"]["min_ratio"])
            kr_min_value = st.number_input("한국 최소 거래대금(원)", value=cfg["liquidity_filter"]["kr_min_value_krw"], step=100000000)
            us_min_value = st.number_input("미국 최소 거래대금($)", value=cfg["liquidity_filter"]["us_min_value_usd"], step=1000000)
        with col2:
            st.markdown("**텔레그램**")
            bot_token = st.text_input("Bot Token", value=cfg["telegram"].get("bot_token", ""), type="password")
            chat_id = st.text_input("Chat ID", value=cfg["telegram"].get("chat_id", ""))
            quiet_start = st.text_input("조용한시간 시작", value=cfg["telegram"]["quiet_hours"]["start"])
            quiet_end = st.text_input("조용한시간 종료", value=cfg["telegram"]["quiet_hours"]["end"])

        submitted = st.form_submit_button("저장")
        if submitted:
            cfg["account"]["balance_krw"] = balance_krw
            cfg["account"]["balance_usd"] = balance_usd
            cfg["risk"]["max_position_pct"] = max_position_pct
            cfg["volume_filter"]["min_ratio"] = vol_min_ratio
            cfg["liquidity_filter"]["kr_min_value_krw"] = kr_min_value
            cfg["liquidity_filter"]["us_min_value_usd"] = us_min_value
            cfg["telegram"]["bot_token"] = bot_token
            cfg["telegram"]["chat_id"] = chat_id
            cfg["telegram"]["quiet_hours"]["start"] = quiet_start
            cfg["telegram"]["quiet_hours"]["end"] = quiet_end
            with open(c.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            st.success("저장되었습니다. (반영하려면 대시보드를 재시작하세요 — 모듈 캐시)")

st.caption(f"마지막 새로고침: {c.now_kst().strftime('%Y-%m-%d %H:%M:%S')}")
