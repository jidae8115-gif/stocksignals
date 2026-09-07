# 공통 유틸: build_signals(), position_size(), is_liquid(), send_telegram(), config
import glob
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

# 콘솔 코드페이지가 cp949(한글 Windows 기본값)면 —, ⭐ 같은 문자 print()에서 UnicodeEncodeError로
# 스크립트가 죽는다. PYTHONIOENCODING=utf-8 없이 실행해도(예: .ps1 안 거치고 직접 실행) 안전하도록
# 표준출력/에러 인코딩을 코드에서 직접 못박아 둔다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import FinanceDataReader as fdr
except ImportError:
    fdr = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PENDING_PATH = os.path.join(BASE_DIR, "pending_notifications.json")
NOTIFIED_PATH = os.path.join(BASE_DIR, "notified_state.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


CONFIG = load_config()

KST = ZoneInfo("Asia/Seoul")


def now_kst():
    """실행 서버 시간대와 무관하게 항상 한국시간(KST) 기준 naive datetime을 반환.
    로컬 PC(이미 KST)·GitHub Actions(TZ=Asia/Seoul 지정)에서는 datetime.now()와 결과가 같지만,
    Streamlit Cloud처럼 UTC로 도는 서버에서도 장시간 판정·타임스탬프가 항상 올바르게 나오게 함."""
    return datetime.now(KST).replace(tzinfo=None)


# ---------- 종목 유니버스 ----------

# fdr.StockListing("KOSPI"/"KOSDAQ")는 내부적으로 data.krx.co.kr에 최신거래일을 먼저 물어보는데,
# 이 PC 네트워크에서 그 요청 자체가 막혀 있어(README 알려진 이슈) 매번 예외로 죽는 문제가 있었다.
# 실제 종목 데이터는 어차피 GitHub에 캐싱돼 있으므로(FinanceData/fdr_krx_data_cache) data.krx.co.kr를
# 거치지 않고 날짜를 직접 스캔해 그 캐시 CSV를 받아온다.
_KRX_CACHE_BASE = "https://raw.githubusercontent.com/FinanceData/fdr_krx_data_cache/refs/heads/master/data/listing/krx"
_KRX_LOCAL_CACHE_DIR = os.path.join(BASE_DIR, "cache")
_KRX_LOCAL_CACHE_PATH = os.path.join(_KRX_LOCAL_CACHE_DIR, "krx_listing_latest.csv")


def _find_latest_krx_cache_date(max_back_days=10):
    d = datetime.today()
    for _ in range(max_back_days):
        url = f"{_KRX_CACHE_BASE}/{d.strftime('%Y-%m-%d')}.csv"
        try:
            r = requests.head(url, timeout=10)
            if r.status_code == 200:
                return d.strftime("%Y-%m-%d")
        except Exception:
            pass
        d -= timedelta(days=1)
    return None


def _fetch_krx_listing():
    """KOSPI+KOSDAQ 전체 종목 리스트(Marcap 포함). GitHub 캐시 실패 시 마지막으로 성공한
    로컬 캐시(cache/krx_listing_latest.csv)로 폴백 — 완전 오프라인이어도 감시봇이 죽지 않게."""
    date_str = _find_latest_krx_cache_date()
    if date_str:
        url = f"{_KRX_CACHE_BASE}/{date_str}.csv"
        try:
            df = pd.read_csv(url, dtype={"Code": str, "MarketId": str})
            os.makedirs(_KRX_LOCAL_CACHE_DIR, exist_ok=True)
            df.to_csv(_KRX_LOCAL_CACHE_PATH, index=False, encoding="utf-8-sig")
            return df
        except Exception as e:
            print(f"[WARN] KRX 리스트 캐시({date_str}) 다운로드 실패: {e}")

    if os.path.exists(_KRX_LOCAL_CACHE_PATH):
        print("[WARN] KRX 종목 리스트 최신 조회 실패 — 로컬 캐시로 폴백")
        return pd.read_csv(_KRX_LOCAL_CACHE_PATH, dtype={"Code": str, "MarketId": str})

    raise RuntimeError("KRX 종목 리스트를 가져올 수 없습니다 (GitHub 캐시 + 로컬 캐시 모두 실패)")


def get_kr_universe(top_n=None, market="ALL"):
    """KOSPI/KOSDAQ 종목 리스트. market: KOSPI/KOSDAQ/ALL. top_n 지정 시 시총 상위만."""
    df = _fetch_krx_listing()
    mkt_map = {"KOSPI": "STK", "KOSDAQ": "KSQ"}
    if market == "ALL":
        df = df[df["MarketId"].isin(mkt_map.values())]
    else:
        df = df[df["MarketId"] == mkt_map[market]]
    if "Marcap" in df.columns:
        df = df.sort_values("Marcap", ascending=False)
    if top_n:
        df = df.head(top_n)
    return list(zip(df["Code"], df["Name"]))


def get_us_universe(top_n=None, index="ALL"):
    """S&P500/나스닥 종목 리스트. top_n 지정 시 시총 상위만."""
    frames = []
    if index in ("S&P500", "ALL"):
        frames.append(fdr.StockListing("S&P500"))
    if index in ("NASDAQ", "ALL"):
        frames.append(fdr.StockListing("NASDAQ"))
    df = pd.concat(frames, ignore_index=True).drop_duplicates(subset="Symbol")
    if "Marcap" in df.columns:
        df = df.sort_values("Marcap", ascending=False)
    if top_n:
        df = df.head(top_n)
    return list(zip(df["Symbol"], df["Name"]))


_OHLCV_CACHE = {}


def fetch_ohlcv(ticker, start=None, end=None, days=500):
    """FinanceDataReader로 OHLCV 조회. KRX 로그인 차단(2026-08~) 우회를 위해 FDR(네이버 기반)만 사용.
    같은 (ticker, start, end)는 프로세스 내에서 캐싱 — 백테스트가 여러 전략을 같은 종목에 반복 적용할 때
    매번 재요청하지 않도록 함."""
    if start is None:
        start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    cache_key = (ticker, start, end)
    if cache_key in _OHLCV_CACHE:
        return _OHLCV_CACHE[cache_key]

    try:
        df = fdr.DataReader(ticker, start, end)
    except Exception:
        df = None

    if df is None or df.empty or len(df) < 60:
        _OHLCV_CACHE[cache_key] = None
        return None

    df = df.rename(columns=str.title)
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(df.columns):
        _OHLCV_CACHE[cache_key] = None
        return None

    _OHLCV_CACHE[cache_key] = df
    return df


# ---------- 지표 계산 ----------

def add_indicators(df):
    df = df.copy()
    df["SMA5"] = df["Close"].rolling(5).mean()
    df["SMA20"] = df["Close"].rolling(20).mean()

    # BB1: 20기간, 종가 기준
    bb1_std = df["Close"].rolling(20).std()
    df["BB1_MID"] = df["SMA20"]
    df["BB1_UPPER"] = df["BB1_MID"] + 2 * bb1_std
    df["BB1_LOWER"] = df["BB1_MID"] - 2 * bb1_std

    # BB2: 44기간, 시가 기준 (더블비 전용)
    bb2_mid = df["Open"].rolling(44).mean()
    bb2_std = df["Open"].rolling(44).std()
    df["BB2_MID"] = bb2_mid
    df["BB2_UPPER"] = bb2_mid + 2 * bb2_std
    df["BB2_LOWER"] = bb2_mid - 2 * bb2_std

    # RSI(14), Wilder 방식
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI14"] = (100 - (100 / (1 + rs))).fillna(50)

    # ATR(14), Wilder 방식 — 손절가/목표가 계산에 사용
    prev_close = df["Close"].shift(1)
    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - prev_close).abs(),
        (df["Low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    df["ATR14"] = tr.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

    # 거래량 필터용
    df["VOL_SMA20"] = df["Volume"].rolling(20).mean()
    df["VOL_RATIO"] = df["Volume"] / df["VOL_SMA20"]

    # 유동성 필터용 (20일 평균 거래대금)
    df["TRADE_VALUE"] = df["Close"] * df["Volume"]
    df["TRADE_VALUE_SMA20"] = df["TRADE_VALUE"].rolling(20).mean()

    return df


def is_liquid(df, market, i=-1):
    """20일 평균 거래대금이 시장별 최소치 이상인지."""
    if df.empty or "TRADE_VALUE_SMA20" not in df.columns:
        return False
    value = df["TRADE_VALUE_SMA20"].iloc[i]
    if pd.isna(value):
        return False
    min_value = (
        CONFIG["liquidity_filter"]["kr_min_value_krw"]
        if market == "KR"
        else CONFIG["liquidity_filter"]["us_min_value_usd"]
    )
    return value >= min_value


def has_volume_surge(df, i=-1):
    if "VOL_RATIO" not in df.columns:
        return False
    ratio = df["VOL_RATIO"].iloc[i]
    if pd.isna(ratio):
        return False
    return ratio >= CONFIG["volume_filter"]["min_ratio"]


# ---------- 전략별 시그널 판정 (i번째 행 기준, 기본 마지막 행) ----------

def signal_bb_lower_touch(df, i=-1):
    row = df.iloc[i]
    if pd.isna(row["BB1_LOWER"]):
        return False
    return bool(row["Close"] <= row["BB1_LOWER"])


def signal_rsi_oversold(df, i=-1):
    row = df.iloc[i]
    if pd.isna(row["RSI14"]):
        return False
    return bool(row["RSI14"] < 30)


def signal_doubleb(df, i=-1):
    """20일선이 5거래일 전보다 위(상승추세) + 종가가 BB1·BB2 하단 동시 하회."""
    idx = i if i >= 0 else len(df) + i
    if idx < 44:
        return False
    row = df.iloc[idx]
    prev5 = df.iloc[idx - 5]
    if pd.isna(row["SMA20"]) or pd.isna(prev5["SMA20"]) or pd.isna(row["BB2_LOWER"]):
        return False
    uptrend = row["SMA20"] > prev5["SMA20"]
    below_both = (row["Close"] < row["BB1_LOWER"]) and (row["Close"] < row["BB2_LOWER"])
    return bool(uptrend and below_both)


def signal_golden_cross(df, i=-1):
    idx = i if i >= 0 else len(df) + i
    if idx < 1:
        return False
    row, prev = df.iloc[idx], df.iloc[idx - 1]
    if pd.isna(row["SMA5"]) or pd.isna(row["SMA20"]) or pd.isna(prev["SMA5"]) or pd.isna(prev["SMA20"]):
        return False
    return bool(prev["SMA5"] <= prev["SMA20"] and row["SMA5"] > row["SMA20"])


def signal_new_high_20(df, i=-1):
    idx = i if i >= 0 else len(df) + i
    if idx < 20:
        return False
    row = df.iloc[idx]
    prior_high = df["High"].iloc[idx - 20:idx].max()
    return bool(row["Close"] > prior_high)


def signal_rising_bearish(df, i=-1):
    """상승추세(20일선 상승) 속 당일 음봉이지만 종가는 여전히 20일선 위 — 눌림 진입."""
    idx = i if i >= 0 else len(df) + i
    if idx < 5:
        return False
    row = df.iloc[idx]
    prev5 = df.iloc[idx - 5]
    if pd.isna(row["SMA20"]) or pd.isna(prev5["SMA20"]):
        return False
    uptrend = row["SMA20"] > prev5["SMA20"]
    bearish_candle = row["Close"] < row["Open"]
    above_sma20 = row["Close"] > row["SMA20"]
    return bool(uptrend and bearish_candle and above_sma20)


STRATEGIES = {
    "bb_lower": {"name": "볼린저밴드 하단터치", "signal_fn": signal_bb_lower_touch, "min_bars": 25},
    "rsi_oversold": {"name": "RSI 과매도", "signal_fn": signal_rsi_oversold, "min_bars": 20},
    "doubleb": {"name": "더블비 볼린저밴드", "signal_fn": signal_doubleb, "min_bars": 50},
    "golden_cross": {"name": "골든크로스", "signal_fn": signal_golden_cross, "min_bars": 25},
    "new_high_20": {"name": "20일 신고가 돌파", "signal_fn": signal_new_high_20, "min_bars": 25},
    "rising_bearish": {"name": "상승음봉", "signal_fn": signal_rising_bearish, "min_bars": 25},
}

# 실전 편입 전략 (README §1) — 더블비는 표본 부족으로 미편입 (README §2)
PRODUCTION_STRATEGIES = {"KR": "bb_lower", "US": "rsi_oversold"}

# 신호는 "그날 종가"를 기준으로 계산되므로(RSI/SMA/BB 전부 종가 포함 지표), 장중 조기 스캔은
# 아직 확정 안 된 값으로 잠정 신호일 수 있음 — 마감 직전에 재확인 후 매수하는 게 백테스트 규칙과 일치.
BUY_WINDOW = {
    "KR": "15:00~15:20 (마감 동시호가 전) — 장중 신호는 잠정치이므로 마감 직전 재확인 후 매수 권장",
    "US": "미국 동부시간 15:30~16:00(마감 직전) — 서머타임 기준 한국시간 04:30~05:00, 표준시 기준 05:30~06:00",
}


def load_backtest_stats():
    """최신 backtest_swing_summary_*.csv(5개 전략) + backtest_doubleb_summary_*.csv(더블비)에서
    (market, strategy) -> (win_rate, avg_return_pct) 조회 테이블을 만든다.
    더블비는 실전 스캔이 거래량 필터를 적용한 상태로 도니 그 조건과 일치하는 행을 사용."""
    stats = {}

    swing_files = sorted(glob.glob(os.path.join(BASE_DIR, "backtest_swing_summary_*.csv")))
    if swing_files:
        df = pd.read_csv(swing_files[-1])
        for _, row in df.iterrows():
            stats[(row["market"], row["strategy"])] = (row["win_rate"], row["avg_return_pct"])

    db_files = sorted(glob.glob(os.path.join(BASE_DIR, "backtest_doubleb_summary_*.csv")))
    if db_files:
        df = pd.read_csv(db_files[-1])
        df = df[df["volume_filter"] == "적용"]
        for _, row in df.iterrows():
            stats[(row["market"], "doubleb")] = (row["win_rate"], row["avg_return_pct"])

    return stats


def compute_trade_levels(close, sma20, atr14):
    """매수가(신호일 종가) 대비 손절가/목표가/손익비를 계산.

    손절가 = 매수가 - 1.5*ATR(14) — 변동성 기반 표준 손절폭(ATR을 못 구하면 종가의 2%로 대체).
    목표가 = 20일선(SMA20)이 매수가보다 위에 있으면 그 값을 사용 — 실제 백테스트의 익절 규칙
            (backtest_core.simulate_trades: 종가가 SMA20에 도달하면 익절)과 일치시킴.
            평균회귀 전략(bb_lower/rsi_oversold/doubleb)은 대부분 이 경우에 해당.
            추세추종 전략(golden_cross/new_high_20/rising_bearish)은 진입 시점에 이미
            종가가 SMA20 위인 경우가 많아 SMA20이 목표가로 부적절 — 이때는 손절폭의 2배를
            목표가로 잡아(손익비 2:1) 항상 의미 있는 목표가/손익비가 나오게 함.
    """
    if atr14 is None or pd.isna(atr14) or atr14 <= 0:
        atr14 = close * 0.02

    stop = close - 1.5 * atr14
    if stop <= 0:
        stop = close * 0.9

    if sma20 is not None and pd.notna(sma20) and sma20 > close:
        target = sma20
    else:
        target = close + 2 * (close - stop)

    risk = close - stop
    reward = target - close
    rr = round(reward / risk, 2) if risk > 0 else None

    return round(stop, 2), round(target, 2), rr


def build_signals(tickers, market, strategy_keys=None, require_volume=True, require_liquidity=True, progress_cb=None):
    """종목 리스트를 스캔해서 신호 발생 종목을 DataFrame으로 반환.

    tickers: [(code, name), ...]
    market: 'KR' | 'US'
    strategy_keys: None이면 전체 전략(STRATEGIES) 적용
    """
    if strategy_keys is None:
        strategy_keys = list(STRATEGIES.keys())

    backtest_stats = load_backtest_stats()
    buy_window = BUY_WINDOW.get(market, "")

    results = []
    total = len(tickers)
    for idx, (code, name) in enumerate(tickers):
        if progress_cb:
            progress_cb(idx, total, code, name)

        df = fetch_ohlcv(code)
        if df is None:
            continue
        df = add_indicators(df)

        if require_liquidity and not is_liquid(df, market):
            continue
        if require_volume and not has_volume_surge(df):
            continue

        last = df.iloc[-1]
        for key in strategy_keys:
            spec = STRATEGIES[key]
            if len(df) < spec["min_bars"]:
                continue
            try:
                if spec["signal_fn"](df):
                    close = float(last["Close"])
                    sma20 = None if pd.isna(last["SMA20"]) else float(last["SMA20"])
                    atr14 = None if pd.isna(last["ATR14"]) else float(last["ATR14"])
                    stop_loss, target, risk_reward = compute_trade_levels(close, sma20, atr14)
                    bt_win_rate, bt_avg_return = backtest_stats.get((market, key), (None, None))
                    results.append({
                        "date": df.index[-1].strftime("%Y-%m-%d"),
                        "market": market,
                        "code": code,
                        "name": name,
                        "strategy": key,
                        "strategy_name": spec["name"],
                        "buy_price": close,
                        "close": close,
                        "stop_loss": stop_loss,
                        "target": target,
                        "risk_reward": risk_reward,
                        "backtest_win_rate": bt_win_rate,
                        "backtest_avg_return": bt_avg_return,
                        "buy_window": buy_window,
                        "vol_ratio": None if pd.isna(last["VOL_RATIO"]) else float(last["VOL_RATIO"]),
                        "rsi14": None if pd.isna(last["RSI14"]) else float(last["RSI14"]),
                        "sma20": sma20,
                    })
            except Exception:
                continue
    cols = ["date", "market", "code", "name", "strategy", "strategy_name", "buy_price", "close",
            "stop_loss", "target", "risk_reward", "backtest_win_rate", "backtest_avg_return",
            "buy_window", "vol_ratio", "rsi14", "sma20"]
    return pd.DataFrame(results, columns=cols)


# ---------- 포지션 사이징 ----------

def position_size(price, market="KR"):
    """계좌 잔고 대비 최대 포지션 비율(risk.max_position_pct)로 매수 수량 계산."""
    if price <= 0:
        return 0
    risk_cfg = CONFIG["risk"]
    balance = CONFIG["account"]["balance_krw"] if market == "KR" else CONFIG["account"]["balance_usd"]
    max_position_value = balance * (risk_cfg["max_position_pct"] / 100)
    return max(int(max_position_value // price), 0)


# ---------- 장시간 판정 ----------

def _time_in_range(now_t, start_s, end_s):
    start = datetime.strptime(start_s, "%H:%M").time()
    end = datetime.strptime(end_s, "%H:%M").time()
    if start <= end:
        return start <= now_t <= end
    return now_t >= start or now_t <= end  # 자정을 넘기는 구간(예: 미국장, 조용한시간)


def is_market_hours(market):
    hours = CONFIG["market_hours"][market.lower()]
    return _time_in_range(now_kst().time(), hours["start"], hours["end"])


def in_quiet_hours():
    qh = CONFIG["telegram"]["quiet_hours"]
    return _time_in_range(now_kst().time(), qh["start"], qh["end"])


# ---------- 텔레그램 알림 ----------

def _queue_pending(message):
    pending = []
    if os.path.exists(PENDING_PATH):
        with open(PENDING_PATH, "r", encoding="utf-8") as f:
            pending = json.load(f)
    pending.append({"message": message, "queued_at": now_kst().isoformat()})
    with open(PENDING_PATH, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)


def get_telegram_credentials():
    """환경변수(TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID, GitHub Secrets용)를 config.json보다 우선.
    리포지토리가 공개될 수 있어 토큰을 config.json에 평문으로 커밋하지 않기 위함."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or CONFIG["telegram"].get("bot_token", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or CONFIG["telegram"].get("chat_id", "")
    return token, chat_id


def send_telegram(message, allow_queue=True):
    """텔레그램 전송. 토큰/챗ID 없으면 콘솔 출력으로 대체.
    조용한시간(quiet_hours)엔 큐잉만 하고 06:00 flush_pending()에서 일괄 발송."""
    token, chat_id = get_telegram_credentials()

    if not token or not chat_id:
        print(f"[TELEGRAM-STUB] {message}")
        return False

    if allow_queue and in_quiet_hours():
        _queue_pending(message)
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"[TELEGRAM-ERROR] {e}")
        return False


def flush_pending():
    """조용한시간 동안 쌓인 알림을 일괄 발송. 06:00 스케줄에서 호출."""
    if not os.path.exists(PENDING_PATH):
        return
    with open(PENDING_PATH, "r", encoding="utf-8") as f:
        pending = json.load(f)
    if not pending:
        os.remove(PENDING_PATH)
        return

    token, chat_id = get_telegram_credentials()
    combined = "\n---\n".join(p["message"] for p in pending)
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            requests.post(url, data={"chat_id": chat_id, "text": combined}, timeout=10)
        except Exception as e:
            print(f"[TELEGRAM-ERROR] {e}")
    else:
        print(f"[TELEGRAM-STUB-FLUSH]\n{combined}")
    os.remove(PENDING_PATH)


# ---------- 중복 알림 방지 ----------

def load_notified_state():
    if not os.path.exists(NOTIFIED_PATH):
        return {}
    with open(NOTIFIED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_notified_state(state):
    with open(NOTIFIED_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def notify_new_signals(df, state_key_cols=("date", "market", "code", "strategy")):
    """이미 알림 보낸 (날짜,시장,종목,전략) 조합은 건너뛰고 새 신호만 텔레그램 발송.
    win11toast는 스케줄러의 비대화형 세션에서 무한 대기하는 버그가 있어 데몬 스레드로 분리."""
    if df.empty:
        return df

    state = load_notified_state()
    new_rows = []
    for _, row in df.iterrows():
        key = "|".join(str(row[c]) for c in state_key_cols)
        if key in state:
            continue
        state[key] = now_kst().isoformat()
        new_rows.append(row)

    if not new_rows:
        return df.iloc[0:0]

    new_df = pd.DataFrame(new_rows)
    for _, row in new_df.iterrows():
        lines = [f"[{row['market']}] {row['strategy_name']} 신호", f"{row['name']}({row['code']})"]
        if "buy_price" in row and pd.notna(row.get("buy_price")):
            lines.append(f"매수가 {row['buy_price']} / 목표 {row.get('target')} / 손절 {row.get('stop_loss')}")
            if pd.notna(row.get("risk_reward")):
                lines.append(f"손익비 {row['risk_reward']}")
            if pd.notna(row.get("backtest_win_rate")):
                lines.append(f"백테스트승률 {row['backtest_win_rate']}%")
        else:
            lines.append(f"종가 {row['close']}")
        lines.append(f"날짜: {row['date']}")
        send_telegram("\n".join(lines))

    save_notified_state(state)
    _fire_toast(f"신규 신호 {len(new_df)}건 발생")
    return new_df


def _fire_toast(message):
    def _run():
        try:
            from win11toast import notify
            notify("StockSignals", message)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()
