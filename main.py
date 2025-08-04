import asyncio
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler

TOKEN = "8346251354:AAH3LqivEvbh-DaLmjViyN_ICzlTYb6W1ZM"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"https://qoub.onrender.com{WEBHOOK_PATH}"  # عدله لرابط موقعك على Render

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# أوامر البوت
async def start(update: Update, context):
    await update.message.reply_text("✅ بوتك شغال بنجاح على Render و PTB 20.3!")

# تسجيل الأوامر
application.add_handler(CommandHandler("start", start))

# نقطة استقبال التحديثات من تيليجرام
@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook():
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, application.bot)
    await application.process_update(update)
    return "ok", 200

# الصفحة الرئيسية
@app.route("/")
def home():
    return "✅ البوت شغال"

# بدء التطبيق وتشغيل Webhook
if __name__ == "__main__":
    async def run():
        await application.initialize()
        await application.bot.set_webhook(WEBHOOK_URL)
        app.run(host="0.0.0.0", port=10000)  # أو 8080

    asyncio.run(run())
