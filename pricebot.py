from keep_alive import keep_alive  # Optional if you use keep_alive.py
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import re
import requests

import os
TOKEN = os.getenv("TOKEN")


def get_price(symbol):
    binance_symbol = symbol.upper() + "USDT"
    url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol}"
    try:
        response = requests.get(url)
        data = response.json()
        return float(data['price']) if 'price' in data else None
    except:
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.lower()
    match = re.search(r'#([a-z0-9]+)\s+buy_at_cmp', text)
    if match:
        coin = match.group(1)
        price = get_price(coin)
        if price:
            msg = (
                f"Spot + Future Long\n"
                f"Pair: {coin.upper()}/USDT\n"
                f"Entry: {price:.4f}\n"
                f"TP1: {price*1.05:.4f}\n"
                f"TP2: {price*1.10:.4f}\n"
                f"TP3: {price*1.20:.4f}\n"
                f"TP4: {price*1.40:.4f}\n"
                f"TP5: {price*1.60:.4f}\n"
                f"TP6: {price*1.80:.4f}\n"
                f"TP7: {price*2.00:.4f}\n"
                f"Lev: 2x-5x\n"
                f"Stoploss: {price*0.60:.4f} USD\n"
                f"For Premium contact @shsAdmin"
            )
            await update.message.reply_text(msg)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Optional keep_alive to prevent Render from sleeping
keep_alive()

if __name__ == '__main__':
    print("Bot running...")
    app.run_polling()
