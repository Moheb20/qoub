import os
import logging
import sys
import time
import threading
from bot_instance import bot
from telebot import types

# تعطيل أي بوت آخر
os.environ['DISABLE_OTHER_BOTS'] = 'true'

# إعداد السجل
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# قائمة المستخدمين
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

def fix_old_passwords():
    """إصلاح كلمات المرور القديمة المشفرة"""
    try:
        from database import get_conn
        
        conn = get_conn()
        if not conn:
            logger.warning("⚠️ لا يمكن الاتصال بقاعدة البيانات")
            return False
        
        with conn.cursor() as cursor:
            # البحث عن المستخدمين بكلمات مرور قديمة
            cursor.execute("""
                SELECT chat_id, password 
                FROM users 
                WHERE password LIKE 'gAAAAAB%'
            """)
            old_passwords = cursor.fetchall()
            
            if old_passwords:
                logger.warning(f"⚠️ يوجد {len(old_passwords)} مستخدم بكلمات مرور قديمة")
                
                # تعيين كلمات مرور فارغة
                for chat_id, password in old_passwords:
                    try:
                        cursor.execute(
                            "UPDATE users SET password = '' WHERE chat_id = %s",
                            (chat_id,)
                        )
                        logger.info(f"🔄 أعدت تعيين كلمة مرور للمستخدم: {chat_id}")
                    except Exception as e:
                        logger.error(f"❌ خطأ في تحديث المستخدم {chat_id}: {e}")
                
                conn.commit()
                logger.info(f"✅ تم إصلاح {len(old_passwords)} مستخدم")
                
                # إرسال إشعار للمستخدمين المتأثرين
                send_password_reset_notification([user[0] for user in old_passwords])
                
                return True
            else:
                logger.info("✅ لا توجد كلمات مرور قديمة")
                return True
                
    except Exception as e:
        logger.error(f"❌ فشل إصلاح كلمات المرور: {e}")
        return False

def send_password_reset_notification(user_ids):
    """إرسال إشعار للمستخدمين الذين تمت إعادة تعيين كلمات مرورهم"""
    if not user_ids:
        return
    
    logger.info(f"📨 جاري إعداد إشعارات لـ {len(user_ids)} مستخدم")
    
    message = """
🔐 *تنبيه مهم - تحديث النظام*

عزيزي الطالب/الطالبة،

لقد قمنا بتحديث نظام الأمان في البوت لتحسين الحماية والأداء.

⚠️ *ما عليك فعله:*
1. اختر زر *"👤 تسجيل الدخول"* من القائمة الرئيسية
2. أدخل *رقمك الجامعي* وكلمة المرور كالمعتاد
3. ستتمكن من استخدام جميع الخدمات فوراً

🔄 *ملاحظة:*
- بياناتك آمنة ولم يتم مسحها
- الإعدادات الشخصية محفوظة
- الخدمات ستعمل بشكل أفضل بعد التسجيل

شكراً لتفهمك ودعمك،  
فريق *UniAcademix BOT*
"""
    
    sent_count = 0
    for chat_id in user_ids:
        try:
            bot.send_message(chat_id, message, parse_mode="Markdown")
            sent_count += 1
            time.sleep(0.2)
        except:
            pass
    
    logger.info(f"✅ تم إرسال إشعارات إلى {sent_count} من {len(user_ids)} مستخدم")

def send_message_to_all_users():
    """إرسال رسالة لجميع المستخدمين في القائمة"""
    logger.info("=" * 60)
    logger.info(f"📤 جاري إعداد إرسال رسالة إلى {len(USER_LIST)} مستخدم")
    logger.info("=" * 60)
    
    message_text = """
🎓 *رسالة مهمة من فريق دعم UniAcademix BOT*

عزيزي الطالب/الطالبة،

نود إعلامك أننا قمنا *بتحديث نظام البوت* لتحسين الأمان والأداء.

⚠️ *ما عليك فعله:*
1. اختر زر *"👤 تسجيل الدخول"* من القائمة الرئيسية
2. أدخل *رقمك الجامعي* وكلمة المرور كما كنت تفعل سابقاً
3. بعد التسجيل، ستستعيد جميع خدماتك السابقة

🔄 *ملاحظة:*
- سيتم تحديث جميع بياناتك تلقائياً
- لن تفقد أي من سجلاتك أو إعداداتك
- الخدمات ستكون أسرع وأكثر استقراراً
- ستكون هذه الفترة مخصصة لتحديث البوت وتطويرهه

🙏 نعتذر للإزعاج ونشكرك على تفهمك.

📞 للاستفسارات: يمكنك التواصل مع الدعم الفني.

مع أطيب التمنيات،  
فريق دعم * UniAcademix BOT *
"""
    
    success_count = 0
    failed_count = 0
    failed_users = []
    
    for user in USER_LIST:
        chat_id = user["chat_id"]
        username = user["username"] or "بدون اسم"
        name = user["name"]
        
        try:
            bot.send_message(
                chat_id,
                message_text,
                parse_mode="Markdown"
            )
            
            success_count += 1
            logger.info(f"✅ أرسلت إلى {name} ({username}) - ID: {chat_id}")
            
            time.sleep(0.3)
            
        except Exception as e:
            failed_count += 1
            failed_users.append({
                "chat_id": chat_id,
                "name": name,
                "username": username,
                "error": str(e)
            })
            logger.error(f"❌ فشل الإرسال إلى {name} ({username}): {e}")
    
    logger.info("=" * 60)
    logger.info("📊 *نتائج الإرسال:*")
    logger.info(f"✅ النجاح: {success_count}")
    logger.info(f"❌ الفشل: {failed_count}")
    logger.info("=" * 60)
    
    return success_count, failed_count

def setup_manual_message_sender():
    """إعداد إرسال الرسائل يدوياً للأدمن"""
    
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
    
    @bot.callback_query_handler(func=lambda call: call.data == "preview_update_msg")
    def preview_update_message(call):
        """معاينة الرسالة قبل الإرسال"""
        chat_id = call.message.chat.id
        
        message_text = """
🎓 *رسالة مهمة من فريق دعم UniAcademix BOT*

عزيزي الطالب/الطالبة،

نود إعلامك أننا قمنا *بتحديث نظام البوت* لتحسين الأمان والأداء.

⚠️ *ما عليك فعله:*
1. اختر زر *"👤 تسجيل الدخول"* من القائمة الرئيسية
2. أدخل *رقمك الجامعي* وكلمة المرور كما كنت تفعل سابقاً
3. بعد التسجيل، ستستعيد جميع خدماتك السابقة

🔄 *ملاحظة:*
- سيتم تحديث جميع بياناتك تلقائياً
- لن تفقد أي من سجلاتك أو إعداداتك
- الخدمات ستكون أسرع وأكثر استقراراً
- ستكون هذه الفترة مخصصة لتحديث البوت وتطويرهه

🙏 نعتذر للإزعاج ونشكرك على تفهمك.

📞 للاستفسارات: يمكنك التواصل مع الدعم الفني.

مع أطيب التمنيات،  
فريق دعم * UniAcademix BOT *
"""
        
        markup = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("↩️ العودة للخيارات", callback_data="back_to_options")
        markup.add(back_btn)
        
        bot.edit_message_text(
            "📝 *معاينة الرسالة:*\n\n" + message_text,
            chat_id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "back_to_options")
    def back_to_options(call):
        """العودة لخيارات الإرسال"""
        chat_id = call.message.chat.id
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        confirm_btn = types.InlineKeyboardButton("✅ نعم، أرسل الآن", callback_data="send_update_now")
        preview_btn = types.InlineKeyboardButton("👁️ معاينة الرسالة", callback_data="preview_update_msg")
        cancel_btn = types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_update_msg")
        markup.add(confirm_btn, preview_btn, cancel_btn)
        
        bot.edit_message_text(
            "⚠️ *إرسال رسالة تحديث لجميع المستخدمين*\n\n"
            f"📊 العدد: *{len(USER_LIST)}* مستخدم\n"
            "⏰ الوقت المتوقع: *2-3 دقائق*\n\n"
            "هل تريد المتابعة؟",
            chat_id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    @bot.callback_query_handler(func=lambda call: call.data == "send_update_now")
    def send_update_confirmed(call):
        """بدء إرسال الرسائل بعد التأكيد"""
        chat_id = call.message.chat.id
        
        bot.edit_message_text(
            "🔄 *جاري إرسال الرسائل...*\n\n"
            "⏳ الرجاء الانتظار، هذه العملية قد تستغرق بضع دقائق.",
            chat_id,
            call.message.message_id,
            parse_mode="Markdown"
        )
        
        def send_messages_thread():
            try:
                success_count, failed_count = send_message_to_all_users()
                
                report = f"""
✅ *تم الانتهاء من إرسال الرسائل*

📊 *النتائج النهائية:*
• ✅ النجاح: {success_count}
• ❌ الفشل: {failed_count}
• 📈 نسبة النجاح: {(success_count/len(USER_LIST))*100:.1f}%

👥 *التفاصيل:*
• تم إرسال الرسالة إلى {success_count} مستخدم
• فشل الإرسال إلى {failed_count} مستخدم
• المجموع: {len(USER_LIST)} مستخدم
"""
                
                bot.send_message(
                    chat_id,
                    report,
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                bot.send_message(
                    chat_id,
                    f"❌ *حدث خطأ أثناء الإرسال:*\n{str(e)}",
                    parse_mode="Markdown"
                )
        
        thread = threading.Thread(target=send_messages_thread)
        thread.start()
    
    @bot.callback_query_handler(func=lambda call: call.data == "cancel_update_msg")
    def cancel_update_message(call):
        """إلغاء عملية الإرسال"""
        chat_id = call.message.chat.id
        
        bot.edit_message_text(
            "❌ *تم إلغاء عملية الإرسال*",
            chat_id,
            call.message.message_id,
            parse_mode="Markdown"
        )

def initialize_components():
    """تهيئة المكونات"""
    try:
        # قاعدة البيانات
        from database import init_db, get_all_users
        init_db()
        get_all_users()
        logger.info("✅ قاعدة البيانات")
        
        # إصلاح كلمات المرور القديمة
        logger.info("🔄 جاري فحص كلمات المرور...")
        fix_old_passwords()
        
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
        
        # إضافة زر إرسال الرسائل لقائمة الأدمن
        @bot.message_handler(func=lambda m: m.text == "admin" and m.chat.id in [6292405444, 1851786931])
        def admin_menu_with_messages(message):
            """قائمة الأدمن مع زر إرسال الرسائل"""
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
            markup.add(
                types.KeyboardButton("📊 التحليلات"),
                types.KeyboardButton("📢 إرسال رسالة"),
                types.KeyboardButton("📅 إدارة المواعيد"),
                types.KeyboardButton("➕ إضافة قروب"),
                types.KeyboardButton("📨 إرسال رسالة تحديث"),
                types.KeyboardButton("🏠 العودة للرئيسية")
            )
            bot.send_message(message.chat.id, "⚙️ قائمة الأدمن: اختر خياراً", reply_markup=markup)
        
        logger.info("✅ معالجات الأدمن")
    except Exception as e:
        logger.warning(f"⚠️ معالجات الأدمن: {e}")
    
    # 3. إعداد إرسال الرسائل يدوياً
    setup_manual_message_sender()
    
    # 4. معالجات المستخدمين
    try:
        from bot_users import handle_user_commands
        handle_user_commands()
        logger.info("✅ معالجات المستخدمين")
    except Exception as e:
        logger.error(f"❌ معالجات المستخدمين: {e}")
        return False
    
    # 5. المعالج النهائي
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
    logger.info("=" * 60)
    logger.info("🚀 بدء تشغيل البوت الرئيسي")
    logger.info("=" * 60)
    
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
        bot.remove_webhook()
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        logger.error(f"❌ توقف البوت: {e}")

if __name__ == '__main__':
    main()
