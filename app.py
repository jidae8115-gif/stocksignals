# Streamlit 대시보드 — streamlit run app.py 로 실행, localhost:8501
# 주의: 실행 중 common.py/app.py 를 수정하면 재시작 전까지 반영되지 않는다(모듈 캐시)
import glob
import json
import os
import subprocess
import sys
from datetime import datetime

import pandas as pd
import requests
import streamlit as st

import common as c

st.set_page_config(page_title="StockSignals 대시보드", page_icon="📈", layout="wide")

GITHUB_REPO = "jidae8115-gif/stocksignals"
GITHUB_WORKFLOWS = {
    "추천종목 스캔 (RecommendationsWatch)": "recommendations-watch.yml",
    "성과추적 갱신 (TrackRecommendations)": "track-recommendations.yml",
}


def get_github_token():
    try:
        token = st.secrets.get("GITHUB_TOKEN", "")
    except Exception:
        token = ""
    return token or os.environ.get("GITHUB_TOKEN", "")


def trigger_github_workflow(workflow_file, ref="main"):
    """GitHub Actions workflow_dispatch로 워크플로우를 강제 실행. 자동 스캔이 멈췄을 때 수동 복구용."""
    token = get_github_token()
    if not token:
        return False, "GITHUB_TOKEN이 설정되어 있지 않습니다 (Streamlit Cloud → Settings → Secrets에 추가 필요)."
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{workflow_file}/dispatches"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        resp = requests.post(url, headers=headers, json={"ref": ref}, timeout=10)
        if resp.status_code == 204:
            return True, "GitHub Actions 워크플로우 실행 요청을 보냈습니다. 1~2분 내 반영됩니다."
        return False, f"실패 (HTTP {resp.status_code}): {resp.text[:200]}"
    except Exception as e:
        return False, f"요청 오류: {e}"

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1280px; }
    div[data-testid="stMetric"] {
        background: rgba(120, 120, 120, 0.07);
        border: 1px solid rgba(120, 120, 120, 0.15);
        border-radius: 12px;
        padding: 14px 16px 10px 16px;
    }
    div[data-testid="stMetricLabel"] { font-size: 0.8rem; opacity: 0.75; }
    .pill { display:inline-block; padding:3px 12px; border-radius:999px;
            font-size:0.78rem; font-weight:600; margin:2px 6px 2px 0; }
    .pill-green { background:rgba(16,185,129,0.16); color:#059669; }
    .pill-red   { background:rgba(239,68,68,0.16); color:#dc2626; }
    .pill-blue  { background:rgba(59,130,246,0.16); color:#2563eb; }
    .pill-gray  { background:rgba(107,114,128,0.16); color:#6b7280; }
    .pill-amber { background:rgba(245,158,11,0.16); color:#d97706; }
    [data-testid="stSidebar"] { min-width: 260px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def latest_file(pattern):
    matches = sorted(glob.glob(os.path.join(c.BASE_DIR, pattern)))
    return matches[-1] if matches else None


def load_csv(pattern):
    path = latest_file(pattern)
    if path is None:
        return None, None
    return pd.read_csv(path), path


def pill(text, kind="gray"):
    return f'<span class="pill pill-{kind}">{text}</span>'


def section_card(title, icon=""):
    st.markdown(f"##### {icon} {title}".strip())


# ---------- 사이드바: 상태 요약 + 빠른 실행 ----------
with st.sidebar:
    st.markdown("### 📈 StockSignals")
    st.caption(c.now_kst().strftime("%Y-%m-%d (%a) %H:%M:%S KST"))
    st.divider()

    st.markdown("**빠른 실행**")
    if st.button("🔄 화면 새로고침", width="stretch"):
        st.rerun()
    if st.button("🔍 지금 스캔 실행 (약 3분)", width="stretch"):
        with st.spinner("KOSPI100+S&P500 6개 전략 스캔 중..."):
            subprocess.run([sys.executable, "scan_recommendations.py"], cwd=c.BASE_DIR, check=False)
        st.rerun()
    if st.button("📊 지금 추적 갱신", width="stretch"):
        with st.spinner("보유중 종목 현재가 조회 및 상태 갱신 중..."):
            subprocess.run([sys.executable, "track_recommendations.py"], cwd=c.BASE_DIR, check=False)
        st.rerun()

    st.divider()
    status_path = os.path.join(c.BASE_DIR, "last_scan_recommendations.json")
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)
        last_run = datetime.fromisoformat(status["last_run"])
        age_min = (c.now_kst() - last_run).total_seconds() / 60

        st.markdown("**마지막 스캔**")
        st.markdown(f"{last_run.strftime('%H:%M:%S')} · {age_min:.0f}분 전")
        badges = pill("🇰🇷 개장" if status.get("kr_active") else "🇰🇷 마감", "green" if status.get("kr_active") else "gray")
        badges += pill("🇺🇸 개장" if status.get("us_active") else "🇺🇸 마감", "green" if status.get("us_active") else "gray")
        st.markdown(badges, unsafe_allow_html=True)

        stalled = bool(status.get("error")) or age_min > 15
        if status.get("error"):
            st.error(f"스캔 실패: {status['error']}")
        elif age_min > 15:
            st.warning("15분 이상 지났습니다 — 자동 스캔 확인 필요")
        else:
            st.success("정상 작동 중")

        if stalled:
            st.caption("자동 스캔이 멈춘 것 같으면 아래에서 GitHub Actions를 직접 재실행하세요.")
            wf_label = st.selectbox("워크플로우 선택", options=list(GITHUB_WORKFLOWS.keys()), label_visibility="collapsed")
            if st.button("⚠️ GitHub Actions 강제 재실행", width="stretch"):
                ok, msg = trigger_github_workflow(GITHUB_WORKFLOWS[wf_label])
                (st.success if ok else st.error)(msg)
    else:
        st.info("아직 스캔 기록이 없습니다.")

st.title("📈 StockSignals 대시보드")

tab_reco, tab_track, tab_signals, tab_backtest, tab_config = st.tabs(
    ["🎯 추천종목", "📊 성과추적", "⚡ 실전 신호", "🧪 백테스트 결과", "⚙️ 설정"]
)

# ---------- 추천종목 ----------
with tab_reco:
    with st.expander("ℹ️ 전략 설명 및 계산 기준"):
        st.caption(
            "KOSPI100+S&P500 매 5분 자동 스캔(RecommendationsWatch, 장시간 아니면 스킵) — "
            "볼린저밴드 하단터치/RSI과매도/골든크로스/20일신고가돌파/상승음봉(실전 5개) + 더블비(표본부족으로 미편입, 참고용). "
            "매수가는 신호일 종가, 손절가는 진입가-1.5×ATR(14), 목표가는 20일선(위에 있을 때) 또는 손익비 2:1 기준. "
            "백테스트승률/평균수익률은 최근 backtest_swing.py·backtest_doubleb.py 실행 결과(같은 시장·전략)에서 가져옴 — "
            "backtest_*.py를 다시 돌리면 최신 수치로 갱신됨."
        )
        st.caption(f"🇰🇷 한국 매수 시간대: {c.BUY_WINDOW['KR']}  ·  🇺🇸 미국 매수 시간대: {c.BUY_WINDOW['US']}")

    def render_reco_table(df, key_prefix):
        if df.empty:
            st.info("현재 신호 없음.")
            return

        avg_wr = df["backtest_win_rate"].mean()
        avg_rr = df["risk_reward"].mean()

        k1, k2, k3 = st.columns(3)
        k1.metric("신호 건수", f"{len(df)}건")
        k2.metric("평균 백테스트승률", f"{avg_wr:.1f}%" if pd.notna(avg_wr) else "—")
        k3.metric("평균 손익비", f"{avg_rr:.2f}" if pd.notna(avg_rr) else "—")

        st.write("")
        strategy_opts = sorted(df["strategy_name"].unique())
        chosen = st.multiselect(
            "전략 필터", options=strategy_opts, default=strategy_opts,
            label_visibility="collapsed", placeholder="전략 선택...", key=f"{key_prefix}_strategy",
        )
        shown = df[df["strategy_name"].isin(chosen)] if chosen else df
        shown = shown.sort_values("backtest_win_rate", ascending=False, na_position="last")

        shown = shown.assign(
            매수허용범위=shown["buy_price_min"].map(lambda v: f"{v:g}") + " ~ "
            + shown["buy_price_max"].map(lambda v: f"{v:g}")
        ) if {"buy_price_min", "buy_price_max"}.issubset(shown.columns) else shown

        table_cols = ["date", "market", "code", "name", "strategy_name",
                      "buy_price", "매수허용범위", "target", "stop_loss", "risk_reward",
                      "backtest_win_rate", "backtest_avg_return", "buy_window"]
        table_cols = [col for col in table_cols if col in shown.columns]

        st.dataframe(
            shown[table_cols]
            .rename(columns={
                "date": "날짜", "market": "시장", "code": "코드", "name": "종목명",
                "strategy_name": "전략", "buy_price": "매수가", "target": "목표가",
                "stop_loss": "손절가", "risk_reward": "손익비",
                "backtest_win_rate": "백테스트승률", "backtest_avg_return": "평균수익률",
                "buy_window": "매수 시간대",
            }),
            width="stretch",
            hide_index=True,
            column_config={
                "매수가": st.column_config.NumberColumn(format="%.2f"),
                "목표가": st.column_config.NumberColumn(format="%.2f"),
                "손절가": st.column_config.NumberColumn(format="%.2f"),
                "손익비": st.column_config.NumberColumn(format="%.2f"),
                "백테스트승률": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
                "평균수익률": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )
        st.caption(f"매수허용범위 = 신호가 대비 ±{c.CONFIG.get('risk', {}).get('entry_tolerance_pct', 0.5)}% — 딱 그 가격이 아니어도 이 범위 안이면 매수 유효.")

    df_reco, path_reco = load_csv("latest_recommendations.csv")
    if df_reco is None or df_reco.empty:
        st.info("현재 신호 없음.")
    else:
        kr_n = int((df_reco["market"] == "KR").sum())
        us_n = int((df_reco["market"] == "US").sum())
        sub_all, sub_kr, sub_us = st.tabs([f"전체 ({len(df_reco)})", f"🇰🇷 한국 ({kr_n})", f"🇺🇸 미국 ({us_n})"])
        with sub_all:
            render_reco_table(df_reco, "reco_all")
        with sub_kr:
            render_reco_table(df_reco[df_reco["market"] == "KR"], "reco_kr")
        with sub_us:
            render_reco_table(df_reco[df_reco["market"] == "US"], "reco_us")

# ---------- 성과추적 ----------
with tab_track:
    st.caption(
        "추천된 순간부터 현재가·현재수익률을 계속 추적. 목표가 도달(TARGET_HIT)/손절가 도달(STOP_HIT)/"
        "5거래일 강제청산(FORCE_CLOSED) 중 하나가 발생하면 청산 처리, 아직이면 OPEN으로 계속 갱신."
    )

    status_label = {
        "OPEN": "🔵 보유중", "TARGET_HIT": "🟢 목표달성",
        "STOP_HIT": "🔴 손절", "FORCE_CLOSED": "⚪ 강제청산",
    }

    def render_track_table(df, key_prefix):
        if df.empty:
            st.info("해당 조건의 추적 기록이 없습니다.")
            return

        open_n = int((df["status"] == "OPEN").sum())
        closed = df[df["status"] != "OPEN"]
        target_n = int((closed["status"] == "TARGET_HIT").sum())
        stop_n = int((closed["status"] == "STOP_HIT").sum())
        force_n = int((closed["status"] == "FORCE_CLOSED").sum())
        realized_win_rate = round(target_n / len(closed) * 100, 1) if len(closed) > 0 else None

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("보유중 (OPEN)", open_n)
        k2.metric("목표달성", target_n)
        k3.metric("손절", stop_n)
        k4.metric("강제청산", force_n)
        k5.metric("실현 승률", f"{realized_win_rate}%" if realized_win_rate is not None else "—")

        st.write("")
        fc1, fc2 = st.columns(2)
        date_opts = sorted(df["date"].unique(), reverse=True)
        chosen_dates = fc1.multiselect("추천일 필터", options=date_opts, default=date_opts, key=f"{key_prefix}_date")
        status_opts = sorted(df["status"].unique())
        chosen_status = fc2.multiselect(
            "상태 필터", options=status_opts, default=status_opts,
            format_func=lambda s: status_label.get(s, s), key=f"{key_prefix}_status",
        )

        shown_log = df[df["date"].isin(chosen_dates)] if chosen_dates else df.iloc[0:0]
        shown_log = shown_log[shown_log["status"].isin(chosen_status)] if chosen_status else shown_log.iloc[0:0]
        shown_log = shown_log.sort_values("date", ascending=False)

        shown_log = shown_log.assign(status=shown_log["status"].map(lambda s: status_label.get(s, s)))

        st.dataframe(
            shown_log[["date", "market", "code", "name", "strategy_name", "status",
                       "buy_price", "current_price", "current_return_pct",
                       "target", "stop_loss", "exit_date", "exit_price", "realized_return_pct"]]
            .rename(columns={
                "date": "추천일", "market": "시장", "code": "코드", "name": "종목명",
                "strategy_name": "전략", "status": "상태", "buy_price": "매수가",
                "current_price": "현재가", "current_return_pct": "현재수익률(%)",
                "target": "목표가", "stop_loss": "손절가", "exit_date": "청산일",
                "exit_price": "청산가", "realized_return_pct": "실현수익률(%)",
            }),
            width="stretch",
            hide_index=True,
            column_config={
                "매수가": st.column_config.NumberColumn(format="%.2f"),
                "현재가": st.column_config.NumberColumn(format="%.2f"),
                "목표가": st.column_config.NumberColumn(format="%.2f"),
                "손절가": st.column_config.NumberColumn(format="%.2f"),
                "청산가": st.column_config.NumberColumn(format="%.2f"),
                "현재수익률(%)": st.column_config.NumberColumn(format="%.2f%%"),
                "실현수익률(%)": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )

    df_log, path_log = load_csv("recommendations_log.csv")
    if df_log is None or df_log.empty:
        st.info("아직 추적 기록이 없습니다. 추천종목이 1건 이상 나온 뒤 사이드바에서 추적을 갱신하세요.")
    else:
        kr_n = int((df_log["market"] == "KR").sum())
        us_n = int((df_log["market"] == "US").sum())
        sub_all, sub_kr, sub_us = st.tabs([f"전체 ({len(df_log)})", f"🇰🇷 한국 ({kr_n})", f"🇺🇸 미국 ({us_n})"])
        with sub_all:
            render_track_table(df_log, "track_all")
        with sub_kr:
            render_track_table(df_log[df_log["market"] == "KR"], "track_kr")
        with sub_us:
            render_track_table(df_log[df_log["market"] == "US"], "track_us")

# ---------- 실전 신호 ----------
with tab_signals:
    section_card("최신 실전 신호 (find_entries.py)", "⚡")
    df, path = load_csv("latest_entries.csv")
    if df is None:
        st.info("아직 find_entries.py 실행 결과가 없습니다.")
    else:
        st.caption(f"출처: {os.path.basename(path)}")
        st.dataframe(df, width="stretch", hide_index=True)

    st.divider()
    section_card("전체 전략 스캔 (scan_signals.py)", "🗂️")
    df2, path2 = load_csv("history/scan_signals_*.csv")
    if df2 is None:
        st.info("아직 scan_signals.py 실행 결과가 없습니다.")
    else:
        st.caption(f"출처: {os.path.basename(path2)}")
        strategy_filter = st.multiselect(
            "전략 필터", options=sorted(df2["strategy_name"].unique()) if not df2.empty else [],
            key="signals_strategy_filter",
        )
        shown = df2[df2["strategy_name"].isin(strategy_filter)] if strategy_filter else df2
        st.dataframe(shown, width="stretch", hide_index=True)

# ---------- 백테스트 결과 ----------
with tab_backtest:
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            section_card("5개 전략 백테스트 (KOSPI100/S&P500)", "🧪")
            df3, path3 = load_csv("backtest_swing_summary_*.csv")
            if df3 is None:
                st.info("backtest_swing.py 를 먼저 실행하세요.")
            else:
                st.caption(f"출처: {os.path.basename(path3)}")
                st.dataframe(df3, width="stretch", hide_index=True)

        with st.container(border=True):
            section_card("더블비 볼린저밴드", "🅱️")
            df4, path4 = load_csv("backtest_doubleb_summary_*.csv")
            if df4 is None:
                st.info("backtest_doubleb.py 를 먼저 실행하세요.")
            else:
                st.caption(f"출처: {os.path.basename(path4)}")
                st.dataframe(df4, width="stretch", hide_index=True)

    with col2:
        with st.container(border=True):
            section_card("전체 유니버스 6개 전략", "🌐")
            df5, path5 = load_csv("backtest_full_universe_*.csv")
            if df5 is None:
                st.info("backtest_full_universe.py 를 먼저 실행하세요.")
            else:
                st.caption(f"출처: {os.path.basename(path5)}")
                st.dataframe(df5, width="stretch", hide_index=True)

        with st.container(border=True):
            section_card("요일 효과 (참고용)", "📅")
            df6, path6 = load_csv("backtest_weekday_*.csv")
            if df6 is None:
                st.info("backtest_weekday.py 를 먼저 실행하세요.")
            else:
                st.caption(f"출처: {os.path.basename(path6)}")
                st.dataframe(df6, width="stretch", hide_index=True)

# ---------- 설정 ----------
with tab_config:
    st.caption("변경 후 저장하면 config.json에 반영됩니다. (반영하려면 대시보드를 재시작하세요 — 모듈 캐시)")
    cfg = c.load_config()
    with st.form("config_form"):
        col1, col2 = st.columns(2)
        with col1:
            with st.container(border=True):
                st.markdown("**💰 계좌**")
                balance_krw = st.number_input("계좌 잔고 (KRW)", value=cfg["account"]["balance_krw"], step=1000000)
                balance_usd = st.number_input("계좌 잔고 (USD)", value=cfg["account"]["balance_usd"], step=1000)
            with st.container(border=True):
                st.markdown("**⚖️ 리스크 · 필터**")
                max_position_pct = st.number_input("최대 포지션 비율(%)", value=cfg["risk"]["max_position_pct"])
                entry_tolerance_pct = st.number_input(
                    "매수 허용범위(±%)", value=cfg["risk"].get("entry_tolerance_pct", 0.5), step=0.1,
                    help="신호가 그대로 체결되기 어려우니 이 비율만큼 위아래로 허용범위를 표시합니다.",
                )
                slippage_pct = st.number_input(
                    "청산 슬리피지(%)", value=cfg["risk"].get("slippage_pct", 0.1), step=0.05,
                    help="목표가/손절가 청산 시 실제 체결가가 불리하게 밀리는 정도를 성과추적에 반영합니다.",
                )
                vol_min_ratio = st.number_input("거래량 배수 필터", value=cfg["volume_filter"]["min_ratio"])
                kr_min_value = st.number_input("한국 최소 거래대금(원)", value=cfg["liquidity_filter"]["kr_min_value_krw"], step=100000000)
                us_min_value = st.number_input("미국 최소 거래대금($)", value=cfg["liquidity_filter"]["us_min_value_usd"], step=1000000)
        with col2:
            with st.container(border=True):
                st.markdown("**💬 텔레그램**")
                bot_token = st.text_input("Bot Token", value=cfg["telegram"].get("bot_token", ""), type="password")
                chat_id = st.text_input("Chat ID", value=cfg["telegram"].get("chat_id", ""))
                qc1, qc2 = st.columns(2)
                quiet_start = qc1.text_input("조용한시간 시작", value=cfg["telegram"]["quiet_hours"]["start"])
                quiet_end = qc2.text_input("조용한시간 종료", value=cfg["telegram"]["quiet_hours"]["end"])
                st.caption("실제 알림 발송은 GitHub Secrets(TELEGRAM_BOT_TOKEN/CHAT_ID)가 우선 적용됩니다.")

        submitted = st.form_submit_button("💾 저장", width="stretch")
        if submitted:
            cfg["account"]["balance_krw"] = balance_krw
            cfg["account"]["balance_usd"] = balance_usd
            cfg["risk"]["max_position_pct"] = max_position_pct
            cfg["risk"]["entry_tolerance_pct"] = entry_tolerance_pct
            cfg["risk"]["slippage_pct"] = slippage_pct
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

st.divider()
st.caption(f"마지막 새로고침: {c.now_kst().strftime('%Y-%m-%d %H:%M:%S')}")
