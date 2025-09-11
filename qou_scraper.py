import requests
from bs4 import BeautifulSoup
import os
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import arabic_reshaper
from bidi.algorithm import get_display
from io import BytesIO
import cloudscraper
import time
import random
from urllib.parse import urljoin
import re

# إعدادات logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("qou_bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('qou_scraper')

# URLs
BASE_URL = 'https://portal.qou.edu'
LOGIN_URL = 'https://portal.qou.edu/login.do'
INBOX_URL = 'https://portal.qou.edu/student/inbox.do'
TERM_SUMMARY_URL = 'https://portal.qou.edu/student/showTermSummary.do'
WEEKLY_MEETINGS_URL = 'https://portal.qou.edu/student/showTermSchedule.do'
BALANCE_URL = 'https://portal.qou.edu/student/getSasStudFtermCardList.do'
EXAMS_SCHEDULE_URL = 'https://portal.qou.edu/student/examsScheduleView.do'
GRADES_URL = 'https://portal.qou.edu/student/showTermSummary.do'

# User Agents rotating
USER_AGENTS = [
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36 Edg/140.0.0.0",
    "Mozilla/5.0 (Linux; Android 12; SM-S906N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
]

class QOUScraper:
    def __init__(self, student_id: str, password: str):
        self.student_id = student_id
        self.password = password
        self.session = self._create_session()
        self.is_logged_in = False
        logger.info(f"Initialized scraper for student: {student_id}")

    def _create_session(self):
        """إنشاء session مع إعدادات متقدمة لتجاوز الحماية"""
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'android',
                'mobile': True,
                'desktop': False,
            },
            delay=10,
            interpreter='nodejs',
        )
        
        # إعدادات session إضافية
        scraper.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ar,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
        })
        
        return scraper

    def _get_random_user_agent(self):
        """الحصول على user agent عشوائي"""
        return random.choice(USER_AGENTS)

    def _simulate_human_delay(self):
        """محاكاة التأخير البشري"""
        time.sleep(random.uniform(1, 3))

    def login(self) -> bool:
        """تسجيل الدخول مبسط - إرسال البيانات الأساسية فقط"""
        try:
            # تنظيف الجلسة أولاً
            self.session = self._create_session()
            self.is_logged_in = False
            
            time.sleep(random.uniform(2, 4))
            
            # 1. إعداد headers كاملة كما في الطلب الأصلي
            headers = {
                "User-Agent": self._get_random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "ar,en;q=0.9,en-GB;q=0.8,en-US;q=0.7",
                "Cache-Control": "max-age=0",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://portal.qou.edu",
                "Referer": "https://portal.qou.edu/login.do",
                "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Microsoft Edge";v="140"',
                "Sec-Ch-Ua-Mobile": "?1",
                "Sec-Ch-Ua-Platform": '"Android"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "Priority": "u=0, i"
            }
            
            # 2. إعداد payload مباشرة بدون الحاجة لجلب الصفحة أولاً
            payload = {
                "uip": "172.68.234.77",  # قيمة ثابتة من النموذج
                "defaultUserSettingMode": "light",  # قيمة ثابتة
                "userId": self.student_id,
                "password": self.password,
                "logBtn": "دخول"
            }
            
            # 3. إضافة cookies أساسية إذا لزم الأمر
            self.session.cookies.update({
                "_ga": "GA1.1.1230287084.1753970669",
                "_gid": "GA1.2.1283861126.1757582758",
            })
            
            # 4. إرسال طلب Login مباشرة
            logger.info(f"إرسال بيانات التسجيل لـ {self.student_id}")
            login_resp = self.session.post(
                LOGIN_URL,
                data=payload,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )
            
            # 5. التحقق من النجاح
            if self._check_login_success(login_resp.text):
                logger.info(f"✅ تسجيل الدخول ناجح لـ {self.student_id}")
                self.is_logged_in = True
                return True
            else:
                logger.warning(f"❌ فشل تسجيل الدخول لـ {self.student_id}")
                # تحليل سبب الفشل
                if "الرجاء التأكد من اسم المستخدم و كلمة المرور" in login_resp.text:
                    logger.error("سبب الفشل: بيانات دخول غير صحيحة")
                elif "error" in login_resp.text.lower():
                    logger.error("سبب الفشل: خطأ في الخادم")
                return False
                
        except Exception as e:
            logger.error(f"خطأ في التسجيل لـ {self.student_id}: {str(e)}")
            return False

    def _check_login_success(self, html_content: str) -> bool:
        """تحقق دقيق من نجاح تسجيل الدخول"""
        # مؤشرات النجاح
        success_indicators = [
            "studentPortal", "portalHome", "student/home",
            "مرحبا", "أهلاً", "طالب", "الرئيسية", 
            "تسجيل الخروج", "logout", "log out",
            "الجدول الدراسي", "الدرجات", "الرصيد", "inbox"
        ]
        
        # مؤشرات الفشل
        error_indicators = [
            "الرجاء التأكد من اسم المستخدم و كلمة المرور",
            "خطأ في التسجيل", "كلمة مرور خاطئة",
            "اسم مستخدم غير صحيح", "invalid", "error",
            "فشل", "failed", "غير مصرح"
        ]
        
        content_lower = html_content.lower()
        
        # التحقق من وجود مؤشرات الخطأ أولاً
        for error in error_indicators:
            if error.lower() in content_lower:
                logger.warning(f"تم اكتشاف خطأ في التسجيل: {error}")
                return False
        
        # التحقق من مؤشرات النجاح
        for success in success_indicators:
            if success.lower() in content_lower:
                return True
        
        # التحقق من وجود عناصر واجهة المستخدم للطالب
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # التحقق من وجود قوائم الطالب
        student_menus = soup.find_all(['a', 'div'], string=lambda text: text and any(
            x in (text.lower() if text else '') for x in ['الجدول', 'الدرجات', 'الرصيد', 'الرسائل', 'inbox', 'grades']
        ))
        
        if student_menus:
            return True
        
        # التحقق من الروابط الداخلية للطالب
        student_links = soup.find_all('a', href=lambda href: href and any(
            x in (href.lower() if href else '') for x in ['/student/', 'inbox', 'grades', 'schedule']
        ))
        
        if student_links:
            return True
        
        return False

    def ensure_login(self):
        """التأكد من أن المستخدم مسجل الدخول"""
        if not self.is_logged_in:
            success = self.login()
            if not success:
                logger.error(f"Failed to login for student: {self.student_id}")
            return success
        return True

    def fetch_student_info(self) -> Optional[Dict[str, str]]:
        """جلب معلومات الطالب الأساسية"""
        if not self.ensure_login():
            return None
            
        try:
            self._simulate_human_delay()
            resp = self.session.get(BASE_URL, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # البحث عن معلومات الطالب في الصفحة
            student_info = {}
            
            # البحث عن اسم الطالب
            name_element = (soup.find('span', class_='student-name') or 
                          soup.find('div', class_='user-info') or
                          soup.find('span', string=lambda text: text and 'مرحبا' in text))
            
            if name_element:
                student_info['name'] = name_element.get_text(strip=True)
            
            return student_info if student_info else None
            
        except Exception as e:
            logger.error(f"Error fetching student info for {self.student_id}: {str(e)}")
            return None

    def fetch_latest_message(self) -> Optional[Dict[str, Any]]:
        """جلب آخر رسالة"""
        if not self.ensure_login():
            return None
            
        try:
            self._simulate_human_delay()
            resp = self.session.get(INBOX_URL, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # البحث عن الجدول بطرق مختلفة
            table = (soup.find('table', id='dataTable') or 
                   soup.find('table', class_='table') or
                   soup.find('table'))
            
            if not table:
                return None

            rows = table.find_all('tr')
            if len(rows) < 2:  # رأس الجدول + صف واحد على الأقل
                return None

            # أخذ أول صف بعد الرأس
            first_row = rows[1]
            cols = first_row.find_all('td')
            
            if len(cols) < 5:
                return None

            # استخراج البيانات
            link_tag = cols[3].find('a') if len(cols) > 3 else None
            if not link_tag or not link_tag.get('href'):
                return None

            msg_id = link_tag['href'].split('msgId=')[-1] if 'msgId=' in link_tag['href'] else 'unknown'
            full_link = urljoin(INBOX_URL, link_tag['href'])
            
            subject = link_tag.get_text(strip=True)
            sender = cols[6].get_text(strip=True) if len(cols) > 6 else ''
            date = cols[4].get_text(strip=True) if len(cols) > 4 else ''

            # جلب محتوى الرسالة
            msg_resp = self.session.get(full_link, timeout=30)
            msg_resp.raise_for_status()
            soup_msg = BeautifulSoup(msg_resp.text, 'html.parser')

            body = (soup_msg.find('div', class_='message-body') or 
                   soup_msg.find('div', id='messageContent') or
                   soup_msg.find('body'))
            body_text = body.get_text(strip=True) if body else ''

            return {
                'msg_id': msg_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body_text
            }
            
        except Exception as e:
            logger.error(f"Error fetching message for {self.student_id}: {str(e)}")
            return None

    def validate_credentials(self) -> Dict[str, Any]:
        """التحقق من صحة بيانات الاعتماد"""
        result = {
            "valid": False,
            "message": "❌ فشل تسجيل الدخول. تأكد من صحة البيانات.",
            "details": {}
        }
        
        # التحقق من تنسيق رقم الطالب
        if not self.student_id.isdigit() or len(self.student_id) != 13:
            result["message"] = "❌ رقم الطالب غير صحيح (يجب أن يكون 13 رقمًا)"
            return result
        
        # التحقق من كلمة المرور
        if not self.password or len(self.password) < 6:
            result["message"] = "❌ كلمة المرور غير صحيحة"
            return result
        
        # محاولة التسجيل
        if self.login():
            result["valid"] = True
            result["message"] = "✅ تسجيل الدخول ناجح"
            # جلب بعض المعلومات للتأكد
            student_info = self.fetch_student_info()
            if student_info:
                result["details"] = student_info
        else:
            result["message"] = "❌ فشل تسجيل الدخول. تأكد من صحة البيانات."
        
        return result

    def fetch_term_summary_courses(self) -> List[Dict[str, Any]]:
        """جلب مواد الفصل"""
        if not self.ensure_login():
            return []
            
        try:
            self._simulate_human_delay()
            resp = self.session.get(TERM_SUMMARY_URL, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            courses = []
            
            # البحث عن الجدول بطرق مختلفة
            table = (soup.find('table', id='dataTable') or 
                   soup.find('table', class_='table') or
                   soup.find('table'))
            
            if not table:
                return courses

            rows = table.find_all('tr')[1:]  # تخطي رأس الجدول
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 7:
                    continue

                course = {
                    'course_code': cols[0].get_text(strip=True),
                    'course_name': cols[1].get_text(strip=True),
                    'credit_hours': cols[2].get_text(strip=True),
                    'status': cols[3].get_text(strip=True),
                    'midterm_mark': cols[4].get_text(strip=True) or "-",
                    'final_mark': cols[5].get_text(strip=True) or "-",
                    'final_mark_date': cols[6].get_text(strip=True) or "-"
                }
                courses.append(course)
                
            return courses
            
        except Exception as e:
            logger.error(f"Error fetching courses for {self.student_id}: {str(e)}")
            return []

def fetch_balance_totals(self) -> Dict[str, Any]:
    """جلب إجمالي الرصيد"""
    if not self.ensure_login():
        return {"error": "لم يتم تسجيل الدخول"}
        
    try:
        self._simulate_human_delay()
        resp = self.session.get(BALANCE_URL, timeout=30)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        rows = soup.select("table#dataTable tbody tr")
        
        if not rows:
            return {"error": "لم يتم العثور على بيانات الرصيد"}

        total_required = total_paid = total_grants = total_balance = 0.0

        for row in rows:
            cols = [c.get_text(strip=True).replace(',', '') for c in row.find_all("td")]
            if len(cols) < 7:
                continue
            try:
                total_required += float(cols[1])
                total_paid     += float(cols[2])
                total_grants   += float(cols[4])
                total_balance  += float(cols[5])
            except ValueError:
                continue

        return {
            "total_required": total_required,
            "total_paid": total_paid,
            "total_grants": total_grants,
            "total_balance": total_balance,
            "formatted_text": f"📌 الإجمالي الكلي للرصيد:\n\n💰 المطلوب: {total_required:,.2f}\n✅ المدفوع: {total_paid:,.2f}\n🎓 المنح: {total_grants:,.2f}\n📊 رصيد الفصل: {total_balance:,.2f}"
        }
        
    except Exception as e:
        logger.error(f"Error fetching balance for {self.student_id}: {str(e)}")
        return {"error": "❌ خطأ في جلب بيانات الرصيد"}
            
    
