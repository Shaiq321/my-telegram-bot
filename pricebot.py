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

# Binance Futures price fetcher
def get_price(symbol):
    try:
        binance_symbol = symbol.upper() + "USDT"
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={binance_symbol}"
        response = requests.get(url)
        data = response.json()
        if 'price' in data:
            return float(data['price']), binance_symbol

        alternative_symbol = "1000" + symbol.upper() + "USDT"
        url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={alternative_symbol}"
        response = requests.get(url)
        data = response.json()
        if 'price' in data:
            return float(data['price']), alternative_symbol

    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
    return None, None

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

# Main handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip().lower()
        coin_matches = re.findall(r'#([a-z0-9\-]+)', text, re.IGNORECASE)
        still_holding = set(re.findall(r'still holding\s+#([a-z0-9\-]+)', text, re.IGNORECASE))
        profit_keywords = re.findall(r'\+\d+%|\bclosed in profit\b|\bbooked\b|\bsecured\b', text)
        cancel_loss_keywords = r'\bstopped out\b|\bhit sl\b|\bsl\b|\bstop loss\b|\binvalidated\b'

        # Cancel by coin with loss only
        if re.search(cancel_loss_keywords, text) and coin_matches:
            for coin in sorted(set(coin_matches)):
                if coin.lower() in still_holding:
                    continue
                if not re.search(rf'{coin}.*(\+\d+%|\bclosed in profit\b|\bbooked\b|\bsecured\b)', text, re.IGNORECASE):
                    coin_upper = coin.upper()
                    message = f"Cancel {coin_upper}/USDT"
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
                    await context.bot.send_message(chat_id='-1001541449446', text=message)

        # Global short close
        if "shorts should be closed" in text:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Cancel All Short Trades")
            await context.bot.send_message(chat_id='-1001541449446', text="Cancel All Short Trades")
            return

        # Reopen and entry signals
        is_reopen = 're-open' in text
        long_matches = re.findall(r'#([a-z0-9\-]+)\s+buy_at_cmp|buy_at_cmp\s+#([a-z0-9\-]+)', text)
        short_matches = re.findall(r'#([a-z0-9\-]+)\s+short_at_cmp|short_at_cmp\s+#([a-z0-9\-]+)', text)

        signals = [(m[0] or m[1], False) for m in long_matches] + [(m[0] or m[1], True) for m in short_matches]

        if is_reopen:
            reopen_coins = re.findall(r'#([a-z0-9\-]+)', text, re.IGNORECASE)
            is_short = 'short_at_cmp' in text
            for coin in reopen_coins:
                if coin.lower() not in [s[0].lower() for s in signals]:
                    signals.append((coin, is_short))

        for coin_id, is_short in signals:
            if coin_id.lower() in still_holding:
                continue

            price, actual_symbol = get_price(coin_id)
            if price:
                coin_lower = coin_id.lower()
                if coin_lower in ["btc", "eth", "ltc", "link", "sol"]:
                    amount_line = "Amount per trade : 2%"
                else:
                    amount_line = "Amount per trade : 1%"

                if coin_lower == "btc":
                    tp_factors = [0.982, 0.962, 0.922, 0.902, 0.852, 0.802, 0.702] if is_short else [1.018, 1.038, 1.078, 1.098, 1.148, 1.198, 1.298]
                    stoploss_price = price * 1.10 if is_short else price * 0.90
                    use_whole = True
                elif coin_lower == "eth":
                    tp_factors = [0.955, 0.905, 0.855, 0.805, 0.755, 0.705, 0.655] if is_short else [1.045, 1.095, 1.145, 1.195, 1.245, 1.295, 1.395]
                    stoploss_price = price * 1.15 if is_short else price * 0.85
                    use_whole = True
                else:
                    tp_factors = [0.955, 0.905, 0.805, 0.605, 0.405, 0.205, 0.105] if is_short else [1.045, 1.095, 1.195, 1.395, 1.595, 1.795, 1.995]
                    stoploss_price = price * 1.30 if is_short else price * 0.70
                    use_whole = False

                tp_prices = [price * f for f in tp_factors]
                symbol_pair = f"{actual_symbol.replace('USDT', '')}/USDT"
                leverage = "20x"
                format_price = (lambda p: f"{int(p)}") if use_whole else format_price_custom

                response_message = (
                    f"Future {'Short' if is_short else 'Long + Spot'}\n\n"
                    f"{symbol_pair}\n\n"
                    f"Entry: {format_price(price)}\n\n" +
                    "\n".join([f"TP{i+1}: {format_price(tp)}" for i, tp in enumerate(tp_prices)]) + "\n\n" +
                    f"Stoploss: {format_price(stoploss_price)}\n\n"
                    f"Leverage : {leverage} [cross]\n"
                    f"{amount_line}\n\n"
                    f"@shsAdmin"
                )

                await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)
                await context.bot.send_message(chat_id='-1001541449446', text=response_message)
            else:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"⚠️ Could not fetch price for '{coin_id}'. Please check Binance Futures symbol."
                )

    except Exception as e:
        logger.exception("An error occurred in handle_message")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"❗ Error in bot:\n{e}")

# Run bot
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
keep_alive()

if __name__ == '__main__':
    print("Bot is running...")
    app.run_polling()
