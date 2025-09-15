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
import app
from flask import Flask
from telebot import types
from bot_instance import bot
from database import (
    init_db,
    get_all_users,
    get_bot_stats,
    get_user,
    add_user,
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
branch_selection_states = {}      # لتخزين حالة اختيار الفرع لكل مستخدم
department_selection_states = {}  # لتخزين حالة اختيار القسم لكل مستخدم
add_number_states = {}
edit_contact_states = {}
delete_contact_states = {}



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
        types.KeyboardButton("✉️ إرسال اقتراح")  

    )
    if chat_id in ADMIN_CHAT_ID:
        markup.add(types.KeyboardButton("admin"))
    bot.send_message(chat_id, "⬇️ القائمة الرئيسية:", reply_markup=markup)


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


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    chat_id = message.chat.id
    text = (message.text or "").strip()

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

    # عرض القروبات
    # عرض التصنيفات
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

    else:
        bot.send_message(chat_id, "⚠️ لم أفهم الأمر، الرجاء اختيار زر من القائمة.")


if __name__ == "__main__":
    threading.Thread(target=run_flask).start()    
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling()
