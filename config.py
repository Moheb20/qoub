import os

# محاولة قراءة التوكن من متغيرات البيئة (الطريقة التي يعمل بها ريندر)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# فقط للتطوير المحلي: إذا لم يكن موجوداً في البيئة، جرب قراءته من .env
if not BOT_TOKEN:
    try:
        from dotenv import load_dotenv
        load_dotenv()
        BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
    except ImportError:
        pass  # dotenv غير مثبت في الانتاج

# تحقق نهائي من وجود التوكن
if not BOT_TOKEN:
    raise ValueError("""
❌ BOT_TOKEN غير موجود!

لإصلاح المشكلة:
1. في ريندر: Environment Variables → أضف BOT_TOKEN
2. محلياً: أنشئ ملف .env مع BOT_TOKEN=رقم_التوكن
""")

ADMIN_CHAT_ID = [6292405444, 1851786931]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PLANS_FILE_PATH = os.path.join(BASE_DIR, "data", "qou.json")

# للديباگ فقط - يمكن حذفها لاحقاً
print(f"✅ تم تحميل التوكن بنجاح (الطول: {len(BOT_TOKEN)})")
