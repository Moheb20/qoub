from telebot import types
from bot_instance import bot
from config import ADMIN_CHAT_ID
from database import get_all_chat_ids_from_logs, get_all_deadlines, delete_deadline, get_deadline_by_id, update_deadline
from utils.keyboard_utils import create_admin_keyboard, create_deadline_management_keyboard
from states.user_states import admin_states, admin_deadline_states
import logging

logger = logging.getLogger(__name__)

def setup_admin_handlers():
    @bot.message_handler(func=lambda message: message.text == "admin" and message.chat.id in ADMIN_CHAT_ID)
    def handle_admin_menu(message):
        chat_id = message.chat.id
        markup = create_admin_keyboard()
        bot.send_message(chat_id, "⚙️ قائمة الأدمن: اختر خياراً", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "إرسال رسالة" and message.chat.id in ADMIN_CHAT_ID)
    def handle_broadcast_request(message):
        chat_id = message.chat.id
        bot.send_message(chat_id, "✍️ الرجاء كتابة نص الرسالة التي تريد إرسالها لجميع المستخدمين:")
        admin_states[chat_id] = "awaiting_broadcast_text"

    @bot.message_handler(func=lambda message: message.text == "إدارة المواعيد" and message.chat.id in ADMIN_CHAT_ID)
    def handle_deadline_management(message):
        chat_id = message.chat.id
        markup = create_deadline_management_keyboard()
        bot.send_message(chat_id, "⚙️ إدارة المواعيد: اختر خياراً", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "التحليلات" and message.chat.id in ADMIN_CHAT_ID)
    def handle_stats(message):
        chat_id = message.chat.id
        from database import get_bot_stats
        stats = get_bot_stats()
        stats_text = (
            "📊 *إحصائيات عامة للبوت:*\n\n"
            f"- عدد المستخدمين المسجلين: {stats['total_users']}\n"
            f"- المستخدمين الجدد اليوم: {stats['new_today']}\n"
            f"- المستخدمين الجدد خلال الأسبوع: {stats['new_last_7_days']}\n"
            f"- المستخدمين الجدد خلال الشهر: {stats['new_last_30_days']}\n"
            f"- عدد المستخدمين غير النشطين (>7 أيام بدون تفاعل): {stats['inactive_users']}\n"
        )
        top_groups = stats.get("top_groups", [])
        for group in top_groups:
            stats_text += f"  • {group}\n"
        bot.send_message(chat_id, stats_text, parse_mode="Markdown")

    @bot.message_handler(func=lambda message: admin_states.get(message.chat.id) == "awaiting_broadcast_text")
    def handle_broadcast_text(message):
        chat_id = message.chat.id
        text = message.text.strip()
        
        broadcast_text = text
        header = "📢 رسالة عامة من الإدارة:\n\n"
        full_message = header + broadcast_text

        chat_ids = get_all_chat_ids_from_logs()
        sent_count = 0
        failed_count = 0
        successful_users = []

        for target_chat_id in chat_ids:
            try:
                bot.send_message(target_chat_id, full_message)
                sent_count += 1

                user_info = bot.get_chat(target_chat_id)
                user_id = target_chat_id
                username = f"@{user_info.username}" if user_info.username else "—"
                full_name = user_info.first_name or ""
                if user_info.last_name:
                    full_name += f" {user_info.last_name}"

                successful_users.append((str(user_id), username, full_name))
            except Exception as e:
                logger.exception(f"Failed to send message to {target_chat_id}: {e}")
                failed_count += 1

        header_text = "تم ارسال الرسالة بنجاح إلى:\n"
        table_header = f"{'Chat ID':<15} | {'Username':<15} | {'Name'}\n"
        separator = "-" * 50 + "\n"
        table_rows = ""

        for user_id, username, full_name in successful_users:
            table_rows += f"{user_id:<15} | {username:<15} | {full_name}\n"

        report_text = header_text + table_header + separator + table_rows
        report_text += f"\n❌ فشل الإرسال إلى {failed_count} مستخدم." if failed_count else ""

        if len(report_text) > 4000:
            with open("broadcast_report.txt", "w", encoding="utf-8") as f:
                f.write(report_text)
            with open("broadcast_report.txt", "rb") as f:
                bot.send_document(chat_id, f)
        else:
            bot.send_message(chat_id, f"```{report_text}```", parse_mode="Markdown")

        admin_states.pop(chat_id, None)
        from utils.keyboard_utils import send_main_menu
        send_main_menu(chat_id)