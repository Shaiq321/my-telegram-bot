import re
import requests
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from keep_alive import keep_alive  # Optional if hosting on Replit
import os

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))  # Your Telegram ID

# ✅ Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ✅ Fetch price from Binance Futures
def get_price(symbol):
    try:
        binance_symbol = symbol.upper() + "USDT"
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={binance_symbol}"
        response = requests.get(url)
        data = response.json()
        if 'price' in data:
            return float(data['price']), binance_symbol

        # Try 1000-prefixed version
        alt_symbol = "1000" + symbol.upper() + "USDT"
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={alt_symbol}"
        response = requests.get(url)
        data = response.json()
        if 'price' in data:
            return float(data['price']), alt_symbol
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return None, None

# ✅ Custom price formatting
def format_price_custom(price: float) -> str:
    price_str = f"{price:.10f}"
    if '.' in price_str:
        integer_part, decimal_part = price_str.split('.')
        sig_digits = ''
        count = 0
        for digit in decimal_part:
            sig_digits += digit
            if digit != '0':
                count += 1
            if count == 5:
                break
        return f"{integer_part}.{sig_digits}".rstrip('0').rstrip('.')
    return price_str

# ✅ Main handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip().lower()

        # === Handle closing ===
        cancel_keywords = r'\b(close|closed|closing|stopped out|stop loss|cut loss|hit sl|sl)\b'
        if re.search(cancel_keywords, text, re.IGNORECASE):
            coin_matches = re.findall(r'#([a-z0-9\-]+)', update.message.text, re.IGNORECASE)
            for coin in coin_matches:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Cancel {coin.upper()}/USDT"
                )
            return

        # === Entry detection ===
        long_match = re.search(r'#([a-z0-9\-]+)\s+buy_at_cmp', text)
        short_match = re.search(r'#([a-z0-9\-]+)\s+short_at_cmp', text)

        if long_match or short_match:
            coin_id = (long_match or short_match).group(1)
            price, actual_symbol = get_price(coin_id)

            if not price:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"⚠️ Could not fetch price for '{coin_id}'. Check symbol."
                )
                return

            is_short = bool(short_match)

            # SL/TP logic
            if coin_id.lower() == "btc":
                tp_factors = [0.982, 0.962, 0.922, 0.902, 0.852, 0.802, 0.702] if is_short else [1.018, 1.038, 1.078, 1.098, 1.148, 1.198, 1.298]
                stoploss_price = price * 1.10 if is_short else price * 0.90
                use_whole = True
            elif coin_id.lower() == "eth":
                tp_factors = [0.955, 0.905, 0.855, 0.805, 0.755, 0.705, 0.655] if is_short else [1.045, 1.095, 1.145, 1.195, 1.245, 1.295, 1.395]
                stoploss_price = price * 1.15 if is_short else price * 0.85
                use_whole = True
            else:
                tp_factors = [0.955, 0.905, 0.805, 0.605, 0.405, 0.205, 0.005] if is_short else [1.045, 1.095, 1.195, 1.395, 1.595, 1.795, 1.995]
                stoploss_price = price * 1.30 if is_short else price * 0.70
                use_whole = False

            tp_prices = [price * f for f in tp_factors]
            symbol_pair = f"{actual_symbol.replace('USDT', '')}/USDT"
            leverage = "20x"

            format_price = (lambda p: f"{int(p)}") if use_whole else format_price_custom

            # === Futures message ===
            futures_msg = (
                f"Futures {'Short' if is_short else 'Long'}\n\n"
                f"{symbol_pair}\n\n"
                f"Entry: {format_price(price)}\n\n" +
                "\n".join([f"TP{i+1}: {format_price(tp)}" for i, tp in enumerate(tp_prices)]) + "\n\n" +
                f"Stoploss: {format_price(stoploss_price)}\n\n"
                f"Leverage : {leverage} [cross]\n\n"
                f"@shsAdmin"
            )
            await context.bot.send_message(chat_id=update.effective_chat.id, text=futures_msg)
            await context.bot.send_message(chat_id='-1001541449446', text=futures_msg)

            # === Spot message (only for Long)
            if not is_short:
                spot_msg = (
                    f"Spot Buy\n\n"
                    f"{symbol_pair}\n\n"
                    f"Entry: {format_price(price)}\n\n" +
                    "\n".join([f"TP{i+1}: {format_price(tp)}" for i, tp in enumerate(tp_prices)]) + "\n\n" +
                    f"Stoploss: {format_price(stoploss_price)}\n\n"
                    f"@shsAdmin"
                )
                await context.bot.send_message(chat_id=update.effective_chat.id, text=spot_msg)
                await context.bot.send_message(chat_id='-1001541449446', text=spot_msg)

    except Exception as e:
        logger.exception("Error in handle_message")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"❗ Bot error:\n{e}")

# ✅ Start the bot
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
keep_alive()  # Optional if hosted on Replit

if __name__ == '__main__':
    print("Bot is running...")
    app.run_polling()
