import time
import threading
import json
from datetime import datetime
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


# ---------------------- تشغيل المهمتين بشكل متزامن ----------------------
def start_scheduler():
    threading.Thread(target=check_for_new_messages, daemon=True).start()
    threading.Thread(target=check_for_course_updates, daemon=True).start()

# يمكنك استدعاء start_scheduler() في ملف main.py أو نقطة بدء البرنامج
