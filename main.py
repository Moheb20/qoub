import threading
import re
from flask import Flask
from telebot import types
from bot_instance import bot
from database import init_db, get_all_users, get_user, add_user, update_last_msg
from scheduler import start_scheduler
from qou_scraper import QOUScraper

# دالة لتنظيف callback_data: تحويل أي حرف غير أ-ز، أ-ي، 0-9، _ إلى _
def sanitize_callback_data(text):
    return re.sub(r'[^a-zA-Z0-9_]', '_', text)

# حالة مؤقتة لتخزين بيانات الدخول أثناء التسجيل
user_states = {}

# روابط القروبات مقسمة حسب النوع
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

# تهيئة قاعدة البيانات، جلب المستخدمين، بدء الجدولة
init_db()
get_all_users()
start_scheduler()

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ البوت يعمل بنجاح!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# -- معالج الأمر /start مع عرض قائمة أزرار InlineKeyboard --
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user = get_user(chat_id)

    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("👤 تسجيل الدخول", callback_data="login"))
    markup.add(types.InlineKeyboardButton("📚 عرض القروبات", callback_data="groups"))
    markup.add(types.InlineKeyboardButton("📖 عرض المقررات والعلامات", callback_data="courses"))
    markup.add(types.InlineKeyboardButton("🗓️ جدول المحاضرات", callback_data="lectures"))

    if user:
        bot.send_message(chat_id, "👋 مرحباً بك مجددًا! اختر أحد الخيارات:", reply_markup=markup)
    else:
        bot.send_message(chat_id, "👤 لم يتم تسجيلك بعد. الرجاء تسجيل الدخول:", reply_markup=markup)

# -- التعامل مع ضغطات أزرار القائمة الرئيسية --
@bot.callback_query_handler(func=lambda call: True)
def callback_menu_handler(call):
    chat_id = call.message.chat.id
    data = call.data

    if data == "login":
        bot.answer_callback_query(call.id)
        user_states[chat_id] = {}
        bot.send_message(chat_id, "👤 الرجاء إرسال رقمك الجامعي:")

    elif data == "groups":
        bot.answer_callback_query(call.id)
        handle_groups_command(call.message)

    elif data == "courses":
        bot.answer_callback_query(call.id)
        handle_courses(call.message)

    elif data == "lectures":
        bot.answer_callback_query(call.id)
        fetch_lectures_schedule(call.message)

    elif data.startswith("type_"):
        callback_group_type(call)

    elif data.startswith("group_"):
        callback_group_link(call)

    else:
        bot.answer_callback_query(call.id, "زر غير معروف.")

# -- استقبال رقم الطالب أثناء التسجيل --
@bot.message_handler(func=lambda msg: msg.chat.id in user_states and 'student_id' not in user_states[msg.chat.id])
def get_student_id(message):
    chat_id = message.chat.id
    user_states[chat_id]['student_id'] = message.text.strip()
    bot.send_message(chat_id, "🔒 الآن، الرجاء إرسال كلمة المرور:")

# -- استقبال كلمة المرور والتحقق من الدخول --
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

# -- أمر /groups يعرض أزرار لأنواع القروبات --
@bot.message_handler(commands=['groups'])
def handle_groups_command(message):
    chat_id = message.chat.id
    markup = types.InlineKeyboardMarkup(row_width=2)

    for group_type in groups.keys():
        safe_group_type = sanitize_callback_data(group_type)
        btn = types.InlineKeyboardButton(text=group_type, callback_data=f"type_{safe_group_type}")
        markup.add(btn)

    bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)

# -- الرد على اختيار نوع القروب وعرض القروبات التابعة --
@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def callback_group_type(call):
    safe_group_type = call.data[len("type_"):]
    real_group_type = None
    for gt in groups.keys():
        if sanitize_callback_data(gt) == safe_group_type:
            real_group_type = gt
            break

    if real_group_type is None:
        bot.answer_callback_query(call.id, "نوع القروب غير معروف.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for group_name in groups[real_group_type]:
        safe_group_name = sanitize_callback_data(group_name)
        callback_data = f"group_{safe_group_type}_{safe_group_name}"[:64]
        btn = types.InlineKeyboardButton(text=group_name, callback_data=callback_data)
        markup.add(btn)

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"📂 القروبات ضمن '{real_group_type}': اختر قروب:",
        reply_markup=markup
    )
    bot.answer_callback_query(call.id)

# -- الرد على اختيار القروب وإرسال رابط القروب --
@bot.callback_query_handler(func=lambda call: call.data.startswith("group_"))
def callback_group_link(call):
    data = call.data[len("group_"):]
    parts = data.split("_", 1)
    if len(parts) < 2:
        bot.answer_callback_query(call.id, "خطأ في البيانات.")
        return

    safe_group_type, safe_group_name = parts[0], parts[1]
    real_group_type, real_group_name = None, None

    for gt in groups.keys():
        if sanitize_callback_data(gt) == safe_group_type:
            real_group_type = gt
            for gn in groups[gt].keys():
                if sanitize_callback_data(gn) == safe_group_name:
                    real_group_name = gn
                    break
            break

    if real_group_type and real_group_name:
        link = groups[real_group_type][real_group_name]
        bot.send_message(call.message.chat.id, f"🔗 رابط قروب '{real_group_name}':\n{link}")
        bot.answer_callback_query(call.id)
    else:
        bot.answer_callback_query(call.id, "القروب غير موجود.")

# -- أمر /courses يعرض المقررات والعلامات نصياً --
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
        final_date = c.get('final_date', '-')
        text += f"📘 {code} - {name}\n📝 منتصف الفصل: {midterm}\n📝 نهاية الفصل: {final} بتاريخ {final_date}\n\n"

    bot.send_message(chat_id, text, parse_mode="Markdown")

# -- دالة وهمية كمثال لاسترجاع جدول المحاضرات --
def fetch_lectures_schedule(message):
    chat_id = message.chat.id
    # مثال: استدعاء من QOUScraper أو قاعدة بيانات
    text = "📅 جدول المحاضرات:\n- مادة 1: الاثنين 10:00\n- مادة 2: الأربعاء 14:00\n\n(هذه بيانات وهمية للاختبار)"
    bot.send_message(chat_id, text)

# -- دالة وهمية لاسترجاع آخر رسالة، مثلاً لإعادة استخدامها --
def get_latest_message_for_user(chat_id):
    # هنا يمكن استدعاء قاعدة البيانات أو API لجلب آخر رسالة
    return {
        'subject': 'موضوع اختبار',
        'sender': 'البريد الإلكتروني',
        'date': '2025-08-10 12:00',
        'body': 'نص الرسالة هنا...',
        'msg_id': 123456,
    }

# -- نقطة البداية لتشغيل البوت وفلّاسك معاً --
if __name__ == "__main__":
    # تشغيل Flask في Thread منفصل حتى لا يوقف بوت تيليجرام
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # بدء البوت (Polling)
    bot.infinity_polling()
