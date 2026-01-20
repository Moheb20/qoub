from telebot import types
import logging
from database import (
    get_all_chat_ids_from_logs,
    get_all_deadlines,
    add_deadline,
    update_deadline,
    delete_deadline,
    get_deadline_by_id,
    add_group,
    get_categories,
    get_groups_by_category,
    get_bot_stats,
    get_group_link
)
from scheduler import send_reminder_for_new_deadline
from datetime import date, datetime
from bot_instance import bot

logger = logging.getLogger(__name__)

# ---------- إعداد المتغيرات العامة ----------
ADMIN_CHAT_ID = [6292405444, 1851786931]

# فصل حالات الأدمن عن حالات المستخدمين
admin_states = {}
admin_group_states = {}
admin_deadline_states = {}

def handle_admin_commands():
    """تسجيل جميع معالجات الأدمن"""
    
    @bot.message_handler(func=lambda message: message.text == "admin" and message.chat.id in ADMIN_CHAT_ID)
    def handle_admin_menu(message):
        """قائمة الأدمن الرئيسية"""
        chat_id = message.chat.id
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        markup.add(
            types.KeyboardButton("📊 التحليلات"),
            types.KeyboardButton("📢 إرسال رسالة"),
            types.KeyboardButton("📅 إدارة المواعيد"),
            types.KeyboardButton("➕ إضافة قروب"),
            types.KeyboardButton("🏠 العودة للرئيسية")
        )
        bot.send_message(chat_id, "⚙️ قائمة الأدمن: اختر خياراً", reply_markup=markup)
        return

    @bot.message_handler(func=lambda message: message.text == "📢 إرسال رسالة" and message.chat.id in ADMIN_CHAT_ID)
    def handle_broadcast_request(message):
        """طلب إرسال رسالة جماعية"""
        chat_id = message.chat.id
        bot.send_message(chat_id, "✍️ الرجاء كتابة نص الرسالة التي تريد إرسالها لجميع المستخدمين:")
        admin_states[chat_id] = "awaiting_broadcast_text"

    @bot.message_handler(func=lambda message: 
                         message.chat.id in ADMIN_CHAT_ID and 
                         admin_states.get(message.chat.id) == "awaiting_broadcast_text")
    def handle_broadcast_message(message):
        """معالجة الرسالة الجماعية وإرسالها"""
        chat_id = message.chat.id
        broadcast_text = message.text
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

                # جلب معلومات المستخدم
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

        # إعداد الجدول
        header_text = "تم ارسال الرسالة بنجاح إلى:\n"
        table_header = f"{'Chat ID':<15} | {'Username':<15} | {'Name'}\n"
        separator = "-" * 50 + "\n"
        table_rows = ""

        for user_id, username, full_name in successful_users:
            table_rows += f"{user_id:<15} | {username:<15} | {full_name}\n"

        report_text = header_text + table_header + separator + table_rows
        report_text += f"\n❌ فشل الإرسال إلى {failed_count} مستخدم." if failed_count else ""

        # إذا طول الرسالة كبير، قسمها أو أرسلها كملف
        if len(report_text) > 4000:
            with open("broadcast_report.txt", "w", encoding="utf-8") as f:
                f.write(report_text)
            with open("broadcast_report.txt", "rb") as f:
                bot.send_document(chat_id, f)
        else:
            bot.send_message(chat_id, f"```{report_text}```", parse_mode="Markdown")

        admin_states.pop(chat_id, None)
        send_main_menu(chat_id)

    @bot.message_handler(func=lambda message: message.text == "📅 إدارة المواعيد" and message.chat.id in ADMIN_CHAT_ID)
    def handle_deadlines_menu(message):
        """قائمة إدارة المواعيد"""
        chat_id = message.chat.id
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        markup.add(
            types.KeyboardButton("➕ إضافة موعد"),
            types.KeyboardButton("✏️ تعديل موعد"),
            types.KeyboardButton("❌ حذف موعد"),
            types.KeyboardButton("📋 عرض كل المواعيد"),
            types.KeyboardButton("🏠 العودة للرئيسية")
        )
        bot.send_message(chat_id, "⚙️ إدارة المواعيد: اختر خياراً", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "➕ إضافة موعد" and message.chat.id in ADMIN_CHAT_ID)
    def handle_add_deadline_start(message):
        """بدء إضافة موعد جديد"""
        chat_id = message.chat.id
        admin_deadline_states[chat_id] = {"stage": "awaiting_name"}
        bot.send_message(chat_id, "✍️ اكتب اسم الموعد:")

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_deadline_states and 
                         admin_deadline_states[message.chat.id].get("stage") == "awaiting_name")
    def handle_deadline_name(message):
        """استقبال اسم الموعد"""
        chat_id = message.chat.id
        admin_deadline_states[chat_id]["name"] = message.text
        admin_deadline_states[chat_id]["stage"] = "awaiting_month"
        bot.send_message(chat_id, "📅 اكتب رقم الشهر (1-12):")

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_deadline_states and 
                         admin_deadline_states[message.chat.id].get("stage") == "awaiting_month")
    def handle_deadline_month(message):
        """استقبال شهر الموعد"""
        chat_id = message.chat.id
        text = message.text
        
        if not text.isdigit() or not 1 <= int(text) <= 12:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم شهر صحيح بين 1 و 12.")
            return
            
        admin_deadline_states[chat_id]["month"] = int(text)
        admin_deadline_states[chat_id]["stage"] = "awaiting_day"
        bot.send_message(chat_id, "📅 اكتب رقم اليوم (1-31):")

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_deadline_states and 
                         admin_deadline_states[message.chat.id].get("stage") == "awaiting_day")
    def handle_deadline_day(message):
        """استقبال يوم الموعد وإضافته"""
        chat_id = message.chat.id
        text = message.text
        
        if not text.isdigit() or not 1 <= int(text) <= 31:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم يوم صحيح بين 1 و 31.")
            return
            
        day = int(text)
        month = admin_deadline_states[chat_id]["month"]
        year = datetime.utcnow().year
        
        try:
            deadline_date = date(year, month, day)
        except ValueError:
            bot.send_message(chat_id, "⚠️ التاريخ غير صالح، حاول مرة أخرى.")
            return

        name = admin_deadline_states[chat_id]["name"]
        deadline_id = add_deadline(name, deadline_date)
        
        bot.send_message(chat_id, f"✅ تم إضافة الموعد '{name}' بتاريخ {deadline_date.strftime('%d/%m/%Y')}")
        send_reminder_for_new_deadline(deadline_id)
        admin_deadline_states.pop(chat_id, None)
        send_main_menu(chat_id)

    @bot.message_handler(func=lambda message: message.text == "📋 عرض كل المواعيد" and message.chat.id in ADMIN_CHAT_ID)
    def handle_show_deadlines(message):
        """عرض جميع المواعيد"""
        chat_id = message.chat.id
        deadlines = get_all_deadlines()
        
        if not deadlines:
            bot.send_message(chat_id, "📭 لا توجد مواعيد حالياً.")
            return
            
        msg = "📌 المواعيد الحالية:\n\n"
        for d in deadlines:
            msg += f"ID:{d[0]} - {d[1]} - {d[2].strftime('%d/%m/%Y')}\n"
        bot.send_message(chat_id, msg)

    @bot.message_handler(func=lambda message: message.text == "❌ حذف موعد" and message.chat.id in ADMIN_CHAT_ID)
    def handle_delete_deadline_start(message):
        """بدء عملية حذف موعد"""
        chat_id = message.chat.id
        deadlines = get_all_deadlines()
        
        if not deadlines:
            bot.send_message(chat_id, "📭 لا توجد مواعيد للحذف حالياً.")
            return
            
        msg = "⚠️ اختر ID الموعد للحذف:\n\n"
        for d in deadlines:
            msg += f"ID:{d[0]} - {d[1]} - {d[2].strftime('%d/%m/%Y')}\n"
            
        bot.send_message(chat_id, msg)
        admin_deadline_states[chat_id] = {"stage": "awaiting_delete_id"}

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_deadline_states and 
                         admin_deadline_states[message.chat.id].get("stage") == "awaiting_delete_id")
    def handle_delete_deadline_id(message):
        """حذف الموعد بعد استلام ID"""
        chat_id = message.chat.id
        text = message.text
        
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم ID صحيح.")
            return
            
        deadline_id = int(text)
        if delete_deadline(deadline_id):
            bot.send_message(chat_id, f"✅ تم حذف الموعد رقم {deadline_id} بنجاح.")
        else:
            bot.send_message(chat_id, "⚠️ لم يتم العثور على الموعد المطلوب.")
            
        admin_deadline_states.pop(chat_id, None)
        send_main_menu(chat_id)

    @bot.message_handler(func=lambda message: message.text == "✏️ تعديل موعد" and message.chat.id in ADMIN_CHAT_ID)
    def handle_edit_deadline_start(message):
        """بدء عملية تعديل موعد"""
        chat_id = message.chat.id
        deadlines = get_all_deadlines()
        
        if not deadlines:
            bot.send_message(chat_id, "📭 لا توجد مواعيد للتعديل حالياً.")
            return
            
        msg = "⚙️ اختر ID الموعد للتعديل:\n\n"
        for d in deadlines:
            msg += f"ID:{d[0]} - {d[1]} - {d[2].strftime('%d/%m/%Y')}\n"
            
        bot.send_message(chat_id, msg)
        admin_deadline_states[chat_id] = {"stage": "awaiting_edit_id"}

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_deadline_states and 
                         admin_deadline_states[message.chat.id].get("stage") == "awaiting_edit_id")
    def handle_edit_deadline_id(message):
        """استقبال ID الموعد للتعديل"""
        chat_id = message.chat.id
        text = message.text
        
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم ID صحيح.")
            admin_deadline_states.pop(chat_id, None)
            return
            
        deadline_id = int(text)
        deadline = get_deadline_by_id(deadline_id)
        
        if not deadline:
            bot.send_message(chat_id, "⚠️ لم يتم العثور على الموعد المطلوب.")
            admin_deadline_states.pop(chat_id, None)
            return
            
        admin_deadline_states[chat_id] = {
            "stage": "awaiting_edit_name",
            "id": deadline_id
        }
        bot.send_message(chat_id, f"✏️ اكتب الاسم الجديد للموعد (القديم: {deadline[1]}):")

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_deadline_states and 
                         admin_deadline_states[message.chat.id].get("stage") == "awaiting_edit_name")
    def handle_edit_deadline_name(message):
        """استقبال الاسم الجديد للموعد"""
        chat_id = message.chat.id
        admin_deadline_states[chat_id]["name"] = message.text
        admin_deadline_states[chat_id]["stage"] = "awaiting_edit_month"
        bot.send_message(chat_id, "📅 اكتب رقم الشهر الجديد (1-12):")

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_deadline_states and 
                         admin_deadline_states[message.chat.id].get("stage") == "awaiting_edit_month")
    def handle_edit_deadline_month(message):
        """استقبال الشهر الجديد للموعد"""
        chat_id = message.chat.id
        text = message.text
        
        if not text.isdigit() or not 1 <= int(text) <= 12:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم شهر صحيح بين 1 و 12.")
            return
            
        admin_deadline_states[chat_id]["month"] = int(text)
        admin_deadline_states[chat_id]["stage"] = "awaiting_edit_day"
        bot.send_message(chat_id, "📅 اكتب رقم اليوم الجديد (1-31):")

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_deadline_states and 
                         admin_deadline_states[message.chat.id].get("stage") == "awaiting_edit_day")
    def handle_edit_deadline_day(message):
        """إتمام عملية التعديل"""
        chat_id = message.chat.id
        text = message.text
        
        if not text.isdigit() or not 1 <= int(text) <= 31:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم يوم صحيح بين 1 و 31.")
            return
            
        day = int(text)
        month = admin_deadline_states[chat_id]["month"]
        year = datetime.utcnow().year
        
        try:
            new_date = date(year, month, day)
        except ValueError:
            bot.send_message(chat_id, "⚠️ التاريخ غير صالح، حاول مرة أخرى.")
            return

        deadline_id = admin_deadline_states[chat_id]["id"]
        new_name = admin_deadline_states[chat_id]["name"]
        
        update_deadline(deadline_id, new_name, new_date)
        bot.send_message(chat_id, f"✅ تم تعديل الموعد بنجاح: '{new_name}' بتاريخ {new_date.strftime('%d/%m/%Y')}")
        admin_deadline_states.pop(chat_id, None)
        send_main_menu(chat_id)

    @bot.message_handler(func=lambda message: message.text == "📊 التحليلات" and message.chat.id in ADMIN_CHAT_ID)
    def handle_stats(message):
        """عرض إحصائيات البوت"""
        chat_id = message.chat.id
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
        if top_groups:
            stats_text += "\n🏆 المجموعات الأكثر طلباً:\n"
            for group in top_groups:
                stats_text += f"  • {group}\n"
                
        bot.send_message(chat_id, stats_text, parse_mode="Markdown")

    @bot.message_handler(func=lambda message: message.text == "➕ إضافة قروب" and message.chat.id in ADMIN_CHAT_ID)
    def handle_add_group_start(message):
        """بدء إضافة قروب جديد"""
        chat_id = message.chat.id
        admin_group_states[chat_id] = {"stage": "awaiting_type"}
        bot.send_message(chat_id, "📂 اختر نوع القروب:\n1️⃣ مواد\n2️⃣ تخصصات\n3️⃣ جامعة")

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_group_states and 
                         admin_group_states[message.chat.id].get("stage") == "awaiting_type")
    def handle_group_type(message):
        """استقبال نوع القروب"""
        chat_id = message.chat.id
        choice = message.text.strip()
        type_dict = {"1": "مواد", "2": "تخصصات", "3": "جامعة"}
        
        if choice not in type_dict:
            bot.send_message(chat_id, "⚠️ الرقم غير صحيح. اختر 1 أو 2 أو 3.")
            return
            
        admin_group_states[chat_id]["category"] = type_dict[choice]
        admin_group_states[chat_id]["stage"] = "awaiting_name"
        bot.send_message(chat_id, f"✍️ اكتب اسم القروب ضمن '{type_dict[choice]}':")

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_group_states and 
                         admin_group_states[message.chat.id].get("stage") == "awaiting_name")
    def handle_group_name(message):
        """استقبال اسم القروب"""
        chat_id = message.chat.id
        admin_group_states[chat_id]["name"] = message.text
        admin_group_states[chat_id]["stage"] = "awaiting_link"
        bot.send_message(chat_id, "🔗 ارسل رابط القروب:")

    @bot.message_handler(func=lambda message: 
                         message.chat.id in admin_group_states and 
                         admin_group_states[message.chat.id].get("stage") == "awaiting_link")
    def handle_group_link(message):
        """استقبال رابط القروب وإضافته"""
        chat_id = message.chat.id
        category = admin_group_states[chat_id]["category"]
        name = admin_group_states[chat_id]["name"]
        link = message.text
        
        add_group(category, name, link)
        bot.send_message(chat_id, f"✅ تم إضافة القروب '{name}' ضمن '{category}' بالرابط: {link}")
        admin_group_states.pop(chat_id, None)
        send_main_menu(chat_id)

    @bot.message_handler(func=lambda message: message.text == "🏠 العودة للرئيسية" and message.chat.id in ADMIN_CHAT_ID)
    def handle_admin_back_to_home(message):
        """العودة للقائمة الرئيسية"""
        chat_id = message.chat.id
        # تنظيف جميع حالات الأدمن
        admin_states.pop(chat_id, None)
        admin_group_states.pop(chat_id, None)
        admin_deadline_states.pop(chat_id, None)
        send_main_menu(chat_id)

    @bot.message_handler(func=lambda message: message.text == "🏠 الرئيسية" and message.chat.id in ADMIN_CHAT_ID)
    def handle_admin_home(message):
        """معالج زر الرئيسية للأدمن"""
        chat_id = message.chat.id
        # تنظيف جميع حالات الأدمن
        admin_states.pop(chat_id, None)
        admin_group_states.pop(chat_id, None)
        admin_deadline_states.pop(chat_id, None)
        send_main_menu(chat_id)

def send_main_menu(chat_id):
    """إرسال القائمة الرئيسية (يجب استيرادها من الملف الرئيسي أو تعريفها هنا)"""
    from bot_users import send_main_menu as send_user_main_menu
    send_user_main_menu(chat_id)
