import time
import threading
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo  # ✅ لإدارة التوقيت

from apscheduler.schedulers.background import BackgroundScheduler

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

send_lock = threading.Lock()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PALESTINE_TZ = ZoneInfo("Asia/Jerusalem")  # ✅ توقيت القدس

# ---------------------- متابعة الرسائل الجديدة ----------------------
def check_for_new_messages():
    while True:
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
                    bot.send_message(chat_id, text)
                    update_last_msg(chat_id, latest['msg_id'])
        time.sleep(20 * 60)

# ---------------------- متابعة تغير العلامات ----------------------
def check_for_course_updates():
    while True:
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
                try:
                    courses = scraper.fetch_term_summary_courses()
                    courses_json = json.dumps(courses, ensure_ascii=False)

                    if old_courses_json:
                        old_courses = json.loads(old_courses_json)
                        changes = []
                        for c in courses:
                            old_c = next((o for o in old_courses if o['course_code'] == c['course_code']), None)
                            if old_c and (
                                c['midterm_mark'] != old_c['midterm_mark'] or
                                c['final_mark'] != old_c['final_mark']
                            ):
                                changes.append(c)

                        if changes:
                            msg = "📢 تحديث جديد في العلامات:\n\n"
                            for change in changes:
                                msg += (
                                    f"📚 {change['course_name']}\n"
                                    f"نصفي: {change['midterm_mark']} | نهائي: {change['final_mark']}\n\n"
                                )
                            bot.send_message(chat_id, msg)

                    update_user_courses(chat_id, courses_json)

                except Exception as e:
                    logger.error(f"❌ خطأ مع {student_id}: {e}")

        time.sleep(10 * 60 if 21 <= hour < 24 else 60 * 60)

# ---------------------- متابعة جدول المحاضرات ----------------------
def check_for_lectures():
    notified_today = {}
    notified_1hour = {}
    notified_started = {}

    while True:
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
                try:
                    lectures = scraper.fetch_lectures_schedule()
                    todays_lectures = [lec for lec in lectures if lec['day'].lower() == current_weekday.lower()]
                    if not todays_lectures:
                        continue

                    if chat_id not in notified_today and current_hour == 6:
                        msg = "📅 *محاضرات اليوم:*\n\n"
                        for lec in todays_lectures:
                            msg += (
                                f"📚 {lec['course_name']} ({lec['course_code']})\n"
                                f"🕒 {lec['time']}\n"
                                f"🏫 {lec['building']} - {lec['room']}\n"
                                f"👨‍🏫 {lec['lecturer']}\n\n"
                            )
                        bot.send_message(chat_id, msg, parse_mode="Markdown")
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
                            bot.send_message(chat_id, f"⏰ باقي ساعة على محاضرتك: {lec['course_name']} تبدأ الساعة {start_str}")
                            notified_1hour[key_1h] = True

                        key_start = f"{chat_id}_{lec['course_code']}_start"
                        if start_dt <= now <= end_dt and key_start not in notified_started:
                            bot.send_message(chat_id, f"▶️ محاضرتك بلشت: {lec['course_name']} الآن")
                            notified_started[key_start] = True

                    if now.hour == 0 and now.minute == 0:
                        notified_today.clear()
                        notified_1hour.clear()
                        notified_started.clear()

                except Exception as e:
                    logger.error(f"❌ خطأ في جلب محاضرات الطالب {student_id}: {e}")

        time.sleep(60)

# ---------------------- متابعة تغير المعدل التراكمي ----------------------
def check_for_gpa_changes():
    while True:
        users = get_all_users()
        for user in users:
            chat_id = user['chat_id']
            student_id = user['student_id']
            password = user['password']
            old_gpa = json.loads(user.get('last_gpa')) if user.get('last_gpa') else None

            scraper = QOUScraper(student_id, password)
            if scraper.login():
                try:
                    new_gpa = scraper.fetch_gpa()
                    if new_gpa and new_gpa != old_gpa:
                        message = (
                            "🎓✨ *تم تحديث بوابة الجامعة!*\n\n"
                            "🔥 تم تحديث *المعدل التراكمي!*\n\n"
                            f"📘 *معدل الفصل:* `{new_gpa.get('term_gpa', 'غير متوفر')}`\n"
                            f"📚 *المعدل التراكمي:* `{new_gpa.get('cumulative_gpa', 'غير متوفر')}`\n\n"
                            "📚 تفقد البوابة الآن لمزيد من التفاصيل!\n"
                            "#بوابة_القدس_المفتوحة"
                        )
                        bot.send_message(chat_id, message, parse_mode="Markdown")
                        update_user_gpa(chat_id, json.dumps(new_gpa))

                except Exception as e:
                    logger.error(f"❌ خطأ أثناء التحقق من GPA للطالب {student_id}: {e}")

        time.sleep(24 * 60 * 60)

# ---------------------- التذكير بالمواعيد ----------------------
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
                    bot.send_message(chat_id, "📌 تذكير بالمواعيد القادمة:\n\n" + "\n".join(msg_lines))
        except Exception as e:
            logger.exception("خطأ في التذكير بالمواعيد: %s", e)

        time.sleep(12 * 60 * 60)

def send_reminder_for_new_deadline(deadline_id):
    deadline = get_deadline_by_id(deadline_id)
    if not deadline:
        return

    d_id, d_name, d_date = deadline
    today = datetime.now(PALESTINE_TZ).date()
    days_left = (d_date - today).days
    if days_left < 0:
        return

    for user in get_all_users():
        chat_id = user['chat_id']
        msg = f"⏰ تم إضافة موعد جديد: {d_name} بتاريخ {d_date.strftime('%d/%m/%Y')} (باقي {days_left} يوم)"
        try:
            bot.send_message(chat_id, msg)
        except Exception as e:
            logger.exception(f"فشل في إرسال موعد جديد إلى {chat_id}: {e}")

# ---------------------- حلقات النقاش ----------------------
def check_discussion_sessions():
    notified_today = {}
    notified_half_hour = {}
    last_known_sessions = {}

    while True:
        now = datetime.now(PALESTINE_TZ)
        today_str = now.strftime("%d/%m/%Y")
        users = get_all_users()

        for user in users:
            chat_id = user['chat_id']
            student_id = user['student_id']
            password = user['password']

            scraper = QOUScraper(student_id, password)
            if scraper.login():
                try:
                    sessions = scraper.fetch_discussion_sessions()
                    today_sessions = [s for s in sessions if s['date'] == today_str]

                    if today_sessions and chat_id not in notified_today:
                        msg = "📅 *حلقات النقاش اليوم:*\n\n"
                        for s in today_sessions:
                            msg += (
                                f"📘 {s['course_name']} ({s['course_code']})\n"
                                f"📅 التاريخ: {s['date']} 🕒 الوقت: {s['time']}\n\n"
                            )
                        bot.send_message(chat_id, msg, parse_mode="Markdown")
                        notified_today[chat_id] = now.date()

                    current_ids = set(f"{s['course_code']}_{s['date']}_{s['time']}" for s in sessions)
                    previous_ids = last_known_sessions.get(chat_id, set())
                    new_ids = current_ids - previous_ids
                    if new_ids:
                        for new_id in new_ids:
                            for s in sessions:
                                id_check = f"{s['course_code']}_{s['date']}_{s['time']}"
                                if id_check == new_id:
                                    msg = (
                                        "🆕 *تمت إضافة حلقة نقاش جديدة:*\n\n"
                                        f"📘 {s['course_name']} ({s['course_code']})\n"
                                        f"📅 التاريخ: {s['date']} 🕒 الوقت: {s['time']}"
                                    )
                                    bot.send_message(chat_id, msg, parse_mode="Markdown")
                        last_known_sessions[chat_id] = current_ids

                    for s in today_sessions:
                        start_str = s['time'].split('-')[0].strip()
                        session_time = datetime.strptime(f"{s['date']} {start_str}", "%d/%m/%Y %H:%M").replace(tzinfo=PALESTINE_TZ)
                        diff = (session_time - now).total_seconds() / 60
                        key = f"{chat_id}_{s['course_code']}_{s['date']}_{start_str}"
                        if 0 < diff <= 30 and key not in notified_half_hour:
                            msg = (
                                f"⏰ *تذكير:*\n"
                                f"📘 لديك حلقة نقاش بعد أقل من نصف ساعة\n"
                                f"{s['course_name']} - {s['time']}"
                            )
                            bot.send_message(chat_id, msg, parse_mode="Markdown")
                            notified_half_hour[key] = True

                    if now.hour == 0 and now.minute == 0:
                        notified_today.clear()
                        notified_half_hour.clear()

                except Exception as e:
                    logger.error(f"❌ خطأ في حلقات النقاش للطالب {student_id}: {e}")

        time.sleep(30 * 60)

# ---------------------- متابعة الامتحانات ----------------------
exam_scheduler = BackgroundScheduler(timezone=PALESTINE_TZ)
exam_scheduler.start()

def schedule_exam_reminders_for_all():
    users = get_all_users()
    for user in users:
        chat_id = user['chat_id']
        student_id = user['student_id']
        password = user['password']

        scraper = QOUScraper(student_id, password)
        if scraper.login():
            exams = scraper.fetch_exam_schedule(term_no="current_term", exam_type="final")
            for exam in exams:
                exam_datetime = datetime.strptime(f"{exam['date']} {exam['from_time']}", "%Y-%m-%d %H:%M")
                exam_datetime = exam_datetime.replace(tzinfo=PALESTINE_TZ)

                # تذكير الساعة 05:00 فجراً
                day_start = exam_datetime.replace(hour=5, minute=0, second=0)
                if day_start > datetime.now(PALESTINE_TZ):
                    exam_scheduler.add_job(
                        lambda exam=exam, chat_id=chat_id: bot.send_message(
                            chat_id, f"📢 عندك اليوم امتحان: {exam['course_name']} الساعة {exam['from_time']}"
                        ),
                        trigger="date",
                        run_date=day_start,
                    )

                # تذكير قبل الامتحان بساعة
                one_hour_before = exam_datetime - timedelta(hours=1)
                if one_hour_before > datetime.now(PALESTINE_TZ):
                    exam_scheduler.add_job(
                        lambda exam=exam, chat_id=chat_id: bot.send_message(
                            chat_id, f"⏰ بعد ساعة عندك امتحان {exam['course_name']} الساعة {exam['from_time']}"
                        ),
                        trigger="date",
                        run_date=one_hour_before,
                    )

                # وقت الامتحان
                if exam_datetime > datetime.now(PALESTINE_TZ):
                    exam_scheduler.add_job(
                        lambda exam=exam, chat_id=chat_id: bot.send_message(
                            chat_id, f"🚀 بدأ الآن امتحان {exam['course_name']} بالتوفيق ❤️"
                        ),
                        trigger="date",
                        run_date=exam_datetime,
                    )

def exams_scheduler_loop():
    while True:
        try:
            schedule_exam_reminders_for_all()
        except Exception as e:
            logger.error(f"❌ خطأ في جدولة الامتحانات: {e}")
        time.sleep(6 * 60 * 60)  # تحديث الجدول كل 6 ساعات

# ---------------------- تشغيل كل المهام ----------------------
def start_scheduler():
    threading.Thread(target=check_for_new_messages, daemon=True).start()
    threading.Thread(target=check_for_course_updates, daemon=True).start()
    threading.Thread(target=check_for_lectures, daemon=True).start()
    threading.Thread(target=check_for_gpa_changes, daemon=True).start()
    threading.Thread(target=send_deadline_reminders_loop, daemon=True).start()
    threading.Thread(target=check_discussion_sessions, daemon=True).start()
    threading.Thread(target=exams_scheduler_loop, daemon=True).start()
