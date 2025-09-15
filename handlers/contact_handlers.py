from telebot import types
from bot_instance import bot
from config import ADMIN_CHAT_ID
from database import get_branches_list, get_departments_list, get_contacts_list, add_department, add_contact, update_contact, delete_contact
from utils.keyboard_utils import send_main_menu
from utils.helpers import handle_branch_selection, handle_department_selection, handle_contact_selection
from states.user_states import branch_selection_states, department_selection_states, add_number_states, edit_contact_states, delete_contact_states

def setup_contact_handlers():
    @bot.message_handler(func=lambda message: message.text == "📞 أرقام الأقسام وأعضاء الهيئة التدريسية")
    def handle_contacts_menu(message):
        chat_id = message.chat.id
        branches = get_branches_list()
        if not branches:
            bot.send_message(chat_id, "📭 لا توجد فروع حالياً.")
            return

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        for branch_id, branch_name in branches:
            markup.add(types.KeyboardButton(branch_name))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        
        branch_selection_states[chat_id] = {"stage": "awaiting_branch"}
        bot.send_message(chat_id, "🏢 اختر فرع:", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "🛠️ إدارة الأرقام" and message.chat.id in ADMIN_CHAT_ID)
    def handle_contact_management(message):
        chat_id = message.chat.id
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        markup.add(
            types.KeyboardButton("عرض الفروع"),
            types.KeyboardButton("إضافة رقم"),
            types.KeyboardButton("تعديل رقم"),
            types.KeyboardButton("حذف رقم"),
            types.KeyboardButton("العودة للرئيسية")
        )
        bot.send_message(chat_id, "اختر العملية التي تريد تنفيذها:", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "عرض الفروع" and message.chat.id in ADMIN_CHAT_ID)
    def handle_show_branches(message):
        chat_id = message.chat.id
        branches = get_branches_list()
        if not branches:
            bot.send_message(chat_id, "📭 لا توجد فروع حالياً.")
            return

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        for b_id, b_name in branches:
            markup.add(types.KeyboardButton(b_name))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "🏢 الفروع الحالية:", reply_markup=markup)

    @bot.message_handler(func=lambda message: message.text == "إضافة رقم" and message.chat.id in ADMIN_CHAT_ID)
    def handle_add_number(message):
        chat_id = message.chat.id
        add_number_states[chat_id] = {"stage": "awaiting_branch"}
        bot.send_message(chat_id, "🏢 اكتب اسم الفرع لإضافة الرقم (سيتم إضافته تلقائيًا إذا لم يكن موجودًا):")

    @bot.message_handler(func=lambda message: message.text == "تعديل رقم" and message.chat.id in ADMIN_CHAT_ID)
    def handle_edit_contact(message):
        chat_id = message.chat.id
        edit_contact_states[chat_id] = {"stage": "awaiting_branch"}
        bot.send_message(chat_id, "🏢 اختر الفرع لتعديل الرقم:")

    @bot.message_handler(func=lambda message: message.text == "حذف رقم" and message.chat.id in ADMIN_CHAT_ID)
    def handle_delete_contact(message):
        chat_id = message.chat.id
        delete_contact_states[chat_id] = {"stage": "awaiting_branch"}
        bot.send_message(chat_id, "🏢 اختر الفرع لحذف الرقم:")

    # معالجة اختيار الفرع للعودة للرئيسية
    @bot.message_handler(func=lambda message: branch_selection_states.get(message.chat.id, {}).get("stage") == "awaiting_branch" and message.text == "العودة للرئيسية")
    def handle_branch_back(message):
        chat_id = message.chat.id
        branch_selection_states.pop(chat_id, None)
        send_main_menu(chat_id)

    # معالجة اختيار القسم للعودة للرئيسية
    @bot.message_handler(func=lambda message: department_selection_states.get(message.chat.id, {}).get("stage") == "awaiting_department" and message.text == "العودة للرئيسية")
    def handle_department_back(message):
        chat_id = message.chat.id
        department_selection_states.pop(chat_id, None)
        send_main_menu(chat_id)

    # معالجة اختيار الاسم للعودة للرئيسية
    @bot.message_handler(func=lambda message: department_selection_states.get(message.chat.id, {}).get("stage") == "awaiting_contact" and message.text == "العودة للرئيسية")
    def handle_contact_back(message):
        chat_id = message.chat.id
        department_selection_states.pop(chat_id, None)
        send_main_menu(chat_id)

    # معالجة إضافة رقم - اختيار الفرع
    @bot.message_handler(func=lambda message: add_number_states.get(message.chat.id, {}).get("stage") == "awaiting_branch")
    def handle_add_number_branch(message):
        chat_id = message.chat.id
        text = message.text.strip()
        handle_branch_selection(chat_id, text, add_number_states)

    # معالجة إضافة رقم - اختيار القسم
    @bot.message_handler(func=lambda message: add_number_states.get(message.chat.id, {}).get("stage") == "awaiting_department")
    def handle_add_number_department(message):
        chat_id = message.chat.id
        text = message.text.strip()
        
        if text == "العودة للرئيسية":
            add_number_states.pop(chat_id, None)
            send_main_menu(chat_id)
            return

        branch_id = add_number_states[chat_id]["branch_id"]
        dept_name = text.strip()
        departments = dict(get_departments_list(branch_id))
        dept_id = None
        
        for d_id, d_name in departments.items():
            if d_name == dept_name:
                dept_id = d_id
                break
                
        if not dept_id:
            add_department(branch_id, dept_name)
            departments = dict(get_departments_list(branch_id))
            dept_id = [d_id for d_id, d_name in departments.items() if d_name == dept_name][0]

        add_number_states[chat_id]["stage"] = "awaiting_new_contact"
        add_number_states[chat_id]["dept_id"] = dept_id
        bot.send_message(chat_id, "👤 اكتب الاسم والرقم بالصيغة: الاسم - الرقم")

    # معالجة إضافة رقم - إدخال الاسم والرقم
    @bot.message_handler(func=lambda message: add_number_states.get(message.chat.id, {}).get("stage") == "awaiting_new_contact")
    def handle_add_number_contact(message):
        chat_id = message.chat.id
        text = message.text.strip()
        
        if text == "العودة للرئيسية":
            add_number_states.pop(chat_id, None)
            send_main_menu(chat_id)
            return
            
        if "-" not in text:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال البيانات بالصيغة الصحيحة: الاسم - الرقم")
            return
            
        name, number = map(str.strip, text.split("-", 1))
        dept_id = add_number_states[chat_id]["dept_id"]
        add_contact(dept_id, name, number)
        bot.send_message(chat_id, f"✅ تم إضافة الرقم: {name} - {number}")
        add_number_states.pop(chat_id, None)
        send_main_menu(chat_id)
