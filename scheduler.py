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
sent_reminders = {}


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

def parse_exam_datetime(date_str, time_str):
    """
    تحويل التاريخ والوقت من البوابة إلى كائن aware datetime مع المنطقة الزمنية PALESTINE_TZ.
    """
    date_str = date_str.strip()
    time_str = time_str.strip()
    try:
        date_obj = datetime.strptime(date_str, "%d-%m-%Y")
        time_obj = datetime.strptime(time_str, "%H:%M").time()
        dt_naive = datetime.combine(date_obj, time_obj)
        dt_aware = PALESTINE_TZ.localize(dt_naive)  # هنا تصير aware
        return dt_aware
    except Exception as e:
        logger.warning(f"فشل تحويل التاريخ والوقت: {date_str} {time_str} | خطأ: {e}")
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
                try:
                    scraper = QOUScraper(user['student_id'], user['password'])
                    if scraper.login():
                        courses = scraper.fetch_term_summary_courses()
                        old_courses = json.loads(user.get('courses_data')) if user.get('courses_data') else []
                        changes = []
                        for c in courses:
                            old_c = next((o for o in old_courses if o['course_code'] == c['course_code']), None)
                            if old_c and (c['midterm_mark'] != old_c['midterm_mark'] or c['final_mark'] != old_c['final_mark']):
                                changes.append(c)
                        if changes:
                            msg = "📢 تحديث جديد في العلامات:\n\n"
                            for c in changes:
                                msg += f"📚 {c['course_name']}\nنصفي: {c['midterm_mark']} | نهائي: {c['final_mark']}\n\n"
                            send_message(bot, chat_id, msg)
                            logger.info(f"[{chat_id}] تم إرسال رسالة تحديث العلامات للطالب: {len(changes)} مادة/مواد")
                        else:
                            logger.info(f"[{chat_id}] لا تغييرات في العلامات")
                        update_user_courses(chat_id, json.dumps(courses))
                except Exception as ex:
                    logger.warning(f"[{chat_id}] خطأ أثناء فحص تحديث العلامات: {ex}")
            time.sleep(60*60)
        except Exception as e:
            logger.error(f"❌ خطأ عام في تحديث العلامات: {e}")
            time.sleep(60)

def check_for_gpa_changes():
    while True:
        try:
            users = get_all_users()
            for user in users:
                chat_id = user['chat_id']
                try:
                    scraper = QOUScraper(user['student_id'], user['password'])
                    old_gpa = json.loads(user.get('last_gpa')) if user.get('last_gpa') else None
                    new_gpa = scraper.fetch_gpa()
                    if new_gpa:
                        logger.info(f"[{chat_id}] المعدل الحالي: {old_gpa}, المعدل الجديد: {new_gpa}")
                    if new_gpa and new_gpa != old_gpa:
                        msg = (
                            f"🎓 تم تحديث المعدل التراكمي!\n"
                            f"📘 معدل الفصل: {new_gpa.get('term_gpa', '-')}\n"
                            f"📚 المعدل التراكمي: {new_gpa.get('cumulative_gpa', '-')}"
                        )
                        send_message(bot, chat_id, msg)
                        logger.info(f"[{chat_id}] تم إرسال رسالة تحديث GPA للطالب")
                        update_user_gpa(chat_id, json.dumps(new_gpa))
                    else:
                        logger.info(f"[{chat_id}] لا تغيير في GPA")
                except Exception as ex:
                    logger.warning(f"[{chat_id}] خطأ أثناء متابعة GPA: {ex}")
            time.sleep(24*60*60)
        except Exception as e:
            logger.error(f"❌ خطأ عام في متابعة GPA: {e}")
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



def check_today_lectures():
    try:
        logger.info("✅ بدء فحص محاضرات اليوم")
        users = get_all_users()
        now = datetime.now(PALESTINE_TZ)
        today = now.date()

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
            user_id = user['chat_id']
            student_id = decrypt_text(user['student_id'])
            password = decrypt_text(user['password'])

            scraper = QOUScraper(student_id, password)
            if not scraper.login():
                logger.warning(f"[{user_id}] فشل تسجيل الدخول")
                continue

            lectures = scraper.fetch_lectures_schedule()
            for lecture in lectures:
                lecture_day = lecture["day"].strip()
                if lecture_day not in days_map:
                    continue

                if days_map[lecture_day] != today.weekday():
                    continue

                start_time_str = lecture["time"].split("-")[0].strip()
                hour, minute = map(int, start_time_str.split(":"))
                lecture_start = datetime.combine(today, datetime.min.time()).replace(hour=hour, minute=minute, tzinfo=PALESTINE_TZ)

                # رسائل التذكير
                reminders = [
                    (lecture_start - timedelta(hours=1),
                     f"⏰ بعد ساعة عندك محاضرة {lecture['course_name']} ({lecture['time']})"),
                    (lecture_start - timedelta(minutes=15),
                     f"⚡ بعد ربع ساعة محاضرة {lecture['course_name']}"),
                    (lecture_start,
                     f"🚀 بدأت الآن محاضرة {lecture['course_name']} بالتوفيق ❤️"),
                ]

                for remind_time, msg in reminders:
                    if remind_time > now:
                        # إرسال الرسالة مباشرة لو الوقت قريب جدًا أو جدولة APScheduler
                        send_message(bot, user_id, msg)
                        logger.info(f"[{user_id}] جدولت تذكير: {msg} في {remind_time}")

        logger.info("✅ انتهى فحص محاضرات اليوم")

    except Exception as e:
        logger.exception(f"❌ خطأ أثناء فحص المحاضرات: {e}")


def daily_lecture_checker_loop():
    """
    حلقة لا نهائية تشغل check_today_lectures كل يوم الساعة 00:00.
    """
    while True:
        now = datetime.now(PALESTINE_TZ)
        # حساب الوقت حتى منتصف الليل
        next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_to_sleep = (next_run - now).total_seconds()
        logger.info(f"🕛 الانتظار حتى منتصف الليل: {int(seconds_to_sleep)} ثانية")
        time.sleep(seconds_to_sleep)
        # تنفيذ فحص المحاضرات
        check_today_lectures()

def check_today_exams():
    """
    فحص امتحانات اليوم لكل الطلاب وإرسال الرسائل والتذكيرات.
    """
    try:
        logger.info("✅ بدء فحص امتحانات اليوم لكل الطلاب")
        users = get_all_users()
        today = datetime.now(PALESTINE_TZ).replace(hour=0, minute=0, second=0, microsecond=0)

        for user in users:
            user_id = user['chat_id']
            student_id = user['student_id']
            password = user['password']

            logger.info(f"[{user_id}] محاولة تسجيل الدخول...")
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

            exams_today_count = 0

            for term in terms:
                for exam_code, exam_emoji in EXAM_TYPE_MAP.items():
                    try:
                        exams = user_scraper.fetch_exam_schedule(term["value"], exam_type=exam_code)
                        logger.info(f"[{user_id}] عدد الامتحانات المجلبه للفصل {term['value']} لنوع {exam_code}: {len(exams)}")
                    except Exception as e:
                        logger.exception(f"[{user_id}] خطأ أثناء جلب الامتحانات للفصل {term['value']} ونوع {exam_code}: {e}")
                        continue

                    for e in exams:
                        logger.info(
                            f"[{user_id}] بيانات الامتحان الخام: date={e['date']}, from={e['from_time']}, "
                            f"to={e['to_time']}, course={e['course_name']}"
                        )
                        exam_dt = parse_exam_datetime(e["date"], e["from_time"])
                        if not exam_dt:
                            logger.warning(f"[{user_id}] فشل تحويل التاريخ للامتحان {e['course_name']}")
                            continue

                        if exam_dt.date() == today.date():
                            exams_today_count += 1
                            # رسالة اليوم
                            msg = (
                                f"📌 عندك امتحان اليوم:\n"
                                f"المادة: {e['course_name']}\n"
                                f"النوع: {exam_emoji} ({e['exam_kind']})\n"
                                f"الساعة: {e['from_time']} - {e['to_time']}\n"
                                f"المحاضر: {e['lecturer']}\n"
                                f"القسم: {e['section']}\n"
                                f"ملاحظة: {e['note']}"
                            )
                            logger.info(f"[{user_id}] جاري إرسال رسالة الامتحان: {e['course_name']}")

                            try:
                                bot.send_message(user_id, msg)
                                logger.info(f"[{user_id}] تم إرسال رسالة الامتحان بنجاح")
                            except Exception as ex:
                                logger.warning(f"[{user_id}] فشل إرسال رسالة الامتحان ({e['course_name']}): {ex}")
                                continue  # نكمل باقي الطلاب بدل ما يوقف

                            # جدولة التذكيرات
                            reminders = [
                                ("2h_before", exam_dt - timedelta(hours=2), f"⏰ امتحان {e['course_name']} بعد ساعتين"),
                                ("30m_before", exam_dt - timedelta(minutes=30), f"⚡ امتحان {e['course_name']} بعد 30 دقيقة"),
                                ("at_start", exam_dt, f"🚀 هلا بلش امتحان {e['course_name']}")
                            ]

                            for r_type, r_time, r_msg in reminders:
                                if r_time.tzinfo is None:
                                    r_time = PALESTINE_TZ.localize(r_time)

                                if r_time > datetime.now(PALESTINE_TZ):
                                    try:
                                        job_func = partial(bot.send_message, user_id, r_msg)
                                        exam_scheduler.add_job(job_func, "date", run_date=r_time)
                                        logger.info(f"[{user_id}] تم جدولة تذكير: {r_type} في {r_time}")
                                    except Exception as ex:
                                        logger.warning(f"[{user_id}] فشل جدولة التذكير {r_type}: {ex}")

            logger.info(f"[{user_id}] عدد امتحانات اليوم: {exams_today_count}")

        logger.info("✅ انتهى فحص امتحانات اليوم")

    except Exception as e:
        logger.exception(f"❌ فشل أثناء فحص امتحانات اليوم: {e}")

def daily_exam_checker_loop():
    while True:
        try:
            now = datetime.now(PALESTINE_TZ)
            # احسب متى سيحين منتصف الليل القادم
            tomorrow_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            seconds_until_midnight = (tomorrow_midnight - now).total_seconds()

            logger.info(f"⏳ انتظار {seconds_until_midnight/3600:.2f} ساعة حتى منتصف الليل لتشغيل فحص الامتحانات")

            time.sleep(seconds_until_midnight)  # انتظر حتى منتصف الليل

            # نفذ الفحص
            check_today_exams()

        except Exception as e:
            logger.error(f"❌ خطأ في حلقة فحص الامتحانات اليومية: {e}")
            time.sleep(60)

def live_exam_reminder_loop():
    """
    حلقة لا نهائية لإرسال التذكيرات الحية للامتحانات كل نصف ساعة.
    - تفحص الامتحانات لليوم فقط
    - ترسل التذكيرات بشكل تقريبي (±30 دقيقة)
    - تمنع التكرار لنفس التذكير
    """
    global sent_reminders

    while True:
        now = datetime.now(PALESTINE_TZ)
        try:
            users = get_all_users()

            for user in users:
                user_id = user['chat_id']
                student_id = user['student_id']
                password = user['password']

                scraper = QOUScraper(student_id, password)
                if not scraper.login():
                    continue

                terms = scraper.get_last_two_terms()
                if not terms:
                    continue

                for term in terms:
                    for exam_code, exam_emoji in EXAM_TYPE_MAP.items():
                        try:
                            exams = scraper.fetch_exam_schedule(term["value"], exam_type=exam_code)
                        except Exception as ex:
                            logger.warning(f"[{user_id}] خطأ بجلب الامتحانات: {ex}")
                            continue

                        for e in exams:
                            exam_dt = parse_exam_datetime(e["date"], e["from_time"])
                            if not exam_dt or exam_dt.date() != now.date():
                                continue  # نركز فقط على امتحانات اليوم

                            # مفتاح فريد لكل امتحان (مادة + تاريخ + ساعة)
                            exam_key = f"{e['course_name']}|{exam_dt.strftime('%Y-%m-%d %H:%M')}"
                            if user_id not in sent_reminders:
                                sent_reminders[user_id] = {}
                            if exam_key not in sent_reminders[user_id]:
                                sent_reminders[user_id][exam_key] = set()

                            reminders = [
                                ("2h_before", exam_dt - timedelta(hours=2), f"⏰ امتحان {e['course_name']} بعد ساعتين"),
                                ("30m_before", exam_dt - timedelta(minutes=30), f"⚡ امتحان {e['course_name']} بعد 30 دقيقة أو أقل"),
                                ("at_start", exam_dt, f"🚀 هلا بلش امتحان {e['course_name']}")
                            ]

                            for r_type, r_time, r_msg in reminders:
                                diff = (r_time - now).total_seconds()

                                # إذا الوقت بين -30 دقيقة و +30 دقيقة (تقريبياً) ولم يرسل من قبل
                                if -1800 <= diff <= 1800 and r_type not in sent_reminders[user_id][exam_key]:
                                    try:
                                        bot.send_message(user_id, r_msg)
                                        sent_reminders[user_id][exam_key].add(r_type)  # علمنا إنو انبعت
                                        logger.info(f"[{user_id}] تم إرسال التذكير ({r_type}) للامتحان {e['course_name']}")
                                    except Exception as ex:
                                        logger.warning(f"[{user_id}] فشل إرسال التذكير {r_type}: {ex}")

        except Exception as e:
            logger.error(f"❌ خطأ في التذكيرات الحية: {e}")

        # انتظر نصف ساعة قبل الفحص التالي
        time.sleep(30 * 60)



def start_scheduler():
    """
    تشغيل كل المهام الأخرى + الجدولات
    """
    threading.Thread(target=check_for_new_messages, daemon=True).start()
    threading.Thread(target=check_for_course_updates, daemon=True).start()
    threading.Thread(target=check_discussion_sessions, daemon=True).start()
    threading.Thread(target=check_for_gpa_changes, daemon=True).start()
    threading.Thread(target=send_reminder_for_new_deadline, daemon=True).start()

    # شغل جدولة الامتحانات والتذكيرات
    threading.Thread(target=live_exam_reminder_loop, daemon=True).start()
    threading.Thread(target=daily_lecture_checker_loop, daemon=True).start()
    threading.Thread(target=daily_exam_checker_loop, daemon=True).start()


