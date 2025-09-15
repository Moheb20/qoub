from database import get_branches_list, get_departments_list, get_contacts_list
from bot_instance import bot
from states.user_states import branch_selection_states, department_selection_states
from utils.keyboard_utils import send_main_menu

def handle_branch_selection(chat_id, text, state_dict):
    if text == "العودة للرئيسية":
        state_dict.pop(chat_id, None)
        send_main_menu(chat_id)
        return None

    branches = get_branches_list()
    selected_branch = next(((b_id, b_name) for b_id, b_name in branches if b_name == text), None)
    if not selected_branch:
        bot.send_message(chat_id, "⚠️ الرجاء اختيار فرع صحيح.")
        return None

    branch_id, branch_name = selected_branch
    state_dict[chat_id]["stage"] = "awaiting_department"
    state_dict[chat_id]["branch_id"] = branch_id

    departments = get_departments_list(branch_id)
    if not departments:
        bot.send_message(chat_id, "📭 لا توجد أقسام في هذا الفرع.")
        return None

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    for d_id, d_name in departments:
        markup.add(types.KeyboardButton(d_name))
    markup.add(types.KeyboardButton("العودة للرئيسية"))

    bot.send_message(chat_id, f"🏢 اختر القسم في '{branch_name}':", reply_markup=markup)
    return branch_id

def handle_department_selection(chat_id, text, state_dict):
    if text == "العودة للرئيسية":
        state_dict.pop(chat_id, None)
        send_main_menu(chat_id)
        return None

    branch_id = state_dict[chat_id]["branch_id"]
    departments = get_departments_list(branch_id)
    selected_dept = next(((d_id, d_name) for d_id, d_name in departments if d_name == text), None)
    if not selected_dept:
        bot.send_message(chat_id, "⚠️ الرجاء اختيار قسم صحيح.")
        return None

    dept_id, dept_name = selected_dept
    state_dict[chat_id]["stage"] = "awaiting_contact"
    state_dict[chat_id]["dept_id"] = dept_id

    contacts = get_contacts_list(dept_id)
    if not contacts:
        bot.send_message(chat_id, "📭 لا توجد بيانات في هذا القسم.")
        return None

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    for c_id, c_name, c_phone in contacts:
        markup.add(types.KeyboardButton(c_name))
    markup.add(types.KeyboardButton("العودة للرئيسية"))

    bot.send_message(chat_id, f"👤 اختر الاسم:", reply_markup=markup)
    return dept_id

def handle_contact_selection(chat_id, text, state_dict, action):
    if text == "العودة للرئيسية":
        state_dict.pop(chat_id, None)
        send_main_menu(chat_id)
        return None

    dept_id = state_dict[chat_id]["dept_id"]
    contacts = get_contacts_list(dept_id)
    selected_contact = next(((c_id, c_name, c_phone) for c_id, c_name, c_phone in contacts if c_name == text), None)
    if not selected_contact:
        bot.send_message(chat_id, "⚠️ الرجاء اختيار اسم صحيح.")
        return None

    c_id, c_name, c_phone = selected_contact

    if action == "edit":
        state_dict[chat_id]["stage"] = "awaiting_new_info"
        state_dict[chat_id]["contact_id"] = c_id
        bot.send_message(chat_id, f"✍️ أدخل الاسم والرقم الجديد بصيغة: الاسم - الرقم لـ '{c_name}':")
    elif action == "delete":
        from database import delete_contact
        delete_contact(c_id)
        bot.send_message(chat_id, f"✅ تم حذف '{c_name}' بنجاح.")
        state_dict.pop(chat_id, None)
        send_main_menu(chat_id)

def clear_states_for_home(chat_id):
    from states.user_states import registration_states, session_states
    registration_states.pop(chat_id, None)
    session_states.pop(chat_id, None)