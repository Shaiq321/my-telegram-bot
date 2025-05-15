import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from keep_alive import keep_alive
import os
TOKEN = os.getenv("TOKEN")


# ✅ Fetch price from Binance Futures
def get_price(symbol):
    # Try fetching the price for the standard symbol
    binance_symbol = symbol.upper() + "USDT"
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={binance_symbol}"
    try:
        response = requests.get(url)
        data = response.json()
        if 'price' in data:
            return float(data['price'])
    except:
        pass  # If the standard symbol doesn't work, try the alternative

    # If not found, try fetching the price for the '1000' prefixed symbol (e.g., 1000PEPE)
    alternative_symbol = "1000" + symbol.upper() + "USDT"
    try:
        response = requests.get(f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={alternative_symbol}")
        data = response.json()
        if 'price' in data:
            return float(data['price'])
    except:
        return None  # If neither the standard nor alternative symbol works


# ✅ Format price with up to 5 significant decimal digits
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


# ✅ Handle Telegram messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip().lower()

    # === Cancellation handler ===
    # Match messages that include any variation of close/stopped out/sl/cut loss words,
    # and extract all hashtags with coin symbols
    cancel_keywords = r'\b(close|closed|closing|stopped out|stop loss|cut loss|hit sl|sl)\b'
    if re.search(cancel_keywords, text, re.IGNORECASE):
        coin_matches = re.findall(r'#([a-z0-9\-]+)', update.message.text, re.IGNORECASE)
        if coin_matches:
            responses = [f"Cancel {coin.upper()}/USDT" for coin in coin_matches]
            response_message = "\n".join(responses)

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=response_message
            )
            return  # Don't proceed to buy/short signal handler if cancellation matched

    # === Buy / Short signal handler ===
    long_match = re.search(r'#([a-z0-9\-]+)\s+buy_at_cmp', text)
    short_match = re.search(r'#([a-z0-9\-]+)\s+short_at_cmp', text)

    if long_match or short_match:
        coin_id = (long_match or short_match).group(1)
        price = get_price(coin_id)

        if price:
            is_short = bool(short_match)

            if coin_id.lower() == "btc":
                tp_factors = [0.982, 0.962, 0.922, 0.902, 0.852, 0.802, 0.702] if is_short else [1.018, 1.038, 1.078, 1.098, 1.148, 1.198, 1.298]
                stoploss_price = price * 1.10 if is_short else price * 0.90
                use_whole_numbers = True
            elif coin_id.lower() == "eth":
                tp_factors = [0.955, 0.905, 0.855, 0.805, 0.755, 0.705, 0.655] if is_short else [1.045, 1.095, 1.145, 1.195, 1.245, 1.295, 1.395]
                stoploss_price = price * 1.15 if is_short else price * 0.85
                use_whole_numbers = True
            else:
                tp_factors = [
                    0.955, 0.905, 0.805, 0.605, 0.405, 0.205, 0.005
                ] if is_short else [
                    1.045, 1.095, 1.195, 1.395, 1.595, 1.795, 1.995
                ]
                stoploss_price = price * 1.30 if is_short else price * 0.70
                use_whole_numbers = False

            tp_prices = [price * f for f in tp_factors]
            symbol_pair = f"{coin_id.upper()}/USDT"
            leverage = "20x"

            # Format price
            if coin_id.lower() in ["btc", "eth"]:
                format_price = lambda p: f"{int(p)}"
            else:
                format_price = format_price_custom if not use_whole_numbers else (lambda p: f"{int(p)}")

            response_message = (
                f"Future {'Short' if is_short else 'Long + Spot'}\n\n"
                f"{symbol_pair}\n\n"
                f"Entry: {format_price(price)}\n\n" +
                "\n".join([f"TP{i+1}: {format_price(tp)}" for i, tp in enumerate(tp_prices)]) + "\n\n" +
                f"Stoploss: {format_price(stoploss_price)}\n\n"
                f"Leverage : {leverage} [isolated]\n\n"
                f"@shsAdmin"
            )

            # Send to user
            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)

            # Send to channel
            await context.bot.send_message(chat_id='-1001541449446', text=response_message)

        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ Could not fetch price for '{coin_id}'. Please check Binance Futures symbol."
            )


# ✅ Start bot
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
keep_alive()

if __name__ == '__main__':
    print("Bot is running...")
    app.run_polling()
