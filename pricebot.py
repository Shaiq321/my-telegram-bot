import re
import requests
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from keep_alive import keep_alive
import os

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# === Logging ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === Binance Futures price fetcher ===
def get_price(symbol):
    """
    Try to fetch CMP from Binance Futures for <SYMBOL>USDT.
    If not found, try 1000<SYMBOL>USDT.
    Returns: (price_float, resolved_symbol) or (None, None)
    """
    try:
        base = symbol.upper()
        for candidate in (f"{base}USDT", f"1000{base}USDT"):
            url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={candidate}"
            r = requests.get(url, timeout=5)
            data = r.json()
            if isinstance(data, dict) and 'price' in data:
                return float(data['price']), candidate
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
    return None, None

def format_price_custom(price: float) -> str:
    """
    Keep up to 5 significant non-zero decimals after the first non-zero.
    """
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

# === Main handler ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message or not update.message.text:
            return

        raw_text = update.message.text.strip()
        text = raw_text.lower()

        # Basic extractions
        coin_matches = re.findall(r'#([a-z0-9\-]+)', text, re.IGNORECASE)
        still_holding = set(re.findall(r'still holding\s+#([a-z0-9\-]+)', text, re.IGNORECASE))
        # kept for compatibility with your previous logic (not used directly)
        _profit_keywords = re.findall(r'\+\d+%|\bclosed in profit\b|\bbooked\b|\bsecured\b', text)
        cancel_loss_keywords = r'\bstopped out\b|\bhit sl\b|\bsl\b|\bstop loss\b|\binvalidated\b'

        # --- Cancel by coin with loss only ---
        if re.search(cancel_loss_keywords, text) and coin_matches:
            for coin in sorted(set(coin_matches)):
                if coin.lower() in still_holding:
                    continue
                # don't cancel if the same coin is clearly mentioned with profit
                if not re.search(rf'{coin}\s.*(\+\d+%|\bclosed in profit\b|\bbooked\b|\bsecured\b)', text, re.IGNORECASE):
                    coin_upper = coin.upper()
                    message = f"Cancel {coin_upper}/USDT"
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
                    await context.bot.send_message(chat_id='-1001541449446', text=message)

        # --- Global short close ---
        if "shorts should be closed" in text:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Cancel All Short Trades")
            await context.bot.send_message(chat_id='-1001541449446', text="Cancel All Short Trades")
            return

        # --- Detect Long & Short signals ---
        # Long: "#COIN buy_at_cmp" | "buy_at_cmp #COIN" | "#COIN buy_at: <price>"
        long_matches = re.findall(
            r'#([a-z0-9\-]+)\s+buy[_\s]?at[_\s]?cmp'
            r'|buy[_\s]?at[_\s]?cmp\s+#([a-z0-9\-]+)'
            r'|#([a-z0-9\-]+)\s+buy[_\s]?at\s*[:=]?\s*([0-9]*\.?[0-9]+)',
            text, re.IGNORECASE
        )

        # Short: "#COIN short_at_cmp" | "short_at_cmp #COIN" | "#COIN short_at: <price>"
        short_matches = re.findall(
            r'#([a-z0-9\-]+)\s+short[_\s]?at[_\s]?cmp'
            r'|short[_\s]?at[_\s]?cmp\s+#([a-z0-9\-]+)'
            r'|#([a-z0-9\-]+)\s+short[_\s]?at\s*[:=]?\s*([0-9]*\.?[0-9]+)',
            text, re.IGNORECASE
        )

        signals = []

        # Process long signals
        for m in long_matches:
            # m is a 4-tuple due to the 3 alternations
            coin = (m[0] or m[1] or m[2] or "").strip()
            entry_price = (m[3] if len(m) > 3 and m[3] else None)
            if coin:
                signals.append((coin, False, entry_price))  # False = Long

        # Process short signals
        for m in short_matches:
            coin = (m[0] or m[1] or m[2] or "").strip()
            entry_price = (m[3] if len(m) > 3 and m[3] else None)
            if coin:
                signals.append((coin, True, entry_price))   # True = Short

        # --- Reopen support (kept as in your code) ---
        is_reopen = 're-open' in text
        if is_reopen:
            reopen_coins = re.findall(r'#([a-z0-9\-]+)', text, re.IGNORECASE)
            is_short = 'short_at_cmp' in text
            for coin in reopen_coins:
                if coin.lower() not in [s[0].lower() for s in signals]:
                    signals.append((coin, is_short, None))

        # --- Build and send signals ---
        for coin_id, is_short, entry_price in signals:
            if coin_id.lower() in still_holding:
                continue

            coin_lower = coin_id.lower()
            use_manual = entry_price is not None

            if use_manual:
                # Manual entry: DO NOT call Binance at all (works even if network is blocked / coin doesn't exist on Futures)
                price = float(entry_price)
                symbol_pair = f"{coin_id.upper()}/USDT"
            else:
                # CMP entry: fetch from Binance
                price, actual_symbol = get_price(coin_id)
                if not price:
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=f"⚠️ Could not fetch price for '{coin_id}'. Please check Binance Futures symbol."
                    )
                    continue
                # Display resolved symbol (e.g., 1000PEPE → 1000PEPE/USDT)
                symbol_pair = f"{actual_symbol.replace('USDT', '')}/USDT" if actual_symbol else f"{coin_id.upper()}/USDT"

            # Amount per trade
            if coin_lower in ["btc", "eth", "ltc", "link", "sol"]:
                amount_line = "Amount per trade : 2%"
            else:
                amount_line = "Amount per trade : 1%"

            # TP/SL logic (unchanged; scales from 'price' whether manual or CMP)
            if coin_lower == "btc":
                tp_factors = [0.982, 0.962, 0.922, 0.902, 0.852, 0.802, 0.702] if is_short else [1.018, 1.038, 1.078, 1.098, 1.148, 1.198, 1.298]
                stoploss_price = price * (1.10 if is_short else 0.90)
                use_whole = True
            elif coin_lower == "eth":
                tp_factors = [0.955, 0.905, 0.855, 0.805, 0.755, 0.705, 0.655] if is_short else [1.045, 1.095, 1.145, 1.195, 1.245, 1.295, 1.395]
                stoploss_price = price * (1.15 if is_short else 0.85)
                use_whole = True
            else:
                tp_factors = [0.955, 0.905, 0.805, 0.605, 0.405, 0.205, 0.105] if is_short else [1.045, 1.095, 1.195, 1.395, 1.595, 1.795, 1.995]
                stoploss_price = price * (1.30 if is_short else 0.70)
                use_whole = False

            tp_prices = [price * f for f in tp_factors]
            leverage = "20x"
            fmt = (lambda p: f"{int(p)}") if use_whole else format_price_custom

            response_message = (
                f"Future {'Short' if is_short else 'Long + Spot'}\n\n"
                f"{symbol_pair}\n\n"
                f"Entry: {fmt(price)}\n\n" +
                "\n".join([f"TP{i+1}: {fmt(tp)}" for i, tp in enumerate(tp_prices)]) + "\n\n" +
                f"Stoploss: {fmt(stoploss_price)}\n\n"
                f"Leverage : {leverage} [cross]\n"
                f"{amount_line}\n\n"
                f"@shsAdmin"
            )

            await context.bot.send_message(chat_id=update.effective_chat.id, text=response_message)
            await context.bot.send_message(chat_id='-1001541449446', text=response_message)

    except Exception as e:
        logger.exception("An error occurred in handle_message")
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"❗ Error in bot:\n{e}\n\nMessage was:\n{update.message.text if update and update.message else 'N/A'}")

# === Run bot ===
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
keep_alive()

if __name__ == '__main__':
    print("Bot is running...")
    app.run_polling()
