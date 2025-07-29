import re
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

ADMIN_CHAT_ID = 'your_admin_chat_id_here'  # Replace with your admin ID

cancel_keywords = r'\b(close|closed|closing|stopped out|stop loss|cut loss|hit sl|booking profit|booked profit|secured profit|secured gains|closed in profit|sl)\b'

def extract_coin_list(text: str):
    return re.findall(r'#([a-z0-9\-]+)', text, re.IGNORECASE)

def has_profit_value(text: str):
    return bool(re.search(r'[\+\-]?\d{1,4}[%x]', text))

def get_action_type(text: str):
    if 'short_at_cmp' in text.lower():
        return 'Short'
    elif 'buy_at_cmp' in text.lower():
        return 'Buy'
    return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        text_lower = text.lower()

        # If no hashtags, ignore
        if not re.search(r'#([a-z0-9\-]+)', text, re.IGNORECASE):
            return

        # Extract all coins
        all_coin_matches = extract_coin_list(text)

        # ✅ Cancel coins with SL-related keywords, not profit-related
        cancel_coins = set()

        sl_patterns = [
            r'#([a-z0-9\-]+)[^\n#]{0,20}\b(hit\s+sl|sl\s+hit|hit\s+stoploss|stopped\s+out|sl|stop\s+loss)\b',
            r'\b(hit\s+sl|sl\s+hit|hit\s+stoploss|stopped\s+out|sl|stop\s+loss)\b[^\n#]{0,20}#([a-z0-9\-]+)'
        ]

        for pattern in sl_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                for group in match:
                    if group.startswith("#"):
                        cancel_coins.add(group.replace("#", "").upper())
                    elif re.match(r'[a-z0-9\-]+', group, re.IGNORECASE):
                        cancel_coins.add(group.upper())

        if cancel_coins:
            for coin in sorted(cancel_coins):
                message = f"Cancel {coin}/USDT"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
            return

        # ✅ Handle Re-open setups logic
        if 're-open' in text_lower and get_action_type(text):
            reopen_coins = all_coin_matches
            action = get_action_type(text)
            for coin in sorted(set(reopen_coins)):
                message = f"{action} {coin.upper()}/USDT"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
            return

        # ✅ Still holding — skip sending new trade for those coins
        holding_coins = []
        if 'still holding' in text_lower:
            holding_coins = re.findall(r'still holding\s+#([a-z0-9\-]+)', text, re.IGNORECASE)

        # ✅ Handle new signals normally (Buy_at_CMP, Short_at_CMP)
        action = get_action_type(text)
        if action and all_coin_matches:
            for coin in sorted(set(all_coin_matches)):
                if coin.lower() in [c.lower() for c in holding_coins]:
                    continue  # skip coins still holding
                message = f"{action} {coin.upper()}/USDT"
                await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)

    except Exception as e:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=f"⚠️ Bot error: {str(e)}")

# --- Bot Setup ---
app = ApplicationBuilder().token("YOUR_BOT_TOKEN").build()  # Replace with your bot token
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
