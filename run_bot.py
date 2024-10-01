import time
import argparse
import requests
import sqlite3
from binance.client import Client
import os

# Initialize and adjust trading fee percentage
FEE_PERCENTAGE = 0.001  # 0.1% trading fee

# Binance API Settings
API_KEY = os.getenv("B_API_KEY")
API_SECRET = os.getenv("B_API_SECRET")

# Telegram settings
ENABLE_TELEGRAM_REPORTING = False
TELEGRAM_TOKEN = "YOUR_TELEGRAM_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

# SQLite database setup
def init_db():
    conn = sqlite3.connect('trading_bot.db')
    cursor = conn.cursor()
    
    # Create the trades table with the necessary columns
    cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
                        id INTEGER PRIMARY KEY,
                        symbol TEXT,
                        side TEXT,                  -- 'BUY' or 'SELL'
                        quantity REAL,              -- Quantity of crypto traded
                        price REAL,                 -- Price at which the trade was executed
                        usdt_balance REAL,          -- USDT balance after the trade
                        short_ema REAL,             -- Short EMA value at the time of the trade
                        long_ema REAL,              -- Long EMA value at the time of the trade
                        last_cross TEXT,            -- Last EMA crossover information
                        buy_order_value REAL,       -- Value of the buy order
                        sell_order_value REAL,      -- Value of the sell order
                        pnl REAL,                   -- Profit and Loss from the trade
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    return conn

def log_trade(conn, symbol, side, quantity, price, usdt_balance, short_ema, long_ema, last_cross, buy_order_value, sell_order_value, pnl):
    cursor = conn.cursor()
    cursor.execute('INSERT INTO trades (symbol, side, quantity, price, usdt_balance, short_ema, long_ema, last_cross, buy_order_value, sell_order_value, pnl) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                   (symbol, side, quantity, price, usdt_balance, short_ema, long_ema, last_cross, buy_order_value, sell_order_value, pnl))
    conn.commit()

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

def get_ema(symbol, interval, length, client):
    klines = client.get_klines(symbol=symbol, interval=interval)
    closes = [float(entry[4]) for entry in klines]
    return sum(closes[-length:]) / length

def get_balance(asset, client):
    try:
        balance = client.get_asset_balance(asset=asset)
        return float(balance['free']) if balance else 0.0
    except Exception as e:
        print(f"Error fetching {asset} balance: {e}")
        return 0.0

def get_current_price(symbol, client):
    try:
        ticker = client.get_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        print(f"Error fetching current price for {symbol}: {e}")
        return 0.0

def main():
    parser = argparse.ArgumentParser(description="Binance Spot Trading Bot based on EMA crossover.")
    parser.add_argument('symbol', type=str, help="Trading pair, e.g., 'BTCUSDT'.")
    parser.add_argument('interval', type=str, help="Interval for fetching data, e.g., '1h', '3d', '1m'.")
    parser.add_argument('short_ema_period', type=int, help="Short EMA period, e.g., 7.")
    parser.add_argument('long_ema_period', type=int, help="Long EMA period, e.g., 25.")
    args = parser.parse_args()

    # Initialize the Binance client
    client = Client(API_KEY, API_SECRET)
    conn = init_db()

    last_cross = None
    buy_cost = 0

    while True:
        try:
            current_price = get_current_price(args.symbol, client)
            short_ema = get_ema(args.symbol, args.interval, args.short_ema_period, client)
            long_ema = get_ema(args.symbol, args.interval, args.long_ema_period, client)

            if short_ema > long_ema and last_cross != 'above':
                usdt_balance = get_balance("USDT", client)
                if usdt_balance > 10:  # Minimum amount to trade
                    print("Placing a BUY order.")
                    buy_order = client.order_market_buy(symbol=args.symbol, quoteOrderQty=usdt_balance)
                    buy_cost = float(buy_order['cummulativeQuoteQty'])
                    buy_amount = sum([float(fill['qty']) for fill in buy_order['fills']])
                    
                    # Log the trade with all necessary information
                    log_trade(conn, args.symbol, 'BUY', buy_amount, current_price, usdt_balance, short_ema, long_ema, last_cross, usdt_balance, 0, 0)
                    last_cross = 'above'

            elif short_ema < long_ema and last_cross != 'below':
                crypto_balance = get_balance(args.symbol[:-4], client)
                if crypto_balance > 0.0001:  # Minimum amount to sell
                    print("Placing a SELL order.")
                    sell_order = client.order_market_sell(symbol=args.symbol, quantity=crypto_balance)
                    sell_revenue = float(sell_order['cummulativeQuoteQty'])
                    pnl = sell_revenue - buy_cost
                    print(f"PNL: {pnl:.2f} USDT")
                    
                    # Log the trade with all necessary information
                    log_trade(conn, args.symbol, 'SELL', crypto_balance, current_price, usdt_balance, short_ema, long_ema, last_cross, 0, sell_revenue, pnl)
                    last_cross = 'below'

            time.sleep(5)

        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
