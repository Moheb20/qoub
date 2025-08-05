import threading
from flask import Flask
from database import init_db
from scheduler import start_scheduler
from bot_instance import bot  # يحتوي على كائن TeleBot
from qou_scraper import QOUScraper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# الحالة المؤقتة للمستخدمين
user_states = {}

# روابط قروبات المواد
subject_groups = {
    "مناهج البحث العلمي": "https://chat.whatsapp.com/Ixv647y5WKB8IR43tTWpZc",
    "قواعد الكتابة والترقيم": "https://chat.whatsapp.com/IV0KQVlep5QJ1dBaRoqn5f",
    "تصميم التدريس": "https://chat.whatsapp.com/BoHU1ifJd5n86dRTR1J3Zh",
    "ادارة الصف وتنظيمه": "https://chat.whatsapp.com/FDgewENfci54CutRyr4SEd",
    "الحاسوب في التعليم": "https://chat.whatsapp.com/KlOtrGM8b93JcFekltBPBv",
    "تعديل السلوك": "https://chat.whatsapp.com/BwtqAdepHcpHFWQIt7drhb",
    "الحركة الاسيرة": "https://chat.whatsapp.com/E4j2B4ncNPN2bpT2S1ZFHJ",
    "الحاسوب": "https://chat.whatsapp.com/CPynN3OZm67InIvC3K1BZ4",
    "القياس والتقويم": "https://chat.whatsapp.com/LJfQxUk14BxH1ysxyZTUzK",
    "علم النفس التربوي": "https://chat.whatsapp.com/BglsAZvRlrGH6rCyRLnAoR",
    "طرائق التدريس والتدريب العامة": "https://chat.whatsapp.com/BvAJOUr8fp66VvEWDHXEFG",
    "تكنولوجيا التعليم": "https://chat.whatsapp.com/Gflbw7bjbaf5o8d0bBbz7p",
    "فلسطين والقضية الفلسطينية": "https://chat.whatsapp.com/DZs1DlkzmnJGIf1JlHlDYX",
    "التفكير الابداعي": "https://chat.whatsapp.com/FkvU2389Qzu2vMwDFHrMs4",
    "تعليم اجتماعيات": "https://chat.whatsapp.com/KD7NTx48L2R0WZs0N2r3yX",
    "العلاقات الدولية في الاسلام": "https://chat.whatsapp.com/EfpdyJbX1wS7RhYAzovqW1"
}

# 🔽 أمثلة لإضافة قروبات الجامعة أو التخصصات لاحقًا:
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
init_db()
start_scheduler()

# إعداد Flask
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ البوت يعمل ✔️"

# تشغيل Flask في خيط منفصل
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
        from database import add_user, update_last_msg

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

# أمر /groups يعرض التصنيفات
@bot.message_handler(commands=['groups'])
def handle_groups_command(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("📚 قروبات المواد", callback_data="category:subjects"),
        InlineKeyboardButton("🎓 قروبات التخصصات", callback_data="category:majors"),
        InlineKeyboardButton("🏛 قروبات الجامعة", callback_data="category:university")
    )
    bot.send_message(message.chat.id, "🎯 اختر نوع القروبات:", reply_markup=keyboard)


# التعامل مع اختيار نوع القروب
@bot.callback_query_handler(func=lambda call: call.data.startswith("category:"))
def handle_group_category(call):
    category = call.data.split(":")[1]

    if category == "subjects":
        markup = InlineKeyboardMarkup()
        for name in subject_groups:
            markup.add(InlineKeyboardButton(name, callback_data=f"subject:{name}"))
        bot.send_message(call.message.chat.id, "🧾 اختر المادة للحصول على رابط القروب:", reply_markup=markup)

    elif category == "university":
        markup = InlineKeyboardMarkup()  # ✅ تم إضافة هذا السطر
        for idx, (name, _) in enumerate(university_list):
            markup.add(InlineKeyboardButton(name, callback_data=f"univ_{idx}"))
        bot.send_message(call.message.chat.id, "🏛 اختر قروب الجامعة:", reply_markup=markup)

    elif category == "majors":
        markup = InlineKeyboardMarkup()
        for name in major_groups:
            markup.add(InlineKeyboardButton(name, callback_data=f"major:{name}"))
        bot.send_message(call.message.chat.id, "🧑‍🎓 اختر قروب من قروبات التخصص:", reply_markup=markup)


# التعامل مع اختيار مادة
@bot.callback_query_handler(func=lambda call: call.data.startswith("subject:"))
def handle_subject_selection(call):
    bot.answer_callback_query(call.id)    
    subject = call.data.split("subject:")[1]
    link = subject_groups.get(subject, "❌ الرابط غير متوفر")
    bot.send_message(call.message.chat.id, f"📘 رابط قروب *{subject}*:\n{link}", parse_mode="Markdown")

# التعامل مع قروبات الجامعة
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

# التعامل مع قروبات التخصصات
@bot.callback_query_handler(func=lambda call: call.data.startswith("major:"))
def handle_major_selection(call):
    bot.answer_callback_query(call.id)    
    name = call.data.split("major:")[1]
    link = major_groups.get(name, "❌ الرابط غير متوفر")
    bot.send_message(call.message.chat.id, f"📘 رابط قروب *{name}*:\n{link}", parse_mode="Markdown")

# بدء التشغيل
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.remove_webhook()
    bot.infinity_polling()
