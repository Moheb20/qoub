import time
import threading
import json
from datetime import datetime, timedelta
from database import get_all_users, update_last_msg, update_user_courses
from qou_scraper import QOUScraper
from bot_instance import bot

# ---------------------- متابعة الرسائل الجديدة ----------------------
def check_for_new_messages():
    while True:
        users = get_all_users()
        for user in users:
            chat_id = user['chat_id']
            student_id = user['student_id']
            password = user['password']
            last_msg_id = user.get('last_msg_id', None)

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


# ---------------------- متابعة تغييرات العلامات ----------------------
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

                    # تحديث البيانات
                    update_user_courses(chat_id, courses_json)

                except Exception as e:
                    print(f"خطأ مع {student_id}: {e}")

        # فترة الذروة: 9 مساءً (21) حتى 12 منتصف الليل (24)
        if 21 <= hour < 24:
            time.sleep(10 * 60)  # كل 10 دقائق
        else:
            time.sleep(60 * 60)  # كل ساعة


# ---------------------- متابعة جدول المحاضرات ----------------------
def check_for_lectures():
    notified_today = {}  # لتخزين من تم إخطارهم صباح اليوم
    notified_1hour = {}  # لتخزين من تم إخطارهم "بقيت ساعة"
    notified_started = {}  # لتخزين من تم إخطارهم "المحاضرة بلشت"

    while True:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        current_hour = now.hour
        current_weekday = now.strftime("%A")  # اسم اليوم بالإنجليزي، يمكن تعديله إذا تود بالعربي

        users = get_all_users()
        for user in users:
            chat_id = user['chat_id']
            student_id = user['student_id']
            password = user['password']

            scraper = QOUScraper(student_id, password)
            if scraper.login():
                try:
                    lectures = scraper.fetch_lectures_schedule()  # قائمة محاضرات
                    # فلترة محاضرات اليوم فقط حسب day
                    todays_lectures = [lec for lec in lectures if lec['day'].lower() == current_weekday.lower()]
                    if not todays_lectures:
                        continue

                    # إرسال تنبيه 6 صباحاً مرة يومياً
                    if chat_id not in notified_today and current_hour == 6:
                        msg = "📅 محاضرات اليوم:\n\n"
                        for lec in todays_lectures:
                            msg += (f"📚 {lec['course_name']} ({lec['course_code']})\n"
                                    f"🕒 {lec['time']}\n"
                                    f"🏫 {lec['building']} - {lec['room']}\n"
                                    f"👨‍🏫 {lec['lecturer']}\n\n")
                        bot.send_message(chat_id, msg)
                        notified_today[chat_id] = now.date()

                    # تحقق من كل محاضرة لرسائل التنبيه حسب الوقت
                    for lec in todays_lectures:
                        # وقت المحاضرة بصيغة "09:00 - 12:00"
                        start_str, end_str = lec['time'].split(' - ')
                        start_time = datetime.strptime(start_str, "%H:%M").time()
                        end_time = datetime.strptime(end_str, "%H:%M").time()

                        # نحول الوقت إلى datetime اليوم نفسه
                        start_dt = datetime.combine(now.date(), start_time)
                        end_dt = datetime.combine(now.date(), end_time)

                        diff_to_start = (start_dt - now).total_seconds() / 60  # فرق بالدقائق

                        # تنبيه قبل ساعة (باقي 60 دقيقة)
                        key_1h = f"{chat_id}_{lec['course_code']}_1h"
                        if 0 < diff_to_start <= 60 and key_1h not in notified_1hour:
                            bot.send_message(chat_id, f"⏰ باقي ساعة على محاضرتك: {lec['course_name']} تبدأ الساعة {start_str}")
                            notified_1hour[key_1h] = True

                        # تنبيه بداية المحاضرة (الوقت يساوي أو بعد بداية المحاضرة)
                        key_start = f"{chat_id}_{lec['course_code']}_start"
                        if start_dt <= now <= end_dt and key_start not in notified_started:
                            bot.send_message(chat_id, f"▶️ محاضرتك بلشت: {lec['course_name']} الآن")
                            notified_started[key_start] = True

                    # إعادة تعيين التنبيهات اليومية عند منتصف الليل
                    if now.hour == 0 and now.minute == 0:
                        notified_today.clear()
                        notified_1hour.clear()
                        notified_started.clear()

                except Exception as e:
                    print(f"خطأ في جلب المحاضرات للطالب {student_id}: {e}")

        time.sleep(60)  # فحص كل دقيقة لأن التنبيهات دقيقة بالوقت


# ---------------------- تشغيل المهمات الثلاثة بشكل متزامن ----------------------
def start_scheduler():
    threading.Thread(target=check_for_new_messages, daemon=True).start()
    threading.Thread(target=check_for_course_updates, daemon=True).start()
    threading.Thread(target=check_for_lectures, daemon=True).start()
