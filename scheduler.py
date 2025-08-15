import time
import threading
import json
from datetime import datetime, timedelta
from database import (
    get_all_users,
    update_last_msg,
    update_user_courses,
    update_user_gpa,
)
from qou_scraper import QOUScraper
from bot_instance import bot
send_lock = threading.Lock()  # لقفل الإرسال الآمن داخل الثريد

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

def send_due_date_reminder():
    notified_12h = {}
    notified_1h = {}
    notified_due = {}

    while True:
        now = datetime.now()
        users = get_all_users()

        for user in users:
            chat_id = user['chat_id']
            student_id = user['student_id']
            password = user['password']

            scraper = QOUScraper(student_id, password)
            if scraper.login():
                try:
                    tasks = scraper.fetch_due_dates()  # يفترض أن ترجع قائمة المهام/المواعيد
                    for task in tasks:
                        task_name = task['name']
                        due_dt = datetime.strptime(task['due'], "%Y-%m-%d %H:%M")

                        diff_minutes = (due_dt - now).total_seconds() / 60

                        key_12h = f"{chat_id}_{task_name}_12h"
                        if 0 < diff_minutes <= 12 * 60 and key_12h not in notified_12h:
                            bot.send_message(chat_id, f"⏰ تذكير: لديك مهمة '{task_name}' خلال 12 ساعة!")
                            notified_12h[key_12h] = True

                        key_1h = f"{chat_id}_{task_name}_1h"
                        if 0 < diff_minutes <= 60 and key_1h not in notified_1h:
                            bot.send_message(chat_id, f"⚠️ تبقى ساعة واحدة فقط على انتهاء المهمة '{task_name}'!")
                            notified_1h[key_1h] = True

                        key_due = f"{chat_id}_{task_name}_due"
                        if now >= due_dt and key_due not in notified_due:
                            bot.send_message(chat_id, f"✅ انتهت المهمة '{task_name}'!")
                            notified_due[key_due] = True

                except Exception as e:
                    print(f"❌ خطأ أثناء التحقق من مواعيد الطالب {student_id}: {e}")

        time.sleep(5 * 60)  # كل 5 دقائق

# ---------------------- تشغيل كل المهام ----------------------
def start_scheduler():
    threading.Thread(target=check_for_new_messages, daemon=True).start()
    threading.Thread(target=check_for_course_updates, daemon=True).start()
    threading.Thread(target=check_for_lectures, daemon=True).start()
    threading.Thread(target=check_for_gpa_changes, daemon=True).start()
    threading.Thread(target=send_due_date_reminder, daemon=True).start()  # إضافة التذكير
