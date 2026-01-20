import json
import os
import logging
import random
from datetime import datetime
from telebot import types
from database import (
    get_user, add_user, logout_user, update_last_msg,
    log_chat_id, get_categories, get_groups_by_category,
    get_group_link, get_portal_credentials, update_portal_data,
    get_user_branch_and_courses, find_potential_partners,
    create_anonymous_chat, add_chat_message, end_chat
)
from qou_scraper import QOUScraper
from scheduler import get_user_scheduled_events, format_scheduled_events_message
from scheduler import run_existing_functions_for_user
from bot_instance import bot

logger = logging.getLogger(__name__)

# ---------- إعداد المتغيرات العامة ----------
registration_states = {}
session_states = {}
session_statess = {}
user_sessions = {}
user_categories_data = {}
user_data = {}
study_plan_states = {}

# تحميل الخطط الدراسية
plans_file_path = os.path.join(os.path.dirname(__file__), "qou.json")
with open(plans_file_path, "r", encoding="utf-8") as f:
    study_plans = json.load(f)

def send_main_menu(chat_id):
    """إرسال القائمة الرئيسية مع مراعاة حالة تسجيل الدخول من قاعدة البيانات"""
    user = get_user(chat_id)

    # تحقق إذا المستخدم مسجل
    logged_in = bool(user and user.get("student_id"))

    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)

    if not logged_in:
        markup.add(types.KeyboardButton("👤 تسجيل الدخول"))
        bot.send_message(chat_id, "⬇️ الرجاء تسجيل الدخول أولاً:", reply_markup=markup)
    else:
        markup.add(types.KeyboardButton("📖 الخدمات الأكاديمية"))
        markup.add(types.KeyboardButton("📅 التـــقويــم"))
        markup.add(types.KeyboardButton("🔗 منصة المواد المشتركة"))
        markup.add(types.KeyboardButton("📚 أخرى"))
        markup.add(types.KeyboardButton("🚪 تسجيل الخروج"))
        if chat_id in [6292405444, 1851786931]:  # ADMIN_CHAT_ID
            markup.add(types.KeyboardButton("admin"))

        bot.send_message(chat_id, "⬇️ القائمة الرئيسية:", reply_markup=markup)

def send_academic_stats_menu(chat_id):
    """القائمة الفرعية لعرض الخدمات المتعلقة بالإحصائيات والمقررات"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📊 إحصائياتي"),
        types.KeyboardButton("📚 مقرراتي"),
        types.KeyboardButton("📌 مقررات حالية"),
        types.KeyboardButton("🎯 نسبة الإنجاز"),
        types.KeyboardButton("📋 الخطة الدراسية"),
        types.KeyboardButton("🔄 تحديث بياناتي"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر من القائمة:", reply_markup=markup)

def send_academic_services(chat_id):
    """القائمة الفرعية للخدمات الأكاديمية"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📖 عرض المقررات والعلامات"),
        types.KeyboardButton("🗓️ جدول المحاضرات"),
        types.KeyboardButton("📊 عرض بيانات الفصل"),
        types.KeyboardButton("📅 جدول الامتحانات"),
        types.KeyboardButton("🎙️ حلقات النقاش"),
        types.KeyboardButton("📖 الخطة الدراسية"),
        types.KeyboardButton("📚 الخطط الدراسية"),
        types.KeyboardButton("💻 اللقاءات الافتراضية"),
        types.KeyboardButton("💰 رصيد الطالب"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة أكاديمية:", reply_markup=markup)

def send_cel_services(chat_id):
    """القائمة الفرعية للخدمات الأكاديمية والجدول والتقويم"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    # أزرار التقويم
    markup.add(
        types.KeyboardButton("📅 التقويم الحالي"),
        types.KeyboardButton("📅 عرض التقويم القادم للفصل الحالي")
    )
    
    # زر نوع الأسبوع الحالي
    current_week_text = QOUScraper.get_current_week_type()
    markup.add(types.KeyboardButton(f"🟢 {current_week_text}"))
    
    # أزرار حالة التأجيل والتحديث
    if chat_id in session_statess:
        scraper = session_statess[chat_id]
        delay_status = scraper.get_delay_status()
        markup.add(types.KeyboardButton(f"📅 {delay_status}"))
    else:
        markup.add(types.KeyboardButton("📅 حالة التأجيل: ❌ غير متوفرة")) 
    
    markup.add(types.KeyboardButton("🔄 تحديث حالة التأجيل"))
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))

    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def send_manasa_services(chat_id):
    """القائمة الفرعية للخدمات الأكاديمية والجدول والتقويم"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("👥 منصة المواد المشتركة"),
        types.KeyboardButton("🔗 ربط الحساب بمنصة المواد المشتركة")
    )
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
    
    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def send_other_services(chat_id):
    """القائمة الفرعية للخدمات الأخرى"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📅 المواعيد المجدولة"),
        types.KeyboardButton("📚 عرض القروبات"),
        types.KeyboardButton("✉️ إرسال اقتراح"),
        types.KeyboardButton("⬅️ عودة للرئيسية")
    )
    bot.send_message(chat_id, "⬇️ اختر خدمة:", reply_markup=markup)

def show_main_menu(chat_id):
    """دالة مساعدة لعرض القائمة الرئيسية"""
    send_main_menu(chat_id)

def start_login(chat_id):
    """ابدأ مسار تسجيل الدخول للمستخدم"""
    registration_states[chat_id] = {"stage": "awaiting_student_id"}
    bot.send_message(chat_id, "👤 الرجاء إرسال رقمك الجامعي:")

def clear_states_for_home(chat_id):
    """نمسح حالات الجلسة والتسجيل للمستخدم عند العودة للرئيسية"""
    registration_states.pop(chat_id, None)
    session_states.pop(chat_id, None)

def handle_user_commands():
    """تسجيل جميع معالجات المستخدمين"""
    
    @bot.message_handler(commands=["start"])
    def handle_start(message):
        log_chat_id(message.chat.id)
        chat_id = message.chat.id
        username = message.from_user.username or "بدون اسم مستخدم"
        user = get_user(chat_id)

        if user:
            bot.send_message(chat_id, "👋  مرحــــباً!  ")
        else:
            add_user(chat_id, student_id="", password="", registered_at=datetime.utcnow().isoformat())
            bot.send_message(chat_id, "👤 لم يتم تسجيلك بعد. الرجاء تسجيل الدخول.")
            
            # إرسال إشعار للأدمن (يمكن نقله لملف الأدمن إذا أردت)
            admin_message = (
                f"🚨 مستخدم جديد بدأ استخدام البوت!\n\n"
                f"chat_id: {chat_id}\n"
                f"Username: @{username}"
            )
            for admin_id in [6292405444, 1851786931]:
                try:
                    bot.send_message(admin_id, admin_message)
                except Exception as e:
                    print(f"خطأ في إرسال الرسالة للأدمن {admin_id}: {e}")

        send_main_menu(chat_id)

    @bot.message_handler(commands=['end'])
    def handle_end_chat(message):
        chat_id = message.chat.id
        
        if chat_id in user_sessions and user_sessions[chat_id].get('in_chat'):
            chat_token = user_sessions[chat_id]['chat_token']
            partner_id = user_sessions[chat_id]['partner_id']
            
            end_chat(chat_token)
            
            try:
                bot.send_message(partner_id, "❌ الطرف الآخر أنهى المحادثة")
            except:
                pass
            
            bot.send_message(chat_id, "✅ تم إنهاء المحادثة")
            del user_sessions[chat_id]
        else:
            bot.send_message(chat_id, "❌ لا توجد محادثة نشطة")

    @bot.message_handler(func=lambda message: message.text.startswith("🟢"))
    def handle_info_button(message):
        """معالجة أزرار المعلومات"""
        bot.send_chat_action(message.chat.id, 'typing')
        pass

    @bot.message_handler(func=lambda message: message.text == "🔄 تحديث الجدولة")
    def handle_force_schedule_update(message):
        """تحديث الجدولة الفوري"""
        try:
            chat_id = message.chat.id
            logger.info(f"[{chat_id}] طلب تحديث الجدولة الفوري")
            
            bot.send_chat_action(chat_id, 'typing')
            bot.send_message(chat_id, "🔄 جاري تحديث الجدولة... قد يستغرق هذا بضع ثوانٍ")
            
            success_count = run_existing_functions_for_user(chat_id)
            
            if success_count > 0:
                bot.send_message(chat_id, f"✅ تم تحديث الجدولة بنجاح!\nتم فحص {success_count} عنصر من جدولك")
            else:
                bot.send_message(chat_id, "⚠️ لم يتم العثور على عناصر جديدة في جدولك")
                
        except Exception as e:
            logger.error(f"خطأ في تحديث الجدولة: {e}")
            bot.send_message(chat_id, "❌ حدث خطأ أثناء تحديث الجدولة")

    @bot.callback_query_handler(func=lambda call: call.data == "show_upcoming_lectures")
    def handle_upcoming_lectures(call):
        """عرض المحاضرات القادمة"""
        chat_id = call.message.chat.id
        user = get_user(chat_id)
        
        if not user:
            bot.answer_callback_query(call.id, "❌ لم يتم العثور على بياناتك. أرسل /start أولاً.")
            return

        try:
            bot.delete_message(chat_id, call.message.message_id)
            wait_msg = bot.send_message(chat_id, "⏳ جاري تحضير المحاضرات القادمة...")
            
            scraper = QOUScraper(user['student_id'], user['password'])
            if not scraper.login():
                bot.delete_message(chat_id, wait_msg.message_id)
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
                return

            upcoming_lectures = scraper.get_upcoming_lectures(chat_id)
            bot.delete_message(chat_id, wait_msg.message_id)
            
            keyboard = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton(
                text="↩️ العودة لجدول المحاضرات", 
                callback_data="back_to_schedule"
            )
            keyboard.add(back_btn)
            
            bot.send_message(
                chat_id, 
                upcoming_lectures, 
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.exception(f"Error in upcoming lectures callback for {chat_id}: {e}")
            bot.answer_callback_query(call.id, "❌ حدث خطأ. حاول مرة أخرى.")

    @bot.message_handler(func=lambda message: message.text == "📅 المواعيد المجدولة")
    def handle_scheduled_events(message):
        """عرض المواعيد المجدولة"""
        try:
            chat_id = message.chat.id
            logger.info(f"[{chat_id}] طلب عرض المواعيد المجدولة")
            
            bot.send_chat_action(chat_id, 'typing')
            events_info = get_user_scheduled_events(chat_id)
            
            if events_info is None:
                bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب المواعيد المجدولة")
                return
            
            events_message = format_scheduled_events_message(events_info)
            markup = types.InlineKeyboardMarkup()
            update_button = types.InlineKeyboardButton("🔄 تحديث الجدولة الآن", callback_data="update_schedule")
            markup.add(update_button)
            
            bot.send_message(chat_id, events_message, parse_mode='Markdown', reply_markup=markup)
            logger.info(f"[{chat_id}] تم عرض المواعيد المجدولة بنجاح")
            
        except Exception as e:
            logger.error(f"خطأ في معالجة طلب المواعيد المجدولة: {e}")
            bot.send_message(message.chat.id, "❌ حدث خطأ أثناء جلب المواعيد المجدولة")

    @bot.callback_query_handler(func=lambda call: call.data == "update_schedule")
    def handle_update_schedule_callback(call):
        """تحديث الجدولة من الزر"""
        try:
            chat_id = call.message.chat.id
            logger.info(f"[{chat_id}] طلب تحديث الجدولة من الزر")
            
            bot.edit_message_text(
                "🔄 جاري تحديث الجدولة...", 
                chat_id, 
                call.message.message_id
            )
            
            success_count = run_existing_functions_for_user(chat_id)
            
            if success_count > 0:
                events_info = get_user_scheduled_events(chat_id)
                if events_info:
                    events_message = format_scheduled_events_message(events_info)
                    
                    markup = types.InlineKeyboardMarkup()
                    updated_button = types.InlineKeyboardButton("✅ تم التحديث", callback_data="already_updated")
                    markup.add(updated_button)
                    
                    bot.edit_message_text(
                        events_message,
                        chat_id,
                        call.message.message_id,
                        parse_mode='Markdown',
                        reply_markup=markup
                    )
                    
                    bot.send_message(chat_id, f"✅ تم تحديث الجدولة بنجاح! تم فحص {success_count} عنصر")
                else:
                    bot.edit_message_text(
                        "❌ فشل في تحميل البيانات بعد التحديث",
                        chat_id,
                        call.message.message_id
                    )
            else:
                bot.edit_message_text(
                    "⚠️ لم يتم العثور على عناصر جديدة في جدولك",
                    chat_id,
                    call.message.message_id
                )
                
        except Exception as e:
            logger.error(f"خطأ في معالجة تحديث الجدولة: {e}")
            try:
                bot.send_message(chat_id, "❌ حدث خطأ أثناء تحديث الجدولة")
            except:
                pass

    @bot.callback_query_handler(func=lambda call: call.data == "already_updated")
    def handle_already_updated(call):
        """معالجة النقر على الزر بعد التحديث"""
        bot.answer_callback_query(call.id, "✅ تم تحديث الجدولة مسبقاً", show_alert=False)

    @bot.callback_query_handler(func=lambda call: call.data == "back_to_schedule")
    def handle_back_to_schedule(call):
        """العودة لجدول المحاضرات"""
        chat_id = call.message.chat.id
        
        try:
            bot.delete_message(chat_id, call.message.message_id)
            
            user = get_user(chat_id)
            if not user:
                bot.answer_callback_query(call.id, "❌ لم يتم العثور على بياناتك.")
                return

            scraper = QOUScraper(user['student_id'], user['password'])
            if not scraper.login():
                bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
                return

            schedule = scraper.fetch_lectures_schedule()
            if not schedule:
                bot.send_message(chat_id, "📭 لم يتم العثور على جدول المحاضرات.")
                return

            days_order = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
            schedule_by_day = {}

            for meeting in schedule:
                day = meeting.get('day', '').strip()
                if not day:
                    day = "غير محدد"

                time = meeting.get('time', '--:-- - --:--')
                course_name = meeting.get('course_name', 'غير محدد')
                building = meeting.get('building', '')
                room = meeting.get('room', '')
                lecturer = meeting.get('lecturer', '')

                entry_text = f"📘 {course_name}\n⏰ {time}\n"
                
                if building or room:
                    entry_text += f"📍 {building} - {room}\n"
                if lecturer:
                    entry_text += f"👨‍🏫 {lecturer}"

                schedule_by_day.setdefault(day, []).append(entry_text)

            text_msg = "🗓️ *جدول المحاضرات:*\n\n"
            
            for day in days_order:
                if day in schedule_by_day:
                    text_msg += f"📅 *{day}:*\n"
                    for entry in schedule_by_day[day]:
                        text_msg += f"{entry}\n\n"

            for day, entries in schedule_by_day.items():
                if day not in days_order:
                    text_msg += f"📅 *{day}:*\n"
                    for entry in entries:
                        text_msg += f"{entry}\n\n"

            keyboard = types.InlineKeyboardMarkup()
            show_schedule_btn = types.InlineKeyboardButton(
                text="📢 عرض المحاضرات القادمة", 
                callback_data="show_upcoming_lectures"
            )
            keyboard.add(show_schedule_btn)

            bot.send_message(chat_id, text_msg, parse_mode="Markdown", reply_markup=keyboard)
            
        except Exception as e:
            logger.exception(f"Error in back to schedule for {chat_id}: {e}")
            bot.answer_callback_query(call.id, "❌ حدث خطأ.")

    @bot.message_handler(func=lambda message: message.text.startswith("📅 فترة التأجيل:"))
    def handle_delay_display(message):
        """عرض رسالة توضيحية لحالة التأجيل"""
        bot.send_message(message.chat.id, "ℹ️ هذه العبارة توضح حالة التأجيل الحالية. للتحقق من أحدث حالة، اضغط على \"🔄 تحديث حالة التأجيل\"", 
                        reply_markup=types.ReplyKeyboardRemove(selective=True))

    @bot.message_handler(func=lambda message: message.text == "🔄 تحديث حالة التأجيل")
    def handle_delay_refresh(message):
        """تحديث حالة التأجيل"""
        chat_id = message.chat.id
        
        user = get_user(chat_id)
        
        if not user or not user.get("student_id"):
            bot.send_message(chat_id, "⚠️ يرجى تسجيل الدخول أولاً باستخدام /login")
            return
        
        bot.send_chat_action(chat_id, 'typing')
        scraper = QOUScraper(user["student_id"], user["password"])
        
        if scraper.login():
            session_statess[chat_id] = scraper
            new_status = scraper.get_delay_status()
            bot.send_message(chat_id, f"✅ تم التحديث: {new_status}")
            send_cel_services(chat_id)
        else:
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول")

    @bot.message_handler(func=lambda message: True)
    def handle_all_messages(message):
        """معالجة جميع الرسائل النصية"""
        chat_id = message.chat.id
        text = (message.text or "").strip()
        
        # 1. أولاً: التحقق من المحادثات النشطة
        if chat_id in user_sessions and user_sessions[chat_id].get('in_chat'):
            if text == "✖️ إنهاء المحادثة":
                if chat_id in user_sessions and user_sessions[chat_id].get('in_chat'):
                    chat_token = user_sessions[chat_id]['chat_token']
                    partner_id = user_sessions[chat_id]['partner_id']
                    
                    end_chat(chat_token)
                    
                    if partner_id in user_sessions:
                        del user_sessions[partner_id]
                    if chat_id in user_sessions:
                        del user_sessions[chat_id]
                    
                    try:
                        bot.send_message(partner_id, "❌ الطرف الآخر أنهى المحادثة")
                        send_main_menu(partner_id)
                    except:
                        pass
                    
                    bot.send_message(chat_id, "✅ تم إنهاء المحادثة")
                    send_main_menu(chat_id)
                return
                
            chat_token = user_sessions[chat_id]['chat_token']
            partner_id = user_sessions[chat_id]['partner_id']
            
            add_chat_message(chat_token, chat_id, text)
            
            try:
                markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add("✖️ إنهاء المحادثة")
                bot.send_message(partner_id, f"👤 [مجهول]: {text}", reply_markup=markup)
            except Exception as e:
                bot.send_message(chat_id, "❌ تعذر إرسال الرسالة.")
                del user_sessions[chat_id]
            
            return
        
        # 2. معالجة المسار الرئيسي للرسائل
        handle_main_message_flow(chat_id, text)

def handle_main_message_flow(chat_id, text):
    """معالجة تدفق الرسائل الرئيسي"""
    
    # --- مسار التسجيل ---
    if chat_id in registration_states:
        stage = registration_states[chat_id].get("stage")

        if stage == "awaiting_student_id":
            registration_states[chat_id]["student_id"] = text
            registration_states[chat_id]["stage"] = "awaiting_password"
            bot.send_message(chat_id, "🔒 الآن، الرجاء إرسال كلمة المرور:")
            return

        if stage == "awaiting_password":
            registration_states[chat_id]["password"] = text
            student_id = registration_states[chat_id].get("student_id")
            password = registration_states[chat_id].get("password")

            try:
                scraper = QOUScraper(student_id, password)
                if scraper.login():
                    add_user(chat_id, student_id, password)
                    user_sessions[chat_id] = {"logged_in": True}
                    bot.send_message(chat_id, "✅ تم تسجيلك بنجاح!\n🔍 جاري البحث عن آخر رسالة...")

                    latest = scraper.fetch_latest_message()
                    if latest:
                        update_last_msg(chat_id, latest["msg_id"])
                        text_msg = (
                            f"📬 آخـــر رســالـــة في البـــريـــد:\n"
                            f"📧 {latest['subject']}\n"
                            f"📝 {latest['sender']}\n"
                            f"🕒 {latest['date']}\n\n"
                            f"{latest['body']}\n\n"
                            f"📬 وسيـــتم اعلامــــك\ي بأي رســالة جــديــدة \n"
                        )
                        bot.send_message(chat_id, text_msg)
                    else:
                        bot.send_message(chat_id, "📭 لم يتم العثور على رسائل حالياً.")
                else:
                    bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة البيانات.")
            except Exception as e:
                logger.exception(f"Error during login for {chat_id}: {e}")
                bot.send_message(chat_id, "❌ حدث خطأ أثناء محاولة تسجيل الدخول. حاول مرة أخرى لاحقاً.")
            finally:
                registration_states.pop(chat_id, None)
                send_main_menu(chat_id)
            return
    
    # --- التعامل مع أزرار القائمة الرئيسية ---
    # تقليل التكرار بواسطة استخدام دالة معالجة المركزية
    handle_menu_buttons(chat_id, text)

def handle_menu_buttons(chat_id, text):
    """معالجة أزرار القائمة"""
    
    menu_handlers = {
        "👤 تسجيل الدخول": lambda: start_login(chat_id),
        "📅 التقويم الحالي": lambda: bot.send_message(chat_id, QOUScraper.get_active_calendar()),
        "📚 عرض القروبات": lambda: show_groups_menu(chat_id),
        "🚪 تسجيل الخروج": lambda: logout_and_return(chat_id),
        "📖 الخدمات الأكاديمية": lambda: send_academic_services(chat_id),
        "📚 أخرى": lambda: send_other_services(chat_id),
        "📅 التـــقويــم": lambda: send_cel_services(chat_id),
        "📖 الخطة الدراسية": lambda: send_academic_stats_menu(chat_id),
        "🔗 منصة المواد المشتركة": lambda: send_manasa_services(chat_id),
        "🏠 الرئيسية": lambda: return_to_main_menu(chat_id),
        "⬅️ عودة للرئيسية": lambda: return_to_main_menu(chat_id),
        "📖 عرض المقررات والعلامات": lambda: show_courses_and_grades(chat_id),
        "✉️ إرسال اقتراح": lambda: bot.send_message(chat_id, "📬 لإرسال اقتراح، اضغط على الرابط التالي للتواصل عبر بوت الاقتراحات:"),
        "🗓️ جدول المحاضرات": lambda: show_lecture_schedule(chat_id),
        "📊 عرض بيانات الفصل": lambda: show_term_stats(chat_id),
        "📅 جدول الامتحانات": lambda: show_exam_schedule_menu(chat_id),
        "🎙️ حلقات النقاش": lambda: show_discussion_sessions(chat_id),
        "💰 رصيد الطالب": lambda: show_balance(chat_id),
        "📚 الخطط الدراسية": lambda: show_study_plans(chat_id),
        "📊 إحصائياتي": lambda: show_user_stats(chat_id),
        "📚 مقرراتي": lambda: show_user_courses(chat_id),
        "🎯 نسبة الإنجاز": lambda: show_completion_percentage(chat_id),
        "📋 الخطة الدراسية": lambda: show_study_plan_summary(chat_id),
        "📌 مقررات حالية": lambda: show_current_courses(chat_id),
        "🔄 تحديث بياناتي": lambda: update_user_data(chat_id),
        "🔗 ربط الحساب بمنصة المواد المشتركة": lambda: link_portal_account(chat_id),
        "👥 منصة المواد المشتركة": lambda: show_shared_materials(chat_id),
    }
    
    if text in menu_handlers:
        menu_handlers[text]()
        return True
    
    # معالجات خاصة
    if text in get_categories():
        show_groups_in_category(chat_id, text)
    elif get_group_link(text):
        show_group_link(chat_id, text)
    elif "|" in text and len(text.split("|")) == 2:
        handle_term_selection(chat_id, text)
    elif text in ["📝 النصفي", "🏁 النهائي النظري", "🧪 النهائي العملي", "📈 امتحان المستوى"]:
        handle_exam_type_selection(chat_id, text)
    elif text == "🔍 بحث في القروبات":
        ask_search(chat_id)
    elif text == "العودة للقروبات":
        show_groups_menu(chat_id)
    elif text.startswith("📖 "):
        handle_course_selection(chat_id, text)
    elif text.startswith("🎲 محادثة عشوائية - "):
        handle_random_chat(chat_id, text)
    elif text == "👥 عرض قائمة الزملاء":
        show_partners_list(chat_id)
    elif text == "⬅️ عودة للمواد":
        return_to_materials(chat_id)
    else:
        handle_other_selections(chat_id, text)
    
    return False

# ------ دالات المساعدة للوظائف المختلفة ------

def logout_and_return(chat_id):
    """تسجيل الخروج والعودة للقائمة"""
    logout_user(chat_id)
    bot.send_message(chat_id, "✅ تم تسجيل الخروج بنجاح!")
    send_main_menu(chat_id)

def return_to_main_menu(chat_id):
    """العودة للقائمة الرئيسية"""
    if chat_id in user_data:
        del user_data[chat_id]
    send_main_menu(chat_id)

def show_groups_menu(chat_id):
    """عرض قائمة القروبات"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    categories = get_categories()
    for category in categories:
        markup.add(types.KeyboardButton(category))
    markup.add(types.KeyboardButton("🔍 بحث في القروبات"))
    markup.add(types.KeyboardButton("العودة للرئيسية"))
    bot.send_message(chat_id, "📚 اختر نوع القروب:", reply_markup=markup)

def show_groups_in_category(chat_id, category):
    """عرض القروبات ضمن تصنيف"""
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
    groups_in_category = get_groups_by_category(category)
    for group_id, group_name, link in groups_in_category:
        markup.add(types.KeyboardButton(group_name))
    markup.add(types.KeyboardButton("العودة للقروبات"))
    bot.send_message(chat_id, f"📂 القروبات ضمن '{category}': اختر قروب:", reply_markup=markup)

def show_group_link(chat_id, group_name):
    """عرض رابط القروب"""
    link = get_group_link(group_name)
    bot.send_message(chat_id, f"🔗 رابط قروب '{group_name}':\n{link}")

def ask_search(chat_id):
    """طلب كلمة للبحث"""
    bot.send_message(chat_id, "🔍 اكتب كلمة للبحث في القروبات:")

def show_courses_and_grades(chat_id):
    """عرض المقررات والعلامات"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
            return

        courses = scraper.fetch_term_summary_courses()
        if not courses:
            bot.send_message(chat_id, "📭 لم يتم العثور على مقررات أو علامات.")
            return

        text_msg = "📚 *ملخص علامات المقررات الفصلية:*\n\n"
        for c in courses:
            code = c.get('course_code', '-')
            name = c.get('course_name', '-')
            midterm = c.get('midterm_mark', '-')
            final = c.get('final_mark', '-')
            final_date = c.get('final_mark_date', '-')

            text_msg += (
                f"📘 {code} - {name}\n"
                f"   📝 علامة النصفي: {midterm}\n"
                f"   🏁 العلامة النهائية: {final}\n"
                f"   📅 تاريخ وضع العلامة النهائية: {final_date}\n\n"
            )
        
        bot.send_message(chat_id, text_msg, parse_mode="Markdown")
        
    except Exception as e:
        logger.exception(f"Error fetching courses for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب البيانات. حاول مرة أخرى لاحقاً.")

def show_lecture_schedule(chat_id):
    """عرض جدول المحاضرات"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
            return

        schedule = scraper.fetch_lectures_schedule()
        if not schedule:
            bot.send_message(chat_id, "📭 لم يتم العثور على جدول المحاضرات.")
            return

        days_order = ["السبت", "الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة"]
        schedule_by_day = {}

        for meeting in schedule:
            day = meeting.get('day', '').strip()
            if not day:
                day = "غير محدد"

            time = meeting.get('time', '--:-- - --:--')
            course_name = meeting.get('course_name', 'غير محدد')
            building = meeting.get('building', '')
            room = meeting.get('room', '')
            lecturer = meeting.get('lecturer', '')

            entry_text = f"📘 {course_name}\n"
            entry_text += f"⏰ {time}\n"
            
            if building or room:
                entry_text += f"📍 {building} - {room}\n"
            if lecturer:
                entry_text += f"👨‍🏫 {lecturer}"

            schedule_by_day.setdefault(day, []).append(entry_text)

        text_msg = "🗓️ *جدول المحاضرات:*\n\n"
        
        for day in days_order:
            if day in schedule_by_day:
                text_msg += f"📅 *{day}:*\n"
                for entry in schedule_by_day[day]:
                    text_msg += f"{entry}\n\n"

        for day, entries in schedule_by_day.items():
            if day not in days_order:
                text_msg += f"📅 *{day}:*\n"
                for entry in entries:
                    text_msg += f"{entry}\n\n"

        keyboard = types.InlineKeyboardMarkup()
        show_schedule_btn = types.InlineKeyboardButton(
            text="📢 عرض المحاضرات القادمة", 
            callback_data="show_upcoming_lectures"
        )
        keyboard.add(show_schedule_btn)

        bot.send_message(
            chat_id, 
            text_msg, 
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
    except Exception as e:
        logger.exception(f"Error fetching schedule for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب جدول المحاضرات. حاول مرة أخرى لاحقاً.")

def show_term_stats(chat_id):
    """عرض بيانات الفصل"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
            return

        stats = scraper.fetch_term_summary_stats()
        if not stats:
            bot.send_message(chat_id, "📭 لم يتم العثور على بيانات الفصل.")
            return

        term = stats['term']
        cumulative = stats['cumulative']

        msg = (
            "📊 *البيانــــات الفـــصليـة والــــتراكــمية*\n"
            f"- 🧾 النـــــوع: {term['type']}\n"
            f"- 🕒 المسجــل: {term['registered_hours']} س.\n"
            f"- ✅ المجتــاز: {term['passed_hours']} س.\n"
            f"- 🧮 المحتسبــة: {term['counted_hours']}\n"
            f"- ❌ الراســب: {term['failed_hours']}\n"
            f"- 🚪 المنســحب: {term['withdrawn_hours']}\n"
            f"- 🏅 النقــاط: {term['points']}\n"
            f"- 📈 المعــدل: {term['gpa']}\n"
            f"- 🏆 لوحــة الشــرف: {term['honor_list']}\n\n"
            "📘 *البيانــات التراكــمية:*\n"
            f"- 🧾 النــوع: {cumulative['type']}\n"
            f"- 🕒 المســجل: {cumulative['registered_hours']} س.\n"
            f"- ✅ المجــتاز: {cumulative['passed_hours']} س.\n"
            f"- 🧮 المحتــسبة: {cumulative['counted_hours']}\n"
            f"- ❌ الراســب: {cumulative['failed_hours']}\n"
            f"- 🚪 المنسحـــب: {cumulative['withdrawn_hours']}\n"
            f"- 🏅 النقــاط: {cumulative['points']}\n"
            f"- 📈 المعــدل: {cumulative['gpa']}\n"
            f"- 🏆 لوحــة الشــرف: {cumulative['honor_list']}\n"
        )

        bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception as e:
        logger.exception(f"Error fetching term stats for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب بيانات الفصل. حاول مرة أخرى لاحقاً.")

def show_exam_schedule_menu(chat_id):
    """عرض قائمة اختيار الفصل الدراسي للامتحانات"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول.")
            return

        available_terms = scraper.get_last_two_terms()
        if not available_terms:
            bot.send_message(chat_id, "⚠️ تعذر جلب الفصول المتاحة.")
            return

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for term in available_terms:
            markup.add(types.KeyboardButton(f"📅 {term['label']}|{term['value']}"))
        markup.add(types.KeyboardButton("العودة للرئيسية"))
        bot.send_message(chat_id, "📌 اختر الفصل الدراسي:", reply_markup=markup)
    except Exception as e:
        logger.exception(f"Error fetching terms for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب الفصول. حاول مرة أخرى لاحقاً.")

def handle_term_selection(chat_id, text):
    """معالجة اختيار الفصل الدراسي"""
    try:
        label, term_no = text.replace("📅", "").strip().split("|")
    except Exception:
        bot.send_message(chat_id, "⚠️ تنسيق الاختيار غير صحيح. الرجاء اختيار الفصل من الأزرار.")
        return

    session_states.setdefault(chat_id, {})["term_no"] = term_no.strip()
    session_states[chat_id]["term_label"] = label.strip()

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(
        types.KeyboardButton("📝 النصفي"),
        types.KeyboardButton("🏁 النهائي النظري"),
        types.KeyboardButton("🧪 النهائي العملي"),
        types.KeyboardButton("📈 امتحان المستوى"),
        types.KeyboardButton("العودة للرئيسية"),
    )
    bot.send_message(chat_id, f"📌 اختر نوع الامتحان لـ: {label.strip()}", reply_markup=markup)

def handle_exam_type_selection(chat_id, text):
    """معالجة اختيار نوع الامتحان"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    if chat_id not in session_states or 'term_no' not in session_states[chat_id]:
        bot.send_message(chat_id, "❌ حدث خطأ، يرجى اختيار الفصل أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. يرجى إعادة اختيار الفصل الدراسي.")
            return
    except Exception as e:
        logger.exception(f"Error creating scraper for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء الاتصال بموقع الجامعة. حاول مرة أخرى لاحقاً.")
        return

    term_no = session_states[chat_id]['term_no']
    exam_type_map = {
        "📝 النصفي": "MT&IM",
        "🏁 النهائي النظري": "FT&IF",
        "🧪 النهائي العملي": "FP&FP",
        "📈 امتحان المستوى": "LE&LE",
    }
    exam_type = exam_type_map[text]

    try:
        exams = scraper.fetch_exam_schedule(term_no, exam_type)
        if not exams:
            bot.send_message(chat_id, "📭 لا يوجد جدول لهذا النوع.")
            return

        msg = f"📅 *جدول {text}:*\n\n"
        for ex in exams:
            msg += (
                f"📘 {ex.get('course_code', '-')} - {ex.get('course_name', '-')}\n"
                f"📆 {ex.get('date', '-') } ({ex.get('day', '-')})\n"
                f"⏰ {ex.get('from_time', '-')} - {ex.get('to_time', '-')}\n"
                f"👨‍🏫 {ex.get('lecturer', '-')}\n"
                f"📝 {ex.get('note', '-')}\n"
                f"───────────────\n"
            )

        bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception as e:
        logger.exception(f"Error fetching exams for {chat_id}: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب جدول الامتحانات. حاول مرة أخرى لاحقاً.")

def show_discussion_sessions(chat_id):
    """عرض حلقات النقاش"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    scraper = QOUScraper(user['student_id'], user['password'])
    if not scraper.login():
        bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
        return

    sessions = scraper.fetch_discussion_sessions()
    if not sessions:
        bot.send_message(chat_id, "📭 لا يوجد حلقات نقاش حالياً.")
        return

    msg = "🎙️ *جــــميـــع حـلـقـات الــنـقـاش:*\n\n"
    for s in sessions:
        msg += (
            f"📘 {s['course_name']} ({s['course_code']})\n"
            f"📅 {s['date']} 🕒 {s['time']}\n\n"
        )
    bot.send_message(chat_id, msg, parse_mode="Markdown")

def show_balance(chat_id):
    """عرض رصيد الطالب"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
            return

        balance_pdf_bytes = scraper.fetch_balance_table_pdf()
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        markup.add("📊 الإجمالي", "🏠 العودة للرئيسية")

        if balance_pdf_bytes:
            balance_pdf_bytes.name = "رصيد_الطالب.pdf"
            bot.send_document(chat_id, document=balance_pdf_bytes, reply_markup=markup)
        else:
            bot.send_message(chat_id, "❌ لم يتم العثور على بيانات الرصيد", reply_markup=markup)

    except Exception as e:
        print(f"Error fetching balance: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء جلب بيانات الرصيد. حاول مرة أخرى لاحقاً.")

@bot.message_handler(func=lambda message: message.text == "📊 الإجمالي")
def handle_totals(message):
    """عرض الإجمالي"""
    chat_id = message.chat.id
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "❌ لم يتم العثور على بياناتك. أرسل /start لتسجيل الدخول أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        if not scraper.login():
            bot.send_message(chat_id, "❌ فشل تسجيل الدخول. تأكد من صحة اسم المستخدم وكلمة المرور.")
            return

        totals_text = scraper.fetch_balance_totals()
        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
        markup.add("🏠 العودة للرئيسية")
        bot.send_message(chat_id, totals_text, reply_markup=markup)
    except Exception as e:
        print(f"Error fetching totals: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ أثناء حساب الإجمالي. حاول مرة أخرى لاحقاً.")

def show_study_plans(chat_id):
    """عرض الخطط الدراسية"""
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    for college in study_plans.keys():
        markup.add(types.KeyboardButton(college))
    markup.add(types.KeyboardButton("العودة للرئيسية"))
    study_plan_states[chat_id] = {"stage": "awaiting_college"}
    bot.send_message(chat_id, "📚 اختر الكلية:", reply_markup=markup)

def show_user_stats(chat_id):
    """عرض إحصائيات المستخدم"""
    user = get_user(chat_id)
    if not user or not user['student_id'] or not user['password']:
        bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        study_plan = scraper.fetch_study_plan()
        stats = study_plan['stats']

        if not stats or study_plan['status'] != 'success':
            bot.send_message(chat_id, "⚠️ لم أجد بيانات، جرب تحديث بياناتك أولاً.")
            return

        reply = f"""
📊 *إحصائياتك الحالية:*
✅ الساعات المطلوبة: {stats['total_hours_required']}
🎯 الساعات المجتازة: {stats['total_hours_completed']}
🔄 المحتسبة: {stats['total_hours_transferred']}
📅 عدد الفصول: {stats['semesters_count']}
📈 الإنجاز: {stats['completion_percentage']}%
🏁 حالة الخطة: {"مكتملة ✅" if stats['plan_completed'] else "غير مكتملة ⏳"}
"""
        bot.send_message(chat_id, reply, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(chat_id, f"🚨 حدث خطأ: {e}")

def show_user_courses(chat_id):
    """عرض مقررات المستخدم"""
    user = get_user(chat_id)
    if not user or not user['student_id'] or not user['password']:
        bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
        return

    try:
        loading_msg = bot.send_message(chat_id, "🎓 جاري تحضير مقرراتك...")
        
        scraper = QOUScraper(user['student_id'], user['password'])
        study_plan = scraper.fetch_study_plan()
        
        if study_plan.get('status') != 'success':
            bot.delete_message(chat_id, loading_msg.message_id)
            bot.send_message(chat_id, "⚠️ لم أتمكن من جلب المقررات. حاول لاحقاً.")
            return
        
        courses_list = study_plan['courses']
        categories_data = {}
        
        for course in courses_list:
            category = course.get('category', 'غير مصنف')
            if category not in categories_data:
                categories_data[category] = {
                    'courses': [],
                    'completed': 0,
                    'total': 0,
                    'hours': 0
                }
            
            categories_data[category]['courses'].append(course)
            categories_data[category]['total'] += 1
            categories_data[category]['hours'] += course.get('hours', 0)
            if course.get('status') == 'completed':
                categories_data[category]['completed'] += 1
        
        bot.delete_message(chat_id, loading_msg.message_id)
        
        if not categories_data:
            bot.send_message(chat_id, "📭 لا توجد مقررات مسجلة حالياً.")
            return
        
        main_card = """
🎯 *الخطة الدراسية الشاملة* 
━━━━━━━━━━━━━━━━━━━━

📊 *الإحصاءات العامة:*
• 📚 عدد المقررات في الخطة: {}
• ✅ عدد المقررات المكتملة: {}
• 🕒 مجموع الساعات المكتملة: {}
        
👇 اختر الفئة لعرض المقررات:
        """.format(
            len(courses_list),
            sum(1 for c in courses_list if c.get('status') == 'completed'),
            sum(c.get('hours', 0) for c in courses_list)
        )
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = []
        for category in categories_data.keys():
            short_name = category[:15] + "..." if len(category) > 15 else category
            buttons.append(types.KeyboardButton(f"📁 {short_name}"))
        
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                markup.row(buttons[i], buttons[i+1])
            else:
                markup.row(buttons[i])
        
        markup.row(types.KeyboardButton("🏠 الرئيسية"))
        
        bot.send_message(chat_id, main_card, parse_mode="Markdown", reply_markup=markup)
        
        if chat_id not in user_categories_data:
            user_categories_data[chat_id] = {}
        
        user_categories_data[chat_id] = {
            'categories': categories_data, 
            'action': 'awaiting_category',
            'timestamp': datetime.now().timestamp()
        }
        
    except Exception as e:
        try:
            bot.delete_message(chat_id, loading_msg.message_id)
        except:
            pass
        bot.send_message(chat_id, f"🚨 حدث خطأ: {str(e)}")

def show_completion_percentage(chat_id):
    """عرض نسبة الإنجاز"""
    user = get_user(chat_id)
    if not user or not user['student_id'] or not user['password']:
        bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        stats = scraper.fetch_study_plan().get('stats', {})

        if not stats:
            bot.send_message(chat_id, "⚠️ لم أجد بيانات، جرب 🔄 تحديث بياناتك.")
            return

        percentage = stats['completion_percentage']
        progress_bar = "🟩" * int(percentage / 10) + "⬜" * (10 - int(percentage / 10))
        remaining_hours = stats['total_hours_required'] - stats['total_hours_completed'] - stats['total_hours_transferred']

        reply = f"""
🎯 *نسبة إنجازك الدراسي:*

{progress_bar}
{percentage}% مكتمل

📊 التفاصيل:
• المطلوب: {stats['total_hours_required']} ساعة
• المكتمل: {stats['total_hours_completed']} ساعة
• المحتسب: {stats['total_hours_transferred']} ساعة
• المتبقي: {remaining_hours if remaining_hours > 0 else 0} ساعة
"""
        bot.send_message(chat_id, reply, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(chat_id, f"🚨 حدث خطأ: {e}")

def show_study_plan_summary(chat_id):
    """عرض ملخص الخطة الدراسية"""
    user = get_user(chat_id)
    if not user or not user['student_id'] or not user['password']:
        bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
        return

    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        study_plan = scraper.fetch_study_plan()
        stats = study_plan['stats']
        courses = study_plan['courses']

        if not stats or not courses:
            bot.send_message(chat_id, "⚠️ لم أجد بيانات، جرب 🔄 تحديث بياناتي.")
            return

        categories = {}
        for course in courses:
            cat = course['category']
            categories.setdefault(cat, []).append(course)

        reply = "📋 *الخطة الدراسية الشاملة*\n\n"
        for category, courses_list in categories.items():
            completed = sum(1 for c in courses_list if c['status'] == 'completed')
            total = len(courses_list)
            percentage_cat = (completed / total) * 100 if total else 0
            reply += f"📁 *{category}:*\n   {completed}/{total} مكتمل ({percentage_cat:.1f}%)\n\n"

        reply += f"📊 *الإجمالي: {stats['completion_percentage']}% مكتمل*"
        bot.send_message(chat_id, reply, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(chat_id, f"🚨 حدث خطأ: {e}")

def show_current_courses(chat_id):
    """عرض المقررات الحالية"""
    user = get_user(chat_id)
    if not user or not user['student_id'] or not user['password']:
        bot.send_message(chat_id, "⚠️ لم أجد بياناتك، أرسل 🔄 تحديث بياناتي أولاً.")
        return

    try:
        loading_msg = bot.send_message(chat_id, "🔄 جاري جلب المقررات...")
        
        scraper = QOUScraper(user['student_id'], user['password'])
        study_plan = scraper.fetch_study_plan()
        
        current_courses = [
            c for c in study_plan.get('courses', []) 
            if c.get('status') in ['in_progress', 'registered', 'current']
        ]
        
        bot.delete_message(chat_id, loading_msg.message_id)
        
        if not current_courses:
            bot.send_message(chat_id, "⏳ لا توجد مقررات قيد الدراسة هذا الفصل.")
            return
        
        total_hours = sum(c.get('hours', 0) for c in current_courses)
        
        reply = f"📌 **المقررات الحالية** ({len(current_courses)} مقرر)\n"
        reply += f"🕒 **مجموع الساعات:** {total_hours}\n\n"
        
        for i, course in enumerate(current_courses, 1):
            status_emoji = "📚" if course.get('is_elective', False) else "📖"
            reply += f"{i}. {status_emoji} **{course['course_code']}** - {course['course_name']}\n"
            reply += f"   ⏰ {course.get('hours', 0)} ساعة\n\n"
        
        bot.send_message(chat_id, reply, parse_mode="Markdown")
        
    except Exception as e:
        try:
            bot.delete_message(chat_id, loading_msg.message_id)
        except:
            pass
        bot.send_message(chat_id, f"⚠️ حدث خطأ: {str(e)}")

def update_user_data(chat_id):
    """تحديث بيانات المستخدم"""
    user = get_user(chat_id)
    if not user:
        bot.send_message(chat_id, "⚠️ لم أجد بياناتك، يرجى تسجيل الدخول أولاً.")
        return
    
    bot.send_message(chat_id, "⏳ جاري تحديث بياناتك، الرجاء الانتظار...")
    
    try:
        scraper = QOUScraper(user['student_id'], user['password'])
        success = scraper.update_student_data(chat_id)
        
        if success:
            bot.send_message(chat_id, "✅ تم تحديث بياناتك بنجاح!")
        else:
            bot.send_message(chat_id, "⚠️ فشل التحديث، تحقق من بياناتك وحاول لاحقاً.")
    except Exception as e:
        logger.error(f"Error updating data: {e}")
        bot.send_message(chat_id, f"🚨 خطأ أثناء التحديث: {str(e)}")

def link_portal_account(chat_id):
    """ربط حساب منصة المواد المشتركة"""
    user = get_user(chat_id)
    if not user or not user.get('student_id'):
        bot.send_message(chat_id, "❌ يرجى تسجيل الدخول أولاً باستخدام /login")
        return
    
    bot.send_message(chat_id, "🔄 جاري سحب بياناتك من بوابة الجامعة...")
    
    creds = get_portal_credentials(chat_id)
    if not creds['success']:
        bot.send_message(chat_id, "❌ لم أجد بيانات دخول صالحة.")
        return
    
    try:
        scraper = QOUScraper(creds['username'], creds['password'])
        portal_data = scraper.fetch_student_data_from_portal()
        
        if portal_data["success"]:
            update_success = update_portal_data(chat_id, portal_data['branch'], portal_data['courses'])
            
            if update_success:
                message_text = (
                    f"✅ تم ربط حساب البوابة بنجاح!\n\n"
                    f"🏫 الفرع: {portal_data['branch']}\n"
                    f"📚 عدد المواد المسجلة: {len(portal_data['courses'])}\n\n"
                    f"يمكنك الآن استخدام ميزة \"منصة المواد المشتركة\" للتواصل مع زملائك!"
                )
                bot.send_message(chat_id, message_text)
            else:
                bot.send_message(chat_id, "❌ حدث خطأ في حفظ البيانات في قاعدة البيانات.")
        else:
            bot.send_message(chat_id, f"❌ فشل في سحب البيانات: {portal_data['error']}")
    
    except Exception as e:
        logger.error(f"Error in portal linking: {e}")
        bot.send_message(chat_id, "❌ حدث خطأ غير متوقع أثناء ربط الحساب. حاول مرة أخرى لاحقاً.")

def show_shared_materials(chat_id):
    """عرض منصة المواد المشتركة"""
    portal_data = get_user_branch_and_courses(chat_id)
    
    if not portal_data['branch']:
        bot.send_message(
            chat_id, 
            "❌ لم يتم ربط حساب البوابة بعد.\n\n"
            "يرجى استخدام زر \"🔗 ربط حساب البوابة\" أولاً لسحب بيانات فرعك وموادك من بوابة الجامعة."
        )
        return
    
    if not portal_data['courses']:
        bot.send_message(
            chat_id, 
            "❌ لا توجد مواد مسجلة في الفصل الحالي.\n\n"
            "إما أنك لم تسجل أي مواد هذا الفصل، أو هناك مشكلة في بيانات البوابة."
        )
        return
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    for course in portal_data['courses']:
        if len(course) > 20:
            words = course.split()
            short_name = ' '.join(words[:2]) + "..." if len(words) > 2 else course[:20] + "..."
        else:
            short_name = course
        
        markup.add(types.KeyboardButton(f"📖 {short_name}"))
    
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
    
    message_text = (
        f"🏫 **فرعك: {portal_data['branch']}**\n"
        f"📚 **عدد المواد المسجلة: {len(portal_data['courses'])}**\n\n"
        "اختر المادة التي تريد التواصل مع زملائك فيها:"
    )
    
    bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode="Markdown")

def handle_course_selection(chat_id, text):
    """معالجة اختيار مادة"""
    selected_course = text.replace("📖 ", "").strip()
    user_portal_data = get_user_branch_and_courses(chat_id)
    
    if not user_portal_data['branch'] or not user_portal_data['courses']:
        bot.send_message(chat_id, "❌ بيانات غير كافية. يرجى إعادة ربط حساب البوابة.")
        return
    
    full_course_name = None
    for course in user_portal_data['courses']:
        if selected_course in course or course.startswith(selected_course.replace("...", "")):
            full_course_name = course
            break
    
    if not full_course_name:
        bot.send_message(chat_id, "❌ لم أتعرف على المادة المحددة.")
        return
    
    potential_partners = find_potential_partners(chat_id, full_course_name)
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    if potential_partners:
        partner_count = len(potential_partners)
        message_text = (
            f"📖 **المادة: {full_course_name}**\n"
            f"👥 **عدد الزملاء المتاحين: {partner_count}**\n\n"
            "اختر طريقة التواصل:"
        )
        
        markup.add(types.KeyboardButton(f"🎲 محادثة عشوائية - {selected_course}"))
        markup.add(types.KeyboardButton("👥 عرض قائمة الزملاء"))
        markup.add(types.KeyboardButton("⬅️ عودة للمواد"))
        
    else:
        message_text = (
            f"📖 **المادة: {full_course_name}**\n\n"
            "❌ لا يوجد زملاء متاحين في هذه المادة حالياً.\n"
            "يمكنك المحاولة لاحقاً أو اختيار مادة أخرى."
        )
        markup.add(types.KeyboardButton("⬅️ عودة للمواد"))
    
    markup.add(types.KeyboardButton("🏠 الرئيسية"))
    
    bot.send_message(chat_id, message_text, reply_markup=markup, parse_mode="Markdown")
    
    user_sessions[chat_id] = {
        'current_course': full_course_name,
        'action': 'awaiting_communication_choice'
    }

def return_to_materials(chat_id):
    """العودة لقائمة المواد"""
    portal_courses = get_user_branch_and_courses(chat_id)
    
    if not portal_courses['courses']:
        bot.send_message(chat_id, "❌ لا توجد مواد مسجلة.")
        return
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    for course in portal_courses['courses']:
        if len(course) > 20:
            words = course.split()
            short_name = ' '.join(words[:2]) + "..." if len(words) > 2 else course[:20] + "..."
        else:
            short_name = course
        markup.add(types.KeyboardButton(f"📖 {short_name}"))
    
    markup.add(types.KeyboardButton("⬅️ عودة للرئيسية"))
    
    bot.send_message(chat_id, "📚 اختر مادة:", reply_markup=markup)

def handle_random_chat(chat_id, text):
    """بدء محادثة عشوائية"""
    course_name = text.replace("🎲 محادثة عشوائية - ", "").strip()
    
    if chat_id not in user_sessions:
        user_sessions[chat_id] = {}
    user_sessions[chat_id]['current_course'] = course_name
    
    partners = find_potential_partners(chat_id, course_name)
    
    if not partners:
        bot.send_message(chat_id, f"❌ لا يوجد زملاء متاحين في مادة {course_name} حالياً.")
        return
    
    partner_id = random.choice(partners)
    chat_token = create_anonymous_chat(chat_id, partner_id, course_name)
    
    if not chat_token:
        bot.send_message(chat_id, "❌ فشل في إنشاء المحادثة. حاول مرة أخرى.")
        return
    
    user_sessions[chat_id] = {
        'in_chat': True,
        'chat_token': chat_token,
        'partner_id': partner_id,
        'course_name': course_name
    }
    
    user_sessions[partner_id] = {
        'in_chat': True, 
        'chat_token': chat_token,
        'partner_id': chat_id,
        'course_name': course_name
    }
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✖️ إنهاء المحادثة")
    
    bot.send_message(chat_id,
        f"💬 **بدأت المحادثة المجهولة**\n\n"
        f"📖 المادة: {course_name}\n"
        f"👥 تم الاتصال بزميل دراسة\n\n"
        f"⚡ ابدأ بالحديث الآن!\n",
        parse_mode="Markdown",
        reply_markup=markup
    )
    
    try:
        bot.send_message(partner_id,
            f"💬 **بدعوة محادثة مجهولة**\n\n"
            f"📖 المادة: {course_name}\n"
            f"👤 أحد الزملاء يريد الدراسة معك\n\n"
            f"⚡ ابدأ بالحديث الآن!\n", 
            parse_mode="Markdown",
            reply_markup=markup
        )
    except Exception as e:
        bot.send_message(chat_id, "❌ تعذر الاتصال بالشريك. جرب محادثة أخرى.")
        if chat_id in user_sessions:
            del user_sessions[chat_id]
        if partner_id in user_sessions:
            del user_sessions[partner_id]

def show_partners_list(chat_id):
    """عرض قائمة الزملاء"""
    if chat_id not in user_sessions or 'current_course' not in user_sessions[chat_id]:
        bot.send_message(chat_id, "❌ يرجى اختيار مادة أولاً من القائمة.")
        return
    
    course_name = user_sessions[chat_id]['current_course']
    partners = find_potential_partners(chat_id, course_name)
    
    if not partners:
        bot.send_message(chat_id, f"❌ لا يوجد زملاء متاحين في مادة {course_name} حالياً.")
        return
    
    message = f"👥 **زملاؤك في مادة {course_name}:**\n\n"
    for i, partner_id in enumerate(partners[:5], 1):
        message += f"{i}. 👤 زميل #{partner_id}\n"
    
    if len(partners) > 5:
        message += f"\n... و{len(partners) - 5} زميل آخر"
    
    message += "\n🎲 اختر \"محادثة عشوائية\" للتواصل مع أحدهم!"
    
    bot.send_message(chat_id, message, parse_mode="Markdown")

def handle_other_selections(chat_id, text):
    """معالجة الاختيارات الأخرى"""
    # معالجة اختيارات الخطط الدراسية
    if chat_id in study_plan_states:
        handle_study_plan_selection(chat_id, text)
        return
    
    # معالجة اختيارات الفئات
    if chat_id in user_categories_data and user_categories_data[chat_id].get('action') == 'awaiting_category':
        handle_category_selection(chat_id, text)
        return
    
    bot.send_message(chat_id, "⚠️ لم أفهم الأمر، الرجاء اختيار زر من القائمة.")

def handle_study_plan_selection(chat_id, text):
    """معالجة اختيارات الخطط الدراسية"""
    stage = study_plan_states[chat_id]["stage"]
    
    if stage == "awaiting_college":
        if text in study_plans:
            study_plan_states[chat_id]["college"] = text
            study_plan_states[chat_id]["stage"] = "awaiting_major"
    
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
            for major in study_plans[text].keys():
                markup.add(types.KeyboardButton(major))
            markup.add(types.KeyboardButton("العودة للرئيسية"))
    
            bot.send_message(chat_id, f"🏛️ اختر التخصص ضمن '{text}':", reply_markup=markup)
    
        elif text == "العودة للرئيسية":
            study_plan_states.pop(chat_id, None)
            send_main_menu(chat_id)
        else:
            bot.send_message(chat_id, "⚠️ الرجاء اختيار الكلية من القائمة.")
    
    elif stage == "awaiting_major":
        college = study_plan_states[chat_id]["college"]
        major_item = study_plans[college].get(text)
    
        if major_item:
            if isinstance(major_item, dict):
                markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
                for sublevel in major_item.keys():
                    markup.add(types.KeyboardButton(sublevel))
                markup.add(types.KeyboardButton("العودة للتخصص"))
                study_plan_states[chat_id]["stage"] = "awaiting_sublevel"
                study_plan_states[chat_id]["major"] = text
                study_plan_states[chat_id]["sublevels"] = major_item
                bot.send_message(chat_id, f"🔹 اختر النسخة أو المستوى لـ '{text}':", reply_markup=markup)
            else:
                bot.send_message(chat_id, f"🔗 رابط خطة '{text}' ضمن '{college}':\n{major_item}")
                study_plan_states.pop(chat_id, None)
                send_main_menu(chat_id)
        elif text == "العودة للرئيسية":
            study_plan_states.pop(chat_id, None)
            send_main_menu(chat_id)
        else:
            bot.send_message(chat_id, "⚠️ الرجاء اختيار التخصص من القائمة.")
    
    elif stage == "awaiting_sublevel":
        sublevels = study_plan_states[chat_id]["sublevels"]
        major = study_plan_states[chat_id]["major"]
        college = study_plan_states[chat_id]["college"]
    
        if text in sublevels:
            bot.send_message(chat_id, f"🔗 رابط خطة '{major}' ({text}) ضمن '{college}':\n{sublevels[text]}")
            study_plan_states.pop(chat_id, None)
            send_main_menu(chat_id)
        elif text == "العودة للتخصص":
            study_plan_states[chat_id]["stage"] = "awaiting_major"
            markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
            for major_name in study_plans[college].keys():
                markup.add(types.KeyboardButton(major_name))
            markup.add(types.KeyboardButton("العودة للرئيسية"))
            bot.send_message(chat_id, f"🏛️ اختر التخصص ضمن '{college}':", reply_markup=markup)
        else:
            bot.send_message(chat_id, "⚠️ الرجاء اختيار النسخة من القائمة.")

def handle_category_selection(chat_id, text):
    """معالجة اختيار الفئة"""
    selected_text = text.strip()
    
    if selected_text == "🏠 الرئيسية":
        del user_categories_data[chat_id]
        show_main_menu(chat_id)
        return
    
    selected_category = selected_text.replace("📁 ", "").strip()
    categories = user_categories_data[chat_id]['categories']
    
    matched_category = None
    for category in categories.keys():
        clean_selected = selected_category.replace("...", "").strip()
        clean_category = category.replace("...", "").strip()
        
        if (clean_selected in clean_category or 
            clean_category in clean_selected or 
            clean_selected.startswith(clean_category[:5]) or
            clean_category.startswith(clean_selected[:5])):
            matched_category = category
            break
    
    if matched_category:
        category_data = categories[matched_category]
        
        completion_percent = 0
        if category_data['total'] > 0:
            completion_percent = (category_data['completed'] / category_data['total']) * 100
        
        category_card = f"""
📋 *{matched_category}*
━━━━━━━━━━━━━━━━━━━━
📊 *إحصاءات الفئة:*
• 📚 عدد المقررات: {category_data['total']}
• ✅ مكتمل: {category_data['completed']}
• 📈 نسبة الإنجاز: {completion_percent:.1f}%
• 🕒 مجموع الساعات: {category_data['hours']}

🎓 *المقررات:*
        """
        
        bot.send_message(chat_id, category_card, parse_mode="Markdown")
        
        courses_text = ""
        for i, course in enumerate(category_data['courses']):
            status_emoji = {
                'completed': '✅',
                'failed': '❌', 
                'in_progress': '⏳',
                'exempted': '⚡',
                'registered': '📝',
                'not_taken': '🔘'
            }.get(course.get('status', 'unknown'), '❔')
            
            course_type = "اختياري" if course.get('is_elective', False) else "إجباري"
            grade = course.get('grade', '')
            grade_display = f" | 🎯 {grade}" if grade else ""
            
            course_line = f"{status_emoji} {course.get('course_code', '')} - {course.get('course_name', '')} ({course.get('hours', 0)} س){grade_display}\n"
            
            if len(courses_text + course_line) > 3500:
                bot.send_message(chat_id, courses_text, parse_mode="Markdown")
                courses_text = course_line
            else:
                courses_text += course_line
        
        if courses_text:
            bot.send_message(chat_id, courses_text, parse_mode="Markdown")
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        buttons = []
        for category in categories.keys():
            short_name = category[:15] + "..." if len(category) > 15 else category
            buttons.append(types.KeyboardButton(f"📁 {short_name}"))
        
        for i in range(0, len(buttons), 2):
            if i + 1 < len(buttons):
                markup.row(buttons[i], buttons[i+1])
            else:
                markup.row(buttons[i])
        
        markup.row(types.KeyboardButton("🏠 الرئيسية"))
        
        bot.send_message(chat_id, "👇 اختر فئة أخرى أو العودة للرئيسية:", reply_markup=markup)
        
    else:
        bot.send_message(chat_id, "⚠️ لم أتعرف على الفئة المحددة. اختر من القائمة:")
