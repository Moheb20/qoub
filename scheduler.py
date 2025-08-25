import logging
from functools import partial
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
import time
import threading
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database import (
    get_all_users,
    update_last_msg,
    update_user_courses,
    update_user_gpa,
    get_all_deadlines,

)
from qou_scraper import QOUScraper
from bot_instance import bot
from database import decrypt_text, encrypt_text
from pytz import timezone  # للتوافق مع Render




# ---------------- إعداد الوقت واللوج ----------------
PALESTINE_TZ = pytz.timezone("Asia/Gaza")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("exam_scheduler")
# ---------------- إنشاء Scheduler ----------------
exam_scheduler = BackgroundScheduler(timezone=PALESTINE_TZ)
exam_scheduler.configure(job_defaults={"coalesce": True, "max_instances": 4, "misfire_grace_time": 300})


# ---------------------- Exam type labels ----------------------
EXAM_TYPE_MAP = {
    "MT&IM": "📝 النصفي",
    "FT&IF": "🏁 النهائي النظري",
    "FP&FP": "🧪 النهائي العملي",
    "LE&LE": "📈 امتحان المستوى",
}

# ====================== دوال مساعدة ======================
def send_message(bot_instance, chat_id, message):
    try:
        bot_instance.send_message(chat_id, message)
        logger.info(f"✅ أرسلت رسالة لـ {chat_id}: {message}")
    except Exception as e:
        logger.error(f"❌ خطأ أثناء إرسال الرسالة إلى {chat_id}: {e}")

def _safe_job_id(prefix: str, chat_id, exam: dict, suffix: str):
    cc = (exam.get("course_code") or "-").replace(" ", "_").replace(":", "-")
    dt = (exam.get("date") or "-").replace(" ", "_").replace(":", "-").replace("/", "-")
    tm = (exam.get("from_time") or "-").replace(" ", "_").replace(":", "-")
    return f"{prefix}_{chat_id}_{cc}_{dt}_{tm}_{suffix}"

def parse_exam_datetime(date_str: str, time_str: str):
    try:
        dt = datetime.strptime(f"{date_str.strip()} {time_str.strip()}", "%d-%m-%Y %H:%M")
        return PALESTINE_TZ.localize(dt)
    except Exception as e:
        logger.error(f"❌ خطأ في تحويل التاريخ/الوقت: {date_str} {time_str} | {e}")
        return None

# ====================== المهام الرئيسية ======================
def check_for_new_messages():
    while True:
        try:
            users = get_all_users()
            for user in users:
                chat_id = user['chat_id']
                scraper = QOUScraper(user['student_id'], user['password'])
                if scraper.login():
                    latest = scraper.fetch_latest_message()
                    if latest and latest['msg_id'] != user.get('last_msg_id'):
                        msg = (
                            f"📥 رسالة جديدة!\n"
                            f"📧 {latest['subject']}\n"
                            f"📝 {latest['sender']}\n"
                            f"🕒 {latest['date']}\n\n"
                            f"{latest['body']}"
                        )
                        send_message(bot, chat_id, msg)
                        update_last_msg(chat_id, latest['msg_id'])
            time.sleep(20*60)
        except Exception as e:
            logger.error(f"❌ خطأ في متابعة الرسائل: {e}")
            time.sleep(60)

def check_for_course_updates():
    while True:
        try:
            users = get_all_users()
            for user in users:
                chat_id = user['chat_id']
                scraper = QOUScraper(user['student_id'], user['password'])
                if scraper.login():
                    courses = scraper.fetch_term_summary_courses()
                    old_courses = json.loads(user.get('courses_data')) if user.get('courses_data') else []
                    changes = []
                    for c in courses:
                        old_c = next((o for o in old_courses if o['course_code']==c['course_code']), None)
                        if old_c and (c['midterm_mark'] != old_c['midterm_mark'] or c['final_mark'] != old_c['final_mark']):
                            changes.append(c)
                    if changes:
                        msg = "📢 تحديث جديد في العلامات:\n\n"
                        for c in changes:
                            msg += f"📚 {c['course_name']}\nنصفي: {c['midterm_mark']} | نهائي: {c['final_mark']}\n\n"
                        send_message(bot, chat_id, msg)
                    update_user_courses(chat_id, json.dumps(courses))
            time.sleep(60*60)
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث العلامات: {e}")
            time.sleep(60)

def check_for_gpa_changes():
    while True:
        try:
            users = get_all_users()
            for user in users:
                chat_id = user['chat_id']
                scraper = QOUScraper(user['student_id'], user['password'])
                old_gpa = json.loads(user.get('last_gpa')) if user.get('last_gpa') else None
                new_gpa = scraper.fetch_gpa()
                if new_gpa and new_gpa != old_gpa:
                    msg = f"🎓 تم تحديث المعدل التراكمي!\n📘 معدل الفصل: {new_gpa.get('term_gpa', '-')}\n📚 المعدل التراكمي: {new_gpa.get('cumulative_gpa', '-')}"
                    send_message(bot, chat_id, msg)
                    update_user_gpa(chat_id, json.dumps(new_gpa))
            time.sleep(24*60*60)
        except Exception as e:
            logger.error(f"❌ خطأ في متابعة GPA: {e}")
            time.sleep(60)

def check_discussion_sessions():
    notified_today = {}
    notified_half_hour = {}
    last_known_sessions = {}
    while True:
        try:
            now = datetime.now(PALESTINE_TZ)
            today_str = now.strftime("%d/%m/%Y")
            users = get_all_users()
            for user in users:
                chat_id = user['chat_id']
                scraper = QOUScraper(user['student_id'], user['password'])
                if scraper.login():
                    sessions = scraper.fetch_discussion_sessions()
                    today_sessions = [s for s in sessions if s['date'] == today_str]
                    if today_sessions and chat_id not in notified_today:
                        msg = "📅 حلقات النقاش اليوم:\n\n"
                        for s in today_sessions:
                            msg += f"📘 {s['course_name']} ({s['course_code']}) - {s['time']}\n"
                        send_message(bot, chat_id, msg)
                        notified_today[chat_id] = now.date()
                    current_ids = set(f"{s['course_code']}_{s['date']}_{s['time']}" for s in sessions)
                    previous_ids = last_known_sessions.get(chat_id, set())
                    new_ids = current_ids - previous_ids
                    for new_id in new_ids:
                        for s in sessions:
                            if f"{s['course_code']}_{s['date']}_{s['time']}" == new_id:
                                msg = f"🆕 تمت إضافة حلقة نقاش جديدة:\n📘 {s['course_name']} ({s['course_code']}) - {s['time']}"
                                send_message(bot, chat_id, msg)
                    last_known_sessions[chat_id] = current_ids
                    for s in today_sessions:
                        start_time = datetime.strptime(f"{s['date']} {s['time'].split('-')[0].strip()}", "%d/%m/%Y %H:%M").replace(tzinfo=PALESTINE_TZ)
                        diff = (start_time - now).total_seconds()/60
                        key = f"{chat_id}_{s['course_code']}_{s['date']}"
                        if 0 < diff <= 30 and key not in notified_half_hour:
                            send_message(bot, chat_id, f"⏰ تذكير: حلقة النقاش {s['course_name']} بعد أقل من نصف ساعة")
                            notified_half_hour[key] = True
                    if now.hour == 0 and now.minute == 0:
                        notified_today.clear()
                        notified_half_hour.clear()
            time.sleep(30*60)
        except Exception as e:
            logger.error(f"❌ خطأ في حلقات النقاش: {e}")
            time.sleep(60)

def send_reminder_for_new_deadline():
    while True:
        try:
            deadlines = get_all_deadlines()
            users = get_all_users()
            today = datetime.now(PALESTINE_TZ).date()
            for user in users:
                chat_id = user['chat_id']
                msg_lines = []
                for d_id, d_name, d_date in deadlines:
                    days_left = (d_date - today).days
                    if days_left >= 0:
                        msg_lines.append(f"⏰ باقي {days_left} يوم للموعد: {d_name} ({d_date.strftime('%d/%m/%Y')})")
                if msg_lines:
                    send_message(bot, chat_id, "📌 تذكير بالمواعيد القادمة:\n\n" + "\n".join(msg_lines))
            time.sleep(12*60*60)
        except Exception as e:
            logger.error(f"❌ خطأ في تذكيرات المواعيد: {e}")
            time.sleep(60)



def schedule_lecture_reminders_for_all():
    now = datetime.now(PALESTINE_TZ)
    today = now.date()
    users = get_all_users()  # جلب كل المستخدمين من قاعدة البيانات

    # تحويل أسماء الأيام العربية إلى أرقام weekday
    days_map = {
        "الاثنين": 0,
        "الثلاثاء": 1,
        "الأربعاء": 2,
        "الخميس": 3,
        "الجمعة": 4,
        "السبت": 5,
        "الأحد": 6
    }

    for user in users:
        chat_id = user['chat_id']
        student_id = decrypt_text(user['student_id'])
        password = decrypt_text(user['password'])

        scraper = QOUScraper(student_id, password)
        if scraper.login():
            lectures = scraper.fetch_lectures_schedule()
            logger.info(f"Lectures for {student_id}: {lectures}")

            for lecture in lectures:
                lecture_day = lecture['day'].strip()
                if lecture_day not in days_map:
                    continue

                lecture_time_str = lecture['time']  # مثال: "08:30 - 10:00"
                start_time_str = lecture_time_str.split('-')[0].strip()
                hour, minute = map(int, start_time_str.split(':'))

                # احصل على تاريخ المحاضرة القادمة لهذا اليوم
                today_weekday = today.weekday()
                target_weekday = days_map[lecture_day]
                delta_days = (target_weekday - today_weekday) % 7
                lecture_date = today + timedelta(days=delta_days)

                lecture_start = datetime.combine(lecture_date, time(hour, minute, tzinfo=PALESTINE_TZ))

                # ---- أوقات التذكير ----
                day_start = datetime.combine(lecture_date, time(2, 35, tzinfo=PALESTINE_TZ))
                before_1h = lecture_start - timedelta(hours=1)
                before_15m = lecture_start - timedelta(minutes=15)

                reminders = [
                    (day_start, f"🟢 بداية اليوم عندك محاضرة {lecture['course_name']} الساعة {start_time_str}"),
                    (before_1h, f"⏰ بعد ساعة تقريبًا عندك محاضرة {lecture['course_name']}"),
                    (before_15m, f"⚠️ قرّبت محاضرة {lecture['course_name']}، حضّر حالك!"),
                    (lecture_start, f"🚀 بدأت الآن محاضرة {lecture['course_name']}، بالتوفيق ❤️")
                ]

                for remind_time, message in reminders:
                    if remind_time > now:
                        exam_scheduler.add_job(
                            partial(send_message, bot, chat_id, message),
                            trigger="date",
                            run_date=remind_time,
                            id=_safe_job_id("lecture", chat_id, lecture, str(remind_time)),
                            replace_existing=True
                        )
                        logger.info(f"⏰ جدولت تذكير: {message} في {remind_time}")

def start_exam_scheduler():
    """
    بدء جدولة فحص الامتحانات لكل الطلاب.
    """
    scheduler = BackgroundScheduler(timezone=PALESTINE_TZ)

    def check_today_exams():
        try:
            logger.info("✅ بدء فحص امتحانات اليوم لكل الطلاب")
            users = get_all_users()
            today = datetime.now(PALESTINE_TZ).date()

            for user in users:
                user_id = user[0]
                student_id = user[1]
                password = user[2]

                user_scraper = QOUScraper(student_id, password)
                if not user_scraper.login():
                    logger.warning(f"[{user_id}] فشل تسجيل الدخول للطالب {student_id}")
                    continue
                logger.info(f"[{user_id}] تم تسجيل الدخول بنجاح")

                # جلب آخر فصلين
                terms = user_scraper.get_last_two_terms()
                if not terms:
                    logger.warning(f"[{user_id}] لا توجد فصول دراسية")
                    continue

                for term in terms:
                    # جلب كل أنواع الامتحانات الموجودة
                    exams = []
                    try:
                        exams = user_scraper.fetch_exam_schedule(term["value"], exam_type="")
                    except Exception as e:
                        logger.exception(f"[{user_id}] خطأ أثناء جلب الامتحانات: {e}")
                        continue

                    for e in exams:
                        exam_dt = user_scraper.parse_exam_datetime(e["date"], e["from_time"])
                        if not exam_dt:
                            continue

                        if exam_dt.date() == today:
                            # رسالة اليوم
                            msg = (
                                f"📌 عندك امتحان اليوم:\n"
                                f"المادة: {e['course_name']}\n"
                                f"النوع: {e['exam_kind']}\n"
                                f"الساعة: {e['from_time']} - {e['to_time']}\n"
                                f"المحاضر: {e['lecturer']}\n"
                                f"القسم: {e['section']}\n"
                                f"ملاحظة: {e['note']}"
                            )
                            bot.send_message(user_id, msg)
                            logger.info(f"[{user_id}] تم إعلامه بالامتحان اليوم: {e['course_name']}")

                            # جدولة التذكيرات
                            reminders = [
                                ("2h_before", exam_dt - timedelta(hours=2), f"⏰ امتحان {e['course_name']} بعد ساعتين"),
                                ("30m_before", exam_dt - timedelta(minutes=30), f"⚡ امتحان {e['course_name']} بعد 30 دقيقة"),
                                ("at_start", exam_dt, f"🚀 هلا بلش امتحان {e['course_name']}")
                            ]

                            for r_type, r_time, r_msg in reminders:
                                if r_time > datetime.now(PALESTINE_TZ):
                                    scheduler.add_job(
                                        lambda uid=user_id, msg=r_msg: bot.send_message(uid, msg),
                                        "date",
                                        run_date=r_time
                                    )

            logger.info("✅ انتهى فحص امتحانات اليوم")

        except Exception as e:
            logger.exception(f"فشل أثناء فحص امتحانات اليوم: {e}")

    # --- جدولة الفحص اليومي الساعة 12 صباحًا ---
    scheduler.add_job(check_today_exams, "cron", hour=0, minute=0)
    scheduler.start()
    logger.info("🕒 تم بدء جدولة امتحانات اليوم")

def start_exam_scheduler_thread():
    """
    بدء الـ scheduler في Thread دايم.
    """
    threading.Thread(target=start_exam_scheduler, daemon=True).start()
    logger.info("✅ Thread جدولة امتحانات اليوم بدأ")
# ---------------- تشغيل كل المهام ----------------
def start_scheduler():
    threading.Thread(target=check_for_new_messages, daemon=True).start()
    threading.Thread(target=check_for_course_updates, daemon=True).start()
    threading.Thread(target=check_discussion_sessions, daemon=True).start()
    threading.Thread(target=check_for_gpa_changes, daemon=True).start()
    threading.Thread(target=send_reminder_for_new_deadline, daemon=True).start()
    threading.Thread(target=schedule_daily_exam_check, daemon=True).start()




    logger.info("✅ تم تشغيل جميع المهام المجدولة والخلفية بنجاح")

