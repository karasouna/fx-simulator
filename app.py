import streamlit as st

# ページ設定
st.set_page_config(page_title="FX CHF/TRY Simulator", layout="wide")

st.title("📉 CHF/TRY 売り戦略シミュレータ")

# サイドバー設定
st.sidebar.header("運用条件")
capital = st.sidebar.number_input("元手 [円]", value=20000)
units = st.sidebar.number_input("保有通貨量 [CHF]", value=1000)
entry_rate = st.sidebar.number_input("エントリーレート", value=58.158, format="%.3f")
try_jpy = st.sidebar.number_input("リラ円レート", value=3.47)
daily_change = st.sidebar.number_input("1日の変動量 [リラ]", value=0.03325, format="%.5f")
days = st.sidebar.number_input("運用日数", value=365)
swap_per_10k = st.sidebar.number_input("1万通貨のスワップ [円]", value=1500)
spread_pips = st.sidebar.number_input("スプレッド [pips]", value=9.0)
target_lev = st.sidebar.slider("目標レバレッジ", 1, 25, 15)

# 計算ロジック
spread_val = spread_pips * 0.01
total_swap = (units / 10000) * swap_per_10k * days
end_rate = entry_rate + (daily_change * days)
profit_jpy = (entry_rate - (end_rate + spread_val)) * units * try_jpy
total_profit = total_swap + profit_jpy
pos_value = units * entry_rate * try_jpy
required_margin = (pos_value / target_lev) + (spread_val * units * try_jpy)

# 結果表示
col1, col2, col3 = st.columns(3)
col1.metric("累計スワップ", f"{total_swap:,.0f}円")
col2.metric("為替損益", f"{profit_jpy:,.0f}円")
col3.metric("トータル損益", f"{total_profit:,.0f}円")

st.info(f"目標レバレッジ {target_lev}倍 を維持するための必要資金: {required_margin:,.0f} 円")
