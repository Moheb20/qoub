from telebot import types
from bot_instance import bot
from database import get_categories, get_groups_by_category, get_group_link, add_group
from states.user_states import admin_group_states
from utils.keyboard_utils import send_main_menu
from config import ADMIN_CHAT_ID

def setup_group_handlers():
    @bot.message_handler(func=lambda message: message.text == "📚 عرض القروبات")
    def handle_show_groups(message):
        chat_id = message.chat.id
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        categories = get_categories()
        for category in categories:
            markup.add(types.KeyboardButton(category))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text in get_categories())
    def handle_category_selection(message):
        chat_id = message.chat.id
        text = message.text
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
        groups_in_category = get_groups_by_category(text)
        for group_id, group_name, link in groups_in_category:
            markup.add(types.KeyboardButton(group_name))
        markup.add(types.KeyboardButton("العودة للقروبات"))
        bot.send_message(chat_id, f"📂 القروبات ضمن '{text}': اختر قروب:", reply_markup=markup)

    @bot.message_handler(func=lambda message: get_group_link(message.text))
    def handle_group_link(message):
        chat_id = message.chat.id
        text = message.text
        link = get_group_link(text)
        bot.send_message(chat_id, f"🔗 رابط قروب '{text}':\n{link}")

    @bot.message_handler(func=lambda message: message.text == "إضافة قروب" and message.chat.id in ADMIN_CHAT_ID)
    def handle_add_group(message):
        chat_id = message.chat.id
        admin_group_states[chat_id] = {"stage": "awaiting_type"}
        bot.send_message(chat_id, "📂 اختر نوع القروب:\n1️⃣ مواد\n2️⃣ تخصصات\n3️⃣ جامعة")

    @bot.message_handler(func=lambda message: admin_group_states.get(message.chat.id, {}).get("stage") == "awaiting_type")
    def handle_group_type(message):
        chat_id = message.chat.id
        text = message.text.strip()
        choice = text.strip()
        type_dict = {"1": "المواد", "2": "التخصصات", "3": "الجامعة"}
        if choice not in type_dict:
            bot.send_message(chat_id, "⚠️ الرقم غير صحيح. اختر 1 أو 2 أو 3.")
            return
        admin_group_states[chat_id]["category"] = type_dict[choice]
        admin_group_states[chat_id]["stage"] = "awaiting_name"
        bot.send_message(chat_id, f"✍️ اكتب اسم القروب ضمن '{type_dict[choice]}':")

    @bot.message_handler(func=lambda message: admin_group_states.get(message.chat.id, {}).get("stage") == "awaiting_name")
    def handle_group_name(message):
        chat_id = message.chat.id
        text = message.text.strip()
        admin_group_states[chat_id]["name"] = text
        admin_group_states[chat_id]["stage"] = "awaiting_link"
        bot.send_message(chat_id, "🔗 ارسل رابط القروب:")

    @bot.message_handler(func=lambda message: admin_group_states.get(message.chat.id, {}).get("stage") == "awaiting_link")
    def handle_group_link(message):
        chat_id = message.chat.id
        text = message.text.strip()
        category = admin_group_states[chat_id]["category"]
        name = admin_group_states[chat_id]["name"]
        link = text
        add_group(category, name, link)
        bot.send_message(chat_id, f"✅ تم إضافة القروب '{name}' ضمن '{category}' بالرابط: {link}")
        admin_group_states.pop(chat_id, None)
        send_main_menu(chat_id)