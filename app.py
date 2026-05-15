import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# ページ設定
st.set_page_config(page_title="Professional FX Simulator", layout="wide")

# --- 通貨ペア設定データ（API失敗時のバックアップ値を含む） ---
PAIR_CONFIG = {
    "CHF/TRY": {"symbol": "CHFTRY=X", "jpy_ref": "TRYJPY=X", "swap": 1500, "spread": 9.0, "fb_rate": 38.5, "fb_jpy": 4.5, "fb_vol": 0.0328},
    "USD/JPY": {"symbol": "USDJPY=X", "jpy_ref": "", "swap": 230, "spread": 0.2, "fb_rate": 150.0, "fb_jpy": 1.0, "fb_vol": 0.5},
    "EUR/JPY": {"symbol": "EURJPY=X", "jpy_ref": "", "swap": 200, "spread": 0.4, "fb_rate": 160.0, "fb_jpy": 1.0, "fb_vol": 0.6},
    "GBP/JPY": {"symbol": "GBPJPY=X", "jpy_ref": "", "swap": 250, "spread": 0.6, "fb_rate": 190.0, "fb_jpy": 1.0, "fb_vol": 0.8},
    "MXN/JPY": {"symbol": "MXNJPY=X", "jpy_ref": "", "swap": 30, "spread": 0.3, "fb_rate": 8.8, "fb_jpy": 1.0, "fb_vol": 0.05},
    "TRY/JPY": {"symbol": "TRYJPY=X", "jpy_ref": "", "swap": 50, "spread": 3.0, "fb_rate": 4.5, "fb_jpy": 1.0, "fb_vol": 0.03},
    "ZAR/JPY": {"symbol": "ZARJPY=X", "jpy_ref": "", "swap": 20, "spread": 1.0, "fb_rate": 8.0, "fb_jpy": 1.0, "fb_vol": 0.06},
}

@st.cache_data(ttl=3600)
def get_forex_data_robust(symbol, years, pair_key):
    """
    価格と変動量を一括取得。取得失敗時はPAIR_CONFIGのfb値（フォールバック）を返す。
    """
    try:
        # 余裕を持って過去データを取得
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(years * 365) + 10)
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        
        if df.empty or len(df) < 2:
            return PAIR_CONFIG[pair_key]["fb_rate"], PAIR_CONFIG[pair_key]["fb_vol"]
        
        # Close列を確実に取得（MultiIndex対策）
        if isinstance(df.columns, pd.MultiIndex):
            close_data = df['Close'][symbol]
        else:
            close_data = df['Close']
            
        current_price = float(close_data.iloc[-1])
        daily_vol = float(close_data.diff().abs().mean())
        
        return current_price, daily_vol
    except:
        return PAIR_CONFIG[pair_key]["fb_rate"], PAIR_CONFIG[pair_key]["fb_vol"]

@st.cache_data(ttl=3600)
def get_jpy_rate_robust(ref_symbol, pair_key):
    """決済通貨の対円レートを取得"""
    if not ref_symbol:
        return 1.0
    try:
        # 直近5日分を取得して最新の終値を採用（市場閉場対策）
        df = yf.download(ref_symbol, period="5d", progress=False)
        if df.empty:
            return PAIR_CONFIG[pair_key]["fb_jpy"]
            
        if isinstance(df.columns, pd.MultiIndex):
            close_val = df['Close'][ref_symbol].iloc[-1]
        else:
            close_val = df['Close'].iloc[-1]
            
        return float(close_val)
    except:
        return PAIR_CONFIG[pair_key]["fb_jpy"]

st.title("🛡️ プロフェッショナル FX シミュレータ")

# --- サイドバー：運用条件 ---
st.sidebar.header("📋 運用条件設定")

# 1. 通貨ペアと売買
selected_pair = st.sidebar.selectbox("通貨ペア", list(PAIR_CONFIG.keys()), index=list(PAIR_CONFIG.keys()).index("CHF/TRY"))
order_side = st.sidebar.radio("売買方向", ["SHORT (売)", "LONG (買)"])

# 2. 期間設定
st.sidebar.subheader("📅 運用期間")
d_from = st.sidebar.date_input("開始日 (From)", datetime.now())
d_to = st.sidebar.date_input("終了日 (To)", datetime.now() + timedelta(days=365))
diff_days = (d_to - d_from).days

if diff_days <= 0:
    st.error("終了日は開始日より後の日付にしてください。")
    st.stop()

# 3. 資金設定
capital = st.sidebar.number_input("元手 [円]", value=100000, step=10000)
units = st.sidebar.number_input("保有通貨量", value=10000, step=1000)

# 4. レート・変動量の取得（ここで計算ミスを修正）
vol_period = st.sidebar.slider("変動量参照期間 [年]", 0.5, 30.0, 3.0, step=0.5)

# APIから取得を試みる
curr_p, avg_v = get_forex_data_robust(PAIR_CONFIG[selected_pair]["symbol"], vol_period, selected_pair)
jpy_r = get_jpy_rate_robust(PAIR_CONFIG[selected_pair]["jpy_ref"], selected_pair)

# 入力欄に値を反映（取得失敗時はPAIR_CONFIGのfb値が入る）
entry_rate = st.sidebar.number_input("エントリーレート", value=curr_p, format="%.4f")
jpy_rate_now = st.sidebar.number_input("決済通貨の対円レート", value=jpy_r, format="%.4f")
daily_vol = st.sidebar.number_input("1日の予想変動量", value=avg_v, format="%.5f")

# 5. スワップ・スプレッド
swap_val = st.sidebar.number_input("1万通貨のスワップ [円]", value=PAIR_CONFIG[selected_pair]["swap"])
spread_pips = st.sidebar.number_input("スプレッド [pips]", value=PAIR_CONFIG[selected_pair]["spread"])

# 6. 実行レバレッジ表示
effective_leverage = (units * entry_rate * jpy_rate_now) / capital
st.sidebar.markdown("---")
st.sidebar.write(f"📊 **現在の実行レバレッジ: {effective_leverage:.2f} 倍**")

# 7. 市場トレンド選択
st.sidebar.subheader("📈 市場の動き予測")
market_trend = st.sidebar.radio("レートの推移方向", ["上昇トレンド", "下落トレンド"])
trend_sign = 1 if market_trend == "上昇トレンド" else -1

# --- 計算セクション ---
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

# --- 結果表示 ---
st.header(f"📊 {selected_pair} {order_side} 戦略結果")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("トータル損益", f"{total_profit:,.0f} 円")
col2.metric("為替損益", f"{fx_profit:,.0f} 円")
col3.metric("累積スワップ", f"{total_swap:,.0f} 円")
col4.metric("実行レバレッジ", f"{effective_leverage:.2f} 倍")
col5.metric("ロスカットレート", f"{loss_cut_rate:.4f}")

# --- 推移テーブル ---
st.subheader("🗓️ 期間別推移シミュレーション (30日毎)")
history = []
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
        "合計損益": round(m_swap + m_fx)
    })

if diff_days % 30 != 0:
    history.append({
        "経過日数": f"{diff_days}日 (最終)",
        "予測レート": round(expected_end_rate, 4),
        "累積スワップ": round(total_swap),
        "為替損益": round(fx_profit),
        "合計損益": round(total_profit)
    })

df_hist = pd.DataFrame(history)
st.table(df_hist)

# CSV
csv = df_hist.to_csv(index=False).encode('utf-8-sig')
st.download_button("📥 結果をCSVで保存", data=csv, file_name=f"fx_sim_{selected_pair}.csv", mime="text/csv")
