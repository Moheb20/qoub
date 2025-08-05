# main.py

import threading
from flask import Flask
from database import init_db
from scheduler import start_scheduler
from bot_instance import bot  # هذا يحتوي على كائن TeleBot
from qou_scraper import QOUScraper

# الحالة المؤقتة للمستخدمين
user_states = {}

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

# وظائف بوت تيليجرام
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

# بدء التشغيل

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()

    # إزالة الـ Webhook لتجنب التعارض مع polling
    bot.remove_webhook()

    # تشغيل البوت باستخدام polling
    bot.infinity_polling()
