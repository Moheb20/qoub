import sqlite3

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

def add_user(chat_id, student_id, password):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
            INSERT OR REPLACE INTO users (chat_id, student_id, password)
            VALUES (?, ?, ?)
        ''', (chat_id, student_id, password))
def get_user(chat_id):
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute('SELECT chat_id, student_id, password, last_msg_id FROM users WHERE chat_id = ?', (chat_id,))
        row = cur.fetchone()
        if row:
            return dict(zip(['chat_id', 'student_id', 'password', 'last_msg_id'], row))
        else:
            return None


def remove_user(chat_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('DELETE FROM users WHERE chat_id = ?', (chat_id,))

def update_last_msg(chat_id, msg_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('UPDATE users SET last_msg_id = ? WHERE chat_id = ?', (msg_id, chat_id))

def get_all_users():
    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.cursor()
        cur.execute('SELECT chat_id, student_id, password, last_msg_id FROM users')
        return [dict(zip(['chat_id', 'student_id', 'password', 'last_msg_id'], row)) for row in cur.fetchall()]
