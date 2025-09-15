from flask import Flask, request, jsonify
from bot_instance import bot
from database import (
    get_bot_stats,
    add_deadline,
    update_deadline,
    delete_deadline,
    add_group,
    get_all_deadlines,
    get_categories,
    get_groups_by_category,
    get_group_link,
    get_all_users
)
from datetime import date

app = Flask(__name__)

# هنا لازم تحط IDs الأدمن عندك
ADMIN_CHAT_ID = [6292405444, 1851786931]

# -------------------- التحقق من الأدمن --------------------
def is_admin(chat_id):
    return chat_id in ADMIN_CHAT_ID


# -------------------- الإحصائيات --------------------
@app.route("/api/stats", methods=["GET"])
def api_stats():
    chat_id = int(request.args.get("chat_id", 0))
    if not is_admin(chat_id):
        return jsonify({"error": "غير مصرح"}), 403
    stats = get_bot_stats()
    return jsonify(stats)

@app.route("/dashboard")
def dashboard():
    return app.send_static_file("dashboard.html")

# -------------------- إرسال رسالة جماعية --------------------
@app.route("/api/broadcast", methods=["POST"])
def api_broadcast():
    data = request.json
    chat_id = data.get("chat_id")
    message_text = data.get("message")
    if not is_admin(chat_id):
        return jsonify({"error": "غير مصرح"}), 403

    chat_ids = [u["chat_id"] for u in get_all_users()]
    sent_count = 0
    failed_count = 0

    for target_chat_id in chat_ids:
        try:
            bot.send_message(target_chat_id, message_text)
            sent_count += 1
        except:
            failed_count += 1

    return jsonify({"sent": sent_count, "failed": failed_count})

# -------------------- إدارة المواعيد --------------------
@app.route("/api/deadlines", methods=["GET"])
def api_get_deadlines():
    chat_id = int(request.args.get("chat_id", 0))
    if not is_admin(chat_id):
        return jsonify({"error": "غير مصرح"}), 403
    deadlines = get_all_deadlines()
    result = [{"id": d[0], "name": d[1], "date": d[2].strftime("%Y-%m-%d")} for d in deadlines]
    return jsonify(result)

@app.route("/api/deadlines/add", methods=["POST"])
def api_add_deadline():
    data = request.json
    chat_id = data.get("chat_id")
    if not is_admin(chat_id):
        return jsonify({"error": "غير مصرح"}), 403
    name = data.get("name")
    date_str = data.get("date")  # الصيغة: YYYY-MM-DD
    year, month, day = map(int, date_str.split("-"))
    deadline_date = date(year, month, day)
    deadline_id = add_deadline(name, deadline_date)
    return jsonify({"id": deadline_id, "name": name, "date": date_str})

# -------------------- إضافة قروب --------------------
@app.route("/api/groups/add", methods=["POST"])
def api_add_group():
    data = request.json
    chat_id = data.get("chat_id")
    if not is_admin(chat_id):
        return jsonify({"error": "غير مصرح"}), 403
    name = data.get("name")
    category = data.get("category")
    link = data.get("link")
    group_id = add_group(name, category, link)
    return jsonify({"id": group_id, "name": name, "category": category, "link": link})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

