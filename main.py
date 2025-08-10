import threading
from flask import Flask
from telebot import TeleBot, types
from bot_instance import bot
from database import init_db, get_all_users, get_user, add_user, update_last_msg
from scheduler import start_scheduler
from qou_scraper import QOUScraper

# معرف الأدمن (غيره حسب معرفك في تيليجرام)
ADMIN_CHAT_ID = 6292405444

# الحالة المؤقتة لتخزين بيانات الدخول أثناء التسجيل
user_states = {}

# حالة الإدخال للأدمن عند إرسال رسالة جماعية
admin_states = {}

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

# إرسال قائمة رئيسية مع أزرار (تضيف زر admin فقط للأدمن)
def send_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("👤 تسجيل الدخول"),
        types.KeyboardButton("📚 عرض القروبات"),
        types.KeyboardButton("📖 عرض المقررات والعلامات"),
        types.KeyboardButton("🗓️ جدول المحاضرات")
    )
    if chat_id == ADMIN_CHAT_ID:
        markup.add(types.KeyboardButton("admin"))
    bot.send_message(chat_id, "👋 أهلاً!اختر أحد الخيارات:", reply_markup=markup)

# بدء التسجيل: طلب رقم الطالب
def start_login(chat_id):
    user_states[chat_id] = {}
    bot.send_message(chat_id, "👤 الرجاء إرسال رقمك الجامعي:")

@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    user = get_user(chat_id)
    if user:
        bot.send_message(chat_id, "👋 مرحباً انت قيــد التــــسـجيل!")
    else:
        bot.send_message(chat_id, "👤 لم يتم تسجيلك بعد. الرجاء تسجيل الدخول.")
    send_main_menu(chat_id)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    text = message.text.strip()

    # أولاً: تحقق إذا الأدمن في حالة إرسال رسالة جماعية
    if chat_id == ADMIN_CHAT_ID and chat_id in admin_states and admin_states[chat_id] == "awaiting_broadcast_text":
        # هذا نص الرسالة التي كتبها الأدمن
        broadcast_text = text
        # ترويسة ثابتة
        header = "📢 رسالة عامة من الإدارة:\n\n"
        full_message = header + broadcast_text

        users = get_all_users()
        sent_count = 0
        failed_count = 0
        for user in users:
            try:
                bot.send_message(user['chat_id'], full_message)
                sent_count += 1
            except Exception as e:
                print(f"Failed to send message to {user['chat_id']}: {e}")
                failed_count += 1

        bot.send_message(chat_id, f"✅ تم إرسال الرسالة إلى {sent_count} مستخدم.\n❌ فشل الإرسال إلى {failed_count} مستخدم.")
        admin_states.pop(chat_id)  # انهاء حالة الإدخال
        send_main_menu(chat_id)
        return

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
                    f"{latest['body']}\n\n"
                    f"📬 وسيـــتم اعلامــــك\ي بأي رســالة جــديــدة \n"
                )
                bot.send_message(chat_id, text_msg)
            else:
                bot.send_message(chat_id, "📭 لم يتم العثور على رسائل حالياً.")

        else:
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة البيانات.")

        user_states.pop(chat_id, None)
        send_main_menu(chat_id)
        return

    # التعامل مع أزرار القائمة الرئيسية
    if text == "👤 تسجيل الدخول":
        start_login(chat_id)
        return

    elif text == "📚 عرض القروبات":
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

    elif text == "📖 عرض المقررات والعلامات":
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

    elif text == "🗓️ جدول المحاضرات":
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
        schedule_by_day = {}

        for meeting in schedule:
            day = meeting.get('day')
            time = meeting.get('time', '-')
            course = f"{meeting.get('course_code', '-')}: {meeting.get('course_name', '-')}"
            building = meeting.get('building', '-')
            room = meeting.get('room', '-')

            if not day:
                continue

            if day not in schedule_by_day:
                schedule_by_day[day] = []

            schedule_by_day[day].append(
                f"⏰ {time}\n📘 {course}\n📍 {building} - {room}"
            )

        for day, lectures in schedule_by_day.items():
            text_msg += f"📅 {day}:\n"
            for lecture in lectures:
                text_msg += lecture + "\n\n"

        bot.send_message(chat_id, text_msg, parse_mode="Markdown")

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

    # زر الأدمن الخاص
    elif text == "admin" and chat_id == ADMIN_CHAT_ID:
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("التحليلات"))
        markup.add(types.KeyboardButton("إرسال رسالة"))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "⚙️ قائمة الأدمن: اختر خياراً", reply_markup=markup)
        return

    elif text == "إرسال رسالة" and chat_id == ADMIN_CHAT_ID:
        bot.send_message(chat_id, "✍️ الرجاء كتابة نص الرسالة التي تريد إرسالها لجميع المستخدمين:")
        admin_states[chat_id] = "awaiting_broadcast_text"
        return

    elif text == "التحليلات" and chat_id == ADMIN_CHAT_ID:
        stats = get_bot_stats()
        stats_text = f"""
    📊 *إحصائيات عامة للبوت:*

    - عدد المستخدمين المسجلين: {stats['total_users']}
    - عدد المستخدمين الذين سجلوا دخول ناجح: {stats['users_logged_in']}
    - عدد المستخدمين النشطين (آخر 7 أيام): {stats['active_last_7_days']}
    - عدد الرسائل المرسلة من البوت: {stats['messages_sent']}
    - عدد الرسائل المستلمة من المستخدمين: {stats['messages_received']}
    - المستخدمين الجدد اليوم: {stats['new_today']}
    - المستخدمين الجدد خلال الأسبوع: {stats['new_last_7_days']}
    - المستخدمين الجدد خلال الشهر: {stats['new_last_30_days']}
    - عدد المستخدمين غير النشطين (>7 أيام بدون تفاعل): {stats['inactive_users']}
    - عدد المستخدمين الذين ألغوا الاشتراك: {stats['unsubscribed']}
    - إجمالي الأوامر/الطلبات: {stats['total_commands']}
    - أكثر 5 قروبات طلباً:
    """
        for group, count in stats['top_groups']:
            stats_text += f"  • {group}: {count} مرة\n"

        stats_text += f"""
    - معدل التفاعل اليومي (رسائل مستلمة في اليوم): {stats['avg_daily_interactions']:.2f}
    """
        bot.send_message(chat_id, stats_text, parse_mode="Markdown")
        return


    else:
        bot.send_message(chat_id, "⚠️ لم أفهم الأمر، الرجاء اختيار زر من القائمة.")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    bot.remove_webhook()
    bot.infinity_polling()
