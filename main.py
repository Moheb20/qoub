import os
import logging
import sys
from bot_instance import bot

# تعطيل أي بوت آخر
os.environ['DISABLE_OTHER_BOTS'] = 'true'

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_token():
    """اختبار صحة التوكن"""
    try:
        import requests
        
        BOT_TOKEN = os.getenv("BOT_TOKEN")
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN غير موجود")
            return False
        
        # اختبار مباشر مع Telegram API
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ التوكن صالح للبوت: @{data['result']['username']}")
            return True
        else:
            logger.error(f"❌ التوكن غير صالح: {response.status_code}")
            logger.error(f"الرسالة: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطأ في اختبار التوكن: {e}")
        return False

def initialize_components():
    """تهيئة المكونات"""
    try:
        # قاعدة البيانات
        from database import init_db, get_all_users
        init_db()
        get_all_users()
        logger.info("✅ قاعدة البيانات")
    except Exception as e:
        logger.warning(f"⚠️ قاعدة البيانات: {e}")
    
    try:
        # الجدولة (بدون بوت الاقتراحات)
        from scheduler import start_scheduler
        start_scheduler()
        logger.info("✅ الجدولة")
    except Exception as e:
        logger.warning(f"⚠️ الجدولة: {e}")

def register_handlers():
    """تسجيل معالجات البوت"""
    # 1. الأمر /start
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        try:
            from bot_users import handle_start
            handle_start(message)
        except Exception as e:
            logger.error(f"❌ خطأ في /start: {e}")
            bot.reply_to(message, "👋 مرحباً! حدث خطأ.")
    
    # 2. معالجات الأدمن
    try:
        from bot_admin import handle_admin_commands
        handle_admin_commands()
        logger.info("✅ معالجات الأدمن")
    except Exception as e:
        logger.warning(f"⚠️ معالجات الأدمن: {e}")
    
    # 3. معالجات المستخدمين
    try:
        from bot_users import handle_user_commands
        handle_user_commands()
        logger.info("✅ معالجات المستخدمين")
    except Exception as e:
        logger.error(f"❌ معالجات المستخدمين: {e}")
        return False
    
    # 4. المعالج النهائي
    @bot.message_handler(func=lambda message: True)
    def all_messages(message):
        try:
            from bot_users import handle_all_messages
            handle_all_messages(message)
        except Exception as e:
            logger.error(f"❌ خطأ في الرسالة: {e}")
            bot.reply_to(message, "📝 اختر زراً من القائمة")
    
    return True

def main():
    """الدالة الرئيسية"""
    logger.info("=" * 50)
    logger.info("🚀 بدء تشغيل البوت الرئيسي")
    logger.info("=" * 50)
    
    # 1. اختبار التوكن أولاً
    if not test_token():
        logger.error("❌ فشل اختبار التوكن. توقف.")
        sys.exit(1)
    
    # 2. تهيئة المكونات
    initialize_components()
    
    # 3. تسجيل المعالجات
    if not register_handlers():
        logger.error("❌ فشل تسجيل المعالجات. توقف.")
        sys.exit(1)
    
    # 4. تشغيل البوت
    try:
        logger.info("🔄 بدء استقبال الرسائل...")
        bot.remove_webhook()  # تأكد من إزالة Webhook
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"❌ توقف البوت: {e}")

if __name__ == '__main__':
    main()
