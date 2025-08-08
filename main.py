import threading
from flask import Flask
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot_instance import bot
from database import get_all_users, get_user, add_user, update_last_msg
from scheduler import start_scheduler
from qou_scraper import QOUScraper

# الحالة المؤقتة لتخزين بيانات الدخول أثناء عملية التسجيل
user_states = {}

# روابط القروبات
subject_groups = {
    "مناهج البحث العلمي": "https://chat.whatsapp.com/Ixv647y5WKB8IR43tTWpZc",
    "قواعد الكتابة والترقيم": "https://chat.whatsapp.com/IV0KQVlep5QJ1dBaRoqn5f",
}

university_groups = {
    "طلاب جامعة القدس المفتوحة": "https://chat.whatsapp.com/Bvbnq3XTtnJAFsqJkSFl6e"
}

major_groups = {
    "رياضيات": "https://chat.whatsapp.com/FKCxgfaJNWJ6CBnIB30FYO"
}

subject_list = list(subject_groups.items())
university_list = list(university_groups.items())
major_list = list(major_groups.items())

# تهيئة قاعدة البيانات والجدولة
get_all_users()
start_scheduler()

# إعداد تطبيق Flask لمراقبة حالة السيرفر
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ البوت يعمل بنجاح!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ⬇️ بدء تنفيذ البوت ⬇️

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user = get_user(chat_id)

    if user:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("📚 قروبات الجامعة والمواد", callback_data="show_groups"),
            InlineKeyboardButton("📋 عرض المقررات والعلامات", callback_data="show_courses"),
        )
        bot.send_message(chat_id, "👋 مرحباً بك مجددًا! اختر من القائمة:", reply_markup=keyboard)
    else:
        user_states[chat_id] = {}
        bot.send_message(chat_id, "👤 لم يتم تسجيلك بعد.\n📩 الرجاء إرسال رقمك الجامعي:")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and 'student_id' not in user_states[msg.chat.id])
def get_student_id(message):
    chat_id = message.chat.id
    user_states[chat_id]['student_id'] = message.text.strip()
    bot.send_message(chat_id, "🔒 الآن، الرجاء إرسال كلمة المرور:")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and 'password' not in user_states[msg.chat.id])
def get_password(message):
    chat_id = message.chat.id
    user_states[chat_id]['password'] = message.text.strip()

    student_id = user_states[chat_id]['student_id']
    password = user_states[chat_id]['password']

    scraper = QOUScraper(student_id, password)
    if scraper.login():
        add_user(chat_id, student_id, password)
        bot.send_message(chat_id, "✅ تم تسجيلك بنجاح!\n🔍 جاري البحث عن آخر رسالة...")

        latest = scraper.fetch_latest_message()
        if latest:
            update_last_msg(chat_id, latest['msg_id'])
            text = (
                f"📬 آخر رسالة في البريد:\n"
                f"📧 {latest['subject']}\n"
                f"📝 {latest['sender']}\n"
                f"🕒 {latest['date']}\n\n"
                f"{latest['body']}"
            )
            bot.send_message(chat_id, text)
        else:
            bot.send_message(chat_id, "📭 لم يتم العثور على رسائل حالياً.")

        bot.send_message(chat_id, "📡 سيتم تتبع الرسائل الجديدة وإرسالها تلقائيًا.")
    else:
        bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة البيانات.")

    user_states.pop(chat_id, None)

# قروبات الجامعة والمواد
@bot.message_handler(commands=['groups'])
def handle_groups_command(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("📚 قروبات المواد", callback_data="category:subjects"),
        InlineKeyboardButton("🎓 قروبات التخصصات", callback_data="category:majors"),
        InlineKeyboardButton("🏛 قروبات الجامعة", callback_data="category:university")
    )
    bot.send_message(message.chat.id, "🎯 اختر نوع القروبات:", reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: call.data.startswith("category:"))
def handle_group_category(call):
    category = call.data.split(":")[1]

    markup = InlineKeyboardMarkup()
    if category == "subjects":
        for name in subject_groups:
            markup.add(InlineKeyboardButton(name, callback_data=f"subject:{name}"))
        bot.send_message(call.message.chat.id, "🧾 اختر المادة للحصول على رابط القروب:", reply_markup=markup)

    elif category == "university":
        for idx, (name, _) in enumerate(university_list):
            markup.add(InlineKeyboardButton(name, callback_data=f"univ_{idx}"))
        bot.send_message(call.message.chat.id, "🏛 اختر قروب الجامعة:", reply_markup=markup)

    elif category == "majors":
        for name in major_groups:
            markup.add(InlineKeyboardButton(name, callback_data=f"major:{name}"))
        bot.send_message(call.message.chat.id, "🧑‍🎓 اختر قروب التخصص:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("subject:"))
def handle_subject_selection(call):
    subject = call.data.split("subject:")[1]
    link = subject_groups.get(subject, "❌ الرابط غير متوفر")
    bot.send_message(call.message.chat.id, f"📘 رابط قروب *{subject}*:\n{link}", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("univ_"))
def handle_university_selection(call):
    try:
        index = int(call.data.split("_")[1])
        name, link = university_list[index]
        bot.send_message(call.message.chat.id, f"🏫 رابط قروب *{name}*:\n{link}", parse_mode="Markdown")
    except Exception:
        bot.send_message(call.message.chat.id, "❌ حدث خطأ أثناء استرجاع الرابط.")

@bot.callback_query_handler(func=lambda call: call.data.startswith("major:"))
def handle_major_selection(call):
    name = call.data.split("major:")[1]
    link = major_groups.get(name, "❌ الرابط غير متوفر")
    bot.send_message(call.message.chat.id, f"📘 رابط قروب *{name}*:\n{link}", parse_mode="Markdown")

# عرض المقررات والعلامات
@bot.message_handler(commands=['courses'])
def handle_courses(message):
    chat_id = message.chat.id
    user = get_user(chat_id)

    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    student_id, password = user['student_id'], user['password']
    scraper = QOUScraper(student_id, password)

    if not scraper.login():
        bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
        return

    courses = scraper.fetch_term_summary_courses()
    if not courses:
        bot.send_message(chat_id, "📭 لم يتم العثور على مقررات أو علامات.")
        return

    text = "📚 *ملخص علامات المقررات الفصلية:*\n\n"
    for c in courses:
        code = c.get('course_code', '-')
        name = c.get('course_name', '-')
        midterm = c.get('midterm_mark', '-')
        final = c.get('final_mark', '-')
        final_date = c.get('final_mark_date', '-')
        text += (
            f"🔹 *{code}* - {name}\n"
            f"    🧪 نصفي: {midterm}\n"
            f"    🏁 نهائي: {final} (تاريخ: {final_date})\n\n"
        )
    bot.send_message(chat_id, text, parse_mode="Markdown")

# التعامل مع أزرار القائمة الرئيسية
@bot.callback_query_handler(func=lambda call: call.data in ["show_groups", "show_courses"])
def callback_handler(call):
    if call.data == "show_groups":
        handle_groups_command(call.message)
    elif call.data == "show_courses":
        handle_courses(call.message)

# أوامر البوت
if __name__ == "__main__":
    bot.set_my_commands([
        types.BotCommand("start", "بدء التسجيل وتسجيل الدخول"),
        types.BotCommand("groups", "عرض قروبات الجامعة والمواد"),
        types.BotCommand("courses", "عرض المقررات والعلامات"),
    ])
    threading.Thread(target=run_flask).start()
    bot.remove_webhook()
    bot.infinity_polling()
