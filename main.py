import os
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import json
import arabic_reshaper
from bidi.algorithm import get_display
load_dotenv()
import threading
import logging
from flask import Flask
from telebot import types
from scheduler import start_scheduler
# استيراد المكونات الخاصة بنا
from bot_instance import bot
from database import init_db, get_all_users
from config import PLANS_FILE_PATH

# استيراد معالجات البوت من المجلدات
from handlers import (
    setup_admin_handlers,
    setup_user_handlers,
    setup_contact_handlers,
    setup_deadline_handlers,
    setup_group_handlers
)

from states.user_states import study_plan_states

# ---------- إعداد السجل (logging) ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# تحميل الخطط الدراسية
with open(PLANS_FILE_PATH, "r", encoding="utf-8") as f:
    study_plans = json.load(f)

# ---------- تهيئة قاعدة البيانات والجدولة ----------
init_db()
get_all_users()
start_scheduler()

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ البوت يعمل بنجاح!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# إعداد معالجات البوت
setup_admin_handlers()
setup_user_handlers()
setup_contact_handlers()
setup_deadline_handlers()
setup_group_handlers()

# معالجات إضافية
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

    # معالجة باقي الأوامر التي لم يتم تغطيتها في الملفات الأخرى
    if text == "العودة للرئيسية":
        from utils.helpers import clear_states_for_home
        from utils.keyboard_utils import send_main_menu
        clear_states_for_home(chat_id)
        send_main_menu(chat_id)
        return
    elif text == "العودة للقروبات":
        from utils.keyboard_utils import send_main_menu
        from database import get_categories
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        categories = get_categories()
        for category in categories:
            markup.add(types.KeyboardButton(category))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)
        return
    elif text == "العودة للقائمة" and chat_id in ADMIN_CHAT_ID:
        from utils.keyboard_utils import send_main_menu
        send_main_menu(chat_id)
        return
    else:
        bot.send_message(chat_id, "⚠️ لم أفهم الأمر، الرجاء اختيار زر من القائمة.")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling()
