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
    match = re.search(r'#([a-z0-9\-]+)\s+buy_at_cmp', text)
    if match:
        coin_id = match.group(1)
        price = get_price(coin_id)

        if price:
            if coin_id.lower() == "btc":
                tp1_price = price * 1.02
                tp2_price = price * 1.04
                tp3_price = price * 1.08
                tp4_price = price * 1.10
                tp5_price = price * 1.15
                tp6_price = price * 1.20
                tp7_price = price * 1.30
                stoploss_price = price * 0.90  # 10% stoploss for BTC
                use_whole_numbers = True
            else:
                # Default TP levels
                tp1_price = price * 1.05
                tp2_price = price * 1.10
                tp3_price = price * 1.20
                tp4_price = price * 1.40
                tp5_price = price * 1.60
                tp6_price = price * 1.80
                tp7_price = price * 2.00
                stoploss_price = price * 0.70
                use_whole_numbers = False

            leverage = "2x-5x"
            symbol_pair = f"{coin_id.upper()}/USDT"

            # ✅ Format prices
            if coin_id.lower() in ["btc", "eth"]:
                format_price = lambda p: f"{int(p)}"
            else:
                format_price = format_price_custom if not use_whole_numbers else (lambda p: f"{int(p)}")

            response_message = (
                f"Spot + Future Long\n"
                f"{symbol_pair}\n"
                f"Entry: {format_price(price)}\n"
                f"TP1: {format_price(tp1_price)}\n"
                f"TP2: {format_price(tp2_price)}\n"
                f"TP3: {format_price(tp3_price)}\n"
                f"TP4: {format_price(tp4_price)}\n"
                f"TP5: {format_price(tp5_price)}\n"
                f"TP6: {format_price(tp6_price)}\n"
                f"TP7: {format_price(tp7_price)}\n"
                f"Lev: {leverage}\n"
                f"Stoploss: {format_price(stoploss_price)}\n\n"
                f"For Premium contact @shsAdmin"
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
