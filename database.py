import psycopg2
import os
import datetime
from cryptography.fernet import Fernet
from typing import Dict, Any, List
import logging

logger = logging.getLogger("database")



# الاتصال بقاعدة البيانات
DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# مفتاح التشفير
KEY_FILE = 'secret.key'

def load_or_create_key():
    key = os.getenv("FERNET_KEY")
    if not key:
        raise Exception("FERNET_KEY not found in environment variables")
    return Fernet(key.encode())


fernet = load_or_create_key()

def encrypt_text(text):
    if text is None:
        return None
    return fernet.encrypt(text.encode()).decode()

def decrypt_text(token):
    if not token:  # يشمل None و "" وكل النصوص الفارغة
        return None
    return fernet.decrypt(token.encode()).decode()




# ---------- إنشاء الجداول ----------
def init_db():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # جدول المستخدمين
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        chat_id BIGINT PRIMARY KEY,
                        student_id TEXT NOT NULL,
                        password TEXT NOT NULL,
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
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 
                            FROM information_schema.columns 
                            WHERE table_name='student_courses' AND column_name='detailed_status'
                        ) THEN
                            ALTER TABLE student_courses ADD COLUMN detailed_status TEXT;
                        END IF;
                    END$$;
                """)  
                # إنشاء فهرس لأداء أفضل
                cur.execute('CREATE INDEX IF NOT EXISTS idx_student_courses_chat_id ON student_courses(chat_id)')
                try:
                    cur.execute("SELECT detailed_status FROM student_courses LIMIT 1")
                except Exception:
                    try:
                        cur.execute("ALTER TABLE student_courses ADD COLUMN detailed_status TEXT")
                        logger.info("تم إضافة العمود detailed_status إلى الجدول student_courses")
                    except Exception as alter_error:
                        logger.warning(f"لم يتمكن من إضافة العمود: {alter_error}")
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
                user['student_id'] = decrypt_text(user['student_id'])
                user['password'] = decrypt_text(user['password'])
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

def save_student_stats(chat_id, stats_data):
    """حفظ الإحصائيات الدراسية للطالب"""
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
                stats_data.get('required_hours', 0),
                stats_data.get('completed_hours', 0),
                stats_data.get('transferred_hours', 0),
                stats_data.get('semesters_count', 0),
                stats_data.get('plan_completed', False),
                stats_data.get('completion_percentage', 0)
            ))
        conn.commit()

def save_student_courses(chat_id, courses_data):
    """حفظ المقررات الدراسية للطالب"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # حذف المقررات القديمة أولاً
            cur.execute('DELETE FROM student_courses WHERE chat_id = %s', (chat_id,))
            
            # إضافة المقررات الجديدة
            for course in courses_data:
                cur.execute('''
                    INSERT INTO student_courses 
                    (chat_id, course_code, course_name, category, hours, status, semester_offered, grade, is_elective)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    chat_id,
                    course.get('course_code', ''),
                    course.get('course_name', ''),
                    course.get('category', ''),
                    course.get('hours', 0),
                    course.get('status', 'not_taken'),
                    course.get('semester_offered', ''),
                    course.get('grade', ''),
                    course.get('is_elective', False)
                ))
        conn.commit()

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

def save_student_stats(chat_id: int, stats_data: Dict[str, Any]):
    """حفظ الإحصائيات الدراسية"""
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

def save_student_courses(chat_id: int, courses_data: List[Dict[str, Any]]):
    """حفظ المقررات الدراسية"""
    try:
        # ✅ إذا كان جاي كـ string نحوله ل list
        if isinstance(courses_data, str):
            try:
                courses_data = json.loads(courses_data)
            except Exception:
                logger.error(f"Invalid JSON format for courses_data for {chat_id}")
                return

        if not isinstance(courses_data, list):
            logger.error(f"courses_data is not a list for {chat_id}")
            return

        with get_conn() as conn:
            with conn.cursor() as cur:
                # حذف المقررات القديمة
                cur.execute('DELETE FROM student_courses WHERE chat_id = %s', (chat_id,))
                
                # إضافة المقررات الجديدة
                for course in courses_data:
                    if not isinstance(course, dict):  # 🔒 حماية إضافية
                        continue
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
