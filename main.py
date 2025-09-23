import os
import json
import time
import logging
import threading
import arabic_reshaper
from datetime import datetime, date
from bidi.algorithm import get_display
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from flask import Flask
from bs4 import BeautifulSoup
from telebot import types
import random
import secrets

# استيرادات الملفات الداخلية
from bot_instance import bot
from database import (
    init_db, get_all_users, get_bot_stats, get_user, add_user, logout_user,
    update_last_msg, get_all_chat_ids_from_logs, log_chat_id, get_all_deadlines,
    add_deadline, update_deadline, delete_deadline, add_group, get_group_link,
    get_categories, get_groups_by_category, get_deadline_by_id, get_portal_credentials,
    update_portal_data, get_user_branch_and_courses, find_potential_partners,
    clear_portal_data, has_portal_data, get_courses_by_branch, get_portal_stats,
    create_anonymous_chat, add_chat_message, get_chat_partner, end_chat, get_conn
)
from scheduler import start_scheduler, send_reminder_for_new_deadline
from qou_scraper import QOUScraper

# تحميل البيئة
load_dotenv()

# ---------- الإعدادات العامة ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = [6292405444, 1851786931]

# حالات التطبيق
registration_states = {}
session_states = {}  
session_statess = {}   
admin_states = {}
admin_group_states = {}
user_sessions = {}
user_categories_data = {}
user_data = {}
admin_deadline_states = {}
study_plan_states = {}

# تحميل الخطط الدراسية
plans_file_path = os.path.join(os.path.dirname(__file__), "qou.json")
with open(plans_file_path, "r", encoding="utf-8") as f:
    study_plans = json.load(f)

# ---------- التهيئة ----------
init_db()
get_all_users()
start_scheduler()

app = Flask(__name__)

# ================================
# 📋 قسم الدوال المساعدة
# ================================

@app.route("/")
def home():
    return "✅ البوت يعمل بنجاح!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

def log_chat_interaction(chat_id, action):
    """تسجيل تفاعلات المستخدم"""
    logger.info(f"👤 {chat_id} - {action}")

def cleanup_states(chat_id):
    """تنظيف حالات المستخدم"""
    states_to_clean = [
        registration_states, session_states, session_statess,
        admin_states, admin_group_states, user_categories_data,
        user_data, admin_deadline_states, study_plan_states
    ]
    
    for state_dict in states_to_clean:
        state_dict.pop(chat_id, None)

# ================================
# 🏠 قسم القوائم والواجهات
# ================================

def send_main_menu(chat_id):
    """القائمة الرئيسية"""
    user = get_user(chat_id)
    logged_in = bool(user and user.get("student_id"))
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    if not logged_in:
        markup.add(types.KeyboardButton("👤 تسجيل الدخول"))
        bot.send_message(chat_id, "⬇️ الرجاء تسجيل الدخول أولاً:", reply_markup=markup)
    else:
        markup.add(
            types.KeyboardButton("📖 الخدمات الأكاديمية"),
            types.KeyboardButton("📅 التـــقويــم"),
            types.KeyboardButton("🔗 منصة المواد المشتركة"),
            types.KeyboardButton("📚 أخرى"),
            types.KeyboardButton("🚪 تسجيل الخروج")
        )
        if chat_id in ADMIN_CHAT_ID:
            markup.add(types.KeyboardButton("admin"))
        
        bot.send_message(chat_id, "⬇️ القائمة الرئيسية:", reply_markup=markup)

def send_academic_services(chat_id):
    """خدمات أكاديمية"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        "📖 عرض المقررات والعلامات", "🗓️ جدول المحاضرات", "📊 عرض بيانات الفصل",
        "📅 جدول الامتحانات", "🎙️ حلقات النقاش", "📖 الخطة الدراسية",
        "📚 الخطط الدراسية", "💰 رصيد الطالب", "⬅️ عودة للرئيسية"
    ]
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(types.KeyboardButton(buttons[i]), types.KeyboardButton(buttons[i+1]))
        else:
            markup.row(types.KeyboardButton(buttons[i]))
    
    bot.send_message(chat_id, "⬇️ اختر خدمة أكاديمية:", reply_markup=markup)

def send_cel_services(chat_id):
    """خدمات التقويم"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    current_week_text = QOUScraper.get_current_week_type()
    markup.add(
        types.KeyboardButton("📅 التقويم الحالي"),
        types.KeyboardButton("📅 عرض التقويم القادم للفصل الحالي")
    )
    markup.add(types.KeyboardButton(f"🟢 {current_week_text}"))
    
    if chat_id in session_statess:
        scraper = session_statess[chat_id]
        delay_status = scraper.get_delay_status()
        markup.add(types.KeyboardButton(f"📅 {delay_status}"))
    else:
        markup.add(types.KeyboardButton("📅 حالة التأجيل: ❌ غير متوفرة"))
    
    markup.add(types.KeyboardButton("🔄 تحديث حالة التأجيل"))
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))

    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def send_manasa_services(chat_id):
    """منصة المواد المشتركة"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("👥 منصة المواد المشتركة"),
        types.KeyboardButton("🔗 ربط الحساب بمنصة المواد المشتركة"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def send_other_services(chat_id):
    """خدمات أخرى"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📚 عرض القروبات"),
        types.KeyboardButton("✉️ إرسال اقتراح"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def send_academic_stats_menu(chat_id):
    """إحصائيات أكاديمية"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        "📊 إحصائياتي", "📚 مقرراتي", "📌 مقررات حالية",
        "🎯 نسبة الإنجاز", "📋 الخطة الدراسية", 
        "🔄 تحديث بياناتي", "⬅️ عودة للرئيسية"
    ]
    
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.row(types.KeyboardButton(buttons[i]), types.KeyboardButton(buttons[i+1]))
        else:
            markup.row(types.KeyboardButton(buttons[i]))
    
    bot.send_message(chat_id, "⬇️ اختر من القائمة:", reply_markup=markup)

# ================================
# 🔐 قسم إدارة المستخدمين
# ================================

def start_login(chat_id):
    """بدء تسجيل الدخول"""
    registration_states[chat_id] = {"stage": "awaiting_student_id"}
    bot.send_message(chat_id, "👤 الرجاء إرسال رقمك الجامعي:")

def handle_login_stages(chat_id, text):
    """معالجة مراحل تسجيل الدخول"""
    if chat_id not in registration_states:
        return False
    
    stage = registration_states[chat_id].get("stage")
    
    if stage == "awaiting_student_id":
        registration_states[chat_id]["student_id"] = text
        registration_states[chat_id]["stage"] = "awaiting_password"
        bot.send_message(chat_id, "🔒 الآن، الرجاء إرسال كلمة المرور:")
        return True
        
    elif stage == "awaiting_password":
        registration_states[chat_id]["password"] = text
        student_id = registration_states[chat_id].get("student_id")
        password = registration_states[chat_id].get("password")
        
        try:
            scraper = QOUScraper(student_id, password)
            if scraper.login():
                add_user(chat_id, student_id, password)
                user_sessions[chat_id] = {"logged_in": True}
                bot.send_message(chat_id, "✅ تم تسجيلك بنجاح!\n🔍 جاري البحث عن آخر رسالة...")
                
                # جلب آخر رسالة
                latest = scraper.fetch_latest_message()
                if latest:
                    update_last_msg(chat_id, latest["msg_id"])
                    text_msg = f"📬 آخـــر رســالـــة في البـــريـــد:\n📧 {latest['subject']}\n📝 {latest['sender']}\n🕒 {latest['date']}\n\n{latest['body']}\n\n📬 وسيـــتم اعلامــــك\ي بأي رســالة جــديــدة \n"
                    bot.send_message(chat_id, text_msg)
                else:
                    bot.send_message(chat_id, "📭 لم يتم العثور على رسائل حالياً.")
            else:
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة البيانات.")
        except Exception as e:
            logger.error(f"Login error for {chat_id}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء محاولة تسجيل الدخول.")
        finally:
            registration_states.pop(chat_id, None)
            send_main_menu(chat_id)
        return True
    
    return False

# ================================
# ⚙️ قسم إدارة الأدمن
# ================================

def handle_admin_commands(chat_id, text):
    """معالجة أوامر الأدمن"""
    if chat_id not in ADMIN_CHAT_ID:
        return False
    
    # قائمة الأدمن
    if text == "admin":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        markup.add(
            types.KeyboardButton("التحليلات"),
            types.KeyboardButton("إرسال رسالة"),
            types.KeyboardButton("إدارة المواعيد"),
            types.KeyboardButton("إضافة قروب"),
            types.KeyboardButton("العودة للرئيسية")
        )
        bot.send_message(chat_id, "⚙️ قائمة الأدمن: اختر خياراً", reply_markup=markup)
        return True
    
    # التحليلات
    elif text == "التحليلات":
        stats = get_bot_stats()
        stats_text = f"📊 *إحصائيات عامة للبوت:*\n\n- عدد المستخدمين المسجلين: {stats['total_users']}\n- المستخدمين الجدد اليوم: {stats['new_today']}\n- المستخدمين الجدد خلال الأسبوع: {stats['new_last_7_days']}\n- المستخدمين الجدد خلال الشهر: {stats['new_last_30_days']}\n- عدد المستخدمين غير النشطين: {stats['inactive_users']}\n"
        bot.send_message(chat_id, stats_text, parse_mode="Markdown")
        return True
    
    # إرسال رسالة جماعية
    elif text == "إرسال رسالة":
        bot.send_message(chat_id, "✍️ الرجاء كتابة نص الرسالة التي تريد إرسالها لجميع المستخدمين:")
        admin_states[chat_id] = "awaiting_broadcast_text"
        return True
    
    return False

def handle_admin_broadcast(chat_id, text):
    """معالجة البث الجماعي للأدمن"""
    if chat_id in ADMIN_CHAT_ID and admin_states.get(chat_id) == "awaiting_broadcast_text":
        broadcast_text = text
        header = "📢 رسالة عامة من الإدارة:\n\n"
        full_message = header + broadcast_text

        chat_ids = get_all_chat_ids_from_logs()
        sent_count = 0
        failed_count = 0
        successful_users = []

        for target_chat_id in chat_ids:
            try:
                bot.send_message(target_chat_id, full_message)
                sent_count += 1
                user_info = bot.get_chat(target_chat_id)
                username = f"@{user_info.username}" if user_info.username else "—"
                full_name = user_info.first_name or ""
                if user_info.last_name:
                    full_name += f" {user_info.last_name}"
                successful_users.append((str(target_chat_id), username, full_name))
            except Exception as e:
                logger.error(f"Failed to send to {target_chat_id}: {e}")
                failed_count += 1

        # إعداد التقرير
        report_text = f"تم ارسال الرسالة بنجاح إلى {sent_count} مستخدم\n❌ فشل الإرسال إلى {failed_count} مستخدم."
        
        if len(report_text) > 4000:
            with open("broadcast_report.txt", "w", encoding="utf-8") as f:
                f.write(report_text)
            with open("broadcast_report.txt", "rb") as f:
                bot.send_document(chat_id, f)
        else:
            bot.send_message(chat_id, report_text)

        admin_states.pop(chat_id, None)
        send_main_menu(chat_id)
        return True
    
    return False

# ================================
# 📚 قسم القروبات والبحث
# ================================

def handle_groups_search(chat_id, text):
    """معالجة البحث في القروبات"""
    if text == "📚 عرض القروبات":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        categories = get_categories()
        for category in categories:
            markup.add(types.KeyboardButton(category))
        markup.add(types.KeyboardButton("🔍 بحث في القروبات"))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)
        return True
    
    elif text in get_categories():
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        groups_in_category = get_groups_by_category(text)
        for group_id, group_name, link in groups_in_category:
            markup.add(types.KeyboardButton(group_name))
        markup.add(types.KeyboardButton("العودة للقروبات"))
        bot.send_message(chat_id, f"📂 القروبات ضمن '{text}': اختر قروب:", reply_markup=markup)
        return True
    
    elif text == "العودة للقروبات":
        categories = get_categories()
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        for category in categories:
            markup.add(types.KeyboardButton(category))
        markup.add(types.KeyboardButton("🔍 بحث في القروبات"))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)
        return True
    
    elif text == "🔍 بحث في القروبات":
        msg = bot.send_message(chat_id, "🔍 اكتب كلمة للبحث في القروبات:")
        bot.register_next_step_handler(msg, process_search)
        return True
    
    # عرض رابط القروب
    link = get_group_link(text)
    if link:
        bot.send_message(chat_id, f"🔗 رابط قروب '{text}':\n{link}")
        return True
    
    return False

def process_search(message):
    """معالجة البحث في القروبات"""
    chat_id = message.chat.id
    search_term = message.text.strip()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, link FROM groups WHERE name ILIKE %s ORDER BY name", (f"%{search_term}%",))
            results = cur.fetchall()

    if results:
        response = "🔍 نتائج البحث:\n\n"
        for name, link in results:
            response += f"• {name}\n{link}\n\n"
        bot.send_message(chat_id, response)
    else:
        bot.send_message(chat_id, "❌ لا توجد نتائج")

# ================================
# 🎯 قسم الخدمات الأكاديمية
# ================================

def handle_academic_services(chat_id, text):
    """معالجة الخدمات الأكاديمية"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start أولاً.")
        return True

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
            return True

        # عرض المقررات والعلامات
        if text == "📖 عرض المقررات والعلامات":
            courses = scraper.fetch_term_summary_courses()
            if not courses:
                bot.send_message(chat_id, "📭 لم يتم العثور على مقررات أو علامات.")
                return True

            text_msg = "📚 *ملخص علامات المقررات الفصلية:*\n\n"
            for c in courses:
                text_msg += f"📘 {c.get('course_code', '-')} - {c.get('course_name', '-')}\n📝 علامــــة النـــصفي : {c.get('midterm_mark', '-')}\n🏁 العـــلامـــــة النهـــائية : {c.get('final_mark', '-')}\n📅 تـــــاريـــخ وضع العلامة النــــهائية : {c.get('final_date', '-')}\n\n"
            
            bot.send_message(chat_id, text_msg, parse_mode="Markdown")
            return True

        # جدول المحاضرات
        elif text == "🗓️ جدول المحاضرات":
            schedule = scraper.fetch_lectures_schedule()
            if not schedule:
                bot.send_message(chat_id, "📭 لم يتم العثور على جدول المحاضرات.")
                return True

            days_order = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
            schedule_by_day = {}

            for meeting in schedule:
                day = meeting.get('day', '').strip() or "غير محدد"
                time = meeting.get('time', '--:-- - --:--')
                course_name = meeting.get('course_name', 'غير محدد')
                building = meeting.get('building', '')
                room = meeting.get('room', '')
                lecturer = meeting.get('lecturer', '')

                entry_text = f"📘 {course_name}\n⏰ {time}\n"
                if building or room:
                    entry_text += f"📍 {building} - {room}\n"
                if lecturer:
                    entry_text += f"👨‍🏫 {lecturer}"

                schedule_by_day.setdefault(day, []).append(entry_text)

            text_msg = "🗓️ *جدول المحاضرات:*\n\n"
            for day in days_order:
                if day in schedule_by_day:
                    text_msg += f"📅 *{day}:*\n"
                    for entry in schedule_by_day[day]:
                        text_msg += f"{entry}\n\n"

            for day, entries in schedule_by_day.items():
                if day not in days_order:
                    text_msg += f"📅 *{day}:*\n"
                    for entry in entries:
                        text_msg += f"{entry}\n\n"

            keyboard = types.InlineKeyboardMarkup()
            show_schedule_btn = types.InlineKeyboardButton(text="📢 عرض المحاضرات القادمة", callback_data="show_upcoming_lectures")
            keyboard.add(show_schedule_btn)

            bot.send_message(chat_id, text_msg, parse_mode="Markdown", reply_markup=keyboard)
            return True

        # بيانات الفصل
        elif text == "📊 عرض بيانات الفصل":
            stats = scraper.fetch_term_summary_stats()
            if not stats:
                bot.send_message(chat_id, "📭 لم يتم العثور على بيانات الفصل.")
                return True

            term = stats['term']
            cumulative = stats['cumulative']
            msg = f"📊 *البيانــــات الفـــصليـة والــــتراكــمية*\n- 🧾 النـــــوع: {term['type']}\n- 🕒 المسجــل: {term['registered_hours']} س.\n- ✅ المجتــاز: {term['passed_hours']} س.\n- 🧮 المحتسبــة: {term['counted_hours']}\n- ❌ الراســب: {term['failed_hours']}\n- 🚪 المنســحب: {term['withdrawn_hours']}\n- 🏅 النقــاط: {term['points']}\n- 📈 المعــدل: {term['gpa']}\n- 🏆 لوحــة الشــرف: {term['honor_list']}\n\n📘 *البيانــات التراكــمية:*\n- 🧾 النــوع: {cumulative['type']}\n- 🕒 المســجل: {cumulative['registered_hours']} س.\n- ✅ المجــتاز: {cumulative['passed_hours']} س.\n- 🧮 المحتــسبة: {cumulative['counted_hours']}\n- ❌ الراســب: {cumulative['failed_hours']}\n- 🚪 المنسحـــب: {cumulative['withdrawn_hours']}\n- 🏅 النقــاط: {cumulative['points']}\n- 📈 المعــدل: {cumulative['gpa']}\n- 🏆 لوحــة الشــرف: {cumulative['honor_list']}\n"

            bot.send_message(chat_id, msg, parse_mode="Markdown")
            return True

        # حلقات النقاش
        elif text == "🎙️ حلقات النقاش":
            sessions = scraper.fetch_discussion_sessions()
            if not sessions:
                bot.send_message(chat_id, "📭 لا يوجد حلقات نقاش حالياً.")
                return True

            msg = "🎙️ *جــــميـــع حـلـقـات الــنـقـاش:*\n\n"
            for s in sessions:
                msg += f"📘 {s['course_name']} ({s['course_code']})\n📅 {s['date']} 🕒 {s['time']}\n\n"
            
            bot.send_message(chat_id, msg, parse_mode="Markdown")
            return True

        # رصيد الطالب
        elif text == "💰 رصيد الطالب":
            balance_pdf_bytes = scraper.fetch_balance_table_pdf()
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
            markup.add("📊 الإجمالي", "🏠 العودة للرئيسية")

            if balance_pdf_bytes:
                balance_pdf_bytes.name = "رصيد_الطالب.pdf"
                bot.send_document(chat_id, document=balance_pdf_bytes, reply_markup=markup)
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على بيانات الرصيد", reply_markup=markup)
            return True

        # الإجمالي
        elif text == "📊 الإجمالي":
            totals_text = scraper.fetch_balance_totals()
            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            markup.add("🏠 العودة للرئيسية")
            bot.send_message(chat_id, totals_text, reply_markup=markup)
            return True

    except Exception as e:
        logger.error(f"Academic service error for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب البيانات.")
    
    return False

# ================================
# 📞 المعالجات الرئيسية
# ================================

@bot.message_handler(commands=["start"])
def handle_start(message):
    """معالج أمر /start"""
    chat_id = message.chat.id
    username = message.from_user.username or "بدون اسم مستخدم"
    user = get_user(chat_id)

    log_chat_id(chat_id)
    
    if not user:
        add_user(chat_id, student_id="", password="", registered_at=datetime.utcnow().isoformat())
        bot.send_message(chat_id, "👤 لم يتم تسجيلك بعد. الرجاء تسجيل الدخول.")
        
        # إشعار الأدمن
        admin_message = f"🚨 مستخدم جديد بدأ استخدام البوت!\n\nchat_id: {chat_id}\nUsername: @{username}"
        for admin_id in ADMIN_CHAT_ID:
            try:
                bot.send_message(admin_id, admin_message)
            except Exception as e:
                logger.error(f"Error sending to admin {admin_id}: {e}")
    
    send_main_menu(chat_id)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """المعالج الرئيسي لجميع الرسائل"""
    chat_id = message.chat.id
    text = (message.text or "").strip()
    
    log_chat_interaction(chat_id, text)
    
    # 1. معالجة المحادثات النشطة أولاً
    if handle_active_chats(chat_id, text):
        return
        
    # 2. معالجة بث الأدمن
    if handle_admin_broadcast(chat_id, text):
        return
        
    # 3. معالجة تسجيل الدخول
    if handle_login_stages(chat_id, text):
        return
        
    # 4. معالجة أوامر الأدمن
    if handle_admin_commands(chat_id, text):
        return
        
    # 5. معالجة القروبات والبحث
    if handle_groups_search(chat_id, text):
        return
        
    # 6. معالجة الخدمات الأكاديمية
    if handle_academic_services(chat_id, text):
        return
        
    # 7. معالجة الأزرار العامة
    handle_general_buttons(chat_id, text)

def handle_active_chats(chat_id, text):
    """معالجة المحادثات النشطة"""
    if chat_id in user_sessions and user_sessions[chat_id].get('in_chat'):
        if text == "✖️ إنهاء المحادثة":
            end_active_chat(chat_id)
            return True
            
        # إرسال رسالة في المحادثة النشطة
        chat_token = user_sessions[chat_id]['chat_token']
        partner_id = user_sessions[chat_id]['partner_id']
        
        add_chat_message(chat_token, chat_id, text)
        
        try:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("✖️ إنهاء المحادثة")
            bot.send_message(partner_id, f"👤 [مجهول]: {text}", reply_markup=markup)
        except Exception as e:
            bot.send_message(chat_id, "❌ تعذر إرسال الرسالة.")
            del user_sessions[chat_id]
        
        return True
    return False

def end_active_chat(chat_id):
    """إنهاء المحادثة النشطة"""
    if chat_id in user_sessions and user_sessions[chat_id].get('in_chat'):
        chat_token = user_sessions[chat_id]['chat_token']
        partner_id = user_sessions[chat_id]['partner_id']
        
        end_chat(chat_token)
        
        if partner_id in user_sessions:
            del user_sessions[partner_id]
        if chat_id in user_sessions:
            del user_sessions[chat_id]
        
        try:
            bot.send_message(partner_id, "❌ الطرف الآخر أنهى المحادثة")
            send_main_menu(partner_id)
        except:
            pass
        
        bot.send_message(chat_id, "✅ تم إنهاء المحادثة")
        send_main_menu(chat_id)

def handle_general_buttons(chat_id, text):
    """معالجة الأزرار العامة"""
    # الأزرار الرئيسية
    if text == "👤 تسجيل الدخول":
        start_login(chat_id)
    elif text == "📖 الخدمات الأكاديمية":
        send_academic_services(chat_id)
    elif text == "📚 أخرى":
        send_other_services(chat_id)
    elif text == "📅 التـــقويــم":
        send_cel_services(chat_id)
    elif text == "🔗 منصة المواد المشتركة":
        send_manasa_services(chat_id)
    elif text == "🏠 الرئيسية":
        cleanup_states(chat_id)
        send_main_menu(chat_id)
    elif text == "🚪 تسجيل الخروج":
        logout_user(chat_id)
        bot.send_message(chat_id, "✅ تم تسجيل الخروج بنجاح!")
        send_main_menu(chat_id)
    elif text == "✉️ إرسال اقتراح":
        bot.send_message(chat_id, "📬 لإرسال اقتراح، اضغط على الرابط التالي للتواصل عبر بوت الاقتراحات:\nhttps://t.me/QOUSUGBOT")
    else:
        bot.send_message(chat_id, "⚠️ لم أفهم الأمر، الرجاء اختيار زر من القائمة.")

# ================================
# 🚀 تشغيل التطبيق
# ================================

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()    
    try:
        bot.remove_webhook()
    except Exception:
        pass
    
    logger.info("🚀 بدء تشغيل البوت...")
    bot.infinity_polling()
