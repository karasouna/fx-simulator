import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np

# ページ設定
st.set_page_config(page_title="Advanced FX Simulator", layout="wide")

# --- 通貨ペア設定データ ---
# 主要ペアのスワップ・スプレッド等のデフォルト値（目安）
PAIR_DEFAULTS = {
    "CHF/TRY": {"jpy_ref": "TRYJPY=X", "swap": 1500, "spread": 9.0, "symbol": "CHFTRY=X"},
    "USD/JPY": {"jpy_ref": "USDJPY=X", "swap": 230, "spread": 0.2, "symbol": "USDJPY=X"},
    "EUR/JPY": {"jpy_ref": "EURJPY=X", "swap": 200, "spread": 0.4, "symbol": "EURJPY=X"},
    "AUD/JPY": {"jpy_ref": "AUDJPY=X", "swap": 150, "spread": 0.6, "symbol": "AUDJPY=X"},
    "MXN/JPY": {"jpy_ref": "MXNJPY=X", "swap": 30, "spread": 0.3, "symbol": "MXNJPY=X"},
}

@st.cache_data(ttl=3600)
def get_forex_data(symbol, years):
    """過去の価格データを取得して1日の平均変動量を計算"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=int(years * 365))
    df = yf.download(symbol, start=start_date, end=end_date)
    if df.empty:
        return 0.0, 0.0
    current_price = df['Close'].iloc[-1]
    # 日次の変化量の絶対値の平均
    daily_volatility = df['Close'].diff().abs().mean()
    return float(current_price), float(daily_volatility)

st.title("📈 高機能FXスワップ・シミュレータ")

# --- サイドバー：運用条件 ---
st.sidebar.header("📋 運用条件設定")

# 1. 通貨ペアと売買
selected_pair = st.sidebar.selectbox("通貨ペア選択", list(PAIR_DEFAULTS.keys()))
order_side = st.sidebar.radio("売買", ["SHORT (売)", "LONG (買)"])
side_sign = -1 if order_side == "SHORT (売)" else 1

# 2. 期間設定
st.sidebar.subheader("📅 運用期間")
today = datetime.now().date()
from_date = st.sidebar.date_input("開始日 (From)", today)
to_date = st.sidebar.date_input("終了日 (To)", today + timedelta(days=365))

# 期間バリデーション
diff_days = (to_date - from_date).days
if diff_days <= 0:
    st.error("終了日は開始日より後の日付を選択してください。")
    st.stop()
if diff_days > 30 * 365:
    st.error("運用期間は最大30年までです。")
    st.stop()

st.sidebar.write(f"運用日数: **{diff_days}日**")

# 3. 資金・通貨量
capital = st.sidebar.number_input("元手 [円]", value=100000, step=10000)
units = st.sidebar.number_input("保有通貨量", value=10000, step=1000)

# 4. レート取得と変動量計算
years_for_vol = st.sidebar.slider("変動量計算の参照年数", 0.5, 30.0, 3.0, step=0.5)
current_price, avg_daily_change = get_forex_data(PAIR_DEFAULTS[selected_pair]["symbol"], years_for_vol)
_, ref_jpy_price = get_forex_data(PAIR_DEFAULTS[selected_pair]["jpy_ref"], 1)

entry_rate = st.sidebar.number_input("エントリーレート", value=current_price, format="%.4f")
try_jpy = st.sidebar.number_input("決済時のリラ円(等)レート", value=ref_jpy_price, format="%.4f")
daily_vol = st.sidebar.number_input("1日の変動量予測 [リラ/円]", value=avg_daily_change, format="%.5f")

# 5. スワップ・スプレッド
swap_val = st.sidebar.number_input("1万通貨のスワップ [円]", value=PAIR_DEFAULTS[selected_pair]["swap"])
spread_pips = st.sidebar.number_input("スプレッド [pips]", value=PAIR_DEFAULTS[selected_pair]["spread"])

# --- 計算セクション ---
spread_cost_total = (spread_pips * 0.01) * units * try_jpy
total_swap = (units / 10000) * swap_val * diff_days

# 最終予測レート（売りの場合は上昇すると損失、買いの場合は下落すると損失）
# 期待値としての予測レート
expected_end_rate = entry_rate + (daily_vol * diff_days * side_sign)
# 為替損益 = (決済価格 - 注文価格) * 数量 * 対円レート (Buyの場合)
# Shortの場合は (注文価格 - 決済価格)
if order_side == "SHORT (売)":
    profit_jpy = (entry_rate - (expected_end_rate + (spread_pips * 0.01))) * units * try_jpy
else:
    profit_jpy = ((expected_end_rate - (spread_pips * 0.01)) - entry_rate) * units * try_jpy

total_profit = total_swap + profit_jpy

# ロスカットレート（簡易計算：証拠金維持率100%想定）
# 有効証拠金 = 元手 + 損益 >= 0 となるレート
# (entry - price) * units * jpy + capital = 0  => price = entry + (capital / (units * jpy))
if order_side == "SHORT (売)":
    loss_cut_rate = entry_rate + (capital / (units * try_jpy))
else:
    loss_cut_rate = entry_rate - (capital / (units * try_jpy))

# --- 結果表示 ---
st.header("📊 シミュレーション結果")
c1, c2, c3, c4 = st.columns(4)
c1.metric("トータル損益", f"{total_profit:,.0f} 円")
c2.metric("累計スワップ", f"{total_swap:,.0f} 円")
c3.metric("予測為替損益", f"{profit_jpy:,.0f} 円")
c4.metric("ロスカットレート", f"{loss_cut_rate:.3f}")

# --- 月別詳細テーブル ---
st.subheader("🗓️ 月別推移予測")
months = max(1, diff_days // 30)
history = []
for m in range(1, months + 1):
    m_days = m * 30
    if m_days > diff_days: m_days = diff_days
    
    m_swap = (units / 10000) * swap_val * m_days
    m_rate = entry_rate + (daily_vol * m_days * side_sign)
    
    if order_side == "SHORT (売)":
        m_fx_profit = (entry_rate - m_rate) * units * try_jpy
    else:
        m_fx_profit = (m_rate - entry_rate) * units * try_jpy
        
    history.append({
        "経過月": f"{m}ヶ月目",
        "予測レート": round(m_rate, 4),
        "累計スワップ": round(m_swap),
        "為替損益": round(m_fx_profit),
        "合計損益": round(m_swap + m_fx_profit)
    })
    if m_days == diff_days: break

df_history = pd.DataFrame(history)
st.table(df_history)

# CSVダウンロード
csv = df_history.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 結果をCSVでダウンロード", data=csv, file_name="fx_simulation.csv", mime="text/csv")
