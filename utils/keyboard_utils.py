from telebot import types
from bot_instance import bot
from config import ADMIN_CHAT_ID
from database import get_categories

def send_main_menu(chat_id):
    """إرسال القائمة الرئيسية مع زر الأدمن للمستخدم المناسب"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("👤 تسجيل الدخول"),
        types.KeyboardButton("📚 عرض القروبات"),
        types.KeyboardButton("📖 عرض المقررات والعلامات"),
        types.KeyboardButton("🗓️ جدول المحاضرات"),
        types.KeyboardButton("📊 عرض بيانات الفصل"),
        types.KeyboardButton("📅 جدول الامتحانات"),
        types.KeyboardButton("🎙️ حلقات النقاش"),
        types.KeyboardButton("📚 الخطط الدراسية"),
        types.KeyboardButton("💰 رصيد الطالب"),
        types.KeyboardButton("📞 أرقام الأقسام وأعضاء الهيئة التدريسية"),
        types.KeyboardButton("✉️ إرسال اقتراح")  
    )
    if chat_id in ADMIN_CHAT_ID:
        markup.add(types.KeyboardButton("admin"))
    bot.send_message(chat_id, "⬇️ القائمة الرئيسية:", reply_markup=markup)

def create_admin_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("التحليلات"))
    markup.add(types.KeyboardButton("إرسال رسالة"))
    markup.add(types.KeyboardButton("إدارة المواعيد"))
    markup.add(types.KeyboardButton("إضافة قروب"))
    markup.add(types.KeyboardButton("🛠️ إدارة الأرقام"))  
    markup.add(types.KeyboardButton("العودة للرئيسية"))
    return markup

def create_deadline_management_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        types.KeyboardButton("➕ إضافة موعد"),
        types.KeyboardButton("✏️ تعديل موعد"),
        types.KeyboardButton("❌ حذف موعد"),
        types.KeyboardButton("📋 عرض كل المواعيد"),
        types.KeyboardButton("العودة للقائمة")
    )
    return markup