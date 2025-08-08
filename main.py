import threading
from flask import Flask
from database import get_all_users, add_user, update_last_msg, get_user
from scheduler import start_scheduler
from bot_instance import bot  # كائن TeleBot جاهز
from qou_scraper import QOUScraper
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# الحالة المؤقتة للمستخدمين (لتخزين بيانات مؤقتة لكل مستخدم)
user_states = {}

# روابط قروبات المواد (مثال)
subject_groups = {
    "مناهج البحث العلمي": "https://chat.whatsapp.com/Ixv647y5WKB8IR43tTWpZc",
    "قواعد الكتابة والترقيم": "https://chat.whatsapp.com/IV0KQVlep5QJ1dBaRoqn5f",
    # أضف باقي قروبات المواد هنا حسب الحاجة
}

# قروبات الجامعة والتخصصات
university_groups = {
    "طلاب جامعة القدس المفتوحة": "https://chat.whatsapp.com/Bvbnq3XTtnJAFsqJkSFl6e"
}

major_groups = {
    "رياضيات": "https://chat.whatsapp.com/FKCxgfaJNWJ6CBnIB30FYO"
    # أضف باقي التخصصات هنا حسب الحاجة
}

subject_list = list(subject_groups.items())
university_list = list(university_groups.items())
major_list = list(major_groups.items())

# تهيئة قاعدة البيانات والجدولة
get_all_users()
start_scheduler()

# إعداد Flask لخدمة بسيطة
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ البوت يعمل ✔️"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# أوامر البوت

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user_states[chat_id] = {}
    bot.send_message(chat_id, "👤 الرجاء إدخال اسم المستخدم الخاص بك:")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and 'student_id' not in user_states[msg.chat.id])
def get_student_id(message):
    chat_id = message.chat.id
    user_states[chat_id]['student_id'] = message.text.strip()
    bot.send_message(chat_id, "🔒 الآن، الرجاء إدخال كلمة المرور:")

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and 'password' not in user_states[msg.chat_id])
def get_password(message):
    chat_id = message.chat.id
    user_states[chat_id]['password'] = message.text.strip()

    student_id = user_states[chat_id]['student_id']
    password = user_states[chat_id]['password']
    scraper = QOUScraper(student_id, password)

    if scraper.login():
        add_user(chat_id, student_id, password)
        bot.send_message(chat_id, "✅ تم تسجيل بياناتك بنجاح!\n🔍 يتم الآن البحث عن آخر رسالة...")

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


# =================== قائمة القروبات مع أزرار تحت صندوق الكتابة ===================
@bot.message_handler(commands=['groups'])
def handle_groups_command(message):
    markup = ReplyKeyboardMarkup(row_width=3, resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        KeyboardButton("📚 قروبات المواد"),
        KeyboardButton("🎓 قروبات التخصصات"),
        KeyboardButton("🏛 قروبات الجامعة")
    )
    bot.send_message(message.chat.id, "🎯 اختر نوع القروبات:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "📚 قروبات المواد")
def handle_subjects_group(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for name in subject_groups:
        markup.add(KeyboardButton(name))
    markup.add(KeyboardButton("عودة"))
    bot.send_message(message.chat.id, "🧾 اختر المادة للحصول على رابط القروب:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🎓 قروبات التخصصات")
def handle_majors_group(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for name in major_groups:
        markup.add(KeyboardButton(name))
    markup.add(KeyboardButton("عودة"))
    bot.send_message(message.chat.id, "🧑‍🎓 اختر قروب من قروبات التخصص:", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "🏛 قروبات الجامعة")
def handle_university_group(message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for name in university_groups:
        markup.add(KeyboardButton(name))
    markup.add(KeyboardButton("عودة"))
    bot.send_message(message.chat.id, "🏛 اختر قروب الجامعة:", reply_markup=markup)

# إرسال الرابط حسب اختيار القروب
@bot.message_handler(func=lambda message: message.text in subject_groups)
def send_subject_link(message):
    link = subject_groups.get(message.text, "❌ الرابط غير متوفر")
    bot.send_message(message.chat.id, f"📘 رابط قروب *{message.text}*:\n{link}", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text in major_groups)
def send_major_link(message):
    link = major_groups.get(message.text, "❌ الرابط غير متوفر")
    bot.send_message(message.chat.id, f"📘 رابط قروب *{message.text}*:\n{link}", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text in university_groups)
def send_university_link(message):
    link = university_groups.get(message.text, "❌ الرابط غير متوفر")
    bot.send_message(message.chat.id, f"🏫 رابط قروب *{message.text}*:\n{link}", parse_mode="Markdown")

# زر العودة للقائمة الرئيسية
@bot.message_handler(func=lambda message: message.text == "عودة")
def back_to_main_menu(message):
    bot.send_message(message.chat.id, "🔙 تم الرجوع للقائمة الرئيسية.")
    handle_groups_command(message)


# =================== أمر عرض المقررات والعلامات ===================
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

    # بناء نص ملخص المقررات والعلامات مع تنسيق جميل
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
            f"    🏁 نهائي: {final} (التاريخ: {final_date})\n\n"
        )

    bot.send_message(chat_id, text, parse_mode="Markdown")


if __name__ == "__main__":
    import telebot
    bot.set_my_commands([
        telebot.types.BotCommand("start", "بدء التسجيل وتسجيل الدخول"),
        telebot.types.BotCommand("groups", "عرض قروبات الجامعة والمواد"),
        telebot.types.BotCommand("courses", "عرض المقررات والعلامات"),
    ])
    threading.Thread(target=run_flask).start()
    bot.remove_webhook()
    bot.infinity_polling()
