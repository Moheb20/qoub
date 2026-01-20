import os
import logging
from flask import Flask, request
from bot_instance import bot
import telebot
from waitress import serve

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# المتغيرات البيئية
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

@app.route('/')
def home():
    return "✅ البوت يعمل بنجاح! 🚀"

@app.route('/health')
def health_check():
    return "🟢 البوت يعمل بشكل طبيعي", 200

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    """Webhook endpoint for Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    else:
        return 'Bad Request', 400

def setup_bot_handlers():
    """إعداد جميع معالجات البوت في مكان واحد"""
    
    # معالج الأمر /start
    @bot.message_handler(commands=["start"])
    def handle_start(message):
        # استيراد الدالة من bot_users أو كتابتها هنا
        try:
            from bot_users import handle_start as user_start
            user_start(message)
        except ImportError:
            # نسخة بديلة
            chat_id = message.chat.id
            username = message.from_user.username or "بدون اسم مستخدم"
            bot.send_message(chat_id, f"👋 مرحباً {username}!")
    
    # معالجات أخرى...
    # يمكنك استيرادها أو كتابتها هنا
    
    # المعالج النهائي للرسائل
    @bot.message_handler(func=lambda message: True)
    def handle_all_messages(message):
        chat_id = message.chat.id
        text = (message.text or "").strip()
        
        # حاول استيراد معالج الرسائل من bot_users
        try:
            from bot_users import handle_main_message_flow
            handle_main_message_flow(chat_id, text)
        except ImportError:
            # رد بديل
            bot.reply_to(message, "📝 اختر زراً من القائمة أدناه")

def initialize_bot():
    """تهيئة البوت"""
    try:
        # فحص التوكن
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN غير موجود في البيئة")
            return False
        
        # اختبار البوت
        bot_info = bot.get_me()
        logger.info(f"✅ البوت جاهز: @{bot_info.username}")
        
        # استيراد وتهيئة المكونات
        try:
            from database import init_db, get_all_users
            from scheduler import start_scheduler
            
            init_db()
            get_all_users()
            start_scheduler()
            logger.info("✅ تم تهيئة قاعدة البيانات والجدولة")
        except ImportError as e:
            logger.warning(f"⚠️ بعض المكونات غير متوفرة: {e}")
        
        # إعداد معالجات البوت
        setup_bot_handlers()
        logger.info("✅ تم إعداد معالجات البوت")
        
        return True
    except Exception as e:
        logger.error(f"❌ فشل تهيئة البوت: {e}")
        return False

if __name__ == '__main__':
    logger.info(f"🚀 بدء تشغيل البوت على المنفذ {PORT}...")
    
    # تهيئة البوت
    if initialize_bot():
        # إذا كان هناك WEBHOOK_URL، استخدم Webhook
        if WEBHOOK_URL:
            logger.info(f"🌐 استخدام Webhook: {WEBHOOK_URL}")
            
            try:
                bot.remove_webhook()
                logger.info("✅ تم حذف Webhook السابق")
                
                webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
                bot.set_webhook(url=webhook_url)
                logger.info(f"✅ تم تعيين Webhook: {webhook_url}")
            except Exception as e:
                logger.error(f"❌ فشل إعداد Webhook: {e}")
            
            logger.info(f"🌍 تشغيل Flask على المنفذ {PORT}")
            serve(app, host='0.0.0.0', port=PORT)
        else:
            logger.info("🔄 استخدام Polling المباشر")
            bot.remove_webhook()
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
    else:
        logger.error("❌ فشل تشغيل البوت")
