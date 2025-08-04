
import threading
from flask import Flask
import asyncio
import bot  # يفترض أن bot.py يحتوي على الدالة start_bot أو التشغيل المباشر

# إعداد سيرفر Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "البوت شغال ✔️"

# تشغيل Flask في خيط منفصل
def run_flask():
    app.run(host='0.0.0.0', port=8080)

# تشغيل بوت تيليجرام
def run_bot():
    asyncio.run(bot.main())

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    run_bot()
