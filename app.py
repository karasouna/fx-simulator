import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ページ設定
st.set_page_config(page_title="Professional FX Simulator", layout="wide")

# --- 通貨ペア設定データ（フォールバック値） ---
PAIR_CONFIG = {
    "CHF/TRY": {"symbol": "CHFTRY=X", "jpy_ref": "TRYJPY=X", "swap": 1500, "spread": 9.0, "fb_rate": 38.5, "fb_jpy": 4.5, "fb_vol": 0.0328},
    "USD/JPY": {"symbol": "USDJPY=X", "jpy_ref": "", "swap": 230, "spread": 0.2, "fb_rate": 150.0, "fb_jpy": 1.0, "fb_vol": 0.05},
    "EUR/JPY": {"symbol": "EURJPY=X", "jpy_ref": "", "swap": 200, "spread": 0.4, "fb_rate": 160.0, "fb_jpy": 1.0, "fb_vol": 0.6},
    "GBP/JPY": {"symbol": "GBPJPY=X", "jpy_ref": "", "swap": 250, "spread": 0.6, "fb_rate": 190.0, "fb_jpy": 1.0, "fb_vol": 0.8},
    "MXN/JPY": {"symbol": "MXNJPY=X", "jpy_ref": "", "swap": 30, "spread": 0.3, "fb_rate": 8.8, "fb_jpy": 1.0, "fb_vol": 0.005},
    "TRY/JPY": {"symbol": "TRYJPY=X", "jpy_ref": "", "swap": 50, "spread": 3.0, "fb_rate": 4.5, "fb_jpy": 1.0, "fb_vol": -0.01},
}

@st.cache_data(ttl=3600)
def get_forex_data_by_formula(symbol, years, pair_key):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(years * 365))
        df = yf.download(symbol, start=start_date - timedelta(days=10), end=end_date, progress=False)
        if df.empty or len(df) < 2:
            return PAIR_CONFIG[pair_key]["fb_rate"], PAIR_CONFIG[pair_key]["fb_vol"]
        close_data = df['Close'][symbol] if isinstance(df.columns, pd.MultiIndex) else df['Close']
        last_price = float(close_data.iloc[-1])
        first_price = float(close_data.iloc[0])
        actual_days = (close_data.index[-1] - close_data.index[0]).days
        if actual_days <= 0: return last_price, PAIR_CONFIG[pair_key]["fb_vol"]
        daily_drift = abs(last_price - first_price) / actual_days
        return last_price, daily_drift
    except:
        return PAIR_CONFIG[pair_key]["fb_rate"], PAIR_CONFIG[pair_key]["fb_vol"]

@st.cache_data(ttl=3600)
def get_jpy_rate_robust(ref_symbol, pair_key):
    if not ref_symbol: return 1.0
    try:
        df = yf.download(ref_symbol, period="5d", progress=False)
        close_data = df['Close'][ref_symbol] if isinstance(df.columns, pd.MultiIndex) else df['Close']
        return float(close_data.iloc[-1])
    except:
        return PAIR_CONFIG[pair_key]["fb_jpy"]

# --- メイン UI ---
st.title("🛡️ プロフェッショナル FX シミュレータ")

# --- サイドバー：運用条件（ここを重点的に修正） ---
st.sidebar.header("📋 運用条件設定")

# 1. 基本設定
selected_pair = st.sidebar.selectbox("通貨ペア", list(PAIR_CONFIG.keys()), index=list(PAIR_CONFIG.keys()).index("CHF/TRY"))
order_side = st.sidebar.radio("売買方向", ["SHORT (売)", "LONG (買)"])

# 2. 資金・数量設定
capital = st.sidebar.number_input("元手資金 [円]", value=100000, step=10000)
units = st.sidebar.number_input("保有通貨量", value=10000, step=1000)

# 3. データの取得
vol_period = st.sidebar.slider("変動量参照期間 [年]", 0.5, 30.0, 3.0, step=0.5)
curr_p, calc_daily_vol = get_forex_data_by_formula(PAIR_CONFIG[selected_pair]["symbol"], vol_period, selected_pair)
jpy_r = get_jpy_rate_robust(PAIR_CONFIG[selected_pair]["jpy_ref"], selected_pair)

# 4. レート設定（デフォルト値を自動取得値に）
entry_rate = st.sidebar.number_input("エントリーレート", value=curr_p, format="%.4f")
jpy_rate_now = st.sidebar.number_input("決済時の対円レート", value=jpy_r, format="%.4f")
daily_vol = st.sidebar.number_input("1日の予想変動量", value=calc_daily_vol, format="%.5f")

# ★重要★：サイドバーに実行レバレッジを明示（計算して即表示）
current_leverage = (units * entry_rate * jpy_rate_now) / capital
st.sidebar.markdown("---")
st.sidebar.subheader("📉 現在のリアルタイム統計")
# 色分けして警告を出す
if current_leverage > 25:
    st.sidebar.error(f"実行レバレッジ: {current_leverage:.2f} 倍 (危険)")
elif current_leverage > 10:
    st.sidebar.warning(f"実行レバレッジ: {current_leverage:.2f} 倍 (警戒)")
else:
    st.sidebar.success(f"実行レバレッジ: {current_leverage:.2f} 倍 (安全)")

# 5. その他条件
st.sidebar.markdown("---")
d_from = st.sidebar.date_input("開始日 (From)", datetime.now())
d_to = st.sidebar.date_input("終了日 (To)", datetime.now() + timedelta(days=365))
diff_days = (d_to - d_from).days

swap_val = st.sidebar.number_input("1万通貨のスワップ [円]", value=PAIR_CONFIG[selected_pair]["swap"])
spread_pips = st.sidebar.number_input("スプレッド [pips]", value=PAIR_CONFIG[selected_pair]["spread"])

market_trend = st.sidebar.radio("市場トレンド予測", ["上昇トレンド", "下落トレンド"], index=0 if selected_pair == "CHF/TRY" else 1)
trend_sign = 1 if market_trend == "上昇トレンド" else -1

# --- 計算 ---
if diff_days <= 0:
    st.warning("終了日を開始日より後に設定してください。")
    st.stop()

expected_end_rate = entry_rate + (daily_vol * diff_days * trend_sign)
total_swap = (units / 10000) * swap_val * diff_days
spread_impact = spread_pips * 0.01

if order_side == "SHORT (売)":
    fx_profit = (entry_rate - (expected_end_rate + spread_impact)) * units * jpy_rate_now
    loss_cut_rate = entry_rate + (capital / (units * jpy_rate_now))
else:
    fx_profit = ((expected_end_rate - spread_impact) - entry_rate) * units * jpy_rate_now
    loss_cut_rate = entry_rate - (capital / (units * jpy_rate_now))

total_profit = total_swap + fx_profit

# --- メイン画面表示 ---
st.header(f"📊 シミュレーション結果: {selected_pair}")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("トータル損益", f"{total_profit:,.0f} 円")
col2.metric("為替損益", f"{fx_profit:,.0f} 円")
col3.metric("累積スワップ", f"{total_swap:,.0f} 円")
col4.metric("実行レバレッジ", f"{current_leverage:.2f} 倍")
col5.metric("ロスカットレート", f"{loss_cut_rate:.4f}")

# --- 推移テーブル ---
st.subheader("🗓️ 期間別推移予測 (30日毎)")
history = []
for i in range(0, diff_days + 1, 30):
    if i == 0: continue
    d_m = min(i, diff_days)
    m_rate = entry_rate + (daily_vol * d_m * trend_sign)
    m_swap = (units / 10000) * swap_val * d_m
    m_fx = (entry_rate - m_rate) * units * jpy_rate_now if order_side == "SHORT (売)" else (m_rate - entry_rate) * units * jpy_rate_now
    history.append({
        "経過日数": f"{d_m}日", "予測レート": round(m_rate, 4), "累積スワップ": round(m_swap),
        "為替損益": round(m_fx), "合計損益": round(m_swap + m_fx)
    })
    if d_m == diff_days: break

st.table(pd.DataFrame(history))
