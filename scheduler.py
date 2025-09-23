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
from suggestion_bot import run_suggestion_bot

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
logger = logging.getLogger("BOT : ")
# ---------------- إنشاء Scheduler ----------------
exam_scheduler = BackgroundScheduler(timezone=PALESTINE_TZ)
exam_scheduler.configure(job_defaults={"coalesce": True, "max_instances": 4, "misfire_grace_time": 300})
sent_reminders = {}

today_exams_memory = {}
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
                            f"📥 رســـالــــة جـديــدة!\n"
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
                            msg = "📢 تحــديـــث جـديـد فـي الـعـلامــات:\n\n"
                            for c in changes:
                                msg += f"📚 {c['course_name']}\nعلامـــة النـــــصــفي : {c['midterm_mark']} | العــــلامـــة النــــهائيـــة: {c['final_mark']}\n\n"
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
            logger.info(f"جاري فحص GPA لـ {len(users)} مستخدم")
            
            for user in users:
                chat_id = user['chat_id']
                student_id = user['student_id']
                password = user['password']
                
                try:
                    if not student_id or not password:
                        logger.warning(f"[{chat_id}] بيانات تسجيل الدخول غير كاملة")
                        continue
                    
                    # ✅ تحقق من صحة البيانات
                    if len(student_id) < 8 or len(password) < 3:
                        logger.warning(f"[{chat_id}] بيانات تسجيل الدخول غير صالحة")
                        continue
                    
                    # إنشاء السكرابر
                    scraper = QOUScraper(student_id, password)
                    
                    # تسجيل الدخول أولاً
                    if not scraper.login():
                        logger.warning(f"[{chat_id}] فشل تسجيل الدخول للطالب {student_id}")
                        continue
                    
                    # جلب المعدل القديم
                    old_gpa = None
                    if user.get('last_gpa'):
                        try:
                            old_gpa = json.loads(user['last_gpa'])
                        except json.JSONDecodeError:
                            old_gpa = user['last_gpa']
                    
                    # جلب المعدل الجديد
                    new_gpa = scraper.fetch_gpa()
                    
                    if not new_gpa:
                        logger.warning(f"[{chat_id}] لم يتم الحصول على GPA للطالب {student_id}")
                        continue
                    
                    logger.info(f"[{chat_id}] المعدل القديم: {old_gpa}, المعدل الجديد: {new_gpa}")
                    
                    # المقارنة
                    if old_gpa is None:
                        update_user_gpa(chat_id, json.dumps(new_gpa))
                        logger.info(f"[{chat_id}] تم حفظ GPA لأول مرة")
                    elif (new_gpa.get('term_gpa') != old_gpa.get('term_gpa') or 
                          new_gpa.get('cumulative_gpa') != old_gpa.get('cumulative_gpa')):
                        msg = (
                            f"🎓 تـــم تــــحديث البــــوابة الاكــــاديـــمية!\n\n"
                            f"📘 المــعدل الـــفـصـلي : {new_gpa.get('term_gpa', '-')}\n"
                            f"📚 المــعدل الـتـراكـمـي: {new_gpa.get('cumulative_gpa', '-')}\n\n"
                            f"🆔 الرقم الجامعي: {student_id}"
                        )
                        try:
                            bot.send_message(chat_id, msg)
                            logger.info(f"[{chat_id}] تم إرسال رسالة تحديث GPA")
                        except Exception as msg_error:
                            logger.error(f"[{chat_id}] فشل إرسال الرسالة: {msg_error}")
                        
                        update_user_gpa(chat_id, json.dumps(new_gpa))
                    else:
                        logger.info(f"[{chat_id}] لا تغيير في GPA")
                        
                except Exception as ex:
                    logger.error(f"[{chat_id}] خطأ أثناء متابعة GPA: {ex}")
                    if "InvalidToken" in str(ex) or "base64" in str(ex):
                        logger.warning(f"[{chat_id}] حذف مستخدم ببيانات تالفة")
                        delete_user(chat_id)
            
            time.sleep(24 * 60 * 60)
            
        except Exception as e:
            logger.error(f"❌ خطأ عام في متابعة GPA: {e}")
            time.sleep(60 * 60)



def check_discussion_sessions():
    """
    فحص حلقات النقاش وإرسال التذكيرات المبرمجة
    """
    # تخزين محلي لحلقات النقاش المعروفة لكل مستخدم
    known_sessions = {}
    
    while True:
        try:
            now = datetime.now(PALESTINE_TZ)
            today_str = now.strftime("%d/%m/%Y")
            users = get_all_users()
            
            for user in users:
                chat_id = user['chat_id']
                student_id = user['student_id']
                password = user['password']
                
                # ✅ إنشاء جلسة جديدة لكل مستخدم
                scraper = QOUScraper(student_id, password)
                if not scraper.login():
                    logger.warning(f"[{chat_id}] فشل تسجيل الدخول لفحص حلقات النقاش")
                    continue
                
                try:
                    sessions = scraper.fetch_discussion_sessions()
                    logger.info(f"[{chat_id}] تم جلب {len(sessions)} حلقة نقاش")
                except Exception as e:
                    logger.error(f"[{chat_id}] خطأ في جلب حلقات النقاش: {e}")
                    continue
                
                # ✅ الحصول على الحلقات المعروفة سابقاً لهذا المستخدم
                user_known_sessions = known_sessions.get(chat_id, set())
                current_sessions = set()
                
                # ✅ فحص الحلقات الجديدة
                new_sessions = []
                for session in sessions:
                    session_key = f"{session['course_code']}_{session['date']}_{session['time']}"
                    current_sessions.add(session_key)
                    
                    if session_key not in user_known_sessions:
                        new_sessions.append(session)
                        logger.info(f"[{chat_id}] اكتشفت حلقة نقاش جديدة: {session_key}")
                
                # ✅ إرسال إشعار بالحلقات الجديدة
                if new_sessions:
                    msg = "🆕 تمـــت إضـــافـــة حـــلـقـــات نــقــاش جــديـــدة:\n\n"
                    for session in new_sessions:
                        msg += f"📘 {session['course_name']} ({session['course_code']})\n"
                        msg += f"📅 {session['date']} - ⏰ {session['time']}\n\n"
                    
                    send_message(bot, chat_id, msg)
                
                # ✅ جدولة التذكيرات لجميع حلقات النقاش (الجديدة والقديمة)
                for session in sessions:
                    try:
                        # ✅ تحويل وقت الحلقة
                        start_raw = session['time'].split('-')[0].strip()
                        start_time = datetime.strptime(
                            f"{session['date']} {start_raw}", "%d/%m/%Y %H:%M"
                        ).replace(tzinfo=PALESTINE_TZ)
                        
                        # ✅ إنشاء مفتاح فريد لهذه الحلقة
                        session_key = f"{chat_id}_{session['course_code']}_{session['date']}_{session['time']}"
                        
                        # ✅ التذكيرات المطلوبة
                        reminders = [
                            (start_time - timedelta(hours=2), "2h_before", 
                             f"⏰ باقي ساعتين على حلقة النقاش: {session['course_name']}"),
                            (start_time - timedelta(hours=1), "1h_before", 
                             f"⚡ باقي ساعة على حلقة النقاش: {session['course_name']}"),
                            (start_time, "start_time", 
                             f"🚀 بدأت الآن حلقة النقاش: {session['course_name']} بالتوفيق! ❤️")
                        ]
                        
                        for reminder_time, reminder_type, reminder_msg in reminders:
                            if reminder_time > now:
                                job_id = f"disc_{session_key}_{reminder_type}"
                                try:
                                    exam_scheduler.add_job(
                                        send_message,
                                        'date',
                                        run_date=reminder_time,
                                        args=[bot, chat_id, reminder_msg],
                                        id=job_id,
                                        replace_existing=True
                                    )
                                    logger.info(f"[{chat_id}] تم جدولة تذكير {reminder_type} لحلقة النقاش {session['course_name']}")
                                except Exception as e:
                                    logger.error(f"[{chat_id}] فشل جدولة التذكير: {e}")
                    
                    except Exception as e:
                        logger.error(f"[{chat_id}] خطأ في معالجة حلقة النقاش {session['course_name']}: {e}")
                        continue
                
                # ✅ تحديث الحلقات المعروفة للمستخدم
                known_sessions[chat_id] = current_sessions
            
            # ✅ الانتظار ساعة قبل الفحص التالي
            logger.info("💤 انتظار 24 ساعة للفحص التالي لحلقات النقاش")
            time.sleep(86400)

            
        except Exception as e:
            logger.error(f"❌ خطأ عام في فحص حلقات النقاش: {e}")
            time.sleep(60 * 10)  # انتظار 10 دقائق عند الخطأ

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

        # ✅ تعريف days_map داخل الدالة
        days_map = {
            "الاثنين": 0, "الثلاثاء": 1, "الأربعاء": 2, "الخميس": 3,
            "الجمعة": 4, "السبت": 5, "الأحد": 6
        }

        # ✅ الحصول على اليوم الحالي بالعربية
        arabic_days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
        today_arabic = arabic_days[today.weekday()]
        
        logger.info(f"📅 اليوم هو: {today_arabic} ({today.strftime('%Y-%m-%d')})")

        lecture_count = 0
        reminder_count = 0

        for user in users:
            user_id = user['chat_id']
            
            # ✅ استخدام البيانات المشفرة مباشرة (بدون فك تشفير)
            student_id = user['student_id']
            password = user['password']
            
            if not student_id or not password:
                logger.warning(f"[{user_id}] بيانات تسجيل الدخول غير كافية")
                continue

            # ✅ إنشاء كائن scraper جديد لكل مستخدم
            scraper = QOUScraper(student_id, password)
            if not scraper.login():
                logger.warning(f"[{user_id}] فشل تسجيل الدخول")
                continue

            try:
                lectures = scraper.fetch_lectures_schedule()
                logger.info(f"[{user_id}] تم جلب {len(lectures)} محاضرة")
            except Exception as e:
                logger.error(f"[{user_id}] خطأ في جلب المحاضرات: {e}")
                continue

            user_lectures_today = 0
            
            for lecture in lectures:
                lecture_day = lecture["day"].strip()
                
                # ✅ التحقق إذا كان اليوم مطابق
                if lecture_day != today_arabic:
                    continue
                
                user_lectures_today += 1
                lecture_count += 1

                # ✅ وقت بداية المحاضرة مع معالجة الأخطاء
                try:
                    start_time_str = lecture["time"].split("-")[0].strip()
                    hour, minute = map(int, start_time_str.split(":"))
                    
                    # ✅ إنشاء datetime مع المنطقة الزمنية
                    lecture_start = PALESTINE_TZ.localize(
                        datetime(today.year, today.month, today.day, hour, minute, 0)
                    )
                    
                    logger.info(f"[{user_id}] محاضرة اليوم: {lecture['course_name']} الساعة {hour:02d}:{minute:02d}")
                    
                except Exception as e:
                    logger.error(f"[{user_id}] خطأ في تحويل وقت المحاضرة {lecture['course_name']}: {e}")
                    continue

                # ✅ رسائل التذكير
                reminders = [
                    (lecture_start - timedelta(hours=1), "1h_before",
                     f"⏰ بعد ساعة عندك محاضرة {lecture['course_name']} ({lecture['time']})"),
                    (lecture_start - timedelta(minutes=15), "15m_before",
                     f"⚡ بعد ربع ساعة محاضرة {lecture['course_name']}"),
                    (lecture_start, "start_time",
                     f"🚀 بدأت الآن محاضرة {lecture['course_name']} بالتوفيق ❤️"),
                ]

                # ✅ جدولة التذكيرات
                for remind_time, reminder_type, msg in reminders:
                    if remind_time > now:
                        try:
                            job_id = f"lec_{user_id}_{lecture['course_code']}_{reminder_type}_{int(remind_time.timestamp())}"
                            
                            exam_scheduler.add_job(
                                send_message,
                                'date',
                                run_date=remind_time,
                                args=[bot, user_id, msg],
                                id=job_id,
                                replace_existing=True
                            )
                            reminder_count += 1
                            logger.info(f"[{user_id}] تم جدولة تذكير: {msg} في {remind_time.strftime('%H:%M')}")
                            
                        except Exception as e:
                            logger.error(f"[{user_id}] فشل جدولة التذكير: {e}")

            if user_lectures_today > 0:
                logger.info(f"[{user_id}] لديه {user_lectures_today} محاضرة اليوم")

        logger.info(f"✅ انتهى فحص محاضرات اليوم: {lecture_count} محاضرة, {reminder_count} تذكير مجدول")

    except Exception as e:
        logger.exception(f"❌ خطأ أثناء فحص المحاضرات: {e}")


def daily_lecture_checker_loop():
    """
    حلقة لا نهائية تشغل check_today_lectures كل يوم الساعة 00:05 (بعد منتصف الليل بـ5 دقائق)
    """
    logger.info("🎯 بدء مراقب المحاضرات اليومية")
    
    # ✅ الانتظار قليلاً عند البدء
    time.sleep(10)
    
    while True:
        try:
            now = datetime.now(PALESTINE_TZ)
            
            # ✅ حساب وقت التشغيل التالي (00:05 من اليوم التالي)
            if now.hour == 0 and now.minute < 5:
                # إذا كنا بعد منتصف الليل مباشرة، انتظر حتى 00:05
                next_run = now.replace(hour=0, minute=5, second=0, microsecond=0)
            else:
                # انتظر حتى 00:05 من اليوم التالي
                next_run = (now + timedelta(days=1)).replace(hour=0, minute=5, second=0, microsecond=0)
            
            seconds_to_sleep = (next_run - now).total_seconds()
            
            logger.info(f"🕛 الانتظار حتى {next_run.strftime('%Y-%m-%d %H:%M')} لفحص المحاضرات: {int(seconds_to_sleep)} ثانية")
            
            time.sleep(seconds_to_sleep)
            
            # ✅ تنفيذ فحص المحاضرات
            logger.info("🔍 بدء فحص محاضرات اليوم الجديد")
            check_today_lectures()
            
            # ✅ انتظار دقيقة إضافية لتجنب التشغيل المتكرر
            time.sleep(60)
            
        except KeyboardInterrupt:
            logger.info("⏹️ إيقاف مراقب المحاضرات بطلب من المستخدم")
            break
        except Exception as e:
            logger.error(f"❌ خطأ في مراقب المحاضرات: {e}")
            time.sleep(300)  # انتظار 5 دقائق قبل إعادة المحاولة
def check_today_exams():
    """
    فحص امتحانات اليوم لكل الطلاب وإرسال الرسائل والتذكيرات.
    """
    try:
        logger.info("✅ بدء فحص امتحانات اليوم لكل الطلاب")
        users = get_all_users()
        today = datetime.now(PALESTINE_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        today_exams_memory.clear()  # نظف البيانات القديمة

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
            exams_today_count = 0
            exams_for_memory = []

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
                        exams_today_count += 1
                        exams_for_memory.append(e)  # حفظ مؤقت للامتحان

                        if exam_dt.date() == today.date():
                            exams_today_count += 1
                            # رسالة اليوم
                            msg = (
                                f"📌 عـنـــدك امـتـحــان اليــــوم:\n"
                                f"المــادة: {e['course_name']}\n"
                                f"الــنوع: {exam_emoji} ({e['exam_kind']})\n"
                                f"الســاعة: {e['from_time']} - {e['to_time']}\n"
                                f"المحــاضر: {e['lecturer']}\n"
                                f"الشــعبة: {e['section']}\n"
                                f"ملاحظــة: {e['note']}"
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
            if exams_for_memory:
                today_exams_memory[user_id] = exams_for_memory  
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
    global sent_reminders
    while True:
        now = datetime.now(PALESTINE_TZ)
        try:
            for user_id, exams in today_exams_memory.items():
                if user_id not in sent_reminders:
                    sent_reminders[user_id] = {}

                for e in exams:
                    exam_dt = parse_exam_datetime(e["date"], e["from_time"])
                    if not exam_dt:
                        continue
                    exam_key = f"{e['course_name']}|{exam_dt.strftime('%Y-%m-%d %H:%M')}"
                    if exam_key not in sent_reminders[user_id]:
                        sent_reminders[user_id][exam_key] = set()

                    reminders = [
                        ("2h_before", exam_dt - timedelta(hours=2), f"⏰ امتحان {e['course_name']} بعد ساعتين"),
                        ("30m_before", exam_dt - timedelta(minutes=30), f"⚡ امتحان {e['course_name']} بعد 30 دقيقة أو أقل"),
                        ("at_start", exam_dt, f"🚀 هلا بلش امتحان {e['course_name']}")
                    ]

                    for r_type, r_time, r_msg in reminders:
                        diff = (r_time - now).total_seconds()
                        # ±5 دقائق = 300 ثانية
                        if -300 <= diff <= 300 and r_type not in sent_reminders[user_id][exam_key]:
                            try:
                                bot.send_message(user_id, r_msg)
                                sent_reminders[user_id][exam_key].add(r_type)
                                logger.info(f"[{user_id}] تم إرسال التذكير ({r_type}) للامتحان {e['course_name']}")
                            except Exception as ex:
                                logger.warning(f"[{user_id}] فشل إرسال التذكير {r_type}: {ex}")
        except Exception as e:
            logger.error(f"❌ خطأ في التذكيرات الحية: {e}")
        time.sleep(5 * 60)  # فحص كل 5 دقائق



def start_scheduler():
    """
    تشغيل كل المهام الأخرى + الجدولات
    """
    threading.Thread(target=check_for_new_messages, daemon=True).start()
    threading.Thread(target=check_for_course_updates, daemon=True).start()
    threading.Thread(target=check_discussion_sessions, daemon=True).start()
    threading.Thread(target=check_for_gpa_changes, daemon=True).start()
    threading.Thread(target=send_reminder_for_new_deadline, daemon=True).start()
    threading.Thread(target=run_suggestion_bot, daemon=True).start()

    # شغل جدولة الامتحانات والتذكيرات
    threading.Thread(target=live_exam_reminder_loop, daemon=True).start()
    threading.Thread(target=daily_lecture_checker_loop, daemon=True).start()
    threading.Thread(target=daily_exam_checker_loop, daemon=True).start()


