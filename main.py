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
from bs4 import BeautifulSoup
from flask import Flask
from telebot import types
from bot_instance import bot
# إضف مع باقي الاستيرادات
from database import create_anonymous_chat, add_chat_message, get_chat_partner, end_chat
import random
import secrets
from database import (
    init_db,
    get_all_users,
    get_bot_stats,
    get_user,
    add_user,
    logout_user,
    update_last_msg,
    get_all_chat_ids_from_logs,
    log_chat_id,
    get_all_deadlines,
    add_deadline,
    update_deadline,
    delete_deadline,
    add_group,
    get_group_link,
    get_categories,
    get_groups_by_category,
    get_deadline_by_id,
    get_portal_credentials,      # لجلب بيانات الدخول
    update_portal_data,          # لتحديث بيانات البوابة
    get_user_branch_and_courses, # لجلب الفرع والمواد
    find_potential_partners,     # للبحث عن زملاء دراسة
    clear_portal_data,           # لمسح بيانات البوابة (اختياري)
    has_portal_data,             # للتحقق من وجود بيانات (اختياري)
    get_courses_by_branch,       # لجرد المواد حسب الفرع (اختياري)
    get_portal_stats,


)
from scheduler import start_scheduler
from scheduler import send_reminder_for_new_deadline
from qou_scraper import QOUScraper
from datetime import date, datetime
import time
# ---------- إعداد السجل (logging) ----------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
admin_deadline_states = {}


# ---------- إعداد المتغيرات العامة ----------
ADMIN_CHAT_ID = [6292405444, 1851786931]  # عدله حسب معرف الأدمن عندك

# فصل حالات التسجيل عن حالات الجلسة (avoid overwriting)
registration_states = {}  # للحالات المتعلقة بعملية التسجيل (login)
session_states = {}       # لحالات الجلسة بعد التسجيل (اختيار الفصل، نوع الامتحان...) 

# حالة الإدخال للأدمن عند إرسال رسالة جماعية
admin_states = {}
# حفظ حالة الأدمن عند إضافة/تعديل/حذف القروبات
admin_group_states = {}
user_sessions = {}
user_data = {}


plans_file_path = os.path.join(os.path.dirname(__file__), "qou.json")
with open(plans_file_path, "r", encoding="utf-8") as f:
    study_plans = json.load(f)

# حالة تخزين اختيار الكلية لكل مستخدم
study_plan_states = {}
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



def send_main_menu(chat_id):
    """إرسال القائمة الرئيسية مع مراعاة حالة تسجيل الدخول من قاعدة البيانات"""
    user = get_user(chat_id)  # استدعاء دالة تجيب بيانات المستخدم من DB

    # تحقق إذا المستخدم مسجل
    logged_in = bool(user and user.get("student_id"))

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    if not logged_in:
        # المستخدم غير مسجل → يظهر فقط زر تسجيل الدخول
        markup.add(types.KeyboardButton("👤 تسجيل الدخول"))
        bot.send_message(chat_id, "⬇️ الرجاء تسجيل الدخول أولاً:", reply_markup=markup)
    else:
        markup.add(types.KeyboardButton("📖 الخدمات الأكاديمية"))
        markup.add(types.KeyboardButton("📅 التـــقويــم"))
        markup.add(types.KeyboardButton("🔗 منصة المواد المشتركة"))  # ← الزر الجديد
        markup.add(types.KeyboardButton("📚 أخرى"))
        markup.add(types.KeyboardButton("🚪 تسجيل الخروج"))
        if chat_id in ADMIN_CHAT_ID:
            markup.add(types.KeyboardButton("admin"))

        bot.send_message(chat_id, "⬇️ القائمة الرئيسية:", reply_markup=markup)
        

def send_academic_stats_menu(chat_id):
    """القائمة الفرعية لعرض الخدمات المتعلقة بالإحصائيات والمقررات"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    # إضافة الأزرار حسب طلبك
    markup.add(
        types.KeyboardButton("📊 إحصائياتي"),
        types.KeyboardButton("📚 مقرراتي"),
        types.KeyboardButton("📌 مقررات حالية"),
        types.KeyboardButton("🎯 نسبة الإنجاز"),
        types.KeyboardButton("📋 الخطة الدراسية"),
        types.KeyboardButton("🔄 تحديث بياناتي"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )

    bot.send_message(chat_id, "⬇️ اختر من القائمة:", reply_markup=markup)
    
def send_academic_services(chat_id):
    """القائمة الفرعية للخدمات الأكاديمية"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📖 عرض المقررات والعلامات"),
        types.KeyboardButton("🗓️ جدول المحاضرات"),
        types.KeyboardButton("📊 عرض بيانات الفصل"),
        types.KeyboardButton("📅 جدول الامتحانات"),
        types.KeyboardButton("🎙️ حلقات النقاش"),
        types.KeyboardButton("📖 الخطة الدراسية"),
        types.KeyboardButton("📚 الخطط الدراسية"),
        types.KeyboardButton("💰 رصيد الطالب"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة أكاديمية:", reply_markup=markup)


def send_cel_services(chat_id):
    """القائمة الفرعية للخدمات الأكاديمية والجدول والتقويم"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    # أزرار التقويم
    markup.add(
        types.KeyboardButton("📅 التقويم الحالي"),
        types.KeyboardButton("📅 عرض التقويم القادم للفصل الحالي")
    )
    
    # زر نوع الأسبوع الحالي (غير قابل للضغط على أنه إجراء، فقط عرض)
    current_week_text = QOUScraper.get_current_week_type()
    markup.add(types.KeyboardButton(f"🟢 {current_week_text}"))

    # زر العودة
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))

    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)


def send_manasa_services(chat_id):
    """القائمة الفرعية للخدمات الأكاديمية والجدول والتقويم"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        # أزرار التقويم
    markup.add(
        types.KeyboardButton("👥 منصة المواد المشتركة"),
        types.KeyboardButton("🔗 ربط الحساب بمنصة المواد المشتركة")
    )
        # زر العودة
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
    
    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def send_other_services(chat_id):
    """القائمة الفرعية للخدمات الأخرى"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📚 عرض القروبات"),
        types.KeyboardButton("✉️ إرسال اقتراح"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)
    



def start_login(chat_id):
    """ابدأ مسار تسجيل الدخول للمستخدم: نحفظه في registration_states"""
    registration_states[chat_id] = {"stage": "awaiting_student_id"}
    bot.send_message(chat_id, "👤 الرجاء إرسال رقمك الجامعي:")


def clear_states_for_home(chat_id):
    """نمسح حالات الجلسة والتسجيل للمستخدم عند العودة للرئيسية"""
    registration_states.pop(chat_id, None)
    session_states.pop(chat_id, None)

# ---------- معالج الأوامر والرسائل ----------
@bot.message_handler(commands=["start"])
def handle_start(message):
    log_chat_id(message.chat.id)
    chat_id = message.chat.id
    username = message.from_user.username or "بدون اسم مستخدم"
    user = get_user(chat_id)

    if user:
        bot.send_message(chat_id, "👋  مرحــــباً!  ")
    else:
        # أضف المستخدم إلى قاعدة البيانات (يمكن ترك student_id و password فارغين مؤقتًا)
        add_user(chat_id, student_id="", password="", registered_at=datetime.utcnow().isoformat())
        
        bot.send_message(chat_id, "👤 لم يتم تسجيلك بعد. الرجاء تسجيل الدخول.")
        
        admin_message = (
            f"🚨 مستخدم جديد بدأ استخدام البوت!\n\n"
            f"chat_id: {chat_id}\n"
            f"Username: @{username}"
        )
        for admin_id in ADMIN_CHAT_ID:
            try:
                bot.send_message(admin_id, admin_message)
            except Exception as e:
                print(f"خطأ في إرسال الرسالة للأدمن {admin_id}: {e}")

    # إرسال القائمة الرئيسية للمستخدم
    send_main_menu(chat_id)
@bot.message_handler(commands=['end'])
def handle_end_chat(message):
    chat_id = message.chat.id
    
    if chat_id in user_sessions and user_sessions[chat_id].get('in_chat'):
        chat_token = user_sessions[chat_id]['chat_token']
        partner_id = user_sessions[chat_id]['partner_id']
        
        # إنهاء المحادثة في الداتابيز
        end_chat(chat_token)
        
        # إشعار للطرف الآخر
        try:
            bot.send_message(partner_id, "❌ الطرف الآخر أنهى المحادثة")
        except:
            pass
        
        bot.send_message(chat_id, "✅ تم إنهاء المحادثة")
        del user_sessions[chat_id]
    else:
        bot.send_message(chat_id, "❌ لا توجد محادثة نشطة")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()
    
    # 1. أولاً: التحقق إذا كان المستخدم في محادثة نشطة
    if chat_id in user_sessions and user_sessions[chat_id].get('in_chat'):
        # إذا كتب /end استدعي معالج الإنتهاء
        if text == '/end':
            handle_end_chat(message)
            return
            
        chat_token = user_sessions[chat_id]['chat_token']
        partner_id = user_sessions[chat_id]['partner_id']
        
        # حفظ الرسالة في الداتابيز
        add_chat_message(chat_token, chat_id, text)
        
        # إرسال الرسالة للشريك
        try:
            bot.send_message(partner_id, f"👤 [مجهول]: {text}")
        except Exception as e:
            bot.send_message(chat_id, "❌ تعذر إرسال الرسالة.可能 انتهت المحادثة.")
            del user_sessions[chat_id]
        
        return  # توقف هنا ولا تكمل للمعالجات الأخرى
    
    # 2. ثانياً: معالجات الأدمن (الكود الحالي)
    if chat_id in ADMIN_CHAT_ID and admin_states.get(chat_id) == "awaiting_broadcast_text":
        broadcast_text = text
        header = "📢 رسالة عامة من الإدارة:\n\n"
        full_message = header + broadcast_text

        chat_ids = get_all_chat_ids_from_logs()
        sent_count = 0
        failed_count = 0
        successful_users = []  # لتجميع بيانات المستخدمين الناجحين

        for target_chat_id in chat_ids:
            try:
                bot.send_message(target_chat_id, full_message)
                sent_count += 1

                # جلب معلومات المستخدم
                user_info = bot.get_chat(target_chat_id)
                user_id = target_chat_id
                username = f"@{user_info.username}" if user_info.username else "—"
                full_name = user_info.first_name or ""
                if user_info.last_name:
                    full_name += f" {user_info.last_name}"

                successful_users.append((str(user_id), username, full_name))

            except Exception as e:
                logger.exception(f"Failed to send message to {target_chat_id}: {e}")
                failed_count += 1

        # إعداد الجدول
        header_text = "تم ارسال الرسالة بنجاح إلى:\n"
        table_header = f"{'Chat ID':<15} | {'Username':<15} | {'Name'}\n"
        separator = "-" * 50 + "\n"
        table_rows = ""

        for user_id, username, full_name in successful_users:
            table_rows += f"{user_id:<15} | {username:<15} | {full_name}\n"

        report_text = header_text + table_header + separator + table_rows
        report_text += f"\n❌ فشل الإرسال إلى {failed_count} مستخدم." if failed_count else ""

        # إذا طول الرسالة كبير، قسمها أو أرسلها كملف
        if len(report_text) > 4000:
            with open("broadcast_report.txt", "w", encoding="utf-8") as f:
                f.write(report_text)
            with open("broadcast_report.txt", "rb") as f:
                bot.send_document(chat_id, f)
        else:
            bot.send_message(chat_id, f"```{report_text}```", parse_mode="Markdown")

        admin_states.pop(chat_id, None)
        send_main_menu(chat_id)
        return
    


    # --- مسار التسجيل (مفصول) ---
    if chat_id in registration_states:
        stage = registration_states[chat_id].get("stage")

        # استقبال رقم الطالب
        if stage == "awaiting_student_id":
            registration_states[chat_id]["student_id"] = text
            registration_states[chat_id]["stage"] = "awaiting_password"
            bot.send_message(chat_id, "🔒 الآن، الرجاء إرسال كلمة المرور:")
            return

        # استقبال كلمة المرور ومحاولة تسجيل الدخول
        if stage == "awaiting_password":
            registration_states[chat_id]["password"] = text
            student_id = registration_states[chat_id].get("student_id")
            password = registration_states[chat_id].get("password")

            try:
                scraper = QOUScraper(student_id, password)
                if scraper.login():
                    add_user(chat_id, student_id, password)
                    user_sessions[chat_id] = {"logged_in": True}
                    bot.send_message(chat_id, "✅ تم تسجيلك بنجاح!\n🔍 جاري البحث عن آخر رسالة...")

                    latest = scraper.fetch_latest_message()
                    if latest:
                        update_last_msg(chat_id, latest["msg_id"])
                        text_msg = (
                            f"📬 آخـــر رســالـــة في البـــريـــد:\n"
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
            except Exception as e:
                logger.exception(f"Error during login for {chat_id}: {e}")
                bot.send_message(chat_id, "❌ حدث خطأ أثناء محاولة تسجيل الدخول. حاول مرة أخرى لاحقاً.")
            finally:
                registration_states.pop(chat_id, None)
                send_main_menu(chat_id)
            return

    # --- التعامل مع أزرار القائمة الرئيسية ---
    # تسجيل الدخول
    if text == "👤 تسجيل الدخول":
        start_login(chat_id)
        return
    elif text == "📅 التقويم الحالي":
        try:
            calendar = QOUScraper.get_active_calendar()
            bot.send_message(chat_id, calendar)
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ صار خطأ أثناء جلب التقويم:\n{e}")
        return
    elif text == "📚 عرض القروبات":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        categories = get_categories()  # جلب كل التصنيفات من قاعدة البيانات
        for category in categories:
            markup.add(types.KeyboardButton(category))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)
        return
    
    # عرض القروبات ضمن تصنيف معين
    elif text in get_categories():
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
        groups_in_category = get_groups_by_category(text)  # جلب كل القروبات ضمن التصنيف
        for group_id, group_name, link in groups_in_category:
            markup.add(types.KeyboardButton(group_name))
        markup.add(types.KeyboardButton("العودة للقروبات"))
        bot.send_message(chat_id, f"📂 القروبات ضمن '{text}': اختر قروب:", reply_markup=markup)
        return
    
    # عرض رابط القروب عند اختيار اسمه
    if get_group_link(text):
        link = get_group_link(text)
        bot.send_message(chat_id, f"🔗 رابط قروب '{text}':\n{link}")
        return

    elif text == "🚪 تسجيل الخروج":
        logout_user(chat_id)
        bot.send_message(chat_id, "✅ تم تسجيل الخروج بنجاح!")
        send_main_menu(chat_id)

    # الخدمات الأكاديمية
    elif text == "📖 الخدمات الأكاديمية":
        send_academic_services(chat_id)

    # الخدمات الأخرى
    elif text == "📚 أخرى":
        send_other_services(chat_id)

    elif text == "📅 التـــقويــم":
        send_cel_services(chat_id)

    elif text == "📖 الخطة الدراسية":
        send_academic_stats_menu(chat_id)

    elif text == "🔗 منصة المواد المشتركة":
        send_manasa_services(chat_id)

    elif text == "🏠 الرئيسية":
        if chat_id in user_data:
            del user_data[chat_id]
        send_academic_stats_menu(chat_id)
        return
        
    elif text == "📅 عرض التقويم القادم للفصل الحالي":
        calendar_text1 = QOUScraper.get_full_current_semester_calendar()
        bot.send_message(chat_id, calendar_text1)

    
    # العودة للرئيسية
    elif text == "⬅️ عودة للرئيسية":
        send_main_menu(chat_id)
    # عرض المقررات والعلامات
    elif text == "📖 عرض المقررات والعلامات":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return

        try:
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
                    f"   📝 علامــــة النـــصفي : {midterm}\n"
                    f"   🏁 العـــلامـــــة النهـــائية : {final}\n"
                    f"   📅 تـــــاريـــخ وضع العلامة النــــهائية : {final_date}\n\n"
                )
            bot.send_message(chat_id, text_msg, parse_mode="Markdown")
        except Exception as e:
            logger.exception(f"Error fetching courses for {chat_id}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب البيانات. حاول مرة أخرى لاحقاً.")
        return
    elif text == "✉️ إرسال اقتراح":
        bot.send_message(
            chat_id,
            "📬 لإرسال اقتراح، اضغط على الرابط التالي للتواصل عبر بوت الاقتراحات:\n"
            "https://t.me/QOUSUGBOT"
        )
        return 
    # جدول المحاضرات
    elif text == "🗓️ جدول المحاضرات":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return

        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            if not scraper.login():
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
                return

            schedule = scraper.fetch_lectures_schedule()
            if not schedule:
                bot.send_message(chat_id, "📭 لم يتم العثور على جدول المحاضرات.")
                return

            days_order = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"]
            schedule_by_day = {}

            for meeting in schedule:
                day = meeting.get('day', '').strip()
                if not day:
                    continue

                time = meeting.get('time', '-')
                course = f"{meeting.get('course_code', '-')}: {meeting.get('course_name', '-') }"
                building = meeting.get('building', '-')
                room = meeting.get('room', '-')
                lecturer = meeting.get('lecturer', '-')

                schedule_by_day.setdefault(day, []).append(
                    f"⏰ {time}\n📘 {course}\n📍 {building} - {room}\n👨‍🏫 {lecturer}"
                )

            text_msg = "🗓️ *جدول المحاضرات:*\n\n"
            for day in days_order:
                if day in schedule_by_day:
                    text_msg += f"📅 *{day}:*\n"
                    for entry in schedule_by_day[day]:
                        text_msg += f"{entry}\n\n"

            bot.send_message(chat_id, text_msg, parse_mode="Markdown")
        except Exception as e:
            logger.exception(f"Error fetching schedule for {chat_id}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب جدول المحاضرات. حاول مرة أخرى لاحقاً.")
        return

    elif text == "العودة للقروبات":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        for group_type in groups.keys():
            markup.add(types.KeyboardButton(group_type))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)
        return

    elif text == "العودة للرئيسية":
        clear_states_for_home(chat_id)
        send_main_menu(chat_id)
        return

    # زر الأدمن
    elif text == "admin" and chat_id in ADMIN_CHAT_ID:
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("التحليلات"))
        markup.add(types.KeyboardButton("إرسال رسالة"))
        markup.add(types.KeyboardButton("إدارة المواعيد"))
        markup.add(types.KeyboardButton("إضافة قروب"))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "⚙️ قائمة الأدمن: اختر خياراً", reply_markup=markup)
        return

    elif text == "إرسال رسالة" and chat_id in ADMIN_CHAT_ID:
        bot.send_message(chat_id, "✍️ الرجاء كتابة نص الرسالة التي تريد إرسالها لجميع المستخدمين:")
        admin_states[chat_id] = "awaiting_broadcast_text"
        return




# زر إدارة المواعيد
    elif text == "إدارة المواعيد" and chat_id in ADMIN_CHAT_ID:
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        markup.add(
            types.KeyboardButton("➕ إضافة موعد"),
            types.KeyboardButton("✏️ تعديل موعد"),
            types.KeyboardButton("❌ حذف موعد"),
            types.KeyboardButton("📋 عرض كل المواعيد"),
            types.KeyboardButton("العودة للقائمة")
        )
        bot.send_message(chat_id, "⚙️ إدارة المواعيد: اختر خياراً", reply_markup=markup)
        return
    
    # إضافة موعد
    elif text == "➕ إضافة موعد" and chat_id in ADMIN_CHAT_ID:
        admin_deadline_states[chat_id] = {"stage": "awaiting_name"}
        bot.send_message(chat_id, "✍️ اكتب اسم الموعد:")
        return
    
    # استقبال اسم الموعد
    elif chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_name":
        admin_deadline_states[chat_id]["name"] = text
        admin_deadline_states[chat_id]["stage"] = "awaiting_month"
        bot.send_message(chat_id, "📅 اكتب رقم الشهر (1-12):")
        return
    
    # استقبال الشهر
    elif chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_month":
        if not text.isdigit() or not 1 <= int(text) <= 12:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم شهر صحيح بين 1 و 12.")
            return
        admin_deadline_states[chat_id]["month"] = int(text)
        admin_deadline_states[chat_id]["stage"] = "awaiting_day"
        bot.send_message(chat_id, "📅 اكتب رقم اليوم (1-31):")
        return
    
    # استقبال اليوم
    elif chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_day":
        if not text.isdigit() or not 1 <= int(text) <= 31:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم يوم صحيح بين 1 و 31.")
            return
        day = int(text)
        month = admin_deadline_states[chat_id]["month"]
        year = datetime.utcnow().year
        try:
            deadline_date = date(year, month, day)

        except ValueError:
            bot.send_message(chat_id, "⚠️ التاريخ غير صالح، حاول مرة أخرى.")
            return
    
        name = admin_deadline_states[chat_id]["name"]
        deadline_id = add_deadline(name, deadline_date)  # نخزن ID الموعد الجديد
        bot.send_message(chat_id, f"✅ تم إضافة الموعد '{name}' بتاريخ {deadline_date.strftime('%d/%m/%Y')}")
        send_reminder_for_new_deadline(deadline_id)  # نمرر ID صحيح
        admin_deadline_states.pop(chat_id, None)
        send_main_menu(chat_id)
            
        return
    
    # عرض المواعيد
    elif text == "📋 عرض كل المواعيد" and chat_id in ADMIN_CHAT_ID:
        deadlines = get_all_deadlines()
        if not deadlines:
            bot.send_message(chat_id, "📭 لا توجد مواعيد حالياً.")
            return
        msg = "📌 المواعيد الحالية:\n\n"
        for d in deadlines:
            msg += f"ID:{d[0]} - {d[1]} - {d[2].strftime('%d/%m/%Y')}\n"
        bot.send_message(chat_id, msg)
        return

    elif text == "❌ حذف موعد" and chat_id in ADMIN_CHAT_ID:
        deadlines = get_all_deadlines()
        if not deadlines:
            bot.send_message(chat_id, "📭 لا توجد مواعيد للحذف حالياً.")
            return
        msg = "⚠️ اختر ID الموعد للحذف:\n\n"
        for d in deadlines:
            msg += f"ID:{d[0]} - {d[1]} - {d[2].strftime('%d/%m/%Y')}\n"
        bot.send_message(chat_id, msg)
        admin_deadline_states[chat_id] = {"stage": "awaiting_delete_id"}
        return
    
    elif chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_delete_id":
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم ID صحيح.")
            return
        deadline_id = int(text)
        if delete_deadline(deadline_id):
            bot.send_message(chat_id, f"✅ تم حذف الموعد رقم {deadline_id} بنجاح.")
        else:
            bot.send_message(chat_id, "⚠️ لم يتم العثور على الموعد المطلوب.")
        admin_deadline_states.pop(chat_id, None)
        send_main_menu(chat_id)
        return
    
    # ===================== تعديل موعد =====================
    elif text == "✏️ تعديل موعد" and chat_id in ADMIN_CHAT_ID:
        deadlines = get_all_deadlines()
        if not deadlines:
            bot.send_message(chat_id, "📭 لا توجد مواعيد للتعديل حالياً.")
            return
        msg = "⚙️ اختر ID الموعد للتعديل:\n\n"
        for d in deadlines:
            msg += f"ID:{d[0]} - {d[1]} - {d[2].strftime('%d/%m/%Y')}\n"
        bot.send_message(chat_id, msg)
        admin_deadline_states[chat_id] = {"stage": "awaiting_edit_id"}
        return
    
    elif chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_edit_id":
        if not text.isdigit():
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم ID صحيح.")
            return
        deadline_id = int(text)
        deadline = get_deadline_by_id(deadline_id)
        if not deadline:
            bot.send_message(chat_id, "⚠️ لم يتم العثور على الموعد المطلوب.")
            admin_deadline_states.pop(chat_id, None)
            return
        admin_deadline_states[chat_id] = {
            "stage": "awaiting_edit_name",
            "id": deadline_id
        }
        bot.send_message(chat_id, f"✏️ اكتب الاسم الجديد للموعد (القديم: {deadline[1]}):")
        return
    
    elif chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_edit_name":
        admin_deadline_states[chat_id]["name"] = text
        admin_deadline_states[chat_id]["stage"] = "awaiting_edit_month"
        bot.send_message(chat_id, "📅 اكتب رقم الشهر الجديد (1-12):")
        return
    
    elif chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_edit_month":
        if not text.isdigit() or not 1 <= int(text) <= 12:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم شهر صحيح بين 1 و 12.")
            return
        admin_deadline_states[chat_id]["month"] = int(text)
        admin_deadline_states[chat_id]["stage"] = "awaiting_edit_day"
        bot.send_message(chat_id, "📅 اكتب رقم اليوم الجديد (1-31):")
        return
    
    elif chat_id in admin_deadline_states and admin_deadline_states[chat_id].get("stage") == "awaiting_edit_day":
        if not text.isdigit() or not 1 <= int(text) <= 31:
            bot.send_message(chat_id, "⚠️ الرجاء إدخال رقم يوم صحيح بين 1 و 31.")
            return
        day = int(text)
        month = admin_deadline_states[chat_id]["month"]
        year = datetime.utcnow().year
        try:
            new_date = date(year, month, day)
        except ValueError:
            bot.send_message(chat_id, "⚠️ التاريخ غير صالح، حاول مرة أخرى.")
            return
    
        deadline_id = admin_deadline_states[chat_id]["id"]
        new_name = admin_deadline_states[chat_id]["name"]
        update_deadline(deadline_id, new_name, new_date)
        bot.send_message(chat_id, f"✅ تم تعديل الموعد بنجاح: '{new_name}' بتاريخ {new_date.strftime('%d/%m/%Y')}")
        admin_deadline_states.pop(chat_id, None)
        send_main_menu(chat_id)
        return    
    
    # العودة للقائمة
    elif text == "العودة للقائمة" and chat_id in ADMIN_CHAT_ID:
        send_main_menu(chat_id)
        return


    elif text == "التحليلات" and chat_id in ADMIN_CHAT_ID:
        stats = get_bot_stats()
        stats_text = (
            "📊 *إحصائيات عامة للبوت:*\n\n"
            f"- عدد المستخدمين المسجلين: {stats['total_users']}\n"
            f"- المستخدمين الجدد اليوم: {stats['new_today']}\n"
            f"- المستخدمين الجدد خلال الأسبوع: {stats['new_last_7_days']}\n"
            f"- المستخدمين الجدد خلال الشهر: {stats['new_last_30_days']}\n"
            f"- عدد المستخدمين غير النشطين (>7 أيام بدون تفاعل): {stats['inactive_users']}\n"
        )
        top_groups = stats.get("top_groups", [])
        for group in top_groups:
            stats_text += f"  • {group}\n"
        bot.send_message(chat_id, stats_text, parse_mode="Markdown")
        return

    # عرض بيانات الفصل
    elif text == "📊 عرض بيانات الفصل":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return

        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            if not scraper.login():
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
                return

            stats = scraper.fetch_term_summary_stats()
            if not stats:
                bot.send_message(chat_id, "📭 لم يتم العثور على بيانات الفصل.")
                return

            term = stats['term']
            cumulative = stats['cumulative']

            msg = (
                "📊 *البيانــــات الفـــصليـة والــــتراكــمية*\n"
                f"- 🧾 النـــــوع: {term['type']}\n"
                f"- 🕒 المسجــل: {term['registered_hours']} س.\n"
                f"- ✅ المجتــاز: {term['passed_hours']} س.\n"
                f"- 🧮 المحتسبــة: {term['counted_hours']}\n"
                f"- ❌ الراســب: {term['failed_hours']}\n"
                f"- 🚪 المنســحب: {term['withdrawn_hours']}\n"
                f"- 🏅 النقــاط: {term['points']}\n"
                f"- 📈 المعــدل: {term['gpa']}\n"
                f"- 🏆 لوحــة الشــرف: {term['honor_list']}\n\n"
                "📘 *البيانــات التراكــمية:*\n"
                f"- 🧾 النــوع: {cumulative['type']}\n"
                f"- 🕒 المســجل: {cumulative['registered_hours']} س.\n"
                f"- ✅ المجــتاز: {cumulative['passed_hours']} س.\n"
                f"- 🧮 المحتــسبة: {cumulative['counted_hours']}\n"
                f"- ❌ الراســب: {cumulative['failed_hours']}\n"
                f"- 🚪 المنسحـــب: {cumulative['withdrawn_hours']}\n"
                f"- 🏅 النقــاط: {cumulative['points']}\n"
                f"- 📈 المعــدل: {cumulative['gpa']}\n"
                f"- 🏆 لوحــة الشــرف: {cumulative['honor_list']}\n"
            )

            bot.send_message(chat_id, msg, parse_mode="Markdown")
        except Exception as e:
            logger.exception(f"Error fetching term stats for {chat_id}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب بيانات الفصل. حاول مرة أخرى لاحقاً.")
        return

    # زر جدول الامتحانات - اختيار الفصل
    elif text == "📅 جدول الامتحانات":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return

        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            if not scraper.login():
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
                return

            available_terms = scraper.get_last_two_terms()
            if not available_terms:
                bot.send_message(chat_id, "⚠️ تعذر جلب الفصول المتاحة.")
                return

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            for term in available_terms:
                # نص الزر يحتوي الملصق والقيمة مفصولة بـ |
                markup.add(types.KeyboardButton(f"📅 {term['label']}|{term['value']}"))
            markup.add(types.KeyboardButton("العودة للرئيسية"))
            bot.send_message(chat_id, "📌 اختر الفصل الدراسي:", reply_markup=markup)
        except Exception as e:
            logger.exception(f"Error fetching terms for {chat_id}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب الفصول. حاول مرة أخرى لاحقاً.")
        return

    # استقبال اختيار الفصل الدراسي (زر يحتوي |)
    elif "|" in text and len(text.split("|")) == 2:
        try:
            label, term_no = text.replace("📅", "").strip().split("|")
        except Exception:
            bot.send_message(chat_id, "⚠️ تنسيق الاختيار غير صحيح. الرجاء اختيار الفصل من الأزرار.")
            return

        # خزّن فقط term_no داخل session_states (بدون مسح حالات التسجيل)
        session_states.setdefault(chat_id, {})["term_no"] = term_no.strip()
        session_states[chat_id]["term_label"] = label.strip()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(
            types.KeyboardButton("📝 النصفي"),
            types.KeyboardButton("🏁 النهائي النظري"),
            types.KeyboardButton("🧪 النهائي العملي"),
            types.KeyboardButton("📈 امتحان المستوى"),
            types.KeyboardButton("العودة للرئيسية"),
        )
        bot.send_message(chat_id, f"📌 اختر نوع الامتحان لـ: {label.strip()}", reply_markup=markup)
        return

    # اختيار نوع الامتحان - نتأكد من وجود term_no في session_states
    elif text in ["📝 النصفي", "🏁 النهائي النظري", "🧪 النهائي العملي", "📈 امتحان المستوى"]:
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return

        if chat_id not in session_states or 'term_no' not in session_states[chat_id]:
            bot.send_message(chat_id, "❌ حدث خطأ، يرجى اختيار الفصل أولاً.")
            return

        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            if not scraper.login():
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول. يرجى إعادة اختيار الفصل الدراسي.")
                return
        except Exception as e:
            logger.exception(f"Error creating scraper for {chat_id}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء الاتصال بموقع الجامعة. حاول مرة أخرى لاحقاً.")
            return

        term_no = session_states[chat_id]['term_no']
        exam_type_map = {
            "📝 النصفي": "MT&IM",
            "🏁 النهائي النظري": "FT&IF",
            "🧪 النهائي العملي": "FP&FP",
            "📈 امتحان المستوى": "LE&LE",
        }
        exam_type = exam_type_map[text]

        try:
            exams = scraper.fetch_exam_schedule(term_no, exam_type)
            if not exams:
                bot.send_message(chat_id, "📭 لا يوجد جدول لهذا النوع.")
                return

            msg = f"📅 *جدول {text}:*\n\n"
            for ex in exams:
                msg += (
                    f"📘 {ex.get('course_code', '-')} - {ex.get('course_name', '-')}\n"
                    f"📆 {ex.get('date', '-') } ({ex.get('day', '-')})\n"
                    f"⏰ {ex.get('from_time', '-')} - {ex.get('to_time', '-')}\n"
                    f"👨‍🏫 {ex.get('lecturer', '-')}\n"
                    f"📝 {ex.get('note', '-')}\n"
                    f"───────────────\n"
                )

            bot.send_message(chat_id, msg, parse_mode="Markdown")
        except Exception as e:
            logger.exception(f"Error fetching exams for {chat_id}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب جدول الامتحانات. حاول مرة أخرى لاحقاً.")
        return

    # ===================== إدارة القروبات =====================
    elif text == "إضافة قروب" and chat_id in ADMIN_CHAT_ID:
        # المرحلة الأولى: اختيار نوع القروب (مواد، تخصصات، جامعة)
        admin_group_states[chat_id] = {"stage": "awaiting_type"}
        bot.send_message(chat_id, "📂 اختر نوع القروب:\n1️⃣ مواد\n2️⃣ تخصصات\n3️⃣ جامعة")
        return
    
    elif chat_id in admin_group_states and admin_group_states[chat_id].get("stage") == "awaiting_type":
        # تحديد النوع بناءً على الرقم المدخل
        choice = text.strip()
        type_dict = {"1": "المواد", "2": "التخصصات", "3": "الجامعة"}
        if choice not in type_dict:
            bot.send_message(chat_id, "⚠️ الرقم غير صحيح. اختر 1 أو 2 أو 3.")
            return
        admin_group_states[chat_id]["category"] = type_dict[choice]
        admin_group_states[chat_id]["stage"] = "awaiting_name"
        bot.send_message(chat_id, f"✍️ اكتب اسم القروب ضمن '{type_dict[choice]}':")
        return
    
    elif chat_id in admin_group_states and admin_group_states[chat_id].get("stage") == "awaiting_name":
        admin_group_states[chat_id]["name"] = text
        admin_group_states[chat_id]["stage"] = "awaiting_link"
        bot.send_message(chat_id, "🔗 ارسل رابط القروب:")
        return
    
    elif chat_id in admin_group_states and admin_group_states[chat_id].get("stage") == "awaiting_link":
        category = admin_group_states[chat_id]["category"]
        name = admin_group_states[chat_id]["name"]
        link = text
        add_group(category, name, link)
        bot.send_message(chat_id, f"✅ تم إضافة القروب '{name}' ضمن '{category}' بالرابط: {link}")
        admin_group_states.pop(chat_id, None)
        send_main_menu(chat_id)
        return

    elif text == "🎙️ حلقات النقاش":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return
    
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
            return
    
        sessions = scraper.fetch_discussion_sessions()
        if not sessions:
            bot.send_message(chat_id, "📭 لا يوجد حلقات نقاش حالياً.")
            return
    
        msg = "🎙️ *جــــميـــع حـلـقـات الــنـقـاش:*\n\n"
        for s in sessions:
            msg += (
                f"📘 {s['course_name']} ({s['course_code']})\n"
                f"📅 {s['date']} 🕒 {s['time']}\n\n"
            )
        bot.send_message(chat_id, msg, parse_mode="Markdown")


# ------------------ زر رصيد الطالب ------------------
    elif text == "💰 رصيد الطالب":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return
    
        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            if not scraper.login():
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
                return
    
            # استدعاء الدالة التي ترجع PDF كـ bytes
            balance_pdf_bytes = scraper.fetch_balance_table_pdf()
    
            # لوحة أزرار للإجمالي والعودة للرئيسية
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
            markup.add("📊 الإجمالي", "🏠 العودة للرئيسية")
    
            if balance_pdf_bytes:
                balance_pdf_bytes.name = "رصيد_الطالب.pdf"
                bot.send_document(chat_id, document=balance_pdf_bytes, reply_markup=markup)
            else:
                bot.send_message(chat_id, "❌ لم يتم العثور على بيانات الرصيد", reply_markup=markup)
    
        except Exception as e:
            print(f"Error fetching balance: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب بيانات الرصيد. حاول مرة أخرى لاحقاً.")
        return

    # ------------------ زر الإجمالي ------------------
    elif text == "📊 الإجمالي":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
            return
    
        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            if not scraper.login():
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
                return
    
            totals_text = scraper.fetch_balance_totals()
    
            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
            markup.add("🏠 العودة للرئيسية")
    
            bot.send_message(chat_id, totals_text, reply_markup=markup)
        except Exception as e:
            print(f"Error fetching totals: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء حساب الإجمالي. حاول مرة أخرى لاحقاً.")
        return
    
    # ------------------ العودة للرئيسية ------------------
    elif text == "🏠 العودة للرئيسية":
        send_main_menu(chat_id)
        return


    elif text == "📚 الخطط الدراسية":
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        for college in study_plans.keys():
            markup.add(types.KeyboardButton(college))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        study_plan_states[chat_id] = {"stage": "awaiting_college"}
        bot.send_message(chat_id, "📚 اختر الكلية:", reply_markup=markup)
        return
    
    # اختيار الكلية
    elif chat_id in study_plan_states and study_plan_states[chat_id]["stage"] == "awaiting_college":
        if text in study_plans:
            study_plan_states[chat_id]["college"] = text
            study_plan_states[chat_id]["stage"] = "awaiting_major"
    
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
            for major in study_plans[text].keys():
                markup.add(types.KeyboardButton(major))
            markup.add(types.KeyboardButton("العودة للرئيسية"))
    
            bot.send_message(chat_id, f"🏛️ اختر التخصص ضمن '{text}':", reply_markup=markup)
    
        elif text == "العودة للرئيسية":
            study_plan_states.pop(chat_id, None)
            send_main_menu(chat_id)
        else:
            bot.send_message(chat_id, "⚠️ الرجاء اختيار الكلية من القائمة.")
        return
    
    # اختيار التخصص أو النسخة الفرعية
    elif chat_id in study_plan_states and study_plan_states[chat_id]["stage"] == "awaiting_major":
        college = study_plan_states[chat_id]["college"]
        major_item = study_plans[college].get(text)
    
        if major_item:
            if isinstance(major_item, dict):
                # يوجد مستويات أو نسخ متعددة
                markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
                for sublevel in major_item.keys():
                    markup.add(types.KeyboardButton(sublevel))
                markup.add(types.KeyboardButton("العودة للتخصص"))
                study_plan_states[chat_id]["stage"] = "awaiting_sublevel"
                study_plan_states[chat_id]["major"] = text
                study_plan_states[chat_id]["sublevels"] = major_item
                bot.send_message(chat_id, f"🔹 اختر النسخة أو المستوى لـ '{text}':", reply_markup=markup)
            else:
                # رابط مباشر
                bot.send_message(chat_id, f"🔗 رابط خطة '{text}' ضمن '{college}':\n{major_item}")
                study_plan_states.pop(chat_id, None)
                send_main_menu(chat_id)
        elif text == "العودة للرئيسية":
            study_plan_states.pop(chat_id, None)
            send_main_menu(chat_id)
        else:
            bot.send_message(chat_id, "⚠️ الرجاء اختيار التخصص من القائمة.")
        return
    
    # اختيار النسخة الفرعية
    elif chat_id in study_plan_states and study_plan_states[chat_id]["stage"] == "awaiting_sublevel":
        sublevels = study_plan_states[chat_id]["sublevels"]
        major = study_plan_states[chat_id]["major"]
        college = study_plan_states[chat_id]["college"]
    
        if text in sublevels:
            bot.send_message(chat_id, f"🔗 رابط خطة '{major}' ({text}) ضمن '{college}':\n{sublevels[text]}")
            study_plan_states.pop(chat_id, None)
            send_main_menu(chat_id)
        elif text == "العودة للتخصص":
            study_plan_states[chat_id]["stage"] = "awaiting_major"
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
            for major_name in study_plans[college].keys():
                markup.add(types.KeyboardButton(major_name))
            markup.add(types.KeyboardButton("العودة للرئيسية"))
            bot.send_message(chat_id, f"🏛️ اختر التخصص ضمن '{college}':", reply_markup=markup)
        else:
            bot.send_message(chat_id, "⚠️ الرجاء اختيار النسخة من القائمة.")
        return
    elif text == "📊 إحصائياتي":
        user = get_user(chat_id)
        if not user or not user['student_id'] or not user['password']:
            bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
            return
    
        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            study_plan = scraper.fetch_study_plan()
            stats = study_plan['stats']
    
            if not stats or study_plan['status'] != 'success':
                bot.send_message(chat_id, "⚠️ لم أجد بيانات، جرب تحديث بياناتك أولاً.")
                return
    
            reply = f"""
    📊 *إحصائياتك الحالية:*
    ✅ الساعات المطلوبة: {stats['total_hours_required']}
    🎯 الساعات المجتازة: {stats['total_hours_completed']}
    🔄 المحتسبة: {stats['total_hours_transferred']}
    📅 عدد الفصول: {stats['semesters_count']}
    📈 الإنجاز: {stats['completion_percentage']}%
    🏁 حالة الخطة: {"مكتملة ✅" if stats['plan_completed'] else "غير مكتملة ⏳"}
    """
            bot.send_message(chat_id, reply, parse_mode="Markdown")
    
        except Exception as e:
            bot.send_message(chat_id, f"🚨 حدث خطأ: {e}")
    
    
    elif text == "📚 مقرراتي":
        user = get_user(chat_id)
        if not user or not user['student_id'] or not user['password']:
            bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
            return
    
        try:
            # ⚡ إرسال رسالة تحميل
            loading_msg = bot.send_message(chat_id, "🎓 جاري تحضير مقرراتك...")
            
            scraper = QOUScraper(user['student_id'], user['password'])
            study_plan = scraper.fetch_study_plan()
            
            if study_plan.get('status') != 'success':
                bot.delete_message(chat_id, loading_msg.message_id)
                bot.send_message(chat_id, "⚠️ لم أتمكن من جلب المقررات. حاول لاحقاً.")
                return
            
            courses_list = study_plan['courses']
            
            # تجميع المقررات حسب الفئة مع الإحصاءات
            categories_data = {}
            for course in courses_list:
                category = course.get('category', 'غير مصنف')
                if category not in categories_data:
                    categories_data[category] = {
                        'courses': [],
                        'completed': 0,
                        'total': 0,
                        'hours': 0
                    }
                
                categories_data[category]['courses'].append(course)
                categories_data[category]['total'] += 1
                categories_data[category]['hours'] += course.get('hours', 0)
                if course.get('status') == 'completed':
                    categories_data[category]['completed'] += 1
            
            # حذف رسالة التحميل
            bot.delete_message(chat_id, loading_msg.message_id)
            
            if not categories_data:
                bot.send_message(chat_id, "📭 لا توجد مقررات مسجلة حالياً.")
                return
            
            # إرسال البطاقة الرئيسية
            main_card = """
    🎯 *الخطة الدراسية الشاملة* 
    ━━━━━━━━━━━━━━━━━━━━
    
    📊 *الإحصاءات العامة:*
    • 📚 عدد المقررات في الخطة: {}
    • ✅ عدد المقررات المكتملة: {}
    • 🕒 مجموع الساعات المكتملة: {}
            
    👇 اختر الفئة لعرض المقررات:
            """.format(
                len(courses_list),
                sum(1 for c in courses_list if c.get('status') == 'completed'),
                sum(c.get('hours', 0) for c in courses_list)
            )
            
            # إنشاء keyboard للفئات
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            buttons = []
            for category in categories_data.keys():
                # تقصير اسم الفئة إذا كان طويلاً
                short_name = category[:15] + "..." if len(category) > 15 else category
                buttons.append(types.KeyboardButton(f"📁 {short_name}"))
            
            # تقسيم الأزرار إلى صفوف
            for i in range(0, len(buttons), 2):
                if i + 1 < len(buttons):
                    markup.row(buttons[i], buttons[i+1])
                else:
                    markup.row(buttons[i])
            
            markup.row(types.KeyboardButton("🏠 الرئيسية"))
            
            bot.send_message(chat_id, main_card, parse_mode="Markdown", reply_markup=markup)
            
            # حفظ بيانات الفئات في الذاكرة المؤقتة للاستجابة للاختيارات
            user_data[chat_id] = {'categories': categories_data, 'action': 'awaiting_category'}
            
        except Exception as e:
            try:
                bot.delete_message(chat_id, loading_msg.message_id)
            except:
                pass
            bot.send_message(chat_id, f"🚨 حدث خطأ: {str(e)}")
    
    # ⬇️⬇️⬇️ هذا السطر يجب أن يكون بنفس مستوى elif السابق ⬇️⬇️⬇️
    elif chat_id in user_data and user_data[chat_id].get('action') == 'awaiting_category':
        selected_text = message.text.strip()
        
        # ✅ التحقق من زر الرئيسية فقط
        if selected_text == "🏠 الرئيسية":
            del user_data[chat_id]  # حذف حالة المستخدم
            show_main_menu(chat_id)
            return
        
        # إذا لم يكن زر الرئيسية، نتعامل معه كفئة
        selected_category = selected_text.replace("📁 ", "").strip()
        categories = user_data[chat_id]['categories']
        
        # البحث عن الفئة المطابقة
        matched_category = None
        for category in categories.keys():
            if selected_category in category or category in selected_category:
                matched_category = category
                break
        
        if matched_category:
            category_data = categories[matched_category]
            
            # إنشاء بطاقة الفئة
            completion_percent = (category_data['completed'] / category_data['total'] * 100) if category_data['total'] > 0 else 0
            
            category_card = f"""
    📋 *{matched_category}*
    ━━━━━━━━━━━━━━━━━━━━
    📊 *إحصاءات الفئة:*
    • 📚 عدد المقررات: {category_data['total']}
    • ✅ مكتمل: {category_data['completed']}
    • 📈 نسبة الإنجاز: {completion_percent:.1f}%
    • 🕒 مجموع الساعات: {category_data['hours']}
    
    🎓 *المقررات:*
            """
            
            # إرسال بطاقة الفئة
            bot.send_message(chat_id, category_card, parse_mode="Markdown")
            
            # إرسال كل مقرر كبطاقة منفصلة
            for course in category_data['courses']:
                status_emoji = {
                    'completed': '✅',
                    'failed': '❌', 
                    'in_progress': '⏳',
                    'exempted': '⚡'
                }.get(course.get('status', 'unknown'), '❔')
                
                course_card = f"""
    {status_emoji} *{course.get('course_code', '')} - {course.get('course_name', '')}*
    ┌───────────────────
    │ 📊 الحالة: {course.get('detailed_status', '')}
    │ 🕒 الساعات: {course.get('hours', 0)}
    │ 📁 النوع: {'اختياري' if course.get('is_elective', False) else 'إجباري'}
    └───────────────────
                """
                
                bot.send_message(chat_id, course_card, parse_mode="Markdown")
            
            # إعادة عرض keyboard الفئات
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            buttons = []
            for category in categories.keys():
                short_name = category[:15] + "..." if len(category) > 15 else category
                buttons.append(types.KeyboardButton(f"📁 {short_name}"))
            
            for i in range(0, len(buttons), 2):
                if i + 1 < len(buttons):
                    markup.row(buttons[i], buttons[i+1])
                else:
                    markup.row(buttons[i])
            
            markup.row(types.KeyboardButton("🏠 الرئيسية"))
            
            bot.send_message(chat_id, "👇 اختر فئة أخرى أو العودة للرئيسية:", reply_markup=markup)
            
        else:
            bot.send_message(chat_id, "⚠️ لم أتعرف على الفئة المحددة.")
    
    elif text == "📌 مقررات حالية":
        user = get_user(chat_id)
        if not user or not user['student_id'] or not user['password']:
            bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
            return
    
        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            study_plan = scraper.fetch_study_plan()
            current_courses = [c for c in study_plan['courses'] if c['status'] == 'in_progress']
    
            if not current_courses:
                bot.send_message(chat_id, "⏳ لا يوجد مقررات قيد الدراسة.")
                return
    
            reply = "📌 *المقررات الحالية:*\n\n"
            for c in current_courses:
                reply += f"▫️ {c['course_code']} - {c['course_name']} ({c['hours']} س)\n"
    
            bot.send_message(chat_id, reply, parse_mode="Markdown")
    
        except Exception as e:
            bot.send_message(chat_id, f"🚨 حدث خطأ: {e}")
    
    
    elif text == "🎯 نسبة الإنجاز":
        user = get_user(chat_id)
        if not user or not user['student_id'] or not user['password']:
            bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
            return
    
        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            stats = scraper.fetch_study_plan().get('stats', {})
    
            if not stats:
                bot.send_message(chat_id, "⚠️ لم أجد بيانات، جرب 🔄 تحديث بياناتك.")
                return
    
            percentage = stats['completion_percentage']
            progress_bar = "🟩" * int(percentage / 10) + "⬜" * (10 - int(percentage / 10))
            remaining_hours = stats['total_hours_required'] - stats['total_hours_completed'] - stats['total_hours_transferred']
    
            reply = f"""
    🎯 *نسبة إنجازك الدراسي:*
    
    {progress_bar}
    {percentage}% مكتمل
    
    📊 التفاصيل:
    • المطلوب: {stats['total_hours_required']} ساعة
    • المكتمل: {stats['total_hours_completed']} ساعة
    • المحتسب: {stats['total_hours_transferred']} ساعة
    • المتبقي: {remaining_hours if remaining_hours > 0 else 0} ساعة
            """
            bot.send_message(chat_id, reply, parse_mode="Markdown")
    
        except Exception as e:
            bot.send_message(chat_id, f"🚨 حدث خطأ: {e}")
    
    
    elif text == "📋 الخطة الدراسية":
        user = get_user(chat_id)
        if not user or not user['student_id'] or not user['password']:
            bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
            return
    
        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            study_plan = scraper.fetch_study_plan()
            stats = study_plan['stats']
            courses = study_plan['courses']
    
            if not stats or not courses:
                bot.send_message(chat_id, "⚠️ لم أجد بيانات، جرب 🔄 تحديث بياناتي.")
                return
    
            categories = {}
            for course in courses:
                cat = course['category']
                categories.setdefault(cat, []).append(course)
    
            reply = "📋 *الخطة الدراسية الشاملة*\n\n"
            for category, courses_list in categories.items():
                completed = sum(1 for c in courses_list if c['status'] == 'completed')
                total = len(courses_list)
                percentage_cat = (completed / total) * 100 if total else 0
                reply += f"📁 *{category}:*\n   {completed}/{total} مكتمل ({percentage_cat:.1f}%)\n\n"
    
            reply += f"📊 *الإجمالي: {stats['completion_percentage']}% مكتمل*"
            bot.send_message(chat_id, reply, parse_mode="Markdown")
    
        except Exception as e:
            bot.send_message(chat_id, f"🚨 حدث خطأ: {e}")
    
    
    elif text == "🔄 تحديث بياناتي":
        user = get_user(chat_id)
        if not user:
            bot.send_message(chat_id, "⚠️ لم أجد بياناتك، يرجى تسجيل الدخول أولاً.")
            return
        
        bot.send_message(chat_id, "⏳ جاري تحديث بياناتك، الرجاء الانتظار...")
        
        try:
            scraper = QOUScraper(user['student_id'], user['password'])

            success = scraper.update_student_data(chat_id)

            
            if success:
                bot.send_message(chat_id, "✅ تم تحديث بياناتك بنجاح!")
            else:
                bot.send_message(chat_id, "⚠️ فشل التحديث، تحقق من بياناتك وحاول لاحقاً.")
        except Exception as e:
            logger.error(f"Error updating data: {e}")
            bot.send_message(chat_id, f"🚨 خطأ أثناء التحديث: {str(e)}")

            
        except Exception as e:
            bot.send_message(chat_id, f"🚨 خطأ: {str(e)}")

    elif text == "🔗 ربط الحساب بمنصة المواد المشتركة":
        user = get_user(chat_id)
        if not user or not user.get('student_id'):
            bot.send_message(chat_id, "❌ يرجى تسجيل الدخول أولاً باستخدام /login")
            return
        
        # إعلام المستخدم أن العملية جارية
        bot.send_message(chat_id, "🔄 جاري سحب بياناتك من بوابة الجامعة...")
        
        # جلب بيانات الدخول من DB
        creds = get_portal_credentials(chat_id)
        if not creds['success']:
            bot.send_message(chat_id, "❌ لم أجد بيانات دخول صالحة.")
            return
        try:
            # إنشاء كائن سكرابر جديد - هذا هو التصحيح المهم!
            scraper = QOUScraper(creds['username'], creds['password'])
            
            # استدعاء دالة السكرابنق الجديدة
            portal_data = scraper.fetch_student_data_from_portal()            # معالجة النتيجة
            if portal_data["success"]:
                # حفظ البيانات في DB
                update_success = update_portal_data(chat_id, portal_data['branch'], portal_data['courses'])
                
                if update_success:
                    message_text = (
                        f"✅ تم ربط حساب البوابة بنجاح!\n\n"
                        f"🏫 الفرع: {portal_data['branch']}\n"
                        f"📚 عدد المواد المسجلة: {len(portal_data['courses'])}\n\n"
                        f"يمكنك الآن استخدام ميزة \"منصة المواد المشتركة\" للتواصل مع زملائك!"
                    )
                    bot.send_message(chat_id, message_text)
                else:
                    bot.send_message(chat_id, "❌ حدث خطأ في حفظ البيانات في قاعدة البيانات.")
            else:
                bot.send_message(chat_id, f"❌ فشل في سحب البيانات: {portal_data['error']}")
        
        except Exception as e:
            logger.error(f"Error in portal linking: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ غير متوقع أثناء ربط الحساب. حاول مرة أخرى لاحقاً.")
        
        return
    elif text == "👥 منصة المواد المشتركة":
        # تغيير اسم المتغير لتجنب التعارض
        portal_data = get_user_branch_and_courses(chat_id)
        
        # التحقق من وجود بيانات البوابة
        if not portal_data['branch']:
            bot.send_message(
                chat_id, 
                "❌ لم يتم ربط حساب البوابة بعد.\n\n"
                "يرجى استخدام زر \"🔗 ربط حساب البوابة\" أولاً لسحب بيانات فرعك وموادك من بوابة الجامعة."
            )
            return
        
        if not portal_data['courses']:
            bot.send_message(
                chat_id, 
                "❌ لا توجد مواد مسجلة في الفصل الحالي.\n\n"
                "إما أنك لم تسجل أي مواد هذا الفصل، أو هناك مشكلة في بيانات البوابة."
            )
            return
        
        # إنشاء لوحة المفاتيح مع أزرار المواد
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        # إضافة أزرار المواد مع تقصير الأسماء الطويلة
        for course in portal_data['courses']:
            # تقصير اسم المادة إذا كان طويلاً مع الحفاظ على المعنى
            if len(course) > 20:
                # محاولة تقسيم الاسم إلى كلمات وأخذ أول كلمتين
                words = course.split()
                short_name = ' '.join(words[:2]) + "..." if len(words) > 2 else course[:20] + "..."
            else:
                short_name = course
            
            markup.add(types.KeyboardButton(f"📖 {short_name}"))
        
        # زر العودة
        markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
        
        # إرسال الرسالة مع المعلومات
        message_text = (
            f"🏫 **فرعك: {portal_data['branch']}**\n"
            f"📚 **عدد المواد المسجلة: {len(portal_data['courses'])}**\n\n"
            "اختر المادة التي تريد التواصل مع زملائك فيها:"
        )
        
        bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode="Markdown")
    
    # معالج لاختيار مادة محددة
    elif text.startswith("📖 "):
        # استخراج اسم المادة من النص
        selected_course = text.replace("📖 ", "").strip()
        
        # جلب البيانات الكاملة للمستخدم (باسم متغير مختلف)
        user_portal_data = get_user_branch_and_courses(chat_id)
        
        if not user_portal_data['branch'] or not user_portal_data['courses']:
            bot.send_message(chat_id, "❌ بيانات غير كافية. يرجى إعادة ربط حساب البوابة.")
            return
        
        # البحث عن الاسم الكامل للمادة (للتأكد من المطابقة)
        full_course_name = None
        for course in user_portal_data['courses']:
            if selected_course in course or course.startswith(selected_course.replace("...", "")):
                full_course_name = course
                break
        
        if not full_course_name:
            bot.send_message(chat_id, "❌ لم أتعرف على المادة المحددة.")
            return
        
        # البحث عن زملاء في نفس المادة والفرع
        potential_partners = find_potential_partners(chat_id, full_course_name)
        
        # إنشاء لوحة مفاتيح جديدة
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        if potential_partners:
            partner_count = len(potential_partners)
            message_text = (
                f"📖 **المادة: {full_course_name}**\n"
                f"👥 **عدد الزملاء المتاحين: {partner_count}**\n\n"
                "اختر طريقة التواصل:"
            )
            
            # إضافة أزرار الخيارات
            markup.add(types.KeyboardButton(f"🎲 محادثة عشوائية - {selected_course}"))
            markup.add(types.KeyboardButton("👥 عرض قائمة الزملاء"))
            markup.add(types.KeyboardButton("⬅️ عودة للمواد"))
            
        else:
            message_text = (
                f"📖 **المادة: {full_course_name}**\n\n"
                "❌ لا يوجد زملاء متاحين في هذه المادة حالياً.\n"
                "يمكنك المحاولة لاحقاً أو اختيار مادة أخرى."
            )
            markup.add(types.KeyboardButton("⬅️ عودة للمواد"))
        
        markup.add(types.KeyboardButton("🏠 الرئيسية"))
        
        bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode="Markdown")
        
        # حفظ حالة المستخدم للمراحل القادمة (باستخدام المتغير العام)
        user_sessions[chat_id] = {
            'current_course': full_course_name,
            'action': 'awaiting_communication_choice'
        }
    
    # معالج للعودة إلى قائمة المواد
    elif text == "⬅️ عودة للمواد":
        # استخدام اسم متغير مختلف
        portal_courses = get_user_branch_and_courses(chat_id)
        
        if not portal_courses['courses']:
            bot.send_message(chat_id, "❌ لا توجد مواد مسجلة.")
            return
        
        # إعادة إنشاء لوحة المفاتيح للمواد
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        for course in portal_courses['courses']:
            if len(course) > 20:
                words = course.split()
                short_name = ' '.join(words[:2]) + "..." if len(words) > 2 else course[:20] + "..."
            else:
                short_name = course
            markup.add(types.KeyboardButton(f"📖 {short_name}"))
        
        markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
        
        bot.send_message(chat_id, "📚 اختر مادة:", reply_markup=markup)
    # معالج للمحادثة العشوائية - إضف هذا بعد باقي المعالجات
    elif text.startswith("🎲 محادثة عشوائية - "):
        course_name = text.replace("🎲 محادثة عشوائية - ", "").strip()
        
        # جلب بيانات المستخدم
        user_data = get_user_branch_and_courses(chat_id)
        if not user_data['branch']:
            bot.send_message(chat_id, "❌ يرجى ربط حساب البوابة أولاً")
            return
        
        # البحث عن زملاء
        partners = find_potential_partners(chat_id, course_name)
        
        if not partners:
            bot.send_message(chat_id, f"❌ لا يوجد زملاء في مادة {course_name} حالياً")
            return
        
        # اختيار شريك عشوائي
        partner_id = random.choice(partners)
        
        # إنشاء محادثة
        chat_token = create_anonymous_chat(chat_id, partner_id, course_name)
        
        if not chat_token:
            bot.send_message(chat_id, "❌ فشل في إنشاء المحادثة")
            return
        
        # حفظ حالة المحادثة
        user_sessions[chat_id] = {
            'in_chat': True,
            'chat_token': chat_token,
            'partner_id': partner_id,
            'course_name': course_name
        }
        
        # إرسال إشعار للطرفين
        bot.send_message(chat_id,
            f"💬 **بدأت المحادثة المجهولة**\n\n"
            f"📖 المادة: {course_name}\n"
            f"👥 تم الاتصال بزميل دراسة\n\n"
            f"⚡ ابدأ بالحديث الآن!\n"
            f"❌ /end - لإنهاء المحادثة",
            parse_mode="Markdown"
        )
        
        # إشعار للشريك
        try:
            bot.send_message(partner_id,
                f"💬 **بدعوة محادثة مجهولة**\n\n"
                f"📖 المادة: {course_name}\n"
                f"👤 أحد الزملاء يريد الدراسة معك\n\n"
                f"⚡ ابدأ بالحديث الآن!\n"
                f"❌ /end - لرفض المحادثة",
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.send_message(chat_id, "❌ تعذر الاتصال بالشريك")
            del user_sessions[chat_id]


    # إضف هذا الكود في handle_all_messages بعد باقي المعالجات
    elif text == "👥 عرض قائمة الزملاء":
        if chat_id not in user_sessions or 'current_course' not in user_sessions[chat_id]:
            bot.send_message(chat_id, "❌ يرجى اختيار مادة أولاً من القائمة.")
            return
        
        course_name = user_sessions[chat_id]['current_course']
        
        # البحث عن الزملاء
        partners = find_potential_partners(chat_id, course_name)
        
        if not partners:
            bot.send_message(chat_id, f"❌ لا يوجد زملاء متاحين في مادة {course_name} حالياً.")
            return
        
        # عرض قائمة الزملاء
        message = f"👥 **زملاؤك في مادة {course_name}:**\n\n"
        for i, partner_id in enumerate(partners[:5], 1):  # عرض أول 5 فقط
            message += f"{i}. 👤 زميل #{partner_id}\n"
        
        if len(partners) > 5:
            message += f"\n... و{len(partners) - 5} زميل آخر"
        
        message += "\n🎲 اختر \"محادثة عشوائية\" للتواصل مع أحدهم!"
        
        bot.send_message(chat_id, message, parse_mode="Markdown")
    
    else:
        bot.send_message(chat_id, "⚠️ لم أفهم الأمر، الرجاء اختيار زر من القائمة.")
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()    
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling()
