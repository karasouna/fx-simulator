import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ページ設定
st.set_page_config(page_title="Professional FX Simulator", layout="wide")

# --- 通貨ペア設定データ (証券会社の一般的な目安) ---
PAIR_CONFIG = {
    "USD/JPY": {"symbol": "USDJPY=X", "jpy_ref": "", "swap": 230, "spread": 0.2},
    "EUR/JPY": {"symbol": "EURJPY=X", "jpy_ref": "", "swap": 200, "spread": 0.4},
    "GBP/JPY": {"symbol": "GBPJPY=X", "jpy_ref": "", "swap": 250, "spread": 0.6},
    "AUD/JPY": {"symbol": "AUDJPY=X", "jpy_ref": "", "swap": 150, "spread": 0.6},
    "NZD/JPY": {"symbol": "NZDJPY=X", "jpy_ref": "", "swap": 150, "spread": 0.7},
    "CAD/JPY": {"symbol": "CADJPY=X", "jpy_ref": "", "swap": 180, "spread": 0.8},
    "CHF/JPY": {"symbol": "CHFJPY=X", "jpy_ref": "", "swap": 100, "spread": 1.2},
    "ZAR/JPY": {"symbol": "ZARJPY=X", "jpy_ref": "", "swap": 20, "spread": 1.0},
    "MXN/JPY": {"symbol": "MXNJPY=X", "jpy_ref": "", "swap": 30, "spread": 0.3},
    "TRY/JPY": {"symbol": "TRYJPY=X", "jpy_ref": "", "swap": 50, "spread": 3.0},
    "EUR/USD": {"symbol": "EURUSD=X", "jpy_ref": "USDJPY=X", "swap": -150, "spread": 0.3},
    "GBP/USD": {"symbol": "GBPUSD=X", "jpy_ref": "USDJPY=X", "swap": -100, "spread": 0.3},
    "AUD/USD": {"symbol": "AUDUSD=X", "jpy_ref": "USDJPY=X", "swap": 100, "spread": 0.4},
    "CHF/TRY": {"symbol": "CHFTRY=X", "jpy_ref": "TRYJPY=X", "swap": 1500, "spread": 9.0},
}

@st.cache_data(ttl=3600)
def get_historical_stats(symbol, years):
    """過去の価格と日次変動幅の平均を取得"""
    try:
        ticker = yf.Ticker(symbol)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(years * 365))
        df = ticker.history(start=start_date, end=end_date)
        if df.empty:
            return None, None
        current_price = df['Close'].iloc[-1]
        avg_vol = df['Close'].diff().abs().mean()
        return float(current_price), float(avg_vol)
    except:
        return None, None

@st.cache_data(ttl=3600)
def get_jpy_rate(ref_symbol):
    """決済通貨の対円レートを取得"""
    if not ref_symbol: return 1.0
    try:
        ticker = yf.Ticker(ref_symbol)
        return float(ticker.history(period="1d")['Close'].iloc[-1])
    except:
        return 1.0

st.title("🛡️ プロフェッショナル FX シミュレータ")

# --- サイドバー設定 ---
st.sidebar.header("📋 運用条件")

# 1. 通貨ペアとポジション
selected_pair = st.sidebar.selectbox("通貨ペア", list(PAIR_CONFIG.keys()), index=list(PAIR_CONFIG.keys()).index("CHF/TRY"))
order_side = st.sidebar.radio("売買方向", ["SHORT (売)", "LONG (買)"])

# 2. 期間設定 (カレンダー)
st.sidebar.subheader("📅 運用期間")
d_from = st.sidebar.date_input("開始日 (From)", datetime.now())
d_to = st.sidebar.date_input("終了日 (To)", datetime.now() + timedelta(days=365))
diff_days = (d_to - d_from).days

if diff_days <= 0:
    st.error("終了日は開始日より後の日付にしてください。")
    st.stop()
if diff_days > 30 * 365:
    st.error("シミュレーションは最大30年までです。")
    st.stop()
st.sidebar.info(f"運用日数: {diff_days} 日")

# 3. 資金設定
capital = st.sidebar.number_input("元手 [円]", value=100000, step=10000)
units = st.sidebar.number_input("保有通貨量", value=10000, step=1000)

# 4. 変動量とレートの取得
vol_period = st.sidebar.slider("変動量参照期間 [年]", 0.5, 30.0, 3.0, step=0.5)
curr_p, avg_v = get_historical_stats(PAIR_CONFIG[selected_pair]["symbol"], vol_period)
jpy_r = get_jpy_rate(PAIR_CONFIG[selected_pair]["jpy_ref"])

entry_rate = st.sidebar.number_input("エントリーレート", value=curr_p if curr_p else 1.0, format="%.4f")
jpy_rate_now = st.sidebar.number_input("決済通貨の対円レート", value=jpy_r, format="%.4f")
daily_vol = st.sidebar.number_input("1日の予想変動量", value=avg_v if avg_v else 0.0, format="%.5f")

# 5. スワップ・スプレッド (デフォルト値)
swap_val = st.sidebar.number_input("1万通貨のスワップ [円]", value=PAIR_CONFIG[selected_pair]["swap"])
spread_pips = st.sidebar.number_input("スプレッド [pips]", value=PAIR_CONFIG[selected_pair]["spread"])

# 6. 市場トレンドの選択 (重要: バグ回避)
st.sidebar.subheader("📈 市場の動き予測")
market_trend = st.sidebar.radio("レートの推移方向", ["上昇トレンド", "下落トレンド"])
trend_sign = 1 if market_trend == "上昇トレンド" else -1

# --- 計算セクション ---
expected_end_rate = entry_rate + (daily_vol * diff_days * trend_sign)

# スワップ合計
total_swap = (units / 10000) * swap_val * diff_days

# 為替損益の計算
# SHORTの場合: (エントリーレート - 決済レート) * 数量 * 対円レート
# LONGの場合:  (決済レート - エントリーレート) * 数量 * 対円レート
# ※スプレッド(pips)はコストとしてエントリーレートに加味
spread_impact = spread_pips * 0.01

if order_side == "SHORT (売)":
    fx_profit = (entry_rate - (expected_end_rate + spread_impact)) * units * jpy_rate_now
    loss_cut_rate = entry_rate + (capital / (units * jpy_rate_now))
else:
    fx_profit = ((expected_end_rate - spread_impact) - entry_rate) * units * jpy_rate_now
    loss_cut_rate = entry_rate - (capital / (units * jpy_rate_now))

total_profit = total_swap + fx_profit

# --- 表示 ---
st.header(f"📊 {selected_pair} {order_side} 戦略結果")
col1, col2, col3, col4 = st.columns(4)
col1.metric("トータル損益", f"{total_profit:,.0f} 円")
col2.metric("累積スワップ", f"{total_swap:,.0f} 円")
col3.metric("為替損益", f"{fx_profit:,.0f} 円", delta=fx_profit, delta_color="normal")
col4.metric("ロスカットレート", f"{loss_cut_rate:.4f}")

# --- 推移テーブル ---
st.subheader("🗓️ 期間別推移シミュレーション")
history = []
# 30日毎(約1ヶ月毎)にプロット
for i in range(0, diff_days + 1, 30):
    if i == 0: continue
    d_m = i
    m_rate = entry_rate + (daily_vol * d_m * trend_sign)
    m_swap = (units / 10000) * swap_val * d_m
    if order_side == "SHORT (売)":
        m_fx = (entry_rate - m_rate) * units * jpy_rate_now
    else:
        m_fx = (m_rate - entry_rate) * units * jpy_rate_now
    
    history.append({
        "経過日数": f"{d_m}日",
        "予測レート": round(m_rate, 4),
        "累積スワップ": round(m_swap),
        "為替損益": round(m_fx),
        "トータル損益": round(m_swap + m_fx)
    })

# 最終日を追加
if diff_days % 30 != 0:
    m_rate = expected_end_rate
    m_swap = total_swap
    history.append({
        "経過日数": f"{diff_days}日 (最終)",
        "予測レート": round(m_rate, 4),
        "累積スワップ": round(m_swap),
        "為替損益": round(fx_profit),
        "トータル損益": round(total_profit)
    })

df_hist = pd.DataFrame(history)
st.dataframe(df_hist, use_container_width=True)

# CSV
csv = df_hist.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 シミュレーション結果をCSVで保存", data=csv, file_name=f"fx_sim_{selected_pair}.csv", mime="text/csv")

st.caption("※スワップやスプレッドは一般的な値であり、実際の証券会社や相場状況によって変動します。")
