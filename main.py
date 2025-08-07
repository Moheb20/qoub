import threading
from flask import Flask
from database import get_all_users, add_user, update_last_msg, get_user
from scheduler import start_scheduler
from bot_instance import bot  # كائن TeleBot جاهز
from qou_scraper import QOUScraper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

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

@bot.message_handler(func=lambda msg: msg.chat.id in user_states and 'password' not in user_states[msg.chat.id])
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

# عرض القروبات
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

    if category == "subjects":
        markup = InlineKeyboardMarkup()
        for name in subject_groups:
            markup.add(InlineKeyboardButton(name, callback_data=f"subject:{name}"))
        bot.send_message(call.message.chat.id, "🧾 اختر المادة للحصول على رابط القروب:", reply_markup=markup)

    elif category == "university":
        markup = InlineKeyboardMarkup()
        for idx, (name, _) in enumerate(university_list):
            markup.add(InlineKeyboardButton(name, callback_data=f"univ_{idx}"))
        bot.send_message(call.message.chat.id, "🏛 اختر قروب الجامعة:", reply_markup=markup)

    elif category == "majors":
        markup = InlineKeyboardMarkup()
        for name in major_groups:
            markup.add(InlineKeyboardButton(name, callback_data=f"major:{name}"))
        bot.send_message(call.message.chat.id, "🧑‍🎓 اختر قروب من قروبات التخصص:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("subject:"))
def handle_subject_selection(call):
    bot.answer_callback_query(call.id)
    subject = call.data.split("subject:")[1]
    link = subject_groups.get(subject, "❌ الرابط غير متوفر")
    bot.send_message(call.message.chat.id, f"📘 رابط قروب *{subject}*:\n{link}", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("univ_"))
def handle_university_selection(call):
    bot.answer_callback_query(call.id)
    try:
        index = int(call.data.split("_")[1])
        name, link = university_list[index]
        bot.send_message(call.message.chat.id, f"🏫 رابط قروب *{name}*:\n{link}", parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, "❌ حدث خطأ أثناء استرجاع الرابط.")
        print("[university error]", e)

@bot.callback_query_handler(func=lambda call: call.data.startswith("major:"))
def handle_major_selection(call):
    bot.answer_callback_query(call.id)
    name = call.data.split("major:")[1]
    link = major_groups.get(name, "❌ الرابط غير متوفر")
    bot.send_message(call.message.chat.id, f"📘 رابط قروب *{name}*:\n{link}", parse_mode="Markdown")

# أمر عرض المواد مع العلامات
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

    courses = scraper.fetch_courses_with_marks()
    if not courses:
        bot.send_message(chat_id, "📭 لم يتم العثور على مواد حالياً.")
        return

    markup = InlineKeyboardMarkup()
    for idx, course in enumerate(courses):
        markup.add(InlineKeyboardButton(
            text=f"{course['code']} - {course['title']}",
            callback_data=f"course:{idx}"
        ))

    user_states[chat_id] = {'courses': courses}
    bot.send_message(chat_id, "📘 اختر مادة لعرض التفاصيل:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("course:"))
def handle_course_details(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    try:
        index = int(call.data.split(":")[1])
        course = user_states.get(chat_id, {}).get('courses', [])[index]

        if not course:
            bot.send_message(chat_id, "❌ حدث خطأ أثناء تحميل تفاصيل المادة.")
            return

        marks = course.get('marks', {})
        text = f"📘 *{course['code']} - {course['title']}*\n\n"
        text += f"👨‍🏫 الدكتور: {marks.get('instructor', '-')}\n"
        text += f"📅 اليوم: {marks.get('lecture_day', '-')}\n"
        text += f"🕒 الموعد: {marks.get('lecture_time', '-')}\n"
        text += f"🏢 البناية: {marks.get('building', '-')}\n"
        text += f"🏫 القاعة: {marks.get('hall', '-')}\n\n"

        text += f"📝 التعيين الأول: {marks.get('assignment1', '-')}\n"
        text += f"🧪 الامتحان النصفي: {marks.get('midterm', '-')} | 📆 {marks.get('midterm_date', '-')}\n"
        text += f"📝 التعيين الثاني: {marks.get('assignment2', '-')}\n"
        text += f"🧪 الامتحان النهائي: {marks.get('final_mark', '-')} | 📆 {marks.get('final_date', '-')}\n"
        text += f"📋 الحالة: {marks.get('status', '-')}"
        bot.send_message(chat_id, text, parse_mode="Markdown")
    except Exception as e:
        print("[Course Detail Error]", e)
        bot.send_message(chat_id, "❌ تعذر عرض تفاصيل المادة.")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.remove_webhook()
    bot.infinity_polling()
