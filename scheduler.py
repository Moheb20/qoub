import time
import threading
import json
from datetime import datetime, date, timedelta
from database import (
    get_all_users,
    update_last_msg,
    update_user_courses,
    update_user_gpa,
    get_all_deadlines,
    get_deadline_by_id,

)
from qou_scraper import QOUScraper
import logging
from bot_instance import bot
send_lock = threading.Lock()  # لقفل الإرسال الآمن داخل الثريد

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        time.sleep(20 * 60)  # كل 20 دقيقة

# ---------------------- متابعة تغير العلامات ----------------------
def check_for_course_updates():
    while True:
        now = datetime.now()
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
                            if old_c:
                                if c['midterm_mark'] != old_c['midterm_mark'] or c['final_mark'] != old_c['final_mark']:
                                    changes.append(c)

                        if changes:
                            msg = "📢 تحديث جديد في العلامات:\n\n"
                            for change in changes:
                                msg += f"📚 {change['course_name']}\n"
                                msg += f"نصفي: {change['midterm_mark']} | نهائي: {change['final_mark']}\n\n"
                            bot.send_message(chat_id, msg)

                    update_user_courses(chat_id, courses_json)

                except Exception as e:
                    print(f"❌ خطأ مع {student_id}: {e}")

        if 21 <= hour < 24:
            time.sleep(10 * 60)  # كل 10 دقائق
        else:
            time.sleep(60 * 60)  # كل ساعة

# ---------------------- متابعة جدول المحاضرات ----------------------
def check_for_lectures():
    notified_today = {}
    notified_1hour = {}
    notified_started = {}

    while True:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
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
                        start_time = datetime.strptime(start_str, "%H:%M").time()
                        end_time = datetime.strptime(end_str, "%H:%M").time()

                        start_dt = datetime.combine(now.date(), start_time)
                        end_dt = datetime.combine(now.date(), end_time)
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
                    print(f"❌ خطأ في جلب محاضرات الطالب {student_id}: {e}")

        time.sleep(60)

# ---------------------- متابعة تغير المعدل التراكمي ----------------------
def check_for_gpa_changes():
    while True:
        users = get_all_users()
        for user in users:
            chat_id = user['chat_id']
            student_id = user['student_id']
            password = user['password']
            old_gpa = user.get('last_gpa')
            old_gpa = json.loads(old_gpa) if old_gpa else None

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
                    print(f"❌ خطأ أثناء التحقق من GPA للطالب {student_id}: {e}")

        time.sleep(24 * 60 * 60)


def send_deadline_reminders_loop():
    """
    ترسل تذكيرات للمستخدمين بكل المواعيد كل 12 ساعة.
    """
    while True:
        try:
            deadlines = get_all_deadlines()  # [(id, name, date)]
            users = get_all_users()          # [{'chat_id': ...}, ...]
            today = date.today()

            for user in users:
                chat_id = user['chat_id']
                msg_lines = []

                for d_id, d_name, d_date in deadlines:
                    days_left = (d_date - today).days
                    if days_left >= 0:
                        msg_lines.append(f"⏰ باقي {days_left} يوم للموعد: {d_name} ({d_date.strftime('%d/%m/%Y')})")

                if msg_lines:
                    full_msg = "📌 تذكير بالمواعيد القادمة:\n\n" + "\n".join(msg_lines)
                    try:
                        bot.send_message(chat_id, full_msg)
                    except Exception as e:
                        logger.exception(f"Failed to send deadline reminder to {chat_id}: {e}")

        except Exception as e:
            logger.exception(f"Error in deadline reminders loop: {e}")

        # انتظر 12 ساعة قبل التكرار
        time.sleep(12 * 60 * 60)


# دالة لإرسال تذكير فوري عند إضافة موعد جديد
def send_reminder_for_new_deadline(deadline_id):
    deadline = get_deadline_by_id(deadline_id)
    if not deadline:
        return

    users = get_all_users()
    d_id, d_name, d_date = deadline
    today = date.today()
    days_left = (d_date - today).days

    if days_left < 0:
        return

    for user in users:
        chat_id = user['chat_id']
        msg = f"⏰ تم إضافة موعد جديد: {d_name} بتاريخ {d_date.strftime('%d/%m/%Y')} (باقي {days_left} يوم)"
        try:
            bot.send_message(chat_id, msg)
        except Exception as e:
            logger.exception(f"Failed to send new deadline reminder to {chat_id}: {e}")

def check_discussion_sessions():
    notified_today = {}
    notified_half_hour = {}
    last_known_sessions = {}

    while True:
        now = datetime.now()
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

                    # 📌 1. تنبيه بوجود حلقة نقاش اليوم
                    if today_sessions and chat_id not in notified_today:
                        msg = "📅 *حلقات النقاش اليوم:*\n\n"
                        for s in today_sessions:
                            msg += (
                                f"📘 {s['course_name']} ({s['course_code']})\n"
                                f"📅 التاريخ: {s['date']} 🕒 الوقت: {s['time']}\n\n"
                            )
                        bot.send_message(chat_id, msg, parse_mode="Markdown")
                        notified_today[chat_id] = now.date()

                    # 📌 2. تنبيه عند إضافة حلقة نقاش جديدة
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

                    # 📌 3. تذكير قبل الموعد بـ 30 دقيقة
                    for s in today_sessions:
                        start_str = s['time'].split('-')[0].strip()  # 11:00
                        session_time = datetime.strptime(f"{s['date']} {start_str}", "%d/%m/%Y %H:%M")
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

                    # إعادة التهيئة يومياً
                    if now.hour == 0 and now.minute == 0:
                        notified_today.clear()
                        notified_half_hour.clear()

                except Exception as e:
                    logger.error(f"❌ خطأ أثناء التحقق من حلقات النقاش للطالب {student_id}: {e}")

        time.sleep(30 * 60)  # كل نصف ساعة



# ---------------------- تشغيل كل المهام ----------------------
def start_scheduler():
    threading.Thread(target=check_for_new_messages, daemon=True).start()
    threading.Thread(target=check_for_course_updates, daemon=True).start()
    threading.Thread(target=check_for_lectures, daemon=True).start()
    threading.Thread(target=check_for_gpa_changes, daemon=True).start()
    threading.Thread(target=send_deadline_reminders_loop, daemon=True).start()
    threading.Thread(target=send_reminder_for_new_deadline, daemon=True).start()
    threading.Thread(target=check_discussion_sessions, daemon=True).start()  # ⬅️ تمت إضافتها


