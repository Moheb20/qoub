import json
import psycopg2
import os
import datetime
from cryptography.fernet import Fernet
from typing import Dict, Any, List
import logging

logger = logging.getLogger("database")


# أضف هذه الدالة في database.py
def generate_and_print_key():
    """إنشاء وطباعة مفتاح جديد"""
    from cryptography.fernet import Fernet
    import datetime
    
    key = Fernet.generate_key()
    key_str = key.decode()
    
    print("\n" + "="*60)
    print("🔑 FERNET_KEY الجديد:")
    print("="*60)
    print(key_str)
    print("="*60)
    
    print("\n📋 التعليمات السريعة:")
    print("1. انسخ المفتاح أعلاه")
    print("2. Render → Service → Environment")
    print("3. عدل FERNET_KEY → Save → Restart")
    print("="*60)
    
    # أيضًا نعيد المفتاح للاستخدام
    return key_str

# الاتصال بقاعدة البيانات
DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# مفتاح التشفير
KEY_FILE = 'secret.key'

def load_or_create_key():
    key = os.getenv("FERNET_KEY")
    if not key:
        logger.error("FERNET_KEY not found in environment variables")
        # إنشاء مفتاح جديد للطوارئ
        new_key = Fernet.generate_key()
        logger.warning(f"تم إنشاء مفتاح جديد: {new_key.decode()}")
        return Fernet(new_key)
    
    # تحقق من صحة المفتاح
    try:
        # محاولة تشفير وفك تشفير نص اختبار
        test_fernet = Fernet(key.encode())
        test_text = "test"
        encrypted = test_fernet.encrypt(test_text.encode()).decode()
        decrypted = test_fernet.decrypt(encrypted.encode()).decode()
        if decrypted == test_text:
            logger.info("✅ مفتاح التشفير صالح")
            return test_fernet
        else:
            logger.error("❌ مفتاح التشفير غير صالح")
    except Exception as e:
        logger.error(f"❌ خطأ في مفتاح التشفير: {e}")
    
    # إنشاء مفتاح جديد في حالة فشل التحقق
    new_key = Fernet.generate_key()
    logger.warning(f"تم إنشاء مفتاح جديد: {new_key.decode()}")
    return Fernet(new_key)


fernet = load_or_create_key()

def encrypt_text(text):
    if text is None:
        return None
    try:
        return fernet.encrypt(text.encode()).decode()
    except Exception as e:
        logger.error(f"فشل التشفير: {e}")
        return None

def decrypt_text(token):
    if not token:  # يشمل None و "" وكل النصوص الفارغة
        return None
    
    try:
        # ✅ سجل ما نحاول فك تشفيره
        logger.debug(f"محاولة فك تشفير: {token[:20]}...")
        
        # ✅ إضافة padding إذا لزم الأمر لتصحيح base64
        padding = len(token) % 4
        if padding != 0:
            token += '=' * (4 - padding)
            logger.debug(f"تم إضافة padding: {token}")
        
        # ✅ فك التشفير
        decrypted = fernet.decrypt(token.encode()).decode()
        logger.debug(f"فك التشفير بنجاح: {decrypted[:10]}...")
        return decrypted
        
    except Exception as e:
        logger.error(f"فشل فك التشفير: {str(e)}")
        logger.error(f"النص المشفر: {token}")
        return None




# ---------- إنشاء الجداول ----------
def init_db():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # جدول المستخدمين (محدث بإضافة حقول البوابة)
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        chat_id BIGINT PRIMARY KEY,
                        student_id TEXT NOT NULL,  -- سيستخدم كـ portal_username
                        password TEXT NOT NULL,    -- سيستخدم كـ portal_password
                        -- الحقول الجديدة للبوابة --
                        branch TEXT,               -- الفرع/التخصص (يُسحب من البوابة)
                        portal_courses TEXT,       -- قائمة المواد (JSON) من البوابة
                        -- الحقول الأصلية --
                        last_msg_id TEXT,
                        courses_data TEXT,
                        last_login TEXT,
                        last_interaction TEXT,
                        registered_at TEXT,
                        status TEXT DEFAULT 'active',
                        last_gpa TEXT
                    )
                ''')

                # جدول السجلات (logs)
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS logs (
                        id SERIAL PRIMARY KEY,
                        chat_id BIGINT,   -- شلنا UNIQUE
                        event_type TEXT,
                        event_value TEXT,
                        created_at TEXT
                    )
                ''')

                # جدول المواعيد النهائية
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS deadlines (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        date DATE NOT NULL
                    )
                ''')

                # جدول المجموعات
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS groups (
                        id SERIAL PRIMARY KEY,
                        category TEXT NOT NULL,
                        name TEXT NOT NULL UNIQUE,
                        link TEXT NOT NULL
                    )
                ''')

                # جدول إحصائيات الطلاب
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS student_stats (
                        chat_id BIGINT PRIMARY KEY,
                        total_hours_required INTEGER DEFAULT 0,
                        total_hours_completed INTEGER DEFAULT 0,
                        total_hours_transferred INTEGER DEFAULT 0,
                        semesters_count INTEGER DEFAULT 0,
                        plan_completed BOOLEAN DEFAULT FALSE,
                        completion_percentage NUMERIC(5,2) DEFAULT 0,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # جدول المقررات
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS student_courses (
                        id SERIAL PRIMARY KEY,
                        chat_id BIGINT NOT NULL,
                        course_code VARCHAR(50),
                        course_name TEXT,
                        category TEXT,
                        hours INTEGER DEFAULT 0,
                        status VARCHAR(20),
                        detailed_status TEXT,
                        is_elective BOOLEAN DEFAULT FALSE,
                        FOREIGN KEY (chat_id) REFERENCES student_stats(chat_id) ON DELETE CASCADE
                    )
                ''')
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS anonymous_chats (
                        chat_id SERIAL PRIMARY KEY,
                        user1_id BIGINT NOT NULL,
                        user2_id BIGINT NOT NULL,
                        course_name TEXT NOT NULL,
                        chat_token TEXT UNIQUE NOT NULL,
                        status TEXT DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # جدول رسائل المحادثات - إضف هذا
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        message_id SERIAL PRIMARY KEY,
                        chat_token TEXT NOT NULL,
                        sender_id BIGINT NOT NULL,
                        message_text TEXT NOT NULL,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
            conn.commit()
            logger.info("Database tables initialized successfully")

    except Exception as e:
        logger.error(f"Error initializing database: {e}")


# ---------- إدارة المستخدمين ----------
def add_user(chat_id, student_id, password, registered_at=None, initial_stats=None, initial_courses=None):
    """إضافة مستخدم جديد مع البيانات الأولية للخطة الدراسية"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # إضافة المستخدم الأساسي
            cur.execute('''
                INSERT INTO users (chat_id, student_id, password, registered_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET
                    student_id = EXCLUDED.student_id,
                    password = EXCLUDED.password,
                    registered_at = EXCLUDED.registered_at
            ''', (chat_id, encrypt_text(student_id), encrypt_text(password), registered_at))
            
            # حفظ الإحصائيات إذا وجدت
            if initial_stats:
                save_student_stats(chat_id, initial_stats)
            
            # حفظ المقررات إذا وجدت
            if initial_courses:
                save_student_courses(chat_id, initial_courses)
            
        conn.commit()

def log_chat_id(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO logs (chat_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (chat_id,)
            )
            conn.commit()

def get_user(chat_id):
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT chat_id, student_id, password, last_msg_id, courses_data,
                           last_login, last_interaction, registered_at, status, last_gpa
                    FROM users WHERE chat_id = %s
                ''', (chat_id,))
                row = cur.fetchone()
                if row:
                    columns = ['chat_id', 'student_id', 'password', 'last_msg_id', 'courses_data',
                               'last_login', 'last_interaction', 'registered_at', 'status', 'last_gpa']
                    user = dict(zip(columns, row))
                    
                    # فك تشفير البيانات مع معالجة الأخطاء
                    try:
                        user['student_id'] = decrypt_text(user['student_id'])
                    except Exception as e:
                        logger.error(f"Error decrypting student_id for {chat_id}: {e}")
                        user['student_id'] = None
                    
                    try:
                        user['password'] = decrypt_text(user['password'])
                    except Exception as e:
                        logger.error(f"Error decrypting password for {chat_id}: {e}")
                        user['password'] = None
                    
                    return user
                return None
    except Exception as e:
        logger.error(f"Error getting user {chat_id}: {e}")
        return None

def logout_user(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            # مسح بيانات تسجيل الدخول فقط، مع بقاء المستخدم موجود
            cur.execute('UPDATE users SET student_id = %s, password = %s WHERE chat_id = %s',
                        ("", "", chat_id))
        conn.commit()


def update_last_msg(chat_id, msg_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET last_msg_id = %s WHERE chat_id = %s', (msg_id, chat_id))
        conn.commit()

def update_user_courses(chat_id, courses_json):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET courses_data = %s WHERE chat_id = %s', (courses_json, chat_id))
        conn.commit()

def update_last_login(chat_id, last_login):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET last_login = %s WHERE chat_id = %s', (last_login, chat_id))
        conn.commit()

def update_last_interaction(chat_id, last_interaction):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET last_interaction = %s WHERE chat_id = %s', (last_interaction, chat_id))
        conn.commit()

def update_status(chat_id, status):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET status = %s WHERE chat_id = %s', (status, chat_id))
        conn.commit()

def update_user_gpa(chat_id, new_gpa):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE users SET last_gpa = %s WHERE chat_id = %s', (new_gpa, chat_id))
        conn.commit()

def get_all_users():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT chat_id, student_id, password, last_msg_id, courses_data,
                       last_login, last_interaction, registered_at, status, last_gpa
                FROM users
            ''')
            rows = cur.fetchall()
            columns = ['chat_id', 'student_id', 'password', 'last_msg_id', 'courses_data',
                       'last_login', 'last_interaction', 'registered_at', 'status', 'last_gpa']
            users = []
            for row in rows:
                user = dict(zip(columns, row))

                # ✅ محاولة فك التشفير مع fallback
                sid = decrypt_text(user['student_id'])
                pwd = decrypt_text(user['password'])

                if sid is None:  # يعني ما انشفر أصلاً
                    sid = user['student_id']
                if pwd is None:
                    pwd = user['password']

                user['student_id'] = sid
                user['password'] = pwd
                users.append(user)

            return users

def get_all_users_with_credentials():
    users = get_all_users()
    return [
        {
            "chat_id": u["chat_id"],
            "student_id": u["student_id"],
            "password": u["password"],
            "last_gpa": u.get("last_gpa")
        }
        for u in users
        if u["student_id"] and u["password"]
    ]

# ---------- تسجيل الأحداث ----------
def log_event(chat_id, event_type, event_value=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO logs (chat_id, event_type, event_value, created_at)
                VALUES (%s, %s, %s, %s)
            ''', (chat_id, event_type, event_value, datetime.datetime.utcnow().isoformat()))
        conn.commit()
def delete_user(chat_id: int):
    """حذف مستخدم من قاعدة البيانات"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM users WHERE chat_id = %s', (chat_id,))
                cur.execute('DELETE FROM student_stats WHERE chat_id = %s', (chat_id,))
                cur.execute('DELETE FROM student_courses WHERE chat_id = %s', (chat_id,))
            conn.commit()
        logger.info(f"تم حذف المستخدم {chat_id}")
    except Exception as e:
        logger.error(f"Error deleting user {chat_id}: {e}")
# ---------- الإحصائيات ----------
def get_total_messages_sent():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM logs WHERE event_type = 'sent_message'")
            return cur.fetchone()[0]

def get_total_messages_received():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM logs WHERE event_type = 'received_message'")
            return cur.fetchone()[0]

def get_total_commands_count():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM logs WHERE event_type = 'command'")
            return cur.fetchone()[0]

def get_top_requested_groups(limit=5):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT event_value, COUNT(*) as cnt
                FROM logs
                WHERE event_type = 'group_request'
                GROUP BY event_value
                ORDER BY cnt DESC
                LIMIT %s
            """, (limit,))
            return [row[0] for row in cur.fetchall()]

def get_bot_start_date():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MIN(created_at) FROM logs")
            row = cur.fetchone()[0]
            if row:
                return datetime.datetime.fromisoformat(row)
            return datetime.datetime.utcnow()

def get_bot_stats():
    users = get_all_users()
    total_users = len(users)
    now = datetime.datetime.utcnow()

    def parse_date(val):
        if val is None:
            return None
        try:
            return datetime.datetime.fromisoformat(val)
        except:
            return None

    users_logged_in = sum(1 for u in users if u.get('last_login'))

    active_last_7_days = 0
    new_today = 0
    new_last_7_days = 0
    new_last_30_days = 0
    unsubscribed = 0

    for u in users:
        last_inter = parse_date(u.get('last_interaction'))
        reg_at = parse_date(u.get('registered_at'))

        if last_inter and (now - last_inter).days <= 7:
            active_last_7_days += 1

        if reg_at:
            if reg_at.date() == now.date():
                new_today += 1
            if (now - reg_at).days <= 7:
                new_last_7_days += 1
            if (now - reg_at).days <= 30:
                new_last_30_days += 1

        if u.get('status') == 'unsubscribed':
            unsubscribed += 1

    inactive_users = total_users - active_last_7_days

    messages_sent = get_total_messages_sent()
    messages_received = get_total_messages_received()
    total_commands = get_total_commands_count()
    top_groups = get_top_requested_groups()
    days_active = max((now - get_bot_start_date()).days, 1)
    avg_daily_interactions = messages_received / days_active

    return {
        "total_users": total_users,
        "users_logged_in": users_logged_in,
        "active_last_7_days": active_last_7_days,
        "inactive_users": inactive_users,
        "new_today": new_today,
        "new_last_7_days": new_last_7_days,
        "new_last_30_days": new_last_30_days,
        "unsubscribed": unsubscribed,
        "messages_sent": messages_sent,
        "messages_received": messages_received,
        "total_commands": total_commands,
        "top_groups": top_groups,
        "avg_daily_interactions": avg_daily_interactions,
    }

def get_all_chat_ids_from_logs():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT chat_id FROM logs WHERE chat_id IS NOT NULL")
            return [row[0] for row in cur.fetchall()]

# إضافة موعد جديد
def add_deadline(name, date):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO deadlines (name, date) VALUES (%s, %s) RETURNING id',
                (name, date)
            )
            deadline_id = cur.fetchone()[0]  # احصل على ID الموعد الجديد
        conn.commit()


    return deadline_id


# جلب كل المواعيد
def get_all_deadlines():

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id, name, date FROM deadlines ORDER BY date')
            return cur.fetchall()

# تعديل موعد
def update_deadline(deadline_id, name=None, date=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if name:
                cur.execute('UPDATE deadlines SET name = %s WHERE id = %s', (name, deadline_id))
            if date:
                cur.execute('UPDATE deadlines SET date = %s WHERE id = %s', (date, deadline_id))
        conn.commit()

# حذف موعد
def delete_deadline(deadline_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM deadlines WHERE id = %s RETURNING id', (deadline_id,))
            deleted = cur.fetchone()
        conn.commit()
    return deleted is not None


def get_deadline_by_id(deadline_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, date FROM deadlines WHERE id = %s", (deadline_id,))
            return cur.fetchone()

def edit_deadline(deadline_id, new_name, new_date):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE deadlines SET name = %s, date = %s WHERE id = %s",
                (new_name, new_date, deadline_id)
            )
        conn.commit()

def add_group(category, name, link):
    """إضافة قروب جديد"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO groups (category, name, link) VALUES (%s, %s, %s) RETURNING id",
                (category, name, link)
            )
            group_id = cur.fetchone()[0]
        conn.commit()
    return group_id



def get_groups_by_category(category):
    """جلب كل القروبات ضمن تصنيف معين"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, link FROM groups WHERE category = %s ORDER BY name", (category,))
            return cur.fetchall()




def get_categories():
    """جلب كل التصنيفات المتاحة"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT category FROM groups ORDER BY category")
            return [row[0] for row in cur.fetchall()]


def get_group_link(name):
    """جلب رابط القروب حسب الاسم"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT link FROM groups WHERE name = %s", (name,))
            row = cur.fetchone()
            return row[0] if row else None

# ---------- إدارة الخطة الدراسية ----------



def get_student_stats(chat_id):
    """الحصول على إحصائيات الطالب"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT total_hours_required, total_hours_completed, total_hours_transferred,
                       semesters_count, plan_completed, completion_percentage, last_updated
                FROM student_stats WHERE chat_id = %s
            ''', (chat_id,))
            row = cur.fetchone()
            if row:
                columns = ['total_hours_required', 'total_hours_completed', 'total_hours_transferred',
                          'semesters_count', 'plan_completed', 'completion_percentage', 'last_updated']
                return dict(zip(columns, row))
            return None

def get_student_courses(chat_id, category=None, status=None):
    """الحصول على مقررات الطالب مع إمكانية التصفية"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            query = '''
                SELECT course_code, course_name, category, hours, status, semester_offered, grade, is_elective
                FROM student_courses WHERE chat_id = %s
            '''
            params = [chat_id]
            
            if category:
                query += ' AND category = %s'
                params.append(category)
            
            if status:
                query += ' AND status = %s'
                params.append(status)
            
            query += ' ORDER BY category, course_code'
            
            cur.execute(query, params)
            courses = []
            for row in cur.fetchall():
                courses.append({
                    'course_code': row[0],
                    'course_name': row[1],
                    'category': row[2],
                    'hours': row[3],
                    'status': row[4],
                    'semester_offered': row[5],
                    'grade': row[6],
                    'is_elective': row[7]
                })
            return courses

def get_remaining_courses(chat_id):
    """الحصول على المقررات المتبقية للطالب"""
    return get_student_courses(chat_id, status='not_taken')

def get_completed_courses(chat_id):
    """الحصول على المقررات المكتملة للطالب"""
    return get_student_courses(chat_id, status='completed')

def calculate_completion_percentage(chat_id):
    """حساب نسبة إكمال الخطة الدراسية"""
    stats = get_student_stats(chat_id)
    if stats and stats['total_hours_required'] > 0:
        percentage = (stats['total_hours_completed'] / stats['total_hours_required']) * 100
        return round(percentage, 2)
    return 0

def add_study_reminder(chat_id, reminder_type, reminder_data, due_date=None):
    """إضافة تذكير دراسي"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO study_reminders (chat_id, reminder_type, reminder_data, due_date)
                VALUES (%s, %s, %s, %s)
            ''', (chat_id, reminder_type, reminder_data, due_date))
        conn.commit()

def get_upcoming_reminders(chat_id, days_ahead=7):
    """الحصول على التذكيرات القادمة"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT id, reminder_type, reminder_data, due_date
                FROM study_reminders 
                WHERE chat_id = %s 
                AND is_completed = FALSE
                AND due_date BETWEEN CURRENT_TIMESTAMP AND CURRENT_TIMESTAMP + INTERVAL '%s days'
                ORDER BY due_date
            ''', (chat_id, days_ahead))
            
            reminders = []
            for row in cur.fetchall():
                reminders.append({
                    'id': row[0],
                    'reminder_type': row[1],
                    'reminder_data': row[2],
                    'due_date': row[3]
                })
            return reminders

def save_student_stats(chat_id, stats_data):
    if not isinstance(stats_data, dict):
        logger.error(f"stats_data is not dict for {chat_id}: {stats_data}")
        return    
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO student_stats 
                    (chat_id, total_hours_required, total_hours_completed, 
                     total_hours_transferred, semesters_count, plan_completed, completion_percentage)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (chat_id) DO UPDATE SET
                        total_hours_required = EXCLUDED.total_hours_required,
                        total_hours_completed = EXCLUDED.total_hours_completed,
                        total_hours_transferred = EXCLUDED.total_hours_transferred,
                        semesters_count = EXCLUDED.semesters_count,
                        plan_completed = EXCLUDED.plan_completed,
                        completion_percentage = EXCLUDED.completion_percentage,
                        last_updated = CURRENT_TIMESTAMP
                ''', (
                    chat_id,
                    stats_data.get('total_hours_required', 0),
                    stats_data.get('total_hours_completed', 0),
                    stats_data.get('total_hours_transferred', 0),
                    stats_data.get('semesters_count', 0),
                    stats_data.get('plan_completed', False),
                    stats_data.get('completion_percentage', 0)
                ))
            conn.commit()
    except Exception as e:
        logger.error(f"Error saving student stats for {chat_id}: {e}")

def save_student_courses(chat_id, courses_data):
    if not isinstance(courses_data, list):
        logger.error(f"courses_data is not list for {chat_id}: {courses_data}")
        return
    courses_to_save = [c for c in courses_data if isinstance(c, dict)]
    try:
        if not isinstance(courses_data, list):
            logger.error(f"courses_data is not a list for {chat_id}, got {type(courses_data)}: {courses_data}")
            return  # تجاهل الحفظ بدل ما يفجر
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                # حذف المقررات القديمة
                cur.execute('DELETE FROM student_courses WHERE chat_id = %s', (chat_id,))
                
                # إضافة المقررات الجديدة
                for course in courses_data:
                    if not isinstance(course, dict):
                        continue  # تجاهل أي عنصر مش dict
                    cur.execute('''
                        INSERT INTO student_courses 
                        (chat_id, course_code, course_name, category, hours, status, detailed_status, is_elective)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ''', (
                        chat_id,
                        course.get('course_code', ''),
                        course.get('course_name', ''),
                        course.get('category', ''),
                        course.get('hours', 0),
                        course.get('status', 'unknown'),
                        course.get('detailed_status', ''),
                        course.get('is_elective', False)
                    ))
            conn.commit()
    except Exception as e:
        logger.error(f"Error saving student courses for {chat_id}: {e}")




def clear_portal_data(chat_id):
    """
    مسح بيانات البوابة الخاصة بالمستخدم (الفرع والمواد)
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE users 
                    SET branch = NULL, portal_courses = NULL 
                    WHERE chat_id = %s
                ''', (chat_id,))
            conn.commit()
        logger.info(f"✅ تم مسح بيانات البوابة للمستخدم {chat_id}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل في مسح بيانات البوابة للمستخدم {chat_id}: {e}")
        return False



def has_portal_data(chat_id):
    """
    التحقق إذا كان المستخدم لديه بيانات بوابة (فرع ومواد)
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT branch, portal_courses FROM users 
                    WHERE chat_id = %s AND branch IS NOT NULL
                ''', (chat_id,))
                return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"❌ خطأ في التحقق من بيانات البوابة: {e}")
        return False



def get_courses_by_branch(branch_name):
    """
    جرد جميع المواد المتاحة في فرع معين عبر جميع المستخدمين
    مفيد لعرض قائمة المواد في واجهة "منصة المواد المشتركة"
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT DISTINCT jsonb_array_elements_text(portal_courses::jsonb)
                    FROM users 
                    WHERE branch = %s AND portal_courses IS NOT NULL
                ''', (branch_name,))
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"❌ خطأ في جرد المواد للفرع {branch_name}: {e}")
        return []




def find_potential_partners(chat_id, course_name):
    """
    البحث عن مستخدمين من نفس الفرع ونفس المادة
    """
    try:
        # جلب فرع المستخدم الحالي
        user_data = get_user_branch_and_courses(chat_id)
        user_branch = user_data.get('branch')
        
        if not user_branch:
            return []
        
        # البحث في قاعدة البيانات
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT chat_id, portal_courses FROM users 
                    WHERE branch = %s AND chat_id != %s
                    AND portal_courses IS NOT NULL
                ''', (user_branch, chat_id))
                
                partners = []
                for row in cur.fetchall():
                    partner_id, courses_json = row
                    if courses_json:
                        try:
                            courses_list = json.loads(courses_json)
                            if course_name in courses_list:
                                partners.append(partner_id)
                        except:
                            continue
                
                return partners
                
    except Exception as e:
        logger.error(f"Error finding partners: {e}")
        return []
                
    except Exception as e:
        logger.error(f"❌ خطأ في البحث عن شركاء محتملين: {e}")
        return []



def get_portal_stats():
    """
    إحصائيات عن استخدام ميزة البوابة
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # عدد المستخدمين الذين ربطوا بيانات البوابة
                cur.execute('''
                    SELECT COUNT(*) FROM users WHERE branch IS NOT NULL
                ''')
                linked_users = cur.fetchone()[0]
                
                # عدد الفروع النشطة
                cur.execute('''
                    SELECT COUNT(DISTINCT branch) FROM users WHERE branch IS NOT NULL
                ''')
                active_branches = cur.fetchone()[0]
                
                # عدد المواد المختلفة
                cur.execute('''
                    SELECT COUNT(DISTINCT jsonb_array_elements_text(portal_courses::jsonb))
                    FROM users WHERE portal_courses IS NOT NULL
                ''')
                total_courses = cur.fetchone()[0]
                
                return {
                    'linked_users': linked_users,
                    'active_branches': active_branches,
                    'total_courses': total_courses
                }
    except Exception as e:
        logger.error(f"❌ خطأ في جلب إحصائيات البوابة: {e}")
        return {}




def update_portal_data(chat_id, branch, portal_courses):
    """
    تحديث بيانات البوابة بعد السكرابنق
    """
    try:
        courses_json = json.dumps(portal_courses) if portal_courses else None
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE users 
                    SET branch = %s, portal_courses = %s
                    WHERE chat_id = %s
                ''', (branch, courses_json, chat_id))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error updating portal data: {e}")
        return False

def get_user_branch_and_courses(chat_id):
    """
    جلب فرع ومواد المستخدم
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT branch, portal_courses FROM users WHERE chat_id = %s
                ''', (chat_id,))
                row = cur.fetchone()
                if row:
                    branch, courses_json = row
                    courses_list = json.loads(courses_json) if courses_json else []
                    return {"branch": branch, "courses": courses_list}
                return {"branch": None, "courses": []}
    except Exception as e:
        logger.error(f"Error getting user data: {e}")
        return {"branch": None, "courses": []}


def get_portal_credentials(chat_id):
    """
    جلب بيانات الدخول للبوابة من بيانات المستخدم الأساسية
    """
    user = get_user(chat_id)
    if user and user['student_id'] and user['password']:
        return {
            "success": True,
            "username": user['student_id'],
            "password": user['password']
        }
    else:
        return {"success": False, "error": "No credentials found"}


# دوال إدارة المحادثات المجهولة
def create_anonymous_chat(user1_id, user2_id, course_name):
    """إنشاء محادثة مجهولة جديدة"""
    try:
        import secrets
        chat_token = secrets.token_hex(8)  # كود فريد للمحادثة
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO anonymous_chats (user1_id, user2_id, course_name, chat_token)
                    VALUES (%s, %s, %s, %s)
                    RETURNING chat_token
                ''', (user1_id, user2_id, course_name, chat_token))
                result = cur.fetchone()
            conn.commit()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"Error creating chat: {e}")
        return None

def add_chat_message(chat_token, sender_id, message_text):
    """إضافة رسالة إلى المحادثة"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    INSERT INTO chat_messages (chat_token, sender_id, message_text)
                    VALUES (%s, %s, %s)
                ''', (chat_token, sender_id, message_text))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error adding message: {e}")
        return False

def get_chat_partner(chat_token, current_user_id):
    """جلب رقم الشريك في المحادثة"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    SELECT user1_id, user2_id FROM anonymous_chats 
                    WHERE chat_token = %s AND status = 'active'
                ''', (chat_token,))
                result = cur.fetchone()
                if result:
                    user1, user2 = result
                    return user2 if current_user_id == user1 else user1
                return None
    except Exception as e:
        logger.error(f"Error getting partner: {e}")
        return None

def end_chat(chat_token):
    """إنهاء المحادثة"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute('''
                    UPDATE anonymous_chats SET status = 'ended' 
                    WHERE chat_token = %s
                ''', (chat_token,))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error ending chat: {e}")
        return False



def get_user_deadlines(chat_id=None):
    """الحصول على المواعيد الهامة (للمستخدم أو للجميع)"""
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                if chat_id:
                    # إذا أردت مستقبلاً ربط المواعيد بمستخدمين محددين
                    cur.execute('''
                        SELECT name, date FROM deadlines 
                        ORDER BY date ASC
                    ''')
                else:
                    # حالياً جميع المواعيد عامة
                    cur.execute('''
                        SELECT name, date FROM deadlines 
                        ORDER BY date ASC
                    ''')
                
                deadlines = cur.fetchall()
                result = []
                for name, date in deadlines:
                    result.append({
                        'name': name,
                        'date': date if isinstance(date, datetime.date) else datetime.strptime(str(date), '%Y-%m-%d').date()
                    })
                return result
    except Exception as e:
        logger.error(f"Error getting deadlines: {e}")
        return []

