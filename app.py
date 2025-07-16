import streamlit as st
import yfinance as yf
import pandas as pd
import ta
import matplotlib.pyplot as plt
import requests

def calculate_guppy_oscillator(df):
    short_emas = [df['Close'].ewm(span=span).mean() for span in [3, 5, 8, 10, 12, 15]]
    long_emas = [df['Close'].ewm(span=span).mean() for span in [30, 35, 40, 45, 50, 60]]
    avg_short = pd.concat(short_emas, axis=1).mean(axis=1)
    avg_long = pd.concat(long_emas, axis=1).mean(axis=1)
    return avg_short - avg_long

def send_telegram_alert(message):
    TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except Exception as e:
        st.warning(f"Telegram error: {e}")

def run_screener(tickers):
    results = []
    chart_data = {}

    for ticker in tickers:
        df = yf.download(ticker, period='3mo', interval='1d')
        if df.empty or len(df) < 60:
            continue

        df['GMO'] = calculate_guppy_oscillator(df)
        df['volume_ma20'] = df['Volume'].rolling(20).mean()
        rsi = ta.momentum.RSIIndicator(df['Close'], window=14)
        bb = ta.volatility.BollingerBands(df['Close'], window=20)
        df['RSI'] = rsi.rsi()
        df['bb_upper'] = bb.bollinger_hband()
        df['GMO_trigger'] = df['GMO'].rolling(20).mean()

        latest = df.iloc[-1]

        if (
            latest['Close'] > latest['bb_upper'] and
            latest['Volume'] > 1.5 * latest['volume_ma20'] and
            60 < latest['RSI'] < 85 and
            latest['GMO'] > latest['GMO_trigger']
        ):
            results.append({
                'Ticker': ticker,
                'Close': round(latest['Close'], 2),
                'RSI': round(latest['RSI'], 2),
                'GMO': round(latest['GMO'], 2),
                'GMO Trigger': round(latest['GMO_trigger'], 2),
                'Volume': int(latest['Volume'])
            })
            chart_data[ticker] = df

    return pd.DataFrame(results), chart_data

def plot_chart(df, ticker):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df['Close'], label='Close Price')
    ax.plot(df['bb_upper'], linestyle='--', label='Bollinger Upper')
    ax.set_title(f"Harga dan Bollinger Band: {ticker}")
    ax.legend()
    st.pyplot(fig)

def load_tickers_from_file(uploaded_file):
    df = pd.read_excel(uploaded_file)
    if 'Ticker' in df.columns:
        return df['Ticker'].dropna().astype(str).tolist()
    else:
        st.warning("Kolom 'Ticker' tidak ditemukan dalam file.")
        return []

def load_broker_summary(file):
    df = pd.read_excel(file)
    if 'Ticker' not in df.columns:
        st.warning("Kolom 'Ticker' tidak ditemukan dalam file broker summary.")
        return pd.DataFrame()
    return df

def main():
    st.set_page_config(page_title="Screener Saham Breakout", layout="wide")
    st.title("📈 Stock Screener: GUPPY MMA + Bollinger + RSI + Volume")

    st.sidebar.header("📌 Input Ticker Saham")
    default_tickers = "BBCA.JK, INCO.JK, ANTM.JK, ERAA.JK, INET.JK, MBMA.JK"
    user_input = st.sidebar.text_area("Masukkan ticker saham (pisahkan dengan koma):", default_tickers)

    uploaded_file = st.sidebar.file_uploader("📥 Atau unggah file Excel (dengan kolom 'Ticker'):", type=['xlsx'])
    uploaded_broker = st.sidebar.file_uploader("📊 Unggah file Broker Summary (XLSX):", type=['xlsx'])

    tickers = []
    if uploaded_file:
        tickers = load_tickers_from_file(uploaded_file)
    else:
        tickers = [x.strip() for x in user_input.split(',') if x.strip()]

    if st.sidebar.button("🔍 Jalankan Screener"):
        with st.spinner("Mengambil data dan menjalankan screener..."):
            result_df, chart_data = run_screener(tickers)
            if result_df.empty:
                st.warning("Tidak ada saham yang memenuhi kriteria saat ini.")
            else:
                st.success(f"Ditemukan {len(result_df)} saham memenuhi kriteria.")

                # Alert Telegram
                alert_msg = "\n".join([f"{row['Ticker']} - Close: {row['Close']}, RSI: {row['RSI']}" for _, row in result_df.iterrows()])
                send_telegram_alert(f"📢 Sinyal Breakout Ditemukan:\n{alert_msg}")

                if uploaded_broker:
                    broker_df = load_broker_summary(uploaded_broker)
                    merged_df = pd.merge(result_df, broker_df, on='Ticker', how='left')
                    st.subheader("📌 Hasil Gabungan dengan Broker Summary")
                    st.dataframe(merged_df, use_container_width=True)
                    csv = merged_df.to_csv(index=False).encode('utf-8')
                else:
                    st.dataframe(result_df, use_container_width=True)
                    csv = result_df.to_csv(index=False).encode('utf-8')

                st.download_button("📥 Download Hasil (CSV)", data=csv, file_name="hasil_screener.csv", mime="text/csv")

                st.subheader("📊 Grafik Harga Saham Terpilih")
                for ticker in result_df['Ticker']:
                    st.markdown(f"### {ticker}")
                    plot_chart(chart_data[ticker], ticker)

if __name__ == '__main__':
    main()
