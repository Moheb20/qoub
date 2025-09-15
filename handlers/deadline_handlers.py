from telebot import types
from bot_instance import bot
from config import ADMIN_CHAT_ID
from database import get_all_deadlines, delete_deadline, get_deadline_by_id, update_deadline, add_deadline
from states.user_states import admin_deadline_states
from utils.keyboard_utils import send_main_menu
from datetime import datetime, date
from scheduler import send_reminder_for_new_deadline

def setup_deadline_handlers():
    @bot.message_handler(func=lambda message: message.text == "➕ إضافة موعد" and message.chat.id in ADMIN_CHAT_ID)
    def handle_add_deadline(message):
        chat_id = message.chat.id
        admin_deadline_states[chat_id] = {"stage": "awaiting_name"}
        bot.send_message(chat_id, "✍️ اكتب اسم الموعد:")

    @bot.message_handler(func=lambda message: message.text == "📋 عرض كل المواعيد" and message.chat.id in ADMIN_CHAT_ID)
    def handle_show_deadlines(message):
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
    def handle_delete_deadline(message):
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

    @bot.message_handler(func=lambda message: message.text == "✏️ تعديل موعد" and message.chat.id in ADMIN_CHAT_ID)
    def handle_edit_deadline(message):
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

    @bot.message_handler(func=lambda message: chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_name")
    def handle_deadline_name(message):
        chat_id = message.chat.id
        text = message.text.strip()
        admin_deadline_states[chat_id]["name"] = text
        admin_deadline_states[chat_id]["stage"] = "awaiting_month"
        bot.send_message(chat_id, "📅 اكتب رقم الشهر (1-12):")

    @bot.message_handler(func=lambda message: chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_month")
    def handle_deadline_month(message):
        chat_id = message.chat.id
        text = message.text.strip()
        if not text.isdigit() or not 1 <= int(text) <= 12:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم شهر صحيح بين 1 و 12.")
            return
        admin_deadline_states[chat_id]["month"] = int(text)
        admin_deadline_states[chat_id]["stage"] = "awaiting_day"
        bot.send_message(chat_id, "📅 اكتب رقم اليوم (1-31):")

    @bot.message_handler(func=lambda message: chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_day")
    def handle_deadline_day(message):
        chat_id = message.chat.id
        text = message.text.strip()
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

    @bot.message_handler(func=lambda message: chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_delete_id")
    def handle_deadline_delete_id(message):
        chat_id = message.chat.id
        text = message.text.strip()
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

    @bot.message_handler(func=lambda message: chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_edit_id")
    def handle_deadline_edit_id(message):
        chat_id = message.chat.id
        text = message.text.strip()
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم ID صحيح.")
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

    @bot.message_handler(func=lambda message: chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_edit_name")
    def handle_deadline_edit_name(message):
        chat_id = message.chat.id
        text = message.text.strip()
        admin_deadline_states[chat_id]["name"] = text
        admin_deadline_states[chat_id]["stage"] = "awaiting_edit_month"
        bot.send_message(chat_id, "📅 اكتب رقم الشهر الجديد (1-12):")

    @bot.message_handler(func=lambda message: chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_edit_month")
    def handle_deadline_edit_month(message):
        chat_id = message.chat.id
        text = message.text.strip()
        if not text.isdigit() or not 1 <= int(text) <= 12:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم شهر صحيح بين 1 و 12.")
            return
        
        admin_deadline_states[chat_id]["month"] = int(text)
        admin_deadline_states[chat_id]["stage"] = "awaiting_edit_day"
        bot.send_message(chat_id, "📅 اكتب رقم اليوم الجديد (1-31):")

    @bot.message_handler(func=lambda message: chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_edit_day")
    def handle_deadline_edit_day(message):
        chat_id = message.chat.id
        text = message.text.strip()
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