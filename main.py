import os
import logging
import sys
import time
import threading
from telebot import types
from bot_instance import bot

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# قائمة المستخدمين (لإرسال رسائل التحديث)
USER_LIST = [
    {"chat_id": 6292405444, "username": "@moheb204", "name": "Moheb 🖤🔱"},
    {"chat_id": 6524548429, "username": "@nour_almansi", "name": "Nour🫀"},
    {"chat_id": 6462342575, "username": None, "name": "يحيى ابو نعمة"},
    {"chat_id": 1364052628, "username": "@jbarat908", "name": "محمد"},
    {"chat_id": 8136273269, "username": None, "name": "A"},
    {"chat_id": 892554801, "username": None, "name": "منى العاجز"},
    {"chat_id": 8062169668, "username": None, "name": "Ss . Ss"},
    {"chat_id": 1114529081, "username": "@Malak_hantash", "name": "𝓶𝓪𝓵𝓪𝓴"},
    {"chat_id": 8154874031, "username": None, "name": "Hala Mwafi"},
    {"chat_id": 466448881, "username": None, "name": "Rasha Ashraf"},
    {"chat_id": 5960984359, "username": None, "name": "𓂐『 𝒊𝒕’𝒔 ⌯D𝙾𝚞𝙷𝙰 𝚂𝙰𝚈𝙴𝙴𝙳 𝙰𝙷𝙼𝙰𝙳』♱..࿅ 𓈪"},
    {"chat_id": 2060193932, "username": "@Ha04d", "name": "Hamed Hamada"},
    {"chat_id": 5542428772, "username": "@momo_mr7", "name": "momo♡⁠♡"},
    {"chat_id": 1638266350, "username": None, "name": "Bhaa Hrebat"},
    {"chat_id": 8016302252, "username": "@abo_whwus", "name": "Abod Amr"},
    {"chat_id": 2022661945, "username": None, "name": "لؤي درابيع"},
    {"chat_id": 7864501387, "username": None, "name": "شادي النشوية"},
    {"chat_id": 1962357190, "username": None, "name": "Gada Saleh"},
    {"chat_id": 7159119198, "username": None, "name": "Osayd Amer"},
    {"chat_id": 5229468726, "username": "@ahmad_kassar", "name": "Ahmad Sayarah"},
    {"chat_id": 7384931394, "username": None, "name": "محمد عايد عمرو"},
    {"chat_id": 6168933957, "username": None, "name": "Pal 1710"},
    {"chat_id": 805134098, "username": None, "name": "BOOS"},
    {"chat_id": 6592462064, "username": None, "name": "اسماء سهيل"},
    {"chat_id": 6350785760, "username": None, "name": "Wajd Alotabe"},
    {"chat_id": 2111564767, "username": None, "name": "محمد ❤️🥀"},
    {"chat_id": 7096019126, "username": None, "name": "علي شرحة"},
    {"chat_id": 903858484, "username": "@Abood_jber", "name": "عَبوُدْ ❤️🤍"},
    {"chat_id": 7064463149, "username": None, "name": "(صلاح)🖤"},
    {"chat_id": 7972688199, "username": None, "name": "yamen amjad"},
    {"chat_id": 1145190313, "username": "@doaaahmad553", "name": "doaa ahmad"},
    {"chat_id": 7013143584, "username": None, "name": "m"},
    {"chat_id": 7328824299, "username": None, "name": "Roq Mis"},
    {"chat_id": 7921265217, "username": None, "name": "ODAY"},
    {"chat_id": 5945418878, "username": None, "name": "Hayel Amro"},
    {"chat_id": 6587290235, "username": None, "name": "بنان ابو عبيد"},
    {"chat_id": 6938645185, "username": None, "name": "رنين 🥹🩷"},
    {"chat_id": 6487817066, "username": None, "name": "Shadi Bbb"},
    {"chat_id": 7998443155, "username": None, "name": "Zaina Amro"},
    {"chat_id": 5963156894, "username": None, "name": "qais gh"},
    {"chat_id": 6858176744, "username": None, "name": "Mohamed Abo Hamada"},
    {"chat_id": 5842911171, "username": None, "name": "Roaa Qasem"},
    {"chat_id": 948234118, "username": None, "name": "Roaa Radi"},
    {"chat_id": 5563438183, "username": "@Amar_Amro", "name": "彡صــــيــــاد彡"},
    {"chat_id": 6519091931, "username": None, "name": "Zahraa Sharawi"},
    {"chat_id": 8292920352, "username": None, "name": "..."},
    {"chat_id": 6917948667, "username": None, "name": "Diala𓂆"},
    {"chat_id": 6308552323, "username": None, "name": "🔻المحآرب' ے"},
    {"chat_id": 7456156305, "username": None, "name": "🤏🏼🙄"},
    {"chat_id": 6800862466, "username": None, "name": "✨𝑪𝒍𝒆𝒐𝒑𝒂𝒕𝒓𝒂 ✨"},
    {"chat_id": 5700416962, "username": "@anaa2027", "name": "Ansam Gatasha"},
    {"chat_id": 8078889212, "username": None, "name": "Madleen | مَآدليّن🤍"},
    {"chat_id": 7953952976, "username": None, "name": "Maysa 🤍."},
    {"chat_id": 6014723242, "username": None, "name": "marah darabee"},
    {"chat_id": 7337336058, "username": None, "name": "Amal"},
    {"chat_id": 1851786931, "username": None, "name": "Eᔕᖇᗩᗩ.Y Zozo"}
]

# ========== دوال مساعدة للتشغيل فقط ==========
def test_token():
    """اختبار صحة التوكن"""
    try:
        import requests
        
        BOT_TOKEN = os.getenv("BOT_TOKEN")
        if not BOT_TOKEN:
            logger.error("❌ BOT_TOKEN غير موجود")
            return False
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ التوكن صالح للبوت: @{data['result']['username']}")
            return True
        else:
            logger.error(f"❌ التوكن غير صالح: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطأ في اختبار التوكن: {e}")
        return False

def initialize_components():
    """تهيئة المكونات"""
    try:
        # قاعدة البيانات
        from database import init_db
        init_db()
        logger.info("✅ قاعدة البيانات")
    except Exception as e:
        logger.warning(f"⚠️ قاعدة البيانات: {e}")
    
    try:
        # الجدولة
        from scheduler import start_scheduler
        start_scheduler()
        logger.info("✅ الجدولة")
    except Exception as e:
        logger.warning(f"⚠️ الجدولة: {e}")

# ========== تحميل معالجات bot_users ==========

def load_user_handlers():
    """تحميل معالجات المستخدمين من bot_users"""
    try:
        import bot_users
        
        # استدعاء الدالة التي تسجل جميع المعالجات في bot_users
        bot_users.handle_user_commands()
        logger.info("✅ تم تحميل معالجات المستخدمين (bot_users)")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تحميل معالجات المستخدمين: {e}")
        return False

def load_admin_handlers():
    """تحميل معالجات الأدمن من bot_admin"""
    try:
        import bot_admin
        
        # استدعاء الدالة التي تسجل جميع المعالجات في bot_admin
        bot_admin.handle_admin_commands()
        logger.info("✅ تم تحميل معالجات الأدمن (bot_admin)")
        return True
    except Exception as e:
        logger.warning(f"⚠️ فشل تحميل معالجات الأدمن: {e}")
        return False

# ========== معالجات خاصة للتشغيل ==========

def setup_system_handlers():
    """إعداد المعالجات الخاصة بالتشغيل"""
    
    # 1. الأمر /start
    @bot.message_handler(commands=["start"])
    def cmd_start(message):
        """معالج /start - يعيد توجيه لـ bot_users"""
        try:
            import bot_users
            
            # استدعاء handle_start من bot_users إذا كان موجوداً
            if hasattr(bot_users, 'handle_start'):
                bot_users.handle_start(message)
            else:
                # استخدام القائمة الأساسية
                markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
                markup.add(
                    types.KeyboardButton("👤 تسجيل الدخول"),
                    types.KeyboardButton("📖 الخدمات الأكاديمية"),
                    types.KeyboardButton("📅 التـــقويــم"),
                    types.KeyboardButton("🔗 منصة المواد المشتركة"),
                    types.KeyboardButton("📚 أخرى"),
                    types.KeyboardButton("🚪 تسجيل الخروج")
                )
                
                welcome = """
🎓 *مرحباً بك في UniAcademix BOT*

🔄 *النظام محدّث وجاهز*

👈 اختر زراً للبدء
"""
                bot.send_message(message.chat.id, welcome, parse_mode="Markdown", reply_markup=markup)
                
        except Exception as e:
            logger.error(f"❌ خطأ في /start: {e}")
            bot.send_message(message.chat.id, "🎓 مرحباً! اختر زراً للبدء")

def setup_manual_message_sender():
    """إعداد إرسال الرسائل يدوياً للأدمن فقط"""
    
    @bot.message_handler(func=lambda m: m.text == "📨 إرسال رسالة تحديث" and m.chat.id in [6292405444, 1851786931])
    def handle_send_update_request(message):
        """معالجة طلب إرسال رسالة تحديث"""
        chat_id = message.chat.id
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        confirm_btn = types.InlineKeyboardButton("✅ نعم، أرسل الآن", callback_data="send_update_now")
        preview_btn = types.InlineKeyboardButton("👁️ معاينة الرسالة", callback_data="preview_update_msg")
        cancel_btn = types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_update_msg")
        markup.add(confirm_btn, preview_btn, cancel_btn)
        
        bot.send_message(
            chat_id,
            "⚠️ *إرسال رسالة تحديث لجميع المستخدمين*\n\n"
            f"📊 العدد: *{len(USER_LIST)}* مستخدم\n"
            "⏰ الوقت المتوقع: *2-3 دقائق*\n\n"
            "هل تريد المتابعة؟",
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    # ... (بقية دالة setup_manual_message_sender كما هي)

# ========== الدالة الرئيسية ==========

def main():
    """الدالة الرئيسية"""
    logger.info("=" * 60)
    logger.info("🚀 بدء تشغيل البوت الرئيسي")
    logger.info("=" * 60)
    
    # 1. اختبار التوكن أولاً
    if not test_token():
        logger.error("❌ فشل اختبار التوكن. توقف.")
        sys.exit(1)
    
    # 2. تهيئة المكونات الأساسية
    initialize_components()
    
    # 3. تحميل معالجات المستخدمين
    if not load_user_handlers():
        logger.error("❌ فشل تحميل معالجات المستخدمين. توقف.")
        sys.exit(1)
    
    # 4. تحميل معالجات الأدمن (اختياري)
    load_admin_handlers()
    
    # 5. إعداد المعالجات الخاصة بالتشغيل
    setup_system_handlers()
    
    # 6. إعداد إرسال الرسائل يدوياً (للأدمن فقط)
    setup_manual_message_sender()
    
    # 7. تشغيل البوت
    try:
        logger.info("🔄 بدء استقبال الرسائل...")
        bot.remove_webhook()
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"❌ توقف البوت: {e}")

if __name__ == '__main__':
    main()
