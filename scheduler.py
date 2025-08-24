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
    get_deadline_by_id,
)
from qou_scraper import QOUScraper
from bot_instance import bot

# ---------------------- إعداد اللوج ----------------------
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------------- المنطقة الزمنية ----------------------
PALESTINE_TZ = pytz.timezone("Asia/Gaza")

# ---------------------- Scheduler عالمي ----------------------
exam_scheduler = BackgroundScheduler(timezone=PALESTINE_TZ)

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
    except Exception as e:
        logger.error(f"❌ خطأ أثناء إرسال الرسالة إلى {chat_id}: {e}")

def _safe_job_id(prefix: str, chat_id, exam: dict, suffix: str):
    cc = (exam.get("course_code") or "-").replace(" ", "_").replace(":", "-")
    dt = (exam.get("date") or "-").replace(" ", "_").replace(":", "-").replace("/", "-")
    tm = (exam.get("from_time") or "-").replace(" ", "_").replace(":", "-")
    return f"{prefix}_{chat_id}_{cc}_{dt}_{tm}_{suffix}"

def parse_exam_datetime(date_str: str, time_str: str):
    """
    تحويل التاريخ/الوقت من نص 12 ساعة -> datetime aware 24 ساعة للامتحانات
    """
    try:
        date_str = date_str.strip()
        time_str = time_str.strip().upper()
        dt = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
        return PALESTINE_TZ.localize(dt)
    except Exception as e:
        logger.error(f"❌ خطأ في تحويل التاريخ/الوقت: {date_str} {time_str} | {e}")
        raise e

# ====================== المهام الرئيسية ======================
def check_for_new_messages():
    while True:
        try:
            users = get_all_users()
            for user in users:
                chat_id = user['chat_id']
                student_id = user['student_id']
                password = user['password']
                last_msg_id = user.get('last_msg_id')

                scraper = QOUScraper(student_id, password)
                if scraper.login():
                    latest = scraper.fetch_latest_message()
                    if latest and latest['msg_id'] != last_msg_id:
                        text = (
                            f"📥 رسالة جديدة!\n"
                            f"📧 {latest['subject']}\n"
                            f"📝 {latest['sender']}\n"
                            f"🕒 {latest['date']}\n\n"
                            f"{latest['body']}"
                        )
                        send_message(bot, chat_id, text)
                        update_last_msg(chat_id, latest['msg_id'])
            time.sleep(20*60)
        except Exception as e:
            logger.error(f"❌ خطأ في متابعة الرسائل: {e}")
            time.sleep(60)

def check_for_course_updates():
    while True:
        try:
            now = datetime.now(PALESTINE_TZ)
            hour = now.hour
            users = get_all_users()
            for user in users:
                chat_id = user['chat_id']
                student_id = user['student_id']
                password = user['password']
                old_courses_json = user.get('courses_data')

                scraper = QOUScraper(student_id, password)
                if scraper.login():
                    courses = scraper.fetch_term_summary_courses()
                    courses_json = json.dumps(courses, ensure_ascii=False)
                    if old_courses_json:
                        old_courses = json.loads(old_courses_json)
                        changes = []
                        for c in courses:
                            old_c = next((o for o in old_courses if o['course_code'] == c['course_code']), None)
                            if old_c and (c['midterm_mark'] != old_c['midterm_mark'] or c['final_mark'] != old_c['final_mark']):
                                changes.append(c)
                        if changes:
                            msg = "📢 تحديث جديد في العلامات:\n\n"
                            for change in changes:
                                msg += f"📚 {change['course_name']}\nنصفي: {change['midterm_mark']} | نهائي: {change['final_mark']}\n\n"
                            send_message(bot, chat_id, msg)
                    update_user_courses(chat_id, courses_json)
            time.sleep(10*60 if 21 <= hour < 24 else 60*60)
        except Exception as e:
            logger.error(f"❌ خطأ في تحديث العلامات: {e}")
            time.sleep(60)

def check_for_lectures():
    notified_today = {}
    notified_1hour = {}
    notified_started = {}
    while True:
        try:
            now = datetime.now(PALESTINE_TZ)
            current_hour = now.hour
            current_weekday = now.strftime("%A")
            users = get_all_users()
            for user in users:
                chat_id = user['chat_id']
                student_id = user['student_id']
                password = user['password']
                scraper = QOUScraper(student_id, password)
                if scraper.login():
                    lectures = scraper.fetch_lectures_schedule()
                    todays_lectures = [lec for lec in lectures if lec['day'].lower() == current_weekday.lower()]
                    if not todays_lectures:
                        continue
                    if chat_id not in notified_today and current_hour == 6:
                        msg = "📅 *محاضرات اليوم:*\n\n"
                        for lec in todays_lectures:
                            msg += f"📚 {lec['course_name']} ({lec['course_code']})\n🕒 {lec['time']}\n🏫 {lec['building']} - {lec['room']}\n👨‍🏫 {lec['lecturer']}\n\n"
                        send_message(bot, chat_id, msg)
                        notified_today[chat_id] = now.date()
                    for lec in todays_lectures:
                        start_str, end_str = lec['time'].split(' - ')
                        start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
                        end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
                        start_dt = datetime.combine(now.date(), start_time).replace(tzinfo=PALESTINE_TZ)
                        end_dt = datetime.combine(now.date(), end_time).replace(tzinfo=PALESTINE_TZ)
                        diff_to_start = (start_dt - now).total_seconds() / 60
                        key_1h = f"{chat_id}_{lec['course_code']}_1h"
                        if 0 < diff_to_start <= 60 and key_1h not in notified_1hour:
                            send_message(bot, chat_id, f"⏰ باقي ساعة على محاضرتك: {lec['course_name']} تبدأ الساعة {start_str}")
                            notified_1hour[key_1h] = True
                        key_start = f"{chat_id}_{lec['course_code']}_start"
                        if start_dt <= now <= end_dt and key_start not in notified_started:
                            send_message(bot, chat_id, f"▶️ محاضرتك بلشت: {lec['course_name']} الآن")
                            notified_started[key_start] = True
                    if now.hour == 0 and now.minute == 0:
                        notified_today.clear()
                        notified_1hour.clear()
                        notified_started.clear()
            time.sleep(60)
        except Exception as e:
            logger.error(f"❌ خطأ في متابعة المحاضرات: {e}")
            time.sleep(60)

def check_for_gpa_changes():
    while True:
        try:
            users = get_all_users()
            for user in users:
                chat_id = user['chat_id']
                student_id = user['student_id']
                password = user['password']
                old_gpa = json.loads(user.get('last_gpa')) if user.get('last_gpa') else None
                scraper = QOUScraper(student_id, password)
                if scraper.login():
                    new_gpa = scraper.fetch_gpa()
                    if new_gpa and new_gpa != old_gpa:
                        msg = f"🎓 تم تحديث المعدل التراكمي!\n📘 معدل الفصل: {new_gpa.get('term_gpa', '-')}\n📚 المعدل التراكمي: {new_gpa.get('cumulative_gpa', '-')}"
                        send_message(bot, chat_id, msg)
                        update_user_gpa(chat_id, json.dumps(new_gpa))
            time.sleep(24*60*60)
        except Exception as e:
            logger.error(f"❌ خطأ في متابعة GPA: {e}")
            time.sleep(60)

def send_deadline_reminders_loop():
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
                student_id = user['student_id']
                password = user['password']
                scraper = QOUScraper(student_id, password)
                if scraper.login():
                    sessions = scraper.fetch_discussion_sessions()
                    today_sessions = [s for s in sessions if s['date'] == today_str]
                    if today_sessions and chat_id not in notified_today:
                        msg = "📅 حلقات النقاش اليوم:\n\n"
                        for s in today_sessions:
                            msg += f"📘 {s['course_name']} ({s['course_code']})\n📅 التاريخ: {s['date']} 🕒 الوقت: {s['time']}\n\n"
                        send_message(bot, chat_id, msg)
                        notified_today[chat_id] = now.date()
                    current_ids = set(f"{s['course_code']}_{s['date']}_{s['time']}" for s in sessions)
                    previous_ids = last_known_sessions.get(chat_id, set())
                    new_ids = current_ids - previous_ids
                    for new_id in new_ids:
                        for s in sessions:
                            id_check = f"{s['course_code']}_{s['date']}_{s['time']}"
                            if id_check == new_id:
                                msg = f"🆕 تمت إضافة حلقة نقاش جديدة:\n📘 {s['course_name']} ({s['course_code']})\n📅 {s['date']} 🕒 {s['time']}"
                                send_message(bot, chat_id, msg)
                    last_known_sessions[chat_id] = current_ids
                    for s in today_sessions:
                        start_str = s['time'].split('-')[0].strip()
                        session_time = datetime.strptime(f"{s['date']} {start_str}", "%d/%m/%Y %H:%M").replace(tzinfo=PALESTINE_TZ)
                        diff = (session_time - now).total_seconds()/60
                        key = f"{chat_id}_{s['course_code']}_{s['date']}_{start_str}"
                        if 0 < diff <= 30 and key not in notified_half_hour:
                            msg = f"⏰ تذكير: لديك حلقة نقاش بعد أقل من نصف ساعة\n{s['course_name']} - {s['time']}"
                            send_message(bot, chat_id, msg)
                            notified_half_hour[key] = True
                    if now.hour == 0 and now.minute == 0:
                        notified_today.clear()
                        notified_half_hour.clear()
            time.sleep(30*60)
        except Exception as e:
            logger.error(f"❌ خطأ في حلقات النقاش: {e}")
            time.sleep(60)

# ====================== جدولة الامتحانات ======================
def schedule_exam_reminders_for_all(term_no="current_term"):
    now = datetime.now(PALESTINE_TZ)
    users = get_all_users()
    today = now.date()
    for user in users:
        chat_id = user['chat_id']
        student_id = user['student_id']
        password = user['password']
        scraper = QOUScraper(student_id, password)
        if scraper.login():
            all_today_exams = []
            for exam_type_code, exam_type_label in EXAM_TYPE_MAP.items():
                exams = scraper.fetch_exam_schedule(term_no=term_no, exam_type=exam_type_code) or []
                for exam in exams:
                    try:
                        exam_dt = parse_exam_datetime(exam.get("date",""), exam.get("from_time",""))
                        if exam_dt.date() == today:
                            exam["exam_type_label"] = exam_type_label
                            exam["exam_datetime"] = exam_dt
                            all_today_exams.append(exam)
                    except:
                        continue
            for exam in all_today_exams:
                course_name = exam.get('course_name','-')
                from_time = exam.get('from_time','-')
                exam_dt = exam['exam_datetime']
                before_2h = exam_dt - timedelta(hours=2)
                if before_2h > now:
                    job_id = _safe_job_id("exam", chat_id, exam, "2h")
                    exam_scheduler.add_job(
                        partial(send_message, bot, chat_id, f"⏰ بعد ساعتين تقريبًا عندك امتحان {course_name} الساعة {from_time}"),
                        trigger="date",
                        run_date=before_2h,
                        id=job_id,
                        replace_existing=True
                    )
                before_30m = exam_dt - timedelta(minutes=30)
                if before_30m > now:
                    job_id = _safe_job_id("exam", chat_id, exam, "30m")
                    exam_scheduler.add_job(
                        partial(send_message, bot, chat_id, f"⚠️ قرّب امتحان {course_name} الساعة {from_time}، حضّر حالك!"),
                        trigger="date",
                        run_date=before_30m,
                        id=job_id,
                        replace_existing=True
                    )
                if exam_dt > now:
                    job_id = _safe_job_id("exam", chat_id, exam, "start")
                    exam_scheduler.add_job(
                        partial(send_message, bot, chat_id, f"🚀 بدأ الآن امتحان {course_name}، بالتوفيق ❤️"),
                        trigger="date",
                        run_date=exam_dt,
                        id=job_id,
                        replace_existing=True
                    )

def exams_scheduler_loop(term_no="current_term"):
    job_defaults = {
        "coalesce": True,
        "max_instances": 4,
        "misfire_grace_time": 5*60,
    }
    exam_scheduler.configure(job_defaults=job_defaults)
    exam_scheduler.add_job(
        lambda: schedule_exam_reminders_for_all(term_no=term_no),
        trigger=CronTrigger(hour=0, minute=0),
        id="daily_exam_check",
        replace_existing=True
    )
    exam_scheduler.add_job(
        lambda: schedule_exam_reminders_for_all(term_no=term_no),
        trigger="date",
        run_date=datetime.now(PALESTINE_TZ) + timedelta(seconds=2),
        id="startup_exam_check",
        replace_existing=True
    )
    try:
        exam_scheduler.start()
        logger.info("✅ تم تشغيل جدولة الامتحانات اليومية بنجاح")
    except Exception as e:
        logger.error(f"❌ خطأ أثناء تشغيل المجدول: {e}")

# ====================== تشغيل كل المهام ======================
def start_scheduler():
    threading.Thread(target=check_for_new_messages, daemon=True).start()
    threading.Thread(target=check_for_course_updates, daemon=True).start()
    threading.Thread(target=check_for_lectures, daemon=True).start()
    threading.Thread(target=check_for_gpa_changes, daemon=True).start()
    threading.Thread(target=send_deadline_reminders_loop, daemon=True).start()
    threading.Thread(target=check_discussion_sessions, daemon=True).start()
    threading.Thread(target=exams_scheduler_loop, daemon=True).start()
    logger.info("✅ تم تشغيل جميع المهام المجدولة والخلفية بنجاح")
