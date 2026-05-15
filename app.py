import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ページ設定
st.set_page_config(page_title="Professional FX Simulator", layout="wide")

# --- 通貨ペア設定データ ---
PAIR_CONFIG = {
    # クロス円
    "USD/JPY": {"symbol": "USDJPY=X", "jpy_ref": "", "swap": 230, "spread": 0.2},
    "EUR/JPY": {"symbol": "EURJPY=X", "jpy_ref": "", "swap": 200, "spread": 0.4},
    "GBP/JPY": {"symbol": "GBPJPY=X", "jpy_ref": "", "swap": 250, "spread": 0.6},
    "AUD/JPY": {"symbol": "AUDJPY=X", "jpy_ref": "", "swap": 150, "spread": 0.6},
    "NZD/JPY": {"symbol": "NZDJPY=X", "jpy_ref": "", "swap": 150, "spread": 0.7},
    "CAD/JPY": {"symbol": "CADJPY=X", "jpy_ref": "", "swap": 180, "spread": 0.8},
    "CHF/JPY": {"symbol": "CHFJPY=X", "jpy_ref": "", "swap": 100, "spread": 1.2},
    "MXN/JPY": {"symbol": "MXNJPY=X", "jpy_ref": "", "swap": 30, "spread": 0.3},
    "ZAR/JPY": {"symbol": "ZARJPY=X", "jpy_ref": "", "swap": 20, "spread": 1.0},
    "TRY/JPY": {"symbol": "TRYJPY=X", "jpy_ref": "", "swap": 50, "spread": 3.0},
    # ドルストレート・その他
    "EUR/USD": {"symbol": "EURUSD=X", "jpy_ref": "USDJPY=X", "swap": -150, "spread": 0.3},
    "GBP/USD": {"symbol": "GBPUSD=X", "jpy_ref": "USDJPY=X", "swap": -100, "spread": 0.3},
    "AUD/USD": {"symbol": "AUDUSD=X", "jpy_ref": "USDJPY=X", "swap": 100, "spread": 0.4},
    "EUR/GBP": {"symbol": "EURGBP=X", "jpy_ref": "GBPJPY=X", "swap": -80, "spread": 0.6},
    "CHF/TRY": {"symbol": "CHFTRY=X", "jpy_ref": "TRYJPY=X", "swap": 1500, "spread": 9.0},
    "USD/TRY": {"symbol": "USDTRY=X", "jpy_ref": "TRYJPY=X", "swap": 1200, "spread": 10.0},
    "EUR/TRY": {"symbol": "EURTRY=X", "jpy_ref": "TRYJPY=X", "swap": 1300, "spread": 12.0},
    "USD/MXN": {"symbol": "USDMXN=X", "jpy_ref": "MXNJPY=X", "swap": 500, "spread": 5.0},
}

@st.cache_data(ttl=3600)
def get_forex_data_by_formula(symbol, years):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(years * 365))
        df = yf.download(symbol, start=start_date - timedelta(days=10), end=end_date, progress=False)
        if df.empty or len(df) < 2: return 1.0, 0.0
        close_data = df['Close'][symbol] if isinstance(df.columns, pd.MultiIndex) else df['Close']
        last_p, first_p = float(close_data.iloc[-1]), float(close_data.iloc[0])
        days = (close_data.index[-1] - close_data.index[0]).days
        return last_p, abs(last_p - first_p) / max(1, days)
    except: return 1.0, 0.0

@st.cache_data(ttl=3600)
def get_jpy_rate(ref_symbol):
    if not ref_symbol: return 1.0
    try:
        df = yf.download(ref_symbol, period="5d", progress=False)
        close_data = df['Close'][ref_symbol] if isinstance(df.columns, pd.MultiIndex) else df['Close']
        return float(close_data.iloc[-1])
    except: return 1.0

st.title("🛡️ FX 資金管理シミュレータ")

# --- サイドバー：運用条件 ---
st.sidebar.header("📋 運用条件設定")

selected_pair = st.sidebar.selectbox("通貨ペア", list(PAIR_CONFIG.keys()), index=list(PAIR_CONFIG.keys()).index("CHF/TRY"))
order_side = st.sidebar.radio("売買方向", ["SHORT (売)", "LONG (買)"])

target_leverage = st.sidebar.slider("目標実行レバレッジ (倍)", 1.0, 25.0, 3.0, step=0.1)
units = st.sidebar.number_input("保有通貨量", value=10000, step=1000)

vol_period = st.sidebar.slider("変動量参照期間 [年]", 0.5, 30.0, 3.0, step=0.5)
curr_p, calc_daily_vol = get_forex_data_by_formula(PAIR_CONFIG[selected_pair]["symbol"], vol_period)
jpy_r = get_jpy_rate(PAIR_CONFIG[selected_pair]["jpy_ref"])

entry_rate = st.sidebar.number_input("エントリーレート", value=curr_p, format="%.4f")
jpy_rate_now = st.sidebar.number_input("決済時の対円レート", value=jpy_r, format="%.4f")
daily_vol = st.sidebar.number_input("1日の予想変動量", value=calc_daily_vol, format="%.5f")

# スワップの符号修正（SHORT基準の設定値をLONGで反転）
base_swap = PAIR_CONFIG[selected_pair]["swap"]
actual_swap_val = base_swap if order_side == "SHORT (売)" else -base_swap

swap_input = st.sidebar.number_input("1万通貨のスワップ [円]", value=float(actual_swap_val))
spread_pips = st.sidebar.number_input("スプレッド [pips]", value=PAIR_CONFIG[selected_pair]["spread"])

# 証拠金計算
required_capital = (units * entry_rate * jpy_rate_now) / target_leverage
st.sidebar.markdown("---")
st.sidebar.subheader("💰 必要となる元手資金")
st.sidebar.info(f"{required_capital:,.0f} 円")

d_from = st.sidebar.date_input("開始日", datetime.now())
d_to = st.sidebar.date_input("終了日", datetime.now() + timedelta(days=365))
diff_days = (d_to - d_from).days

market_trend = st.sidebar.radio("市場トレンド予測", ["上昇トレンド", "下落トレンド"], index=0 if selected_pair == "CHF/TRY" else 1)
trend_sign = 1 if market_trend == "上昇トレンド" else -1

# --- シミュレーション計算 ---
if diff_days <= 0: st.stop()

expected_end_rate = entry_rate + (daily_vol * diff_days * trend_sign)
total_swap = (units / 10000) * swap_input * diff_days
spread_impact = spread_pips * 0.01

if order_side == "SHORT (売)":
    fx_profit = (entry_rate - (expected_end_rate + spread_impact)) * units * jpy_rate_now
    loss_cut_rate = entry_rate + (required_capital / (units * jpy_rate_now))
else:
    fx_profit = ((expected_end_rate - spread_impact) - entry_rate) * units * jpy_rate_now
    loss_cut_rate = entry_rate - (required_capital / (units * jpy_rate_now))

total_profit = total_swap + fx_profit

# --- 結果表示 ---
st.header(f"📊 {selected_pair} 運用シミュレーション")
col1, col2, col3, col4 = st.columns(4)
col1.metric("必要元手 (証拠金)", f"{required_capital:,.0f} 円")
col2.metric("合計予測損益", f"{total_profit:,.0f} 円")
col3.metric("累積スワップ", f"{total_swap:,.0f} 円")
col4.metric("ロスカットレート", f"{loss_cut_rate:.4f}")

# --- 推移テーブル ---
st.subheader("🗓️ 資産推移予測")
history = []
for i in range(0, diff_days + 1, 30):
    if i == 0: continue
    d_m = min(i, diff_days)
    m_rate = entry_rate + (daily_vol * d_m * trend_sign)
    m_swap = (units / 10000) * swap_input * d_m
    m_fx = (entry_rate - m_rate) * units * jpy_rate_now if order_side == "SHORT (売)" else (m_rate - entry_rate) * units * jpy_rate_now
    
    # 修正ポイント：想定純資産を削除し、単純な合計損益を表示
    history.append({
        "経過日数": f"{d_m}日", 
        "予測レート": round(m_rate, 4), 
        "累積スワップ": round(m_swap),
        "為替損益": round(m_fx), 
        "損益合計": round(m_swap + m_fx) # 単純な損益を表示
    })
    if d_m == diff_days: break

st.table(pd.DataFrame(history))
