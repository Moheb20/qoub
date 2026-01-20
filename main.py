import os
import logging
from bot_instance import bot

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# المتغيرات البيئية
BOT_TOKEN = os.getenv("BOT_TOKEN")

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    logger.info("🚀 بدء تشغيل البوت...")
    
    # فحص التوكن
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN غير موجود في البيئة")
        return
    
    try:
        # اختبار البوت
        bot_info = bot.get_me()
        logger.info(f"✅ البوت جاهز: @{bot_info.username}")
        
        # تهيئة قاعدة البيانات
        try:
            from database import init_db, get_all_users
            init_db()
            get_all_users()
            logger.info("✅ تم تهيئة قاعدة البيانات")
        except Exception as e:
            logger.warning(f"⚠️ قاعدة البيانات: {e}")
        
        # بدء الجدولة
        try:
            from scheduler import start_scheduler
            start_scheduler()
            logger.info("✅ تم بدء الجدولة")
        except Exception as e:
            logger.warning(f"⚠️ الجدولة: {e}")
        
        # تسجيل معالجات الأدمن
        try:
            from bot_admin import handle_admin_commands
            handle_admin_commands()
            logger.info("✅ تم تحميل معالجات الأدمن")
        except Exception as e:
            logger.warning(f"⚠️ معالجات الأدمن: {e}")
        
        # تسجيل معالجات المستخدمين
        try:
            from bot_users import handle_user_commands
            handle_user_commands()
            logger.info("✅ تم تحميل معالجات المستخدمين")
        except Exception as e:
            logger.error(f"❌ معالجات المستخدمين: {e}")
            return
        
        # المعالج النهائي للرسائل
        @bot.message_handler(func=lambda message: True)
        def handle_all_messages(message):
            try:
                from bot_users import handle_all_messages as user_handler
                user_handler(message)
            except ImportError as e:
                logger.error(f"❌ خطأ في معالجة الرسالة: {e}")
                bot.reply_to(message, "⚠️ حدث خطأ، جرب لاحقاً")
        
        # تشغيل البوت
        logger.info("🔄 بدء استقبال الرسائل...")
        bot.remove_webhook()  # تأكد من إزالة أي Webhook
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        logger.error(f"❌ توقف البوت: {e}")

if __name__ == '__main__':
    main()
