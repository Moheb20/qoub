import os
from dotenv import load_dotenv

load_dotenv()

# إعدادات البوت
BOT_TOKEN = os.getenv("8346251354:AAH3LqivEvbh-DaLmjViyN_ICzlTYb6W1ZM")
ADMIN_CHAT_ID = [6292405444, 1851786931]

# مسارات الملفات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLANS_FILE_PATH = os.path.join(BASE_DIR, "data", "qou.json")
