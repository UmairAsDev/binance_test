import streamlit as st
import time
import requests
from binance.client import Client

# Initialize and Adjust trading fee percentage
FEE_PERCENTAGE = 0.001  # 0.1% trading fee

# Telegram settings
ENABLE_TELEGRAM_REPORTING = False
TELEGRAM_TOKEN = "XXXXXX"
CHAT_ID = "XXXXXXX"

# Function to send telegram messages
def send_telegram_message(message):
    if not ENABLE_TELEGRAM_REPORTING:
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }
    response = requests.post(url, payload)
    return response.json()

# Function to get EMA
def get_ema(symbol, interval, length, client):
    klines = client.get_klines(symbol=symbol, interval=interval)
    closes = [float(entry[4]) for entry in klines]
    return sum(closes[-length:]) / length

# Function to get balance
def get_balance(asset, client):
    balance = client.get_asset_balance(asset=asset)
    return float(balance['free'])

# Function to get current price
def get_current_price(symbol, client):
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

# Streamlit App
st.title("Binance Trading Bot")

# Input for API Key and Secret
api_key = st.text_input("Enter Binance API Key", value="")
api_secret = st.text_input("Enter Binance API Secret", value="", type="password")

# Input for trading parameters
symbol = st.text_input("Trading Pair (e.g., BTCUSDT)", value="BTCUSDT")
interval = st.selectbox("Interval", options=["1m", "5m", "1h", "1d"])
short_ema_period = st.number_input("Short EMA Period", min_value=1, value=7)
long_ema_period = st.number_input("Long EMA Period", min_value=1, value=25)
trade_amount = st.number_input("Trade Amount (USDT)", min_value=1.0, value=10.0)

# Button to start trading
if st.button("Start Trading"):
    if api_key and api_secret:
        client = Client(api_key, api_secret)
        last_cross = None
        buy_price = None

        trade_history = []

        while True:
            try:
                current_price = get_current_price(symbol, client)
                short_ema = get_ema(symbol, interval, short_ema_period, client)
                long_ema = get_ema(symbol, interval, long_ema_period, client)

                if short_ema > long_ema and last_cross != 'above':
                    busd_balance = get_balance("USDT", client)
                    if busd_balance >= trade_amount:
                        buy_order = client.order_market_buy(symbol=symbol, quantity=trade_amount)
                        buy_price = current_price
                        last_cross = 'above'
                        trade_history.append({"action": "BUY", "price": buy_price, "amount": trade_amount, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})

                elif short_ema < long_ema and last_cross != 'below':
                    crypto_balance = get_balance(symbol[:-4], client)
                    if crypto_balance > 0.0001:
                        sell_order = client.order_market_sell(symbol=symbol, quantity=crypto_balance)
                        sell_price = current_price
                        last_cross = 'below'
                        trade_history.append({"action": "SELL", "price": sell_price, "amount": crypto_balance, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})

                # Display current status
                st.write(f"Current Price: {current_price:.2f}, Short EMA: {short_ema:.2f}, Long EMA: {long_ema:.2f}")
                st.write("Trade History:")
                for trade in trade_history:
                    st.write(f"{trade['timestamp']}: {trade['action']} at {trade['price']:.2f}, Amount: {trade['amount']}")

                time.sleep(5)  # wait for 5 seconds before the next iteration

            except Exception as e:
                st.error(f"Error: {str(e)}")
                break  # Exit the loop if there's an error

# Button to stop trading
if st.button("Stop Trading"):
    st.warning("Trading has been stopped.")
