from telebot import TeleBot

def run_suggestion_bot():
    SUGGESTION_BOT_TOKEN = "8439226861:AAFXH0Zor2gHcAAYW3V09NP6zDKmejGKIt8"
    ADMIN_CHAT_ID = [6292405444, 1851786931] 

    bot_suggestion = TeleBot(SUGGESTION_BOT_TOKEN)

    @bot_suggestion.message_handler(func=lambda m: True)
    def forward_to_admin(message):
        username = f"@{message.from_user.username}" if message.from_user.username else ""
        full_name = message.from_user.first_name or ""
        if message.from_user.last_name:
            full_name += f" {message.from_user.last_name}"

        sender_info = username or full_name or "بدون اسم"

        for admin_id in ADMIN_CHAT_ID:
            try:
                bot_suggestion.send_message(
                    admin_id,
                    f"📩 اقتراح جديد من {sender_info}:\n\n{message.text}"
                )
            except Exception as e:
                print(f"Error sending suggestion: {e}")

        bot_suggestion.send_message(message.chat.id, "✅ تم إرسال اقتراحك بنجاح. شكراً لك!")

    bot_suggestion.infinity_polling()
