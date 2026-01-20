import os
from dotenv import load_dotenv
from flask import Flask
from bot_instance import bot
import logging

# استيراد الملفات المقسمة
from bot_admin import handle_admin_commands
from bot_users import handle_user_commands, handle_all_messages
from database import init_db, get_all_users
from scheduler import start_scheduler

load_dotenv()

logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ البوت يعمل بنجاح!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def check_bot_token():
    """فحص صحة التوكن"""
    try:
        token = os.getenv("BOT_TOKEN")
        if not token:
            logger.error("❌ BOT_TOKEN غير موجود في ملف .env")
            return False
            
        # اختبار بسيط للتوكن
        from telebot.apihelper import ApiTelegramException
        try:
            bot.get_me()
            logger.info("✅ التوكن صالح")
            return True
        except ApiTelegramException as e:
            logger.error(f"❌ التوكن غير صالح: {e}")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطأ في فحص التوكن: {e}")
        return False

def setup_webhook():
    """إعداد Webhook (اختياري)"""
    try:
        import requests
        token = os.getenv("BOT_TOKEN")
        webhook_url = os.getenv("WEBHOOK_URL")
        
        if webhook_url:
            # حذف أي Webhook موجود
            delete_url = f"https://api.telegram.org/bot{token}/deleteWebhook"
            response = requests.post(delete_url, timeout=5)
            if response.status_code == 200:
                logger.info("✅ تم حذف Webhook السابق")
            
            # تعيين Webhook جديد
            set_url = f"https://api.telegram.org/bot{token}/setWebhook?url={webhook_url}"
            response = requests.post(set_url, timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ تم تعيين Webhook: {webhook_url}")
            else:
                logger.warning("⚠️ لم يتم تعيين Webhook، سيتم استخدام Polling")
    except Exception as e:
        logger.warning(f"⚠️ لم يتم إعداد Webhook: {e}")

if __name__ == "__main__":
    # تهيئة السجل
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🚀 بدء تشغيل البوت...")
    
    # فحص التوكن أولاً
    if not check_bot_token():
        logger.error("❌ فشل تشغيل البوت بسبب التوكن غير الصالح")
        exit(1)
    
    # تهيئة قاعدة البيانات والجدولة
    init_db()
    get_all_users()
    start_scheduler()
    
    # إعداد Webhook (اختياري)
    setup_webhook()
    
    # تسجيل معالجات الأدمن
    handle_admin_commands()
    
    # تسجيل معالجات المستخدمين
    handle_user_commands()
    
    # تسجيل معالج الرسائل العام
    @bot.message_handler(func=lambda message: True)
    def final_handler(message):
        handle_all_messages(message)
    
    # تشغيل البوت باستخدام Polling
    logger.info("🔄 بدء Polling...")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"❌ توقف البوت: {e}")
