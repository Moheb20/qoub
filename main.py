
import asyncio
import threading
from flask import Flask, request

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters
)

from database import init_db, add_user, update_last_msg
from qou_scraper import QOUScraper
from scheduler import start_scheduler

TOKEN = "8346251354:AAH3LqivEvbh-DaLmjViyN_ICzlTYb6W1ZM"
WEBHOOK_PATH = f"/{TOKEN}"
WEBHOOK_URL = f"https://qoub.onrender.com{WEBHOOK_PATH}"

# حالة المستخدمين
user_states = {}

# تطبيق Flask
app = Flask(__name__)

# تطبيق تيليجرام
application = Application.builder().token(TOKEN).build()


# ✅ أمر /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_states[chat_id] = {}
    await update.message.reply_text("👤 الرجاء إدخال اسم المستخدم الخاص بك:")


# 📥 استقبال اسم المستخدم
async def handle_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_states and 'student_id' not in user_states[chat_id]:
        user_states[chat_id]['student_id'] = update.message.text.strip()
        await update.message.reply_text("🔒 الآن، الرجاء إدخال كلمة المرور:")
        return


# 📥 استقبال كلمة المرور
async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in user_states and 'student_id' in user_states[chat_id] and 'password' not in user_states[chat_id]:
        user_states[chat_id]['password'] = update.message.text.strip()

        student_id = user_states[chat_id]['student_id']
        password = user_states[chat_id]['password']
        scraper = QOUScraper(student_id, password)

        if scraper.login():
            add_user(chat_id, student_id, password)
            await update.message.reply_text("✅ تم تسجيل بياناتك بنجاح!\n🔍 يتم الآن البحث عن آخر رسالة...")

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
                await update.message.reply_text(text)
            else:
                await update.message.reply_text("📭 لم يتم العثور على رسائل حالياً.")

            await update.message.reply_text("📡 سيتم تتبع الرسائل الجديدة وإرسالها تلقائيًا.")
        else:
            await update.message.reply_text("❌ فشل تسجيل الدخول. تأكد من صحة البيانات.")

        user_states.pop(chat_id, None)


# Webhook endpoint
@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update_data = request.get_json(force=True)
    update = Update.de_json(update_data, application.bot)
    asyncio.run(application.process_update(update))
    return "ok", 200


@app.route("/")
def home():
    return "✅ البوت يعمل ✔️"


def run_flask():
    app.run(host="0.0.0.0", port=10000)


async def run_bot():
    init_db()
    start_scheduler()
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    await application.start()
    print("🔗 Webhook set and bot started!")


# إضافة Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_username))
application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_password))


if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    asyncio.run(run_bot())
