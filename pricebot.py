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
logger = logging.getLogger(__name__)

# --- Fetch price from Binance Futures ---
def get_price(symbol: str):
    try:
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol.upper()}USDT"
        response = requests.get(url, timeout=10)
        data = response.json()
        if "price" in data:
            return float(data["price"]), symbol.upper() + "USDT"
        return None, None
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return None, None

# --- Signal Handler ---
async def handle_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    try:
        # --- Detect Long & Short signals ---
        # Long: #COIN Buy_at_CMP | Buy_at_CMP #COIN | #COIN Buy_at:<price>
        long_matches = re.findall(
            r'#([a-z0-9\-]+)\s*buy_at_cmp'
            r'|buy_at_cmp\s*#([a-z0-9\-]+)'
            r'|#([a-z0-9\-]+)\s*buy_at:\s*([\d\.]+)',
            text, re.IGNORECASE
        )

        # Short: #COIN Short_at_CMP | Short_at_CMP #COIN | #COIN Short_at:<price>
        short_matches = re.findall(
            r'#([a-z0-9\-]+)\s*short_at_cmp'
            r'|short_at_cmp\s*#([a-z0-9\-]+)'
            r'|#([a-z0-9\-]+)\s*short_at:\s*([\d\.]+)',
            text, re.IGNORECASE
        )

        signals = []

        # Process long signals
        for m in long_matches:
            coin = m[0] or m[1] or m[2]
            entry_price = m[3] if len(m) > 3 and m[3] else None
            signals.append((coin, False, entry_price))  # False = Long

        # Process short signals
        for m in short_matches:
            coin = m[0] or m[1] or m[2]
            entry_price = m[3] if len(m) > 3 and m[3] else None
            signals.append((coin, True, entry_price))   # True = Short

        # --- Send formatted signals ---
        for coin_id, is_short, entry_price in signals:
            if entry_price:  # manual entry
                price = float(entry_price)
                _, actual_symbol = get_price(coin_id)  # get real Binance symbol
            else:
                price, actual_symbol = get_price(coin_id)

            if not price:
                await update.message.reply_text(f"⚠️ Could not fetch price for {coin_id}")
                continue

            side = "Short" if is_short else "Long"
            mode = "Future" if is_short else "Future Long + Spot"

            message = (
                f"{mode}\n\n"
                f"{actual_symbol}\n\n"
                f"Entry: {entry_price if entry_price else price}\n\n"
                f"TP1: ...\n"
                f"TP2: ...\n"
                f"TP3: ...\n\n"
                f"Stoploss: ...\n"
                f"Leverage : 20x [cross]\n"
                f"Amount per trade : 1%\n\n"
                f"@shsAdmin"
            )

            await update.message.reply_text(message)

    except Exception as e:
        logger.error(f"Error handling signal: {e}")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ Bot Error:\n{e}")

# --- Main Bot ---
def main():
    keep_alive()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_signal))
    app.run_polling()

if __name__ == "__main__":
    main()
