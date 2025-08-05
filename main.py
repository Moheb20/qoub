import threading
import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8346251354:AAH3LqivEvbh-DaLmjViyN_ICzlTYb6W1ZM"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"https://qoub.onrender.com{WEBHOOK_PATH}"

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ البوت شغال على Render!")

application.add_handler(CommandHandler("start", start))

# نقطة استلام التحديثات
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, application.bot)
    asyncio.run(application.process_update(update))  # ✅ هذا هو التعديل
    return "ok", 200

@app.route("/")
def home():
    return "✅ البوت يعمل ✔️"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

async def run_bot():
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    await application.start()
    print("🔗 Webhook set and bot started!")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(run_bot())
