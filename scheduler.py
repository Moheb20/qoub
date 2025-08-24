import logging
from functools import partial
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time
import threading
import json

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
PALESTINE_TZ = ZoneInfo("Asia/Gaza")

# ---------------------- Scheduler عالمي ----------------------
scheduler = BackgroundScheduler(timezone=PALESTINE_TZ)

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
        logger.info(f"✅ أرسلت رسالة لـ {chat_id}")
    except Exception as e:
        logger.error(f"❌ خطأ أثناء إرسال الرسالة لـ {chat_id}: {e}")

def _safe_job_id(prefix: str, chat_id, exam: dict, suffix: str):
    cc = (exam.get("course_code") or "-").replace(" ", "_").replace(":", "-")
    dt = (exam.get("date") or "-").replace(" ", "_").replace(":", "-").replace("/", "-")
    tm = (exam.get("from_time") or "-").replace(" ", "_").replace(":", "-")
    return f"{prefix}_{chat_id}_{cc}_{dt}_{tm}_{suffix}"

def parse_exam_datetime(date_str: str, time_str: str):
    try:
        dt = datetime.strptime(f"{date_str.strip()} {time_str.strip()}", "%d-%m-%Y %H:%M")
        return dt.replace(tzinfo=PALESTINE_TZ)
    except Exception as e:
        logger.error(f"❌ خطأ في تحويل التاريخ/الوقت: {date_str} {time_str} | {e}")
        return None

# ====================== مهام المجدول ======================
def task_check_messages():
    logger.info("🔹 بدء مهمة متابعة الرسائل")
    try:
        users = get_all_users()
        for u in users:
            chat_id = u['chat_id']
            scraper = QOUScraper(u['student_id'], u['password'])
            if scraper.login():
                latest = scraper.fetch_latest_message()
                if latest and latest['msg_id'] != u.get('last_msg_id'):
                    text = f"📥 رسالة جديدة!\n📧 {latest['subject']}\n📝 {latest['sender']}\n🕒 {latest['date']}\n\n{latest['body']}"
                    send_message(bot, chat_id, text)
                    update_last_msg(chat_id, latest['msg_id'])
    except Exception as e:
        logger.error(f"❌ خطأ في متابعة الرسائل: {e}")

def task_check_courses():
    logger.info("🔹 بدء مهمة متابعة العلامات")
    try:
        users = get_all_users()
        for u in users:
            chat_id = u['chat_id']
            scraper = QOUScraper(u['student_id'], u['password'])
            if scraper.login():
                courses = scraper.fetch_term_summary_courses()
                old_courses = json.loads(u.get('courses_data')) if u.get('courses_data') else []
                changes = []
                for c in courses:
                    old = next((o for o in old_courses if o['course_code']==c['course_code']), None)
                    if old and (c['midterm_mark'] != old['midterm_mark'] or c['final_mark'] != old['final_mark']):
                        changes.append(c)
                if changes:
                    msg = "📢 تحديث جديد في العلامات:\n\n"
                    for c in changes:
                        msg += f"📚 {c['course_name']}\nنصفي: {c['midterm_mark']} | نهائي: {c['final_mark']}\n\n"
                    send_message(bot, chat_id, msg)
                update_user_courses(chat_id, json.dumps(courses))
    except Exception as e:
        logger.error(f"❌ خطأ في متابعة العلامات: {e}")

def task_check_lectures():
    logger.info("🔹 بدء مهمة متابعة محاضرات اليوم")
    try:
        users = get_all_users()
        now = datetime.now(PALESTINE_TZ)
        weekday = now.strftime("%A")
        for u in users:
            chat_id = u['chat_id']
            scraper = QOUScraper(u['student_id'], u['password'])
            if scraper.login():
                lectures = scraper.fetch_lectures_schedule()
                todays_lectures = [l for l in lectures if l['day'].lower()==weekday.lower()]
                if not todays_lectures:
                    continue
                msg = "📅 محاضرات اليوم:\n\n"
                for l in todays_lectures:
                    msg += f"📚 {l['course_name']} ({l['course_code']})\n🕒 {l['time']}\n🏫 {l['building']} - {l['room']}\n👨‍🏫 {l['lecturer']}\n\n"
                send_message(bot, chat_id, msg)
    except Exception as e:
        logger.error(f"❌ خطأ في متابعة محاضرات اليوم: {e}")

def task_check_discussions():
    logger.info("🔹 بدء مهمة متابعة حلقات النقاش")
    try:
        users = get_all_users()
        now = datetime.now(PALESTINE_TZ)
        today_str = now.strftime("%d/%m/%Y")
        for u in users:
            chat_id = u['chat_id']
            scraper = QOUScraper(u['student_id'], u['password'])
            if scraper.login():
                sessions = scraper.fetch_discussion_sessions()
                today_sessions = [s for s in sessions if s['date']==today_str]
                for s in today_sessions:
                    msg = f"📅 حلقة نقاش اليوم:\n{s['course_name']} ({s['course_code']})\n🕒 {s['time']}"
                    send_message(bot, chat_id, msg)
    except Exception as e:
        logger.error(f"❌ خطأ في حلقات النقاش: {e}")

def task_check_exams():
    logger.info("🔹 بدء مهمة متابعة الامتحانات")
    try:
        users = get_all_users()
        now = datetime.now(PALESTINE_TZ)
        today = now.date()
        for u in users:
            chat_id = u['chat_id']
            scraper = QOUScraper(u['student_id'], u['password'])
            if scraper.login():
                for exam_type, label in EXAM_TYPE_MAP.items():
                    exams = scraper.fetch_exam_schedule("current_term", exam_type)
                    for ex in exams:
                        ex_dt = parse_exam_datetime(ex['date'], ex['from_time'])
                        if not ex_dt or ex_dt.date() != today:
                            continue
                        # قبل ساعتين
                        before_2h = ex_dt - timedelta(hours=2)
                        if before_2h > now:
                            job_id = _safe_job_id("exam", chat_id, ex, "2h")
                            scheduler.add_job(
                                partial(send_message, bot, chat_id, f"⏰ بعد ساعتين امتحان {ex['course_name']} الساعة {ex['from_time']}"),
                                trigger='date',
                                run_date=before_2h,
                                id=job_id,
                                replace_existing=True
                            )
                        # قبل 30 دقيقة
                        before_30m = ex_dt - timedelta(minutes=30)
                        if before_30m > now:
                            job_id = _safe_job_id("exam", chat_id, ex, "30m")
                            scheduler.add_job(
                                partial(send_message, bot, chat_id, f"⚠️ امتحان {ex['course_name']} قرب الساعة {ex['from_time']}"),
                                trigger='date',
                                run_date=before_30m,
                                id=job_id,
                                replace_existing=True
                            )
                        # وقت الامتحان
                        if ex_dt > now:
                            job_id = _safe_job_id("exam", chat_id, ex, "start")
                            scheduler.add_job(
                                partial(send_message, bot, chat_id, f"🚀 بدأ الآن امتحان {ex['course_name']}"),
                                trigger='date',
                                run_date=ex_dt,
                                id=job_id,
                                replace_existing=True
                            )
    except Exception as e:
        logger.error(f"❌ خطأ في متابعة الامتحانات: {e}")

# ====================== إضافة المهام للجدولة ======================
scheduler.add_job(task_check_messages, 'interval', minutes=20, id="job_messages")
scheduler.add_job(task_check_courses, 'interval', minutes=60, id="job_courses")
scheduler.add_job(task_check_lectures, 'interval', minutes=30, id="job_lectures")
scheduler.add_job(task_check_discussions, 'interval', minutes=30, id="job_discussions")
scheduler.add_job(task_check_exams, 'cron', hour=0, minute=0, id="job_exams")  # تفحص الامتحانات يومياً

scheduler.start()
logger.info("✅ تم تشغيل جميع المهام المجدولة بنجاح")

# ====================== حلقة لمنع خروج البرنامج ======================
try:
    while True:
        time.sleep(60)
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
    logger.info("🛑 تم إيقاف الجدولة")
