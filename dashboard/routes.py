from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from database import get_all_groups, add_group, delete_group, update_group, get_all_users, delete_user, update_user_status, get_user_by_chat_id, get_db
from bot_instance import bot

dashboard_bp = Blueprint('dashboard', __name__, template_folder='templates', static_folder='static')

# بيانات تسجيل دخول المشرف
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = '1234'

@dashboard_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('dashboard.dashboard'))
        else:
            flash('بيانات الدخول غير صحيحة')
    return render_template('login.html')

@dashboard_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('dashboard.login'))

def login_required(func):
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('dashboard.login'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@dashboard_bp.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html')

@dashboard_bp.route('/groups')
@login_required
def groups():
    groups = get_all_groups()
    return render_template('groups.html', groups=groups)

@dashboard_bp.route('/groups/add', methods=['POST'])
@login_required
def add_new_group():
    name = request.form['name']
    category = request.form['category']
    link = request.form['link']
    add_group(name, category, link)
    return redirect(url_for('dashboard.groups'))

@dashboard_bp.route('/groups/delete/<int:group_id>')
@login_required
def delete_group_route(group_id):
    delete_group(group_id)
    return redirect(url_for('dashboard.groups'))

@dashboard_bp.route('/groups/edit/<int:group_id>', methods=['POST'])
@login_required
def edit_group(group_id):
    name = request.form['name']
    category = request.form['category']
    link = request.form['link']
    update_group(group_id, name, category, link)
    return redirect(url_for('dashboard.groups'))

@dashboard_bp.route('/users')
@login_required
def users():
    users = get_all_users()
    return render_template('users.html', users=users)

@dashboard_bp.route('/users/delete/<int:chat_id>')
@login_required
def delete_user_route(chat_id):
    delete_user(chat_id)
    return redirect(url_for('dashboard.users'))

@dashboard_bp.route('/users/toggle/<int:chat_id>')
@login_required
def toggle_user_status(chat_id):
    user = get_user_by_chat_id(chat_id)
    if user:
        new_status = 0 if user['active'] else 1
        update_user_status(chat_id, new_status)
    return redirect(url_for('dashboard.users'))

@dashboard_bp.route('/send', methods=['GET', 'POST'])
@login_required
def send_message():
    if request.method == 'POST':
        message = request.form['message']
        users = get_all_users()
        for user in users:
            try:
                bot.send_message(user['chat_id'], f"📢 رسالة من الإدارة:\n\n{message}")
            except:
                pass
        flash('تم إرسال الرسالة لجميع المستخدمين')
        return redirect(url_for('dashboard.send_message'))
    return render_template('send_message.html')
