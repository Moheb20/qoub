def check_for_new_messages():
    while True:
        users = get_all_users()
        for user in users:
            chat_id = user['chat_id']
            student_id = user['student_id']
            password = user['password']
            last_msg_id = user['last_msg_id']

            scraper = QOUScraper(student_id, password)
            try:
                if scraper.login():
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
            except Exception as e:
                print(f"❌ خطأ مع المستخدم {student_id}: {e}")

            time.sleep(1)  # تخفيف الضغط بين المستخدمين

        time.sleep(20 * 60)
