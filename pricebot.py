import re
import requests
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive
import os

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Logging

logging.basicConfig(
format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
level=logging.INFO
)
logger = logging.getLogger(**name**)

# Fetch price from Binance

def get_price(symbol: str):
try:
url = f"[https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol.upper()}USDT](https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol.upper%28%29}USDT)"
response = requests.get(url, timeout=5)
if response.status_code == 200:
data = response.json()
return float(data["price"]), symbol.upper() + "USDT"
except Exception as e:
logger.error(f"Error fetching price for {symbol}: {e}")
return None, None

# Signal processor

async def process_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
text = update.message.text.lower()

```
    # --- Cancellation keywords ---
    cancel_keywords = [
        'stopped out', 'close', 'hit sl', 'sl', 'booked profit',
        'booking profit', 'secured profit', 'secured gains', 'closed in profit'
    ]

    if any(keyword in text for keyword in cancel_keywords):
        matches = re.findall(r'#([a-z0-9\-]+)', text)
        if matches:
            for coin in matches:
                await update.message.reply_text(f"Cancel {coin.upper()}/USDT")
        return

    # --- Still holding filter ---
    still_holding = []
    if "still holding" in text:
        still_holding = re.findall(r'#([a-z0-9\-]+)', text)

    # --- Reopen ---
    is_reopen = 're-open' in text

    # --- Long signals (CMP or manual Buy_at) ---
    long_matches = re.findall(
        r'#([a-z0-9\-]+)\s+buy_at_cmp'
        r'|buy_at_cmp\s+#([a-z0-9\-]+)'
        r'|#([a-z0-9\-]+)\s*buy_at:\s*([\d\.]+)',
        text, re.IGNORECASE
    )

    # --- Short signals (CMP or manual Short_at) ---
    short_matches = re.findall(
        r'#([a-z0-9\-]+)\s+short_at_cmp'
        r'|short_at_cmp\s+#([a-z0-9\-]+)'
        r'|#([a-z0-9\-]+)\s*short_at:\s*([\d\.]+)',
        text, re.IGNORECASE
    )

    signals = []
    for m in long_matches:
        coin = m[0] or m[1] or m[2]
        entry_price = m[3] if len(m) > 3 and m[3] else None
        signals.append((coin, False, entry_price))

    for m in short_matches:
        coin = m[0] or m[1] or m[2]
        entry_price = m[3] if len(m) > 3 and m[3] else None
        signals.append((coin, True, entry_price))

    for coin_id, is_short, entry_price in signals:
        if coin_id.lower() in still_holding:
            continue

        if entry_price:  # Manual entry
            price = float(entry_price)
            _, actual_symbol = get_price(coin_id)  # fetch Binance symbol only
        else:  # CMP
            price, actual_symbol = get_price(coin_id)

        if price:
            coin_lower = coin_id.lower()

            if is_short:
                tp1 = price * 0.99
                tp2 = price * 0.98
                sl = price * 1.01
                direction = "Short"
            else:
                tp1 = price * 1.01
                tp2 = price * 1.02
                sl = price * 0.99
                direction = "Long"

            msg = (
                f"Exchange: Binance Futures\n"
                f"Pair: {actual_symbol}\n"
                f"Direction: {direction}\n"
                f"Entry: {price:.6f}\n"
                f"Targets:\n"
                f"TP1: {tp1:.6f}\n"
                f"TP2: {tp2:.6f}\n"
                f"Stoploss: {sl:.6f}"
            )

            if is_reopen:
                msg = "[Re-opened Trade]\n" + msg

            await update.message.reply_text(msg)

except Exception as e:
    logger.error(f"Error in process_signal: {e}")
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"Error: {e}")
```

# Start bot

def main():
keep_alive()
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), process_signal))
app.run_polling()

if **name** == "**main**":
main()
