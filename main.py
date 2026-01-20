import os
from dotenv import load_dotenv
from flask import Flask
from telebot import types
from bot_instance import bot

# استيراد الملفات المقسمة
from bot_admin import handle_admin_commands
from bot_users import handle_user_commands, handle_all_messages
from database import init_db, get_all_users
from scheduler import start_scheduler

load_dotenv()

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ البوت يعمل بنجاح!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    # تهيئة قاعدة البيانات والجدولة
    init_db()
    get_all_users()
    start_scheduler()
    
    # تسجيل معالجات الأدمن
    handle_admin_commands()
    
    # تسجيل معالجات المستخدمين
    handle_user_commands()
    
    # تسجيل معالج الرسائل العام
    @bot.message_handler(func=lambda message: True)
    def final_handler(message):
        handle_all_messages(message)
    
    # تأكد من حذف Webhook
    try:
        import requests
        token = os.getenv("BOT_TOKEN")
        requests.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
    except:
        pass
    
    # ابدأ البوت
    print("Starting bot...")
    bot.infinity_polling()
