from telebot import types
from bot_instance import bot
from database import get_user, add_user, log_chat_id
from utils.keyboard_utils import send_main_menu
from states.user_states import registration_states
from config import ADMIN_CHAT_ID
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def setup_user_handlers():
    @bot.message_handler(commands=["start"])
    def handle_start(message):
        log_chat_id(message.chat.id)
        chat_id = message.chat.id
        username = message.from_user.username or "بدون اسم مستخدم"
        user = get_user(chat_id)

        if user:
            bot.send_message(chat_id, "👋  مرحــــباً!  ")
        else:
            add_user(chat_id, student_id="", password="", registered_at=datetime.utcnow().isoformat())
            bot.send_message(chat_id, "👤 لم يتم تسجيلك بعد. الرجاء تسجيل الدخول.")
            
            admin_message = (
                f"🚨 مستخدم جديد بدأ استخدام البوت!\n\n"
                f"chat_id: {chat_id}\n"
                f"Username: @{username}"
            )
            for admin_id in ADMIN_CHAT_ID:
                try:
                    bot.send_message(admin_id, admin_message)
                except Exception as e:
                    print(f"خطأ في إرسال الرسالة للأدمن {admin_id}: {e} - deadline_handlers.py:35")

        send_main_menu(chat_id)

    @bot.message_handler(func=lambda message: message.text == "👤 تسجيل الدخول")
    def handle_login_request(message):
        chat_id = message.chat.id
        start_login(chat_id)

    def start_login(chat_id):
        registration_states[chat_id] = {"stage": "awaiting_student_id"}
        bot.send_message(chat_id, "👤 الرجاء إرسال رقمك الجامعي:")

    @bot.message_handler(func=lambda message: registration_states.get(message.chat.id, {}).get("stage") == "awaiting_student_id")
    def handle_student_id(message):
        chat_id = message.chat.id
        text = message.text.strip()
        registration_states[chat_id]["student_id"] = text
        registration_states[chat_id]["stage"] = "awaiting_password"
        bot.send_message(chat_id, "🔒 الآن، الرجاء إرسال كلمة المرور:")

    @bot.message_handler(func=lambda message: registration_states.get(message.chat.id, {}).get("stage") == "awaiting_password")
    def handle_password(message):
        chat_id = message.chat.id
        text = message.text.strip()
        registration_states[chat_id]["password"] = text
        student_id = registration_states[chat_id].get("student_id")
        password = registration_states[chat_id].get("password")

        try:
            from qou_scraper import QOUScraper
            from database import update_last_msg
            
            scraper = QOUScraper(student_id, password)
            if scraper.login():
                add_user(chat_id, student_id, password)
                bot.send_message(chat_id, "✅ تم تسجيلك بنجاح!\n🔍 جاري البحث عن آخر رسالة...")

                latest = scraper.fetch_latest_message()
                if latest:
                    update_last_msg(chat_id, latest["msg_id"])
                    text_msg = (
                        f"📬 آخـــر رســالـــة في البـــريـــد:\n"
                        f"📧 {latest['subject']}\n"
                        f"📝 {latest['sender']}\n"
                        f"🕒 {latest['date']}\n\n"
                        f"{latest['body']}\n\n"
                        f"📬 وسيـــتم اعلامــــك\ي بأي رســالة جــديــدة \n"
                    )
                    bot.send_message(chat_id, text_msg)
                else:
                    bot.send_message(chat_id, "📭 لم يتم العثور على رسائل حالياً.")
            else:
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة البيانات.")
        except Exception as e:
            logger.exception(f"Error during login for {chat_id}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء محاولة تسجيل الدخول. حاول مرة أخرى لاحقاً.")
        finally:
            registration_states.pop(chat_id, None)
            send_main_menu(chat_id)