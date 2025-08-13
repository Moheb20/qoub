import psycopg2
import os
import datetime
from cryptography.fernet import Fernet



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
    if token is None:
        return None
    return fernet.decrypt(token.encode()).decode()

# ---------- إنشاء الجداول ----------
def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
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

            cur.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT,
                    event_type TEXT,
                    event_value TEXT,
                    created_at TEXT
                )
            ''')
        conn.commit()

# ---------- إدارة المستخدمين ----------
def add_user(chat_id, student_id, password, registered_at=None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO users (chat_id, student_id, password, registered_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET
                    student_id = EXCLUDED.student_id,
                    password = EXCLUDED.password,
                    registered_at = EXCLUDED.registered_at
            ''', (chat_id, encrypt_text(student_id), encrypt_text(password), registered_at))
        conn.commit()

def get_user(chat_id):
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
                user['student_id'] = decrypt_text(user['student_id'])
                user['password'] = decrypt_text(user['password'])
                return user
            return None

def remove_user(chat_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM users WHERE chat_id = %s', (chat_id,))
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
