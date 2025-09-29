import os
import json
import logging
import threading
import secrets
from datetime import datetime
from io import BytesIO

from flask import Flask
from telebot import types
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from bot_instance import bot
from database import (
    init_db, get_all_users, get_bot_stats, get_user, add_user, logout_user, 
    update_last_msg, get_all_chat_ids_from_logs, log_chat_id, get_all_deadlines,
    add_deadline, update_deadline, delete_deadline, get_deadline_by_id, add_group,
    get_group_link, get_categories, get_groups_by_category, get_portal_credentials,
    update_portal_data, get_user_branch_and_courses, find_potential_partners,
    clear_portal_data, has_portal_data, get_courses_by_branch, get_portal_stats,
    create_anonymous_chat, add_chat_message, get_chat_partner, end_chat
)
from scheduler import (
    start_scheduler, get_user_scheduled_events, format_scheduled_events_message,
    run_existing_functions_for_user, send_reminder_for_new_deadline
)
from qou_scraper import QOUScraper

# ========== إعداد السجل والمتغيرات ==========
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = [6292405444, 1851786931]

# حالات المستخدمين
registration_states = {}
session_states = {}
session_statess = {}
admin_states = {}
admin_group_states = {}
admin_deadline_states = {}
user_sessions = {}
user_categories_data = {}
user_data = {}
study_plan_states = {}

# تحميل الخطط الدراسية
plans_file_path = os.path.join(os.path.dirname(__file__), "qou.json")
with open(plans_file_path, "r", encoding="utf-8") as f:
    study_plans = json.load(f)

# ========== تهيئة التطبيق ==========
init_db()
get_all_users()
start_scheduler()

app = Flask(__name__)

# ========== دوال القوائم ==========
def send_main_menu(chat_id):
    """إرسال القائمة الرئيسية"""
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
        types.KeyboardButton("💻 اللقاءات الافتراضية"),
        types.KeyboardButton("💰 رصيد الطالب"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة أكاديمية:", reply_markup=markup)

def send_academic_stats_menu(chat_id):
    """القائمة الفرعية للإحصائيات الأكاديمية"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
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

def send_cel_services(chat_id):
    """القائمة الفرعية للتقويم"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    current_week_text = QOUScraper.get_current_week_type()
    
    markup.add(
        types.KeyboardButton("📅 التقويم الحالي"),
        types.KeyboardButton("📅 عرض التقويم القادم للفصل الحالي"),
        types.KeyboardButton(f"🟢 {current_week_text}")
    )
    
    if chat_id in session_statess:
        scraper = session_statess[chat_id]
        delay_status = scraper.get_delay_status()
        markup.add(types.KeyboardButton(f"📅 {delay_status}"))
    else:
        markup.add(types.KeyboardButton("📅 حالة التأجيل: ❌ غير متوفرة"))
    
    markup.add(
        types.KeyboardButton("🔄 تحديث حالة التأجيل"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def send_manasa_services(chat_id):
    """القائمة الفرعية لمنصة المواد المشتركة"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("👥 منصة المواد المشتركة"),
        types.KeyboardButton("🔗 ربط الحساب بمنصة المواد المشتركة"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def send_other_services(chat_id):
    """القائمة الفرعية للخدمات الأخرى"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📅 المواعيد المجدولة"),
        types.KeyboardButton("📚 عرض القروبات"),
        types.KeyboardButton("✉️ إرسال اقتراح"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def start_login(chat_id):
    """بدء عملية تسجيل الدخول"""
    registration_states[chat_id] = {"stage": "awaiting_student_id"}
    bot.send_message(chat_id, "👤 الرجاء إرسال رقمك الجامعي:")

# ========== معالجات Flask ==========
@app.route("/")
def home():
    return "✅ البوت يعمل بنجاح!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ========== معالجات البوت الرئيسية ==========
@bot.message_handler(commands=["start"])
def handle_start(message):
    """معالج أمر البدء"""
    log_chat_id(message.chat.id)
    chat_id = message.chat.id
    username = message.from_user.username or "بدون اسم مستخدم"
    user = get_user(chat_id)

    if user:
        bot.send_message(chat_id, "👋  مرحــــباً!  ")
    else:
        add_user(chat_id, student_id="", password="", registered_at=datetime.utcnow().isoformat())
        bot.send_message(chat_id, "👤 لم يتم تسجيلك بعد. الرجاء تسجيل الدخول.")
        
        admin_message = f"🚨 مستخدم جديد بدأ استخدام البوت!\n\nchat_id: {chat_id}\nUsername: @{username}"
        for admin_id in ADMIN_CHAT_ID:
            try:
                bot.send_message(admin_id, admin_message)
            except Exception as e:
                print(f"خطأ في إرسال الرسالة للأدمن {admin_id}: {e}")

    send_main_menu(chat_id)

@bot.message_handler(commands=['end'])
def handle_end_chat(message):
    """إنهاء المحادثة المجهولة"""
    chat_id = message.chat.id
    
    if chat_id in user_sessions and user_sessions[chat_id].get('in_chat'):
        chat_token = user_sessions[chat_id]['chat_token']
        partner_id = user_sessions[chat_id]['partner_id']
        
        end_chat(chat_token)
        
        try:
            bot.send_message(partner_id, "❌ الطرف الآخر أنهى المحادثة")
        except:
            pass
        
        bot.send_message(chat_id, "✅ تم إنهاء المحادثة")
        del user_sessions[chat_id]
    else:
        bot.send_message(chat_id, "❌ لا توجد محادثة نشطة")

# ========== معالجات Callback ==========
@bot.callback_query_handler(func=lambda call: call.data == "show_upcoming_lectures")
def handle_upcoming_lectures(call):
    """عرض المحاضرات القادمة"""
    chat_id = call.message.chat.id
    user = get_user(chat_id)
    
    if not user:
        bot.answer_callback_query(call.id, "❌ لم يتم العثور على بياناتك. أرسل /start أولاً.")
        return

    try:
        bot.delete_message(chat_id, call.message.message_id)
        wait_msg = bot.send_message(chat_id, "⏳ جاري تحضير المحاضرات القادمة...")
        
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.delete_message(chat_id, wait_msg.message_id)
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
            return

        upcoming_lectures = scraper.get_upcoming_lectures(chat_id)
        bot.delete_message(chat_id, wait_msg.message_id)
        
        keyboard = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton(text="↩️ العودة لجدول المحاضرات", callback_data="back_to_schedule")
        keyboard.add(back_btn)
        
        bot.send_message(chat_id, upcoming_lectures, parse_mode="Markdown", reply_markup=keyboard)
        
    except Exception as e:
        logger.exception(f"Error in upcoming lectures callback for {chat_id}: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ. حاول مرة أخرى.")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_schedule")
def handle_back_to_schedule(call):
    """العودة لجدول المحاضرات"""
    chat_id = call.message.chat.id
    
    try:
        bot.delete_message(chat_id, call.message.message_id)
        
        user = get_user(chat_id)
        if not user:
            bot.answer_callback_query(call.id, "❌ لم يتم العثور على بياناتك.")
            return

        handle_lecture_schedule(chat_id, user)
        
    except Exception as e:
        logger.exception(f"Error in back to schedule for {chat_id}: {e}")
        bot.answer_callback_query(call.id, "❌ حدث خطأ.")

@bot.callback_query_handler(func=lambda call: call.data == "update_schedule")
def handle_update_schedule_callback(call):
    """تحديث الجدولة"""
    try:
        chat_id = call.message.chat.id
        logger.info(f"[{chat_id}] طلب تحديث الجدولة من الزر")
        
        bot.edit_message_text("🔄 جاري تحديث الجدولة...", chat_id, call.message.message_id)
        
        success_count = run_existing_functions_for_user(chat_id)
        
        if success_count > 0:
            events_info = get_user_scheduled_events(chat_id)
            if events_info:
                events_message = format_scheduled_events_message(events_info)
                
                markup = types.InlineKeyboardMarkup()
                updated_button = types.InlineKeyboardButton("✅ تم التحديث", callback_data="already_updated")
                markup.add(updated_button)
                
                bot.edit_message_text(
                    events_message,
                    chat_id,
                    call.message.message_id,
                    parse_mode='Markdown',
                    reply_markup=markup
                )
                
                bot.send_message(chat_id, f"✅ تم تحديث الجدولة بنجاح! تم فحص {success_count} عنصر")
            else:
                bot.edit_message_text("❌ فشل في تحميل البيانات بعد التحديث", chat_id, call.message.message_id)
        else:
            bot.edit_message_text("⚠️ لم يتم العثور على عناصر جديدة في جدولك", chat_id, call.message.message_id)
            
    except Exception as e:
        logger.error(f"خطأ في معالجة تحديث الجدولة: {e}")
        try:
            bot.send_message(chat_id, "❌ حدث خطأ أثناء تحديث الجدولة")
        except:
            pass

@bot.callback_query_handler(func=lambda call: call.data == "already_updated")
def handle_already_updated(call):
    """معالجة الزر بعد التحديث"""
    bot.answer_callback_query(call.id, "✅ تم تحديث الجدولة مسبقاً", show_alert=False)

# ========== معالجات اللقاءات الافتراضية ==========
def handle_virtual_meetings(chat_id, text):
    """معالجة اللقاءات الافتراضية"""
    if text != "💻 اللقاءات الافتراضية":
        return False
    
    user = get_user(chat_id)
    if not user or not user.get('student_id'):
        bot.send_message(chat_id, "❌ يرجى تسجيل الدخول أولاً.")
        return True

    try:
        loading_msg = bot.send_message(chat_id, "🔄 جاري الاتصال بالنظام الإلكتروني...")
        
        scraper = QOUScraper(user['student_id'], user['password'])
        ecourse_result = scraper.fetch_ecourse_courses(user['student_id'], user['password'])
        
        bot.delete_message(chat_id, loading_msg.message_id)
        
        if not ecourse_result['success']:
            bot.send_message(chat_id, f"❌ {ecourse_result['error']}")
            return True
        
        courses = ecourse_result['courses']
        
        if not courses:
            bot.send_message(chat_id, "📭 لا توجد مقررات مسجلة في النظام الإلكتروني.")
            return True
        
        user_sessions[chat_id] = {
            'ecourses': courses,
            'action': 'awaiting_ecourse_selection',
            'username': user['student_id'],
            'password': user['password']
        }
        
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        for course in courses[:8]:
            course_name = course['name']
            if len(course_name) > 20:
                course_name = course_name[:20] + "..."
            markup.add(types.KeyboardButton(f"📚 {course_name}"))
        
        markup.add(types.KeyboardButton("🔄 تحديث القائمة"))
        markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
        
        bot.send_message(
            chat_id, 
            f"📋 **المقررات المسجلة في النظام الإلكتروني**\n\nتم العثور على {len(courses)} مقرر.\n\nاختر المقرر لعرض اللقاءات الافتراضية:",
            parse_mode="Markdown", 
            reply_markup=markup
        )
        return True
        
    except Exception as e:
        logger.error(f"Error in virtual meetings for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء الاتصال بالنظام الإلكتروني.")
        return True

def handle_ecourse_selection(chat_id, text):
    """معالجة اختيار المقرر"""
    if (chat_id not in user_sessions or 
        user_sessions[chat_id].get('action') != 'awaiting_ecourse_selection'):
        return False
    
    if text == "⬅️ عودة للرئيسية":
        if chat_id in user_sessions:
            del user_sessions[chat_id]
        send_main_menu(chat_id)
        return True
    
    if text == "🔄 تحديث القائمة":
        user = get_user(chat_id)
        if not user:
            return True
            
        loading_msg = bot.send_message(chat_id, "🔄 جاري تحديث القائمة...")
        
        try:
            scraper = QOUScraper(user['student_id'], user['password'])
            ecourse_result = scraper.fetch_ecourse_courses(user['student_id'], user['password'])
            
            bot.delete_message(chat_id, loading_msg.message_id)
            
            if ecourse_result['success']:
                courses = ecourse_result['courses']
                user_sessions[chat_id]['ecourses'] = courses
                
                markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
                for course in courses[:8]:
                    course_name = course['name']
                    if len(course_name) > 20:
                        course_name = course_name[:20] + "..."
                    markup.add(types.KeyboardButton(f"📚 {course_name}"))
                
                markup.add(types.KeyboardButton("🔄 تحديث القائمة"))
                markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
                
                bot.send_message(chat_id, f"✅ تم التحديث! العدد: {len(courses)} مقرر.", reply_markup=markup)
            else:
                bot.send_message(chat_id, f"❌ {ecourse_result['error']}")
                
        except Exception as e:
            bot.delete_message(chat_id, loading_msg.message_id)
            bot.send_message(chat_id, "❌ فشل التحديث.")
        return True
    
    if text.startswith("📚 "):
        selected_course_name = text.replace("📚 ", "").strip()
        courses = user_sessions[chat_id].get('ecourses', [])
        
        selected_course = None
        for course in courses:
            if selected_course_name in course['name'] or course['name'].startswith(selected_course_name.replace("...", "")):
                selected_course = course
                break
        
        if not selected_course:
            bot.send_message(chat_id, "❌ لم أتعرف على المقرر.")
            return True
        
        loading_msg = bot.send_message(chat_id, f"🔍 جاري البحث عن اللقاءات في {selected_course['name']}...")
        
        try:
            scraper = QOUScraper(user_sessions[chat_id]['username'], user_sessions[chat_id]['password'])
            meetings_result = scraper.fetch_course_virtual_meetings(
                selected_course['url'], 
                user_sessions[chat_id]['username'], 
                user_sessions[chat_id]['password']
            )
            
            bot.delete_message(chat_id, loading_msg.message_id)
            
            if not meetings_result['success']:
                bot.send_message(chat_id, f"❌ {meetings_result['error']}")
                return True
            
            meetings = meetings_result['meetings']
            
            if not meetings:
                bot.send_message(chat_id, f"📭 لا توجد لقاءات افتراضية لـ {selected_course['name']}.")
                return True
            
            user_sessions[chat_id].update({
                'selected_course': selected_course,
                'meetings': meetings,
                'action': 'awaiting_meeting_selection'
            })
            
            meetings_by_semester = {}
            for meeting in meetings:
                semester = meeting['semester']
                if semester != "غير محدد":
                    if semester not in meetings_by_semester:
                        meetings_by_semester[semester] = []
                    meetings_by_semester[semester].append(meeting)
            
            if not meetings_by_semester:
                meetings_by_semester["اللقاءات المتاحة"] = meetings
            
            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            
            for semester, semester_meetings in meetings_by_semester.items():
                if semester_meetings:
                    if semester != "اللقاءات المتاحة":
                        markup.add(types.KeyboardButton(f"📅 {semester}"))
                    
                    for meeting in semester_meetings:
                        title = meeting['title']
                        if len(title) > 30:
                            title = title[:30] + "..."
                        markup.add(types.KeyboardButton(f"🎥 {title}"))
            
            markup.add(types.KeyboardButton("⬅️ عودة للمقررات"))
            markup.add(types.KeyboardButton("🏠 الرئيسية"))
            
            message = f"💻 **لقاءات {selected_course['name']}**\n\n"
            message += f"📊 **إجمالي اللقاءات:** {len(meetings)}\n\n"
            
            for semester, semester_meetings in meetings_by_semester.items():
                message += f"**{semester}:** {len(semester_meetings)} لقاء\n"
            
            message += "\n👇 اختر اللقاء الذي تريد مشاهدته:"
            
            bot.send_message(chat_id, message, parse_mode="Markdown", reply_markup=markup)
            return True
            
        except Exception as e:
            bot.delete_message(chat_id, loading_msg.message_id)
            logger.error(f"Meetings error for {chat_id}: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب اللقاءات.")
            return True
    
    return False

def handle_meeting_selection(chat_id, text):
    """معالجة اختيار اللقاء الافتراضي"""
    if (chat_id not in user_sessions or 
        user_sessions[chat_id].get('action') != 'awaiting_meeting_selection'):
        return False
    
    if text == "⬅️ عودة للمقررات":
        user_sessions[chat_id]['action'] = 'awaiting_ecourse_selection'
        courses = user_sessions[chat_id].get('ecourses', [])
        
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        for course in courses[:8]:
            course_name = course['name']
            if len(course_name) > 20:
                course_name = course_name[:20] + "..."
            markup.add(types.KeyboardButton(f"📚 {course_name}"))
        
        markup.add(types.KeyboardButton("🔄 تحديث القائمة"))
        markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
        
        bot.send_message(chat_id, "📋 اختر المقرر:", reply_markup=markup)
        return True
    
    if text == "🏠 الرئيسية":
        if chat_id in user_sessions:
            del user_sessions[chat_id]
        send_main_menu(chat_id)
        return True
    
    if text.startswith("🎥 "):
        meeting_title = text.replace("🎥 ", "").strip()
        meetings = user_sessions[chat_id].get('meetings', [])
        course = user_sessions[chat_id].get('selected_course', {})
        
        selected_meeting = None
        for meeting in meetings:
            if meeting_title in meeting['title'] or meeting['title'].startswith(meeting_title.replace("...", "")):
                selected_meeting = meeting
                break
        
        if not selected_meeting:
            bot.send_message(chat_id, "❌ اللقاء غير موجود.")
            return True
        
        meeting_url = selected_meeting['url']
        
        info_message = f"💻 **اللقاء الافتراضي**\n\n"
        info_message += f"📚 **المقرر:** {course.get('name', 'غير معروف')}\n"
        
        if selected_meeting['semester'] != "غير محدد":
            info_message += f"📅 **الفصل:** {selected_meeting['semester']}\n"
        
        info_message += f"🎯 **العنوان:** {selected_meeting['title']}\n\n"
        info_message += f"🔗 **رابط اللقاء:**\n{meeting_url}\n\n"
        info_message += "💡 انسخ الرابط وافتحه في المتصفح"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🎥 فتح اللقاء مباشرة", url=meeting_url))
        
        bot.send_message(
            chat_id, 
            info_message, 
            parse_mode="Markdown",
            reply_markup=markup,
            disable_web_page_preview=False
        )
        
        nav_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        nav_markup.add(types.KeyboardButton("📋 عرض جميع اللقاءات"))
        nav_markup.add(types.KeyboardButton("📚 عرض المقررات"))
        nav_markup.add(types.KeyboardButton("🏠 الرئيسية"))
        
        bot.send_message(chat_id, "🔍 اختر الإجراء التالي:", reply_markup=nav_markup)
        return True
    
    if text == "📋 عرض جميع اللقاءات":
        user_sessions[chat_id]['action'] = 'awaiting_meeting_selection'
        meetings = user_sessions[chat_id].get('meetings', [])
        course = user_sessions[chat_id].get('selected_course', {})
        
        meetings_by_semester = {}
        for meeting in meetings:
            semester = meeting['semester']
            if semester != "غير محدد":
                if semester not in meetings_by_semester:
                    meetings_by_semester[semester] = []
                meetings_by_semester[semester].append(meeting)
        
        if not meetings_by_semester:
            meetings_by_semester["اللقاءات المتاحة"] = meetings
        
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        
        for semester, semester_meetings in meetings_by_semester.items():
            if semester_meetings:
                if semester != "اللقاءات المتاحة":
                    markup.add(types.KeyboardButton(f"📅 {semester}"))
                
                for meeting in semester_meetings:
                    title = meeting['title']
                    if len(title) > 30:
                        title = title[:30] + "..."
                    markup.add(types.KeyboardButton(f"🎥 {title}"))
        
        markup.add(types.KeyboardButton("⬅️ عودة للمقررات"))
        markup.add(types.KeyboardButton("🏠 الرئيسية"))
        
        bot.send_message(
            chat_id, 
            f"💻 **جميع لقاءات {course.get('name', 'المقرر')}**\nاختر لقاء:",
            parse_mode="Markdown",
            reply_markup=markup
        )
        return True
    
    if text.startswith("📅 "):
        semester_name = text.replace("📅 ", "").strip()
        bot.send_message(
            chat_id, 
            f"📅 **{semester_name}**\n\nاختر أحد اللقاءات أعلاه لمشاهدته.",
            parse_mode="Markdown"
        )
        return True
    
    if text == "📚 عرض المقررات":
        user_sessions[chat_id]['action'] = 'awaiting_ecourse_selection'
        courses = user_sessions[chat_id].get('ecourses', [])
        
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        for course in courses[:8]:
            course_name = course['name']
            if len(course_name) > 20:
                course_name = course_name[:20] + "..."
            markup.add(types.KeyboardButton(f"📚 {course_name}"))
        
        markup.add(types.KeyboardButton("🔄 تحديث القائمة"))
        markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
        
        bot.send_message(chat_id, "📋 اختر المقرر:", reply_markup=markup)
        return True
    
    return False

# ========== معالجات الخدمات الأكاديمية ==========
def handle_courses_grades(chat_id, user):
    """عرض المقررات والعلامات"""
    scraper = QOUScraper(user['student_id'], user['password'])
    if not scraper.login():
        bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
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

def handle_lecture_schedule(chat_id, user):
    """عرض جدول المحاضرات"""
    scraper = QOUScraper(user['student_id'], user['password'])
    if not scraper.login():
        bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
        return

    schedule = scraper.fetch_lectures_schedule()
    if not schedule:
        bot.send_message(chat_id, "📭 لم يتم العثور على جدول المحاضرات.")
        return

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

def handle_term_stats(chat_id, user):
    """عرض بيانات الفصل"""
    scraper = QOUScraper(user['student_id'], user['password'])
    if not scraper.login():
        bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
        return

    stats = scraper.fetch_term_summary_stats()
    if not stats:
        bot.send_message(chat_id, "📭 لم يتم العثور على بيانات الفصل.")
        return

    term = stats['term']
    cumulative = stats['cumulative']

    msg = (
        "📊 *البيانــــات الفـــصليـة والــــتراكــمية*\n\n"
        "*📘 البيانات الفصلية:*\n"
        f"- 🧾 النـــــوع: {term['type']}\n"
        f"- 🕒 المسجــل: {term['registered_hours']} س.\n"
        f"- ✅ المجتــاز: {term['passed_hours']} س.\n"
        f"- 🧮 المحتسبــة: {term['counted_hours']}\n"
        f"- ❌ الراســب: {term['failed_hours']}\n"
        f"- 🚪 المنســحب: {term['withdrawn_hours']}\n"
        f"- 🏅 النقــاط: {term['points']}\n"
        f"- 📈 المعــدل: {term['gpa']}\n"
        f"- 🏆 لوحــة الشــرف: {term['honor_list']}\n\n"
        "*📘 البيانــات التراكــمية:*\n"
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

def handle_exam_schedule(chat_id, user):
    """عرض جدول الامتحانات"""
    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
            return

        schedule = scraper.fetch_exam_schedule()
        if not schedule:
            bot.send_message(chat_id, "📭 لا يوجد جدول امتحانات حالياً.")
            return

        msg = "📅 *جدول الامتحانات:*\n\n"
        for exam in schedule:
            msg += (
                f"📘 {exam['course_name']} ({exam['course_code']})\n"
                f"📅 {exam['date']}\n"
                f"🕒 {exam['time']}\n"
                f"📍 {exam['location']}\n\n"
            )
        
        bot.send_message(chat_id, msg, parse_mode="Markdown")
        
    except Exception as e:
        logger.exception(f"Error fetching exam schedule for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب جدول الامتحانات.")

def handle_discussion_sessions(chat_id, user):
    """عرض حلقات النقاش"""
    scraper = QOUScraper(user['student_id'], user['password'])
    if not scraper.login():
        bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
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

def handle_student_balance(chat_id, user):
    """عرض رصيد الطالب"""
    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
            return

        balance_pdf_bytes = scraper.fetch_balance_table_pdf()

        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        markup.add("📊 الإجمالي", "🏠 العودة للرئيسية")

        if balance_pdf_bytes:
            balance_pdf_bytes.name = "رصيد_الطالب.pdf"
            bot.send_document(chat_id, document=balance_pdf_bytes, reply_markup=markup)
        else:
            bot.send_message(chat_id, "❌ لم يتم العثور على بيانات الرصيد", reply_markup=markup)

    except Exception as e:
        logger.error(f"Error fetching balance: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب بيانات الرصيد.")

def handle_study_plans_menu(chat_id):
    """عرض قائمة الخطط الدراسية"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    for college in study_plans.keys():
        markup.add(types.KeyboardButton(college))
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
    study_plan_states[chat_id] = {"stage": "awaiting_college"}
    bot.send_message(chat_id, "📚 اختر الكلية:", reply_markup=markup)

def handle_academic_stats(chat_id, text):
    """معالجة الإحصائيات الأكاديمية"""
    user = get_user(chat_id)
    if not user or not user['student_id'] or not user['password']:
        bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        
        if text == "📊 إحصائياتي":
            study_plan = scraper.fetch_study_plan()
            stats = study_plan.get('stats')

            if not stats or study_plan.get('status') != 'success':
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

        elif text == "🔄 تحديث بياناتي":
            bot.send_message(chat_id, "⏳ جاري تحديث بياناتك، الرجاء الانتظار...")
            success = scraper.update_student_data(chat_id)
            if success:
                bot.send_message(chat_id, "✅ تم تحديث بياناتك بنجاح!")
            else:
                bot.send_message(chat_id, "⚠️ فشل التحديث، تحقق من بياناتك وحاول لاحقاً.")

    except Exception as e:
        logger.error(f"Error in academic stats for {chat_id}: {e}")
        bot.send_message(chat_id, f"🚨 حدث خطأ: {str(e)}")

# ========== معالجات منصة المواد المشتركة ==========
def handle_portal_linking(chat_id):
    """ربط حساب منصة المواد المشتركة"""
    user = get_user(chat_id)
    if not user or not user.get('student_id'):
        bot.send_message(chat_id, "❌ يرجى تسجيل الدخول أولاً")
        return
    
    bot.send_message(chat_id, "🔄 جاري سحب بياناتك من بوابة الجامعة...")
    
    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        portal_data = scraper.fetch_student_data_from_portal()
        
        if portal_data.get("success"):
            update_success = update_portal_data(chat_id, portal_data['branch'], portal_data['courses'])
            
            if update_success:
                message_text = (
                    f"✅ تم ربط حساب البوابة بنجاح!\n\n"
                    f"🏫 الفرع: {portal_data['branch']}\n"
                    f"📚 عدد المواد المسجلة: {len(portal_data['courses'])}\n\n"
                    f"يمكنك الآن استخدام ميزة منصة المواد المشتركة للتواصل مع زملائك!"
                )
                bot.send_message(chat_id, message_text)
            else:
                bot.send_message(chat_id, "❌ حدث خطأ في حفظ البيانات في قاعدة البيانات.")
        else:
            bot.send_message(chat_id, f"❌ فشل في سحب البيانات: {portal_data.get('error', 'خطأ غير معروف')}")
    
    except Exception as e:
        logger.error(f"Error in portal linking: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ غير متوقع أثناء ربط الحساب.")

def handle_shared_courses_platform(chat_id):
    """عرض منصة المواد المشتركة"""
    portal_data = get_user_branch_and_courses(chat_id)
    
    if not portal_data.get('branch'):
        bot.send_message(
            chat_id, 
            "❌ لم يتم ربط حساب البوابة بعد.\n\n"
            "يرجى استخدام زر 🔗 ربط الحساب بمنصة المواد المشتركة أولاً."
        )
        return
    
    if not portal_data.get('courses'):
        bot.send_message(
            chat_id, 
            "❌ لا توجد مواد مسجلة في الفصل الحالي."
        )
        return
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    for course in portal_data['courses']:
        if len(course) > 20:
            words = course.split()
            short_name = ' '.join(words[:2]) + "..." if len(words) > 2 else course[:20] + "..."
        else:
            short_name = course
        markup.add(types.KeyboardButton(f"📖 {short_name}"))
    
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
    
    message_text = (
        f"🏫 **فرعك: {portal_data['branch']}**\n"
        f"📚 **عدد المواد المسجلة: {len(portal_data['courses'])}**\n\n"
        "اختر المادة التي تريد التواصل مع زملائك فيها:"
    )
    
    bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode="Markdown")

# ========== معالجات القروبات ==========
def handle_groups_display(chat_id):
    """عرض القروبات"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    categories = get_categories()
    for category in categories:
        markup.add(types.KeyboardButton(category))
    markup.add(types.KeyboardButton("🔍 بحث في القروبات"))
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
    bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔍 بحث في القروبات")
def ask_search(message):
    bot.send_message(message.chat.id, "🔍 اكتب كلمة للبحث في القروبات:")
    bot.register_next_step_handler(message, process_search)

def process_search(message):
    chat_id = message.chat.id
    search_term = message.text.strip()

    groups = get_groups_by_category(search_term)
    
    if groups:
        response = "🔍 نتائج البحث:\n\n"
        for name, link in groups:
            response += f"• {name}\n{link}\n\n"
        bot.send_message(chat_id, response)
    else:
        bot.send_message(chat_id, "❌ لا توجد نتائج")

# ========== معالجات التقويم ==========
@bot.message_handler(func=lambda message: message.text.startswith("📅 فترة التأجيل:") or message.text.startswith("📅 حالة التأجيل:"))
def handle_delay_display(message):
    """عرض حالة التأجيل"""
    bot.send_message(message.chat.id, "ℹ️ هذه العبارة توضح حالة التأجيل الحالية. للتحقق من أحدث حالة، اضغط على 🔄 تحديث حالة التأجيل")

@bot.message_handler(func=lambda message: message.text == "🔄 تحديث حالة التأجيل")
def handle_delay_refresh(message):
    """تحديث حالة التأجيل"""
    chat_id = message.chat.id
    user = get_user(chat_id)
    
    if not user or not user.get("student_id"):
        bot.send_message(chat_id, "⚠️ يرجى تسجيل الدخول أولاً")
        return
    
    bot.send_chat_action(chat_id, 'typing')
    
    scraper = QOUScraper(user["student_id"], user["password"])
    
    if scraper.login():
        session_statess[chat_id] = scraper
        new_status = scraper.get_delay_status()
        bot.send_message(chat_id, f"✅ تم التحديث: {new_status}")
        send_cel_services(chat_id)
    else:
        bot.send_message(chat_id, "❌ فشل تسجيل الدخول")

@bot.message_handler(func=lambda message: message.text == "📅 المواعيد المجدولة")
def handle_scheduled_events_message(message):
    """معالجة عرض المواعيد المجدولة"""
    try:
        chat_id = message.chat.id
        logger.info(f"[{chat_id}] طلب عرض المواعيد المجدولة")
        
        bot.send_chat_action(chat_id, 'typing')
        events_info = get_user_scheduled_events(chat_id)
        
        if events_info is None:
            bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب المواعيد المجدولة")
            return
        
        events_message = format_scheduled_events_message(events_info)
        
        markup = types.InlineKeyboardMarkup()
        update_button = types.InlineKeyboardButton("🔄 تحديث الجدولة الآن", callback_data="update_schedule")
        markup.add(update_button)
        
        bot.send_message(chat_id, events_message, parse_mode='Markdown', reply_markup=markup)
        
        logger.info(f"[{chat_id}] تم عرض المواعيد المجدولة بنجاح")
        
    except Exception as e:
        logger.error(f"خطأ في معالجة طلب المواعيد المجدولة: {e}")
        bot.send_message(message.chat.id, "❌ حدث خطأ أثناء جلب المواعيد المجدولة")

# ========== معالجات الأدمن ==========
def show_admin_menu(chat_id):
    """عرض قائمة الأدمن"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        types.KeyboardButton("التحليلات"),
        types.KeyboardButton("إرسال رسالة"),
        types.KeyboardButton("إدارة المواعيد"),
        types.KeyboardButton("إضافة قروب"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⚙️ قائمة الأدمن: اختر خياراً", reply_markup=markup)

def start_broadcast(chat_id):
    """بدء عملية البث"""
    bot.send_message(chat_id, "✍️ الرجاء كتابة نص الرسالة التي تريد إرسالها لجميع المستخدمين:")
    admin_states[chat_id] = "awaiting_broadcast_text"

def show_deadline_management(chat_id):
    """إدارة المواعيد للأدمن"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        types.KeyboardButton("➕ إضافة موعد"),
        types.KeyboardButton("✏️ تعديل موعد"),
        types.KeyboardButton("❌ حذف موعد"),
        types.KeyboardButton("📋 عرض كل المواعيد"),
        types.KeyboardButton("⬅️ عودة للقائمة")
    )
    bot.send_message(chat_id, "⚙️ إدارة المواعيد: اختر خياراً", reply_markup=markup)

def show_analytics(chat_id):
    """عرض التحليلات"""
    stats = get_bot_stats()
    stats_text = (
        "📊 *إحصائيات عامة للبوت:*\n\n"
        f"- عدد المستخدمين المسجلين: {stats.get('total_users', 0)}\n"
        f"- المستخدمين الجدد اليوم: {stats.get('new_today', 0)}\n"
        f"- المستخدمين الجدد خلال الأسبوع: {stats.get('new_last_7_days', 0)}\n"
        f"- المستخدمين الجدد خلال الشهر: {stats.get('new_last_30_days', 0)}\n"
        f"- عدد المستخدمين غير النشطين (>7 أيام): {stats.get('inactive_users', 0)}\n"
    )
    bot.send_message(chat_id, stats_text, parse_mode="Markdown")

def start_add_group(chat_id):
    """بدء إضافة قروب"""
    admin_group_states[chat_id] = {"stage": "awaiting_category"}
    bot.send_message(chat_id, "📂 أدخل تصنيف القروب (مثل: مواد، تخصصات، جامعة):")

# ========== المعالج الرئيسي للرسائل ==========
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()
    
    # 1. التحقق من المحادثات النشطة
    if chat_id in user_sessions and user_sessions[chat_id].get('in_chat'):
        handle_active_chat(chat_id, text)
        return
    
    # 2. معالجة رسائل البث للأدمن
    if chat_id in ADMIN_CHAT_ID and admin_states.get(chat_id) == "awaiting_broadcast_text":
        handle_admin_broadcast(chat_id, text)
        return
    
    # 3. معالجة التسجيل
    if chat_id in registration_states:
        handle_registration(chat_id, text)
        return
    
    # 4. معالجة اللقاءات الافتراضية
    if handle_virtual_meetings(chat_id, text):
        return
    if handle_ecourse_selection(chat_id, text):
        return
    if handle_meeting_selection(chat_id, text):
        return
    
    # 5. معالجة الأزرار الرئيسية
    handle_main_buttons(chat_id, text)
    
    # 6. معالجة أزرار الأدمن
    if chat_id in ADMIN_CHAT_ID:
        handle_admin_buttons(chat_id, text)

def handle_active_chat(chat_id, text):
    """معالجة المحادثات النشطة"""
    if text == "✖️ إنهاء المحادثة":
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
        return
        
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

def handle_admin_broadcast(chat_id, text):
    """معالجة بث الرسائل للأدمن"""
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
            user_id = target_chat_id
            username = f"@{user_info.username}" if user_info.username else "—"
            full_name = user_info.first_name or ""
            if user_info.last_name:
                full_name += f" {user_info.last_name}"

            successful_users.append((str(user_id), username, full_name))

        except Exception as e:
            logger.exception(f"Failed to send message to {target_chat_id}: {e}")
            failed_count += 1

    header_text = "تم ارسال الرسالة بنجاح إلى:\n"
    table_header = f"{'Chat ID':<15} | {'Username':<15} | {'Name'}\n"
    separator = "-" * 50 + "\n"
    table_rows = ""

    for user_id, username, full_name in successful_users:
        table_rows += f"{user_id:<15} | {username:<15} | {full_name}\n"

    report_text = header_text + table_header + separator + table_rows
    report_text += f"\n❌ فشل الإرسال إلى {failed_count} مستخدم." if failed_count else ""

    if len(report_text) > 4000:
        with open("broadcast_report.txt", "w", encoding="utf-8") as f:
            f.write(report_text)
        with open("broadcast_report.txt", "rb") as f:
            bot.send_document(chat_id, f)
    else:
        bot.send_message(chat_id, f"```{report_text}```", parse_mode="Markdown")

    admin_states.pop(chat_id, None)
    send_main_menu(chat_id)

def handle_registration(chat_id, text):
    """معالجة عملية التسجيل"""
    stage = registration_states[chat_id].get("stage")

    if stage == "awaiting_student_id":
        registration_states[chat_id]["student_id"] = text
        registration_states[chat_id]["stage"] = "awaiting_password"
        bot.send_message(chat_id, "🔒 الآن، الرجاء إرسال كلمة المرور:")
        return

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

def handle_main_buttons(chat_id, text):
    """معالجة أزرار القائمة الرئيسية"""
    # أزرار التنقل الرئيسية
    if text == "👤 تسجيل الدخول":
        start_login(chat_id)
        return
    elif text == "📖 الخدمات الأكاديمية":
        send_academic_services(chat_id)
        return
    elif text == "📚 أخرى":
        send_other_services(chat_id)
        return
    elif text == "📅 التـــقويــم":
        send_cel_services(chat_id)
        return
    elif text == "📖 الخطة الدراسية":
        send_academic_stats_menu(chat_id)
        return
    elif text == "🔗 منصة المواد المشتركة":
        send_manasa_services(chat_id)
        return
    elif text == "⬅️ عودة للرئيسية":
        send_main_menu(chat_id)
        return
    elif text == "🚪 تسجيل الخروج":
        logout_user(chat_id)
        bot.send_message(chat_id, "✅ تم تسجيل الخروج بنجاح!")
        send_main_menu(chat_id)
        return

    # الخدمات الأكاديمية
    handle_academic_services(chat_id, text)
    
    # الخدمات الأخرى
    handle_other_services(chat_id, text)
    
    # منصة المواد المشتركة
    handle_manasa_services(chat_id, text)
    
    # الخطط الدراسية
    handle_study_plans(chat_id, text)

def handle_academic_services(chat_id, text):
    """معالجة الخدمات الأكاديمية"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    try:
        if text == "📖 عرض المقررات والعلامات":
            handle_courses_grades(chat_id, user)
        elif text == "🗓️ جدول المحاضرات":
            handle_lecture_schedule(chat_id, user)
        elif text == "📊 عرض بيانات الفصل":
            handle_term_stats(chat_id, user)
        elif text == "📅 جدول الامتحانات":
            handle_exam_schedule(chat_id, user)
        elif text == "🎙️ حلقات النقاش":
            handle_discussion_sessions(chat_id, user)
        elif text == "💰 رصيد الطالب":
            handle_student_balance(chat_id, user)
        elif text == "📚 الخطط الدراسية":
            handle_study_plans_menu(chat_id)
        elif text == "💻 اللقاءات الافتراضية":
            handle_virtual_meetings(chat_id, text)
    except Exception as e:
        logger.error(f"Error in academic services for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء معالجة طلبك.")

def handle_other_services(chat_id, text):
    """معالجة الخدمات الأخرى"""
    if text == "📅 المواعيد المجدولة":
        handle_scheduled_events_message(chat_id)
    elif text == "📚 عرض القروبات":
        handle_groups_display(chat_id)
    elif text == "✉️ إرسال اقتراح":
        bot.send_message(chat_id, "📬 لإرسال اقتراح، اضغط على الرابط التالي للتواصل عبر بوت الاقتراحات:\nhttps://t.me/QOUSUGBOT")

def handle_manasa_services(chat_id, text):
    """معالجة منصة المواد المشتركة"""
    if text == "🔗 ربط الحساب بمنصة المواد المشتركة":
        handle_portal_linking(chat_id)
    elif text == "👥 منصة المواد المشتركة":
        handle_shared_courses_platform(chat_id)
    elif text.startswith("📖 "):
        handle_course_selection(chat_id, text)

def handle_study_plans(chat_id, text):
    """معالجة الخطط الدراسية"""
    if text in ["📊 إحصائياتي", "📚 مقرراتي", "📌 مقررات حالية", "🎯 نسبة الإنجاز", "📋 الخطة الدراسية", "🔄 تحديث بياناتي"]:
        handle_academic_stats(chat_id, text)

def handle_course_selection(chat_id, text):
    """معالجة اختيار المادة في منصة المواد المشتركة"""
    if text.startswith("📖 "):
        selected_course = text.replace("📖 ", "").strip()
        
        portal_data = get_user_branch_and_courses(chat_id)
        if not portal_data.get('courses'):
            bot.send_message(chat_id, "❌ لا توجد مواد متاحة.")
            return
        
        # البحث عن المادة الكاملة
        full_course_name = None
        for course in portal_data['courses']:
            if selected_course in course or course.startswith(selected_course.replace("...", "")):
                full_course_name = course
                break
        
        if not full_course_name:
            bot.send_message(chat_id, "❌ لم أتعرف على المادة المحددة.")
            return
        
        # البحث عن زملاء
        partners = find_potential_partners(chat_id, full_course_name)
        
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        if partners:
            partner_count = len(partners)
            message_text = (
                f"📖 **المادة: {full_course_name}**\n"
                f"👥 **عدد الزملاء المتاحين: {partner_count}**\n\n"
                "اختر طريقة التواصل:"
            )
            
            markup.add(types.KeyboardButton(f"🎲 محادثة عشوائية - {selected_course}"))
            markup.add(types.KeyboardButton("👥 عرض قائمة الزملاء"))
            
        else:
            message_text = (
                f"📖 **المادة: {full_course_name}**\n\n"
                "❌ لا يوجد زملاء متاحين في هذه المادة حالياً.\n"
                "يمكنك المحاولة لاحقاً أو اختيار مادة أخرى."
            )
        
        markup.add(types.KeyboardButton("⬅️ عودة للمواد"))
        markup.add(types.KeyboardButton("🏠 الرئيسية"))
        
        bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode="Markdown")
        
        # حفظ حالة المستخدم
        user_sessions[chat_id] = {
            'current_course': full_course_name,
            'action': 'awaiting_communication_choice'
        }

def handle_admin_buttons(chat_id, text):
    """معالجة أزرار الأدمن"""
    if text == "admin":
        show_admin_menu(chat_id)
    elif text == "إرسال رسالة":
        start_broadcast(chat_id)
    elif text == "إدارة المواعيد":
        show_deadline_management(chat_id)
    elif text == "التحليلات":
        show_analytics(chat_id)
    elif text == "إضافة قروب":
        start_add_group(chat_id)
    elif text == "➕ إضافة موعد":
        start_add_deadline(chat_id)
    elif text == "📋 عرض كل المواعيد":
        show_all_deadlines(chat_id)
    elif text == "⬅️ عودة للقائمة" or text == "⬅️ عودة للرئيسية":
        if chat_id in ADMIN_CHAT_ID:
            show_admin_menu(chat_id)
        else:
            send_main_menu(chat_id)

def start_add_deadline(chat_id):
    """بدء إضافة موعد جديد"""
    admin_deadline_states[chat_id] = {"stage": "awaiting_name"}
    bot.send_message(chat_id, "✍️ اكتب اسم الموعد:")

def show_all_deadlines(chat_id):
    """عرض جميع المواعيد"""
    deadlines = get_all_deadlines()
    if not deadlines:
        bot.send_message(chat_id, "📭 لا توجد مواعيد حالياً.")
        return
    
    msg = "📌 المواعيد الحالية:\n\n"
    for deadline in deadlines:
        msg += f"• {deadline['name']} - {deadline['date'].strftime('%d/%m/%Y')}\n"
    
    bot.send_message(chat_id, msg)

# ========== معالجات إضافية للخطط الدراسية ==========
@bot.message_handler(func=lambda message: message.text in ["📚 مقرراتي", "📌 مقررات حالية", "🎯 نسبة الإنجاز", "📋 الخطة الدراسية"])
def handle_more_academic_stats(message):
    """معالجة المزيد من الإحصائيات الأكاديمية"""
    chat_id = message.chat.id
    text = message.text
    user = get_user(chat_id)
    
    if not user or not user['student_id'] or not user['password']:
        bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        study_plan = scraper.fetch_study_plan()
        
        if study_plan.get('status') != 'success':
            bot.send_message(chat_id, "⚠️ لم أتمكن من جلب بيانات الخطة الدراسية.")
            return

        courses = study_plan.get('courses', [])
        stats = study_plan.get('stats', {})
        
        if text == "📚 مقرراتي":
            show_all_courses(chat_id, courses)
        elif text == "📌 مقررات حالية":
            show_current_courses(chat_id, courses)
        elif text == "🎯 نسبة الإنجاز":
            show_completion_rate(chat_id, stats)
        elif text == "📋 الخطة الدراسية":
            show_study_plan_summary(chat_id, courses, stats)
            
    except Exception as e:
        logger.error(f"Error in academic stats for {chat_id}: {e}")
        bot.send_message(chat_id, f"❌ حدث خطأ: {str(e)}")

def show_all_courses(chat_id, courses):
    """عرض جميع المقررات"""
    if not courses:
        bot.send_message(chat_id, "📭 لا توجد مقررات مسجلة.")
        return
    
    # تجميع المقررات حسب التصنيف
    categories = {}
    for course in courses:
        category = course.get('category', 'غير مصنف')
        if category not in categories:
            categories[category] = []
        categories[category].append(course)
    
    message = "📚 *جميع المقررات في خطتك الدراسية:*\n\n"
    
    for category, category_courses in categories.items():
        message += f"📁 *{category}:*\n"
        for course in category_courses:
            status_emoji = "✅" if course.get('status') == 'completed' else "📝"
            message += f"{status_emoji} {course.get('course_code', '')} - {course.get('course_name', '')}\n"
        message += "\n"
    
    bot.send_message(chat_id, message, parse_mode="Markdown")

def show_current_courses(chat_id, courses):
    """عرض المقررات الحالية"""
    current_courses = [c for c in courses if c.get('status') in ['in_progress', 'registered', 'current']]
    
    if not current_courses:
        bot.send_message(chat_id, "⏳ لا توجد مقررات قيد الدراسة هذا الفصل.")
        return
    
    message = "📌 *المقررات الحالية:*\n\n"
    total_hours = 0
    
    for i, course in enumerate(current_courses, 1):
        hours = course.get('hours', 0)
        total_hours += hours
        message += f"{i}. 📚 {course.get('course_code', '')} - {course.get('course_name', '')}\n"
        message += f"   ⏰ {hours} ساعة\n\n"
    
    message += f"📊 *المجموع: {len(current_courses)} مقرر، {total_hours} ساعة*"
    
    bot.send_message(chat_id, message, parse_mode="Markdown")

def show_completion_rate(chat_id, stats):
    """عرض نسبة الإنجاز"""
    if not stats:
        bot.send_message(chat_id, "⚠️ لا توجد بيانات إحصائية متاحة.")
        return
    
    percentage = stats.get('completion_percentage', 0)
    completed = stats.get('total_hours_completed', 0)
    required = stats.get('total_hours_required', 0)
    transferred = stats.get('total_hours_transferred', 0)
    
    # إنشاء شريط التقدم
    progress_bar = "🟩" * int(percentage / 10) + "⬜" * (10 - int(percentage / 10))
    remaining = required - completed - transferred
    
    message = f"""
🎯 *نسبة إنجازك الدراسي:*

{progress_bar}
{percentage}% مكتمل

📊 *التفاصيل:*
• 📅 المطلوب: {required} ساعة
• ✅ المكتمل: {completed} ساعة  
• 🔄 المحتسب: {transferred} ساعة
• ⏳ المتبقي: {remaining if remaining > 0 else 0} ساعة
"""
    
    bot.send_message(chat_id, message, parse_mode="Markdown")

def show_study_plan_summary(chat_id, courses, stats):
    """عرض ملخص الخطة الدراسية"""
    if not courses:
        bot.send_message(chat_id, "📭 لا توجد مقررات في الخطة الدراسية.")
        return
    
    # تجميع الإحصائيات حسب التصنيف
    categories = {}
    for course in courses:
        category = course.get('category', 'غير مصنف')
        if category not in categories:
            categories[category] = {'total': 0, 'completed': 0, 'hours': 0}
        
        categories[category]['total'] += 1
        categories[category]['hours'] += course.get('hours', 0)
        if course.get('status') == 'completed':
            categories[category]['completed'] += 1
    
    message = "📋 *الخطة الدراسية الشاملة*\n\n"
    
    for category, data in categories.items():
        completion_rate = (data['completed'] / data['total']) * 100 if data['total'] > 0 else 0
        message += f"📁 *{category}:*\n"
        message += f"   {data['completed']}/{data['total']} مكتمل ({completion_rate:.1f}%)\n"
        message += f"   🕒 {data['hours']} ساعة\n\n"
    
    if stats:
        message += f"📊 *الإجمالي: {stats.get('completion_percentage', 0)}% مكتمل*"
    
    bot.send_message(chat_id, message, parse_mode="Markdown")

# ========== تشغيل البوت ==========
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()    
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling()
