from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher
import bot  # هذا ملف bot.py

# ✅ توكن البوت (رجاءً غيّره لاحقًا لحمايتك)
TOKEN = "8346251354:AAH3LqivEvbh-DaLmjViyN_ICzlTYb6W1ZM"

bot_instance = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot_instance, None, workers=0)

# تسجيل الهاندلرز من ملف bot.py
bot.register_handlers(dispatcher)

# نقطة استلام التحديثات من Telegram
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_instance)
    dispatcher.process_update(update)
    return "ok", 200

# صفحة اختبار
@app.route("/")
def home():
    return "✅ البوت شغال على Render!", 200

if __name__ == "__main__":
    app.run(port=5000)
