import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ページ設定
st.set_page_config(page_title="Advanced FX Simulator", layout="wide")

# --- 通貨ペア設定データ ---
PAIR_DEFAULTS = {
    "CHF/TRY": {"jpy_ref": "TRYJPY=X", "swap": 1500, "spread": 9.0, "symbol": "CHFTRY=X", "def_rate": 58.158, "def_vol": 0.03325},
    "USD/JPY": {"jpy_ref": "USDJPY=X", "swap": 230, "spread": 0.2, "symbol": "USDJPY=X", "def_rate": 150.00, "def_vol": 0.5},
    "EUR/JPY": {"jpy_ref": "EURJPY=X", "swap": 200, "spread": 0.4, "symbol": "EURJPY=X", "def_rate": 160.00, "def_vol": 0.6},
    "AUD/JPY": {"jpy_ref": "AUDJPY=X", "swap": 150, "spread": 0.6, "symbol": "AUDJPY=X", "def_rate": 100.00, "def_vol": 0.4},
    "MXN/JPY": {"jpy_ref": "MXNJPY=X", "swap": 30, "spread": 0.3, "symbol": "MXNJPY=X", "def_rate": 8.5, "def_vol": 0.05},
}

@st.cache_data(ttl=3600)
def get_forex_data(symbol, years, pair_key):
    """過去の価格データを取得して1日の平均変動量を計算（失敗時はデフォルト値を返す）"""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(years * 365))
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        
        if df.empty or len(df) < 2:
            return PAIR_DEFAULTS[pair_key]["def_rate"], PAIR_DEFAULTS[pair_key]["def_vol"]
        
        # Seriesエラー回避のため、値を抽出
        current_price = float(df['Close'].iloc[-1])
        daily_volatility = float(df['Close'].diff().abs().mean())
        return current_price, daily_volatility
    except Exception as e:
        # APIエラー時はデフォルト値を返す
        return PAIR_DEFAULTS[pair_key]["def_rate"], PAIR_DEFAULTS[pair_key]["def_vol"]

st.title("📈 高機能FXスワップ・シミュレータ")

# --- サイドバー：運用条件 ---
st.sidebar.header("📋 運用条件設定")

selected_pair = st.sidebar.selectbox("通貨ペア選択", list(PAIR_DEFAULTS.keys()))
order_side = st.sidebar.radio("売買", ["SHORT (売)", "LONG (買)"])
side_sign = -1 if order_side == "SHORT (売)" else 1

st.sidebar.subheader("📅 運用期間")
today = datetime.now().date()
from_date = st.sidebar.date_input("開始日 (From)", today)
to_date = st.sidebar.date_input("終了日 (To)", today + timedelta(days=365))

diff_days = (to_date - from_date).days
if diff_days <= 0:
    st.error("終了日は開始日より後の日付を選択してください。")
    st.stop()
if diff_days > 30 * 365:
    st.error("運用期間は最大30年までです。")
    st.stop()

st.sidebar.write(f"運用日数: **{diff_days}日**")

capital = st.sidebar.number_input("元手 [円]", value=100000, step=10000)
units = st.sidebar.number_input("保有通貨量", value=10000, step=1000)

# 変動量参照年数
years_for_vol = st.sidebar.slider("変動量計算の参照年数", 0.5, 30.0, 3.0, step=0.5)

# レート取得（失敗しても止まらない）
current_price_auto, avg_daily_change_auto = get_forex_data(PAIR_DEFAULTS[selected_pair]["symbol"], years_for_vol, selected_pair)
_, ref_jpy_price_auto = get_forex_data(PAIR_DEFAULTS[selected_pair]["jpy_ref"], 1, selected_pair)

entry_rate = st.sidebar.number_input("エントリーレート", value=current_price_auto, format="%.4f")
try_jpy = st.sidebar.number_input("決済時の対円レート", value=ref_jpy_price_auto, format="%.4f")
daily_vol = st.sidebar.number_input("1日の変動量予測", value=avg_daily_change_auto, format="%.5f")

swap_val = st.sidebar.number_input("1万通貨のスワップ [円]", value=PAIR_DEFAULTS[selected_pair]["swap"])
spread_pips = st.sidebar.number_input("スプレッド [pips]", value=PAIR_DEFAULTS[selected_pair]["spread"])

# --- 計算 ---
spread_cost_total = (spread_pips * 0.01) * units * try_jpy
total_swap = (units / 10000) * swap_val * diff_days

expected_end_rate = entry_rate + (daily_vol * diff_days * side_sign)

if order_side == "SHORT (売)":
    profit_jpy = (entry_rate - (expected_end_rate + (spread_pips * 0.01))) * units * try_jpy
    loss_cut_rate = entry_rate + (capital / (units * try_jpy))
else:
    profit_jpy = ((expected_end_rate - (spread_pips * 0.01)) - entry_rate) * units * try_jpy
    loss_cut_rate = entry_rate - (capital / (units * try_jpy))

total_profit = total_swap + profit_jpy

# --- 表示 ---
st.header("📊 シミュレーション結果")
c1, c2, c3, c4 = st.columns(4)
c1.metric("トータル損益", f"{total_profit:,.0f} 円")
c2.metric("累計スワップ", f"{total_swap:,.0f} 円")
c3.metric("予測為替損益", f"{profit_jpy:,.0f} 円")
c4.metric("ロスカットレート", f"{loss_cut_rate:.3f}")

# --- 推移テーブル ---
st.subheader("🗓️ 推移予測（30日毎）")
months = max(1, diff_days // 30)
history = []
for m in range(1, months + 2): # 最後の日まで含める
    current_m_days = min(m * 30, diff_days)
    m_swap = (units / 10000) * swap_val * current_m_days
    m_rate = entry_rate + (daily_vol * current_m_days * side_sign)
    
    if order_side == "SHORT (売)":
        m_fx_profit = (entry_rate - m_rate) * units * try_jpy
    else:
        m_fx_profit = (m_rate - entry_rate) * units * try_jpy
        
    history.append({
        "経過日数": f"{current_m_days}日",
        "予測レート": round(m_rate, 4),
        "累計スワップ": round(m_swap),
        "為替損益": round(m_fx_profit),
        "合計損益": round(m_swap + m_fx_profit)
    })
    if current_m_days == diff_days: break

df_history = pd.DataFrame(history)
st.table(df_history)

csv = df_history.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 結果をCSVでダウンロード", data=csv, file_name="fx_simulation.csv", mime="text/csv")
