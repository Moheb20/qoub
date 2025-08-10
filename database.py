import sqlite3
import datetime

DB_NAME = 'users.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                chat_id INTEGER PRIMARY KEY,
                student_id TEXT NOT NULL,
                password TEXT NOT NULL,
                last_msg_id TEXT
            )
        ''')

        cur = conn.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cur.fetchall()]

        if 'courses_data' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN courses_data TEXT")
        if 'last_login' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_login TEXT")
        if 'last_interaction' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN last_interaction TEXT")
        if 'registered_at' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN registered_at TEXT")
        if 'status' not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")

def add_user(chat_id, student_id, password, registered_at=None):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            INSERT OR REPLACE INTO users (chat_id, student_id, password, registered_at)
            VALUES (?, ?, ?, ?)
        ''', (chat_id, student_id, password, registered_at))

def get_user(chat_id):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT chat_id, student_id, password, last_msg_id, courses_data,
                   last_login, last_interaction, registered_at, status
            FROM users WHERE chat_id = ?
        ''', (chat_id,))
        row = cur.fetchone()
        if row:
            columns = ['chat_id', 'student_id', 'password', 'last_msg_id', 'courses_data',
                       'last_login', 'last_interaction', 'registered_at', 'status']
            return dict(zip(columns, row))
        else:
            return None

def remove_user(chat_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('DELETE FROM users WHERE chat_id = ?', (chat_id,))

def update_last_msg(chat_id, msg_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('UPDATE users SET last_msg_id = ? WHERE chat_id = ?', (msg_id, chat_id))

def update_user_courses(chat_id, courses_json):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('UPDATE users SET courses_data = ? WHERE chat_id = ?', (courses_json, chat_id))

def update_last_login(chat_id, last_login):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('UPDATE users SET last_login = ? WHERE chat_id = ?', (last_login, chat_id))

def update_last_interaction(chat_id, last_interaction):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('UPDATE users SET last_interaction = ? WHERE chat_id = ?', (last_interaction, chat_id))

def update_status(chat_id, status):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('UPDATE users SET status = ? WHERE chat_id = ?', (status, chat_id))

def get_all_users():
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT chat_id, student_id, password, last_msg_id, courses_data,
                   last_login, last_interaction, registered_at, status
            FROM users
        ''')
        columns = ['chat_id', 'student_id', 'password', 'last_msg_id', 'courses_data',
                   'last_login', 'last_interaction', 'registered_at', 'status']
        return [dict(zip(columns, row)) for row in cur.fetchall()]

# دوال وهمية مساعدة للإحصائيات (استبدلها بواقعك)
def get_total_messages_sent():
    return 1000

def get_total_messages_received():
    return 1500

def get_total_commands_count():
    return 300

def get_top_requested_groups(limit=5):
    return ['Group A', 'Group B', 'Group C', 'Group D', 'Group E']

def get_bot_start_date():
    return datetime.datetime.utcnow() - datetime.timedelta(days=30)

def get_bot_stats():
    users = get_all_users()
    total_users = len(users)

    now = datetime.datetime.utcnow()

    def parse_date(val):
        if val is None:
            return None
        if isinstance(val, datetime.datetime):
            return val
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
    top_groups = get_top_requested_groups(limit=5)

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
