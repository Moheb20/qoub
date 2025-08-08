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
        text = ("👋 مرحباً بك مجددًا!\n"
                "استخدم الأوامر التالية:\n"
                "/groups - لعرض روابط القروبات\n"
                "/courses - لعرض المقررات والعلامات")
        bot.send_message(chat_id, text)
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

# أمر /groups يعرض أزرار روابط القروبات
@bot.message_handler(commands=['groups'])
def handle_groups_command(message):
    chat_id = message.chat.id

    markup = types.InlineKeyboardMarkup(row_width=1)

    # أزرار قروبات المواد
    for name, link in subject_groups.items():
        btn = types.InlineKeyboardButton(text=name, url=link)
        markup.add(btn)

    # أزرار قروبات التخصصات
    for name, link in major_groups.items():
        btn = types.InlineKeyboardButton(text=name, url=link)
        markup.add(btn)

    # أزرار قروبات الجامعة
    for name, link in university_groups.items():
        btn = types.InlineKeyboardButton(text=name, url=link)
        markup.add(btn)

    bot.send_message(chat_id, "📚 اختر القروب الذي تريد الدخول إليه:", reply_markup=markup)

# أمر /courses يعرض المقررات والعلامات نصياً بدون أزرار
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

# لا أزرار أو كولباك أخرى، فقط الأوامر نصية

# بدء الخادم Flask وبوت التيليجرام
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.remove_webhook()
    bot.infinity_polling()
