import streamlit as st
import time
import requests
from binance.client import Client
import sqlite3
import pandas as pd

# SQLite3 Database Connection
conn = sqlite3.connect('trading_bot.db', check_same_thread=False)
c = conn.cursor()

# Create table if not exists
c.execute('''
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    trade_type TEXT,
    amount REAL,
    price REAL,
    pnl REAL,
    usdt_balance REAL,
    crypto_balance REAL,
    timestamp TEXT
)
''')

# Function to insert trade into the database
def log_trade(symbol, trade_type, amount, price, pnl, usdt_balance, crypto_balance):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO trades (symbol, trade_type, amount, price, pnl, usdt_balance, crypto_balance, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (symbol, trade_type, amount, price, pnl, usdt_balance, crypto_balance, timestamp))
    conn.commit()

# EMA Calculation
def get_ema(symbol, interval, length, client):
    klines = client.get_klines(symbol=symbol, interval=interval)
    closes = [float(entry[4]) for entry in klines]
    return sum(closes[-length:]) / length

# Trading Conditions (EMA Crossover Strategy)
def trade_condition(symbol, short_ema, long_ema, client, usdt_balance, crypto_balance):
    buy_order_value, sell_order_value, pnl = None, None, None

    if short_ema > long_ema:
        if usdt_balance > 10:
            st.write("Short EMA is above Long EMA. Placing a BUY order.")
            buy_order = client.order_market_buy(symbol=symbol, quoteOrderQty=usdt_balance)
            buy_order_value = float(buy_order['fills'][0]['price'])
            log_trade(symbol, 'BUY', usdt_balance, buy_order_value, pnl, usdt_balance, crypto_balance)
            st.success(f'Buy Order placed. Amount: {usdt_balance}, Price: {buy_order_value}')
    
    elif short_ema < long_ema:
        if crypto_balance > 0.0001:
            st.write("Short EMA is below Long EMA. Placing a SELL order.")
            sell_order = client.order_market_sell(symbol=symbol, quantity=crypto_balance)
            sell_order_value = float(sell_order['fills'][0]['price'])
            pnl = sell_order_value - buy_order_value
            log_trade(symbol, 'SELL', crypto_balance, sell_order_value, pnl, usdt_balance, crypto_balance)
            st.success(f'Sell Order placed. Amount: {crypto_balance}, PNL: {pnl}')
    
    return buy_order_value, sell_order_value, pnl

# Streamlit Dashboard Layout
st.title("Binance Trading Bot Dashboard")

# User inputs for Binance API keys
api_key = st.text_input("Enter Binance API Key", type="password")
api_secret = st.text_input("Enter Binance API Secret", type="password")

# Initialize Binance client
client = Client(api_key, api_secret)
# client.ping()  # Test connection
# st.success("Successfully connected to Binance API!")

if client:
    # User inputs for symbol, interval, and EMA periods
    symbol = st.text_input("Enter the Trading Symbol (e.g., BTCUSDT)", value="BTCUSDT")
    interval = st.selectbox("Select Interval", ['1m', '5m', '15m', '1h', '1d'])
    short_ema_period = st.number_input("Short EMA Period", min_value=1, max_value=50, value=7)
    long_ema_period = st.number_input("Long EMA Period", min_value=1, max_value=50, value=25)

    # Amount to trade
    trade_amount = st.number_input("Amount to Trade in USDT", min_value=10.0, value=100.0)

    if st.button("Start Trading", key="start_trading"):
        usdt_balance = float(client.get_asset_balance(asset='USDT')['free'])
        crypto_balance = float(client.get_asset_balance(asset=symbol[:-4])['free'])

        # Create placeholders for dynamic updates
        current_price_placeholder = st.empty()
        usdt_balance_placeholder = st.empty()
        crypto_balance_placeholder = st.empty()
        short_ema_placeholder = st.empty()
        long_ema_placeholder = st.empty()
        buy_order_value_placeholder = st.empty()
        sell_order_value_placeholder = st.empty()
        pnl_placeholder = st.empty()

        while True:
            short_ema = get_ema(symbol, interval, short_ema_period, client)
            long_ema = get_ema(symbol, interval, long_ema_period, client)
            current_price = float(client.get_symbol_ticker(symbol=symbol)['price'])

            # Update placeholders
            current_price_placeholder.write(f"Current Price: {current_price}")
            usdt_balance_placeholder.write(f"USDT Balance: {usdt_balance}")
            crypto_balance_placeholder.write(f"Crypto Balance: {crypto_balance}")
            short_ema_placeholder.write(f"Short EMA: {short_ema}, Long EMA: {long_ema}")

            buy_order_value, sell_order_value, pnl = trade_condition(symbol, short_ema, long_ema, client, usdt_balance, crypto_balance)

            # Update the displayed values
            buy_order_value_placeholder.write(f"Buy Order Value: {buy_order_value if buy_order_value else 'N/A'}")
            sell_order_value_placeholder.write(f"Sell Order Value: {sell_order_value if sell_order_value else 'N/A'}")
            pnl_placeholder.write(f"Profit/Loss (PNL): {pnl if pnl else 'N/A'}")

            # Display the last executed trade
            if buy_order_value or sell_order_value:
                last_trade_data = pd.read_sql('SELECT * FROM trades ORDER BY id DESC LIMIT 1', conn)
                st.write("Last Trade Details:")
                st.dataframe(last_trade_data)

            time.sleep(5)
    else:
        print("Please enter API KEY AND secret key")    

    # Display Trade Log
    st.write("Trade Log")
    trade_data = pd.read_sql('SELECT * FROM trades', conn)
    st.dataframe(trade_data)
