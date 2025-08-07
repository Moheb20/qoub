import time
import threading
from database import get_all_users, update_last_msg, update_last_marks
from qou_scraper import QOUScraper
from bot_instance import bot

def check_for_updates():
    while True:
        users = get_all_users()
        for user in users:
            chat_id = user['chat_id']
            student_id = user['student_id']
            password = user['password']
            last_msg_id = user.get('last_msg_id', None)
            last_marks = user.get('last_marks', None)  # افترض إنك تخزن شيء معرف للعلامات

            scraper = QOUScraper(student_id, password)
            try:
                if scraper.login():
                    # فحص الرسائل
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

                    # فحص العلامات
                    courses_with_marks = scraper.fetch_courses_with_marks()

                    # هنا نفترض أنك تخزن "last_marks" بطريقة مناسبة، مثلاً JSON أو dict مع course codes والدرجات
                    # لتبسيط، راح نحول الدرجات المهمة لتمثيل نصي ونقارنها
                    current_marks_repr = {}
                    for c in courses_with_marks:
                        marks = c.get('marks', {})
                        # خلينا ناخد فقط العلامة النهائية وحالة المادة
                        key = c['code']
                        val = f"{marks.get('final_mark', 'غير متوفر')}|{marks.get('status', 'غير متوفر')}"
                        current_marks_repr[key] = val

                    if current_marks_repr != last_marks:
                        # جهز رسالة التحديث
                        marks_text = "📊 تحديث العلامات:\n"
                        for code, val in current_marks_repr.items():
                            marks_text += f"المادة {code}: {val}\n"
                        
                        bot.send_message(chat_id, marks_text)
                        update_last_marks(chat_id, current_marks_repr)

            except Exception as e:
                print(f"❌ خطأ مع المستخدم {student_id}: {e}")

            time.sleep(1)  # تخفيف الضغط بين المستخدمين

        time.sleep(20 * 60)  # انتظار 20 دقيقة قبل الفحص التالي

def start_scheduler():
    threading.Thread(target=check_for_updates, daemon=True).start()
