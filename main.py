import threading
import re
from flask import Flask
from telebot import TeleBot, types
from bot_instance import bot
from database import init_db, get_all_users, get_user, add_user, update_last_msg
from scheduler import start_scheduler
from qou_scraper import QOUScraper

# الحالة المؤقتة لتخزين بيانات الدخول أثناء التسجيل
user_states = {}

# روابط القروبات (مقسمة حسب النوع)
groups = {
    "المواد": {
        "مناهج البحث العلمي": "https://chat.whatsapp.com/Ixv647y5WKB8IR43tTWpZc",
        "قواعد الكتابة والترقيم": "https://chat.whatsapp.com/IV0KQVlep5QJ1dBaRoqn5f",
    },
    "التخصصات": {
        "رياضيات": "https://chat.whatsapp.com/FKCxgfaJNWJ6CBnIB30FYO",
    },
    "الجامعة": {
        "طلاب جامعة القدس المفتوحة": "https://chat.whatsapp.com/Bvbnq3XTtnJAFsqJkSFl6e",
    }
}

# تهيئة قاعدة البيانات والجدولة
init_db()
get_all_users()
start_scheduler()

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ البوت يعمل بنجاح!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# إرسال قائمة رئيسية مع أزرار
def send_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("👤 تسجيل الدخول"),
        types.KeyboardButton("📚 عرض القروبات"),
        types.KeyboardButton("📖 عرض المقررات والعلامات"),
        types.KeyboardButton("🗓️ جدول المحاضرات")
    )
    bot.send_message(chat_id, "👋 أهلاً! اختر أحد الخيارات:", reply_markup=markup)

# بدء التسجيل: طلب رقم الطالب
def start_login(chat_id):
    user_states[chat_id] = {}
    bot.send_message(chat_id, "👤 الرجاء إرسال رقمك الجامعي:")

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user = get_user(chat_id)
    if user:
        bot.send_message(chat_id, "👋 مرحباً بك مجددًا!")
    else:
        bot.send_message(chat_id, "👤 لم يتم تسجيلك بعد. الرجاء تسجيل الدخول.")
    send_main_menu(chat_id)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    text = message.text.strip()

    # حالة التسجيل (طلب رقم الطالب)
    if chat_id in user_states and 'student_id' not in user_states[chat_id]:
        user_states[chat_id]['student_id'] = text
        bot.send_message(chat_id, "🔒 الآن، الرجاء إرسال كلمة المرور:")
        return

    # حالة التسجيل (طلب كلمة المرور)
    if chat_id in user_states and 'student_id' in user_states[chat_id] and 'password' not in user_states[chat_id]:
        user_states[chat_id]['password'] = text

        student_id = user_states[chat_id]['student_id']
        password = user_states[chat_id]['password']

        scraper = QOUScraper(student_id, password)
        if scraper.login():
            add_user(chat_id, student_id, password)
            bot.send_message(chat_id, "✅ تم تسجيلك بنجاح!\n🔍 جاري البحث عن آخر رسالة...")

            latest = scraper.fetch_latest_message()
            if latest:
                update_last_msg(chat_id, latest['msg_id'])
                text_msg = (
                    f"📬 آخر رسالة في البريد:\n"
                    f"📧 {latest['subject']}\n"
                    f"📝 {latest['sender']}\n"
                    f"🕒 {latest['date']}\n\n"
                    f"{latest['body']}"
                )
                bot.send_message(chat_id, text_msg)
            else:
                bot.send_message(chat_id, "📭 لم يتم العثور على رسائل حالياً.")

            bot.send_message(chat_id, "📡 سيتم تتبع الرسائل الجديدة وإرسالها تلقائيًا.")
        else:
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة البيانات.")

        user_states.pop(chat_id, None)
        send_main_menu(chat_id)
        return

    # التعامل مع أزرار القائمة الرئيسية
    if text == "تسجيل الدخول":
        start_login(chat_id)
        return

    elif text == "عرض القروبات":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        for group_type in groups.keys():
            markup.add(types.KeyboardButton(group_type))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)
        return

    elif text in groups.keys():
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
        for group_name in groups[text].keys():
            markup.add(types.KeyboardButton(group_name))
        markup.add(types.KeyboardButton("العودة للقروبات"))
        bot.send_message(chat_id, f"📂 القروبات ضمن '{text}': اختر قروب:", reply_markup=markup)
        return

    elif any(text in group_dict for group_dict in groups.values()):
        for group_type, group_dict in groups.items():
            if text in group_dict:
                link = group_dict[text]
                bot.send_message(chat_id, f"🔗 رابط قروب '{text}':\n{link}")
                break
        return

    elif text == "عرض المقررات والعلامات":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return

        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
            return

        courses = scraper.fetch_term_summary_courses()
        if not courses:
            bot.send_message(chat_id, "📭 لم يتم العثور على مقررات أو علامات.")
            return

        text_msg = "📚 *ملخص علامات المقررات الفصلية:*\n\n"
        for c in courses:
            code = c.get('course_code', '-')
            name = c.get('course_name', '-')
            midterm = c.get('midterm_mark', '-')
            final = c.get('final_mark', '-')
            final_date = c.get('final_date', '-')

            text_msg += (
                f"📘 {code} - {name}\n"
                f"   📝 الامتحان النصفي: {midterm}\n"
                f"   🏁 الامتحان النهائي: {final}\n"
                f"   📅 تاريخ النهائي: {final_date}\n\n"
            )
        bot.send_message(chat_id, text_msg, parse_mode="Markdown")
        return

    elif text == "جدول المحاضرات":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return

        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
            return

        schedule = scraper.fetch_lectures_schedule()
        if not schedule:
            bot.send_message(chat_id, "📭 لم يتم العثور على جدول المحاضرات.")
            return

        text_msg = "🗓️ *جدول المحاضرات:*\n\n"
        for lec in schedule:
            day = lec.get('day', '-')
            start = lec.get('start', '-')
            end = lec.get('end', '-')
            course = lec.get('course', '-')
            location = lec.get('location', '-')

            text_msg += f"📅 {day}: {start} - {end}\n📘 {course}\n📍 {location}\n\n"

        bot.send_message(chat_id, text_msg, parse_mode="Markdown")
        return

    elif text == "العودة للقروبات":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        for group_type in groups.keys():
            markup.add(types.KeyboardButton(group_type))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)
        return

    elif text == "العودة للرئيسية":
        send_main_menu(chat_id)
        return

    else:
        bot.send_message(chat_id, "⚠️ لم أفهم الأمر، الرجاء اختيار زر من القائمة.")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.remove_webhook()
    bot.infinity_polling()
