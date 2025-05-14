import re
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

from keep_alive import keep_alive
import os
TOKEN = os.getenv("TOKEN")


# Fetch price from binance

def get_price(symbol):
            binance_symbol = symbol.upper() + "USDT"
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={binance_symbol}"
            try:
                response = requests.get(url)
                data = response.json()
                return float(data['price']) if 'price' in data else None
            except:
                return None


# Handle Telegram messages
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
                    # Calculate TP levels (percentage above current market price)
                    tp1_price = price * 1.05  # 5% above current price
                    tp2_price = price * 1.10  # 10% above current price
                    tp3_price = price * 1.20  # 20% above current price
                    tp4_price = price * 1.40  # 40% above current price
                    tp5_price = price * 1.60  # 60% above current price
                    tp6_price = price * 1.80  # 80% above current price
                    tp7_price = price * 2.00  # 100% above current price
                    # Calculate stoploss (40% below current market price)
                    stoploss_price = price * 0.70  # 30% below current price
                    use_whole_numbers = False
                    

                # Define leverage options
                leverage = "2x-5x"
                symbol_pair = f"{coin_id.upper()}/USDT"
                # Format the message with entry, stoploss, TP levels, and leverage
                if coin_id.lower() in ["btc", "eth"]:
                    format_price = lambda p: f"{int(p)}"
                else:
                    format_price = lambda p: f"{p:.4f}"
                response_message = (f"Spot + Future Long\n"
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
                                    f"For Premium contact @shsAdmin")

                # send to the user
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=response_message
                )

                # also send to the channel
                await context.bot.send_message(
                    chat_id='-1001541449446',  # or use the channel ID
                    text=response_message
                )

        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"⚠️ Could not fetch price for '{coin_id}'. Please check binance ID."
            )


    # Start the Flask keep-alive server
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
keep_alive()
# Direct entry point (no asyncio.run)
if __name__ == '__main__':
    print("Bot is running...")
    app.run_polling()  # ✅ Let it manage its own event loop in
