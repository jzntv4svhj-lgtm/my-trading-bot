import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import date

st.set_page_config(page_title="My Trading Dashboard", page_icon="📈", layout="wide")
st.title("📈 My Trading Dashboard")
st.caption("Research scanner and manual trade journal — it does not connect to Trading 212 or place orders.")

with st.sidebar:
    st.header("Risk rules")
    capital = st.number_input("Starting capital (£)", min_value=1.0, value=50.0, step=5.0)
    max_trade = st.number_input("Maximum planned trade (£)", min_value=1.0, value=10.0, step=1.0)
    max_positions = st.number_input("Maximum open positions", min_value=1, max_value=10, value=2)
    loss_limit = st.number_input("Stop scanning after realised losses (£)", min_value=1.0, value=15.0, step=1.0)
    st.caption("These are reminders only. They cannot enforce broker limits or prevent losses.")

US_TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "PLTR", "SOFI", "RKLB"]
UK_TICKERS = ["SHEL.L", "AZN.L", "HSBA.L", "BARC.L", "RR.L", "VOD.L", "BKG.L", "ITM.L", "SMIN.L", "STAN.L"]

@st.cache_data(ttl=900, show_spinner=False)
def get_history(ticker):
    return yf.download(ticker, period="6mo", interval="1d", auto_adjust=True, progress=False)

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))

def scan(tickers, market):
    rows = []
    for ticker in tickers:
        try:
            df = get_history(ticker)
            if df is None or df.empty or len(df) < 55:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                close = df["Close"].iloc[:, 0].dropna()
                volume = df["Volume"].iloc[:, 0].dropna()
            else:
                close = df["Close"].dropna()
                volume = df["Volume"].dropna()
            if len(close) < 55:
                continue
            last = float(close.iloc[-1])
            sma20 = float(close.rolling(20).mean().iloc[-1])
            sma50 = float(close.rolling(50).mean().iloc[-1])
            current_rsi = float(rsi(close).iloc[-1])
            avg_vol = float(volume.tail(20).mean())
            rel_vol = float(volume.iloc[-1] / avg_vol) if avg_vol else 0
            if last > sma20 > sma50 and 45 <= current_rsi <= 70 and rel_vol >= 1:
                signal = "BUY CANDIDATE"
            elif last > sma50:
                signal = "WATCH"
            else:
                signal = "NO SIGNAL"
            rows.append({"Market": market, "Ticker": ticker, "Last price": round(last, 3),
                         "RSI (14)": round(current_rsi, 1), "Rel. volume": round(rel_vol, 2),
                         "SMA 20": round(sma20, 3), "SMA 50": round(sma50, 3), "Signal": signal})
        except Exception:
            continue
    return pd.DataFrame(rows)

tab1, tab2, tab3 = st.tabs(["Overview & scanner", "Log a trade", "Trade history"])

with tab1:
    st.subheader("Account plan")
    c1, c2, c3 = st.columns(3)
    c1.metric("Starting capital", f"£{capital:.2f}")
    c2.metric("Max planned trade", f"£{max_trade:.2f}")
    c3.metric("Max open positions", max_positions)
    st.info("A BUY CANDIDATE is a technical-screening result, not a recommendation. Check the company, news, spread, fees and currency risk before deciding.")
    st.subheader("Daily share scanner")
    st.write("Prices and volume are sourced from Yahoo Finance via yfinance. Data may be delayed, incomplete or unavailable.")
    if st.button("Run / refresh scan", type="primary"):
        with st.spinner("Checking UK and US shares…"):
            results = pd.concat([scan(US_TICKERS, "US"), scan(UK_TICKERS, "UK")], ignore_index=True)
            st.session_state["scan_results"] = results
    results = st.session_state.get("scan_results")
    if results is not None:
        if results.empty:
            st.warning("No usable price data returned. Try again later.")
        else:
            chosen = st.multiselect("Show signals", ["BUY CANDIDATE", "WATCH", "NO SIGNAL"],
                                    default=["BUY CANDIDATE", "WATCH"])
            view = results[results["Signal"].isin(chosen)].sort_values(["Signal", "Rel. volume"], ascending=[True, False])
            st.dataframe(view, use_container_width=True, hide_index=True)
            st.download_button("Download scan CSV", results.to_csv(index=False), "share_scan.csv", "text/csv")
    else:
        st.caption("Press “Run / refresh scan” to fetch the latest available daily data.")

with tab2:
    st.subheader("Record a trade manually")
    st.caption("This only records what you enter. It does not send an order to Trading 212.")
    with st.form("trade_form"):
        ticker = st.text_input("Ticker (e.g. AAPL or RR.L)").strip().upper()
        side = st.selectbox("Action", ["Buy", "Sell"])
        amount = st.number_input("Amount (£)", min_value=0.01, value=min(10.0, max_trade), step=0.5)
        trade_date = st.date_input("Trade date", value=date.today())
        notes = st.text_input("Notes (optional)")
        submitted = st.form_submit_button("Save trade")
    if submitted:
        if not ticker:
            st.error("Enter a ticker.")
        else:
            record = {"Date": str(trade_date), "Ticker": ticker, "Action": side, "Amount (£)": amount, "Notes": notes}
            st.session_state.setdefault("trades", []).append(record)
            st.success("Trade recorded in this session.")
            if amount > max_trade:
                st.warning("This entry is above your planned maximum trade size.")

with tab3:
    st.subheader("Trade history")
    trades = pd.DataFrame(st.session_state.get("trades", []))
    if trades.empty:
        st.write("No trades recorded in this session yet.")
    else:
        st.dataframe(trades, use_container_width=True, hide_index=True)
        st.download_button("Download trade journal CSV", trades.to_csv(index=False), "trade_journal.csv", "text/csv")
        st.caption("Download your journal before closing or restarting the app. Session data may not persist.")

st.divider()
st.caption("Educational research tool only. Not financial advice. Investing can result in loss of capital. A £50 account is particularly sensitive to spreads, dealing costs and FX conversion. Risk settings are not guaranteed loss limits.")
