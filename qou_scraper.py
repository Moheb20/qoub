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
PORTAL_URL = 'https://portal.qou.edu/portalLogin.do?reLogin=y'
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

# تهيئة الخطوط للـ PDF
try:
    font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'arial.ttf')
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('Arial', font_path))
    else:
        logger.warning("Font file not found, PDF generation may not work properly")
except Exception as e:
    logger.error(f"Error loading font: {e}")

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

    def _extract_hidden_fields(self, soup):
        """استخراج الحقول المخفية من النموذج"""
        hidden_fields = {}
        for input_tag in soup.find_all('input', type='hidden'):
            name = input_tag.get('name')
            value = input_tag.get('value', '')
            if name:
                hidden_fields[name] = value
        return hidden_fields

    def login(self) -> bool:
        """تسجيل الدخول مع تحسينات لتجاوز الحماية"""
        try:
            self._simulate_human_delay()
            
            # 1. تغيير User-Agent
            self.session.headers.update({
                "User-Agent": self._get_random_user_agent()
            })
            
            # 2. زيارة الصفحة الرئيسية أولاً للحصول على الكوكيز
            logger.info(f"Visiting main page for {self.student_id}")
            main_resp = self.session.get(BASE_URL, timeout=30)
            main_resp.raise_for_status()
            
            # 3. زيارة صفحة Login
            logger.info(f"Visiting login page for {self.student_id}")
            login_page_resp = self.session.get(LOGIN_URL, timeout=30)
            login_page_resp.raise_for_status()
            
            soup = BeautifulSoup(login_page_resp.text, 'html.parser')
            
            # 4. استخراج الحقول المخفية
            payload = self._extract_hidden_fields(soup)
            
            # 5. إضافة بيانات المستخدم (بناءً على تحليل البايلود)
            payload.update({
                "uip": payload.get("uip", "162.158.23.52"),
                "defaultUserSettingMode": payload.get("defaultUserSettingMode", "light"),
                "userId": self.student_id,
                "password": self.password,
                "logBtn": "دخول"
            })
            
            # 6. إعداد headers للطلب POST
            headers = {
                "User-Agent": self._get_random_user_agent(),
                "Referer": LOGIN_URL,
                "Origin": BASE_URL,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ar,en-US;q=0.7,en;q=0.3",
            }
            
            # 7. إرسال طلب Login
            logger.info(f"Posting login for {self.student_id}")
            login_resp = self.session.post(
                LOGIN_URL,
                data=payload,
                headers=headers,
                timeout=30,
                allow_redirects=True
            )
            login_resp.raise_for_status()
            
            # 8. التحقق من نجاح Login
            if self._check_login_success(login_resp.text):
                logger.info(f"Login successful for {self.student_id}")
                self.is_logged_in = True
                return True
            else:
                logger.warning(f"Login failed for {self.student_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error during login for {self.student_id}: {str(e)}")
            return False

    def _check_login_success(self, html_content: str) -> bool:
        """التحقق من نجاح تسجيل الدخول من محتوى HTML"""
        success_indicators = [
            "studentPortal",
            "مرحبا",
            "طالب",
            "الرئيسية",
            "logout",
            "تسجيل الخروج"
        ]
        
        # التحقق من وجود أي من المؤشرات
        content_lower = html_content.lower()
        for indicator in success_indicators:
            if indicator.lower() in content_lower:
                return True
        
        # التحقق من عدم وجود رسالة خطأ
        error_indicators = [
            "الرجاء التأكد من اسم المستخدم و كلمة المرور",
            "خطأ في التسجيل",
            "invalid",
            "error"
        ]
        
        for error in error_indicators:
            if error.lower() in content_lower:
                return False
        
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
            
            # مثال: البحث عن اسم الطالب
            name_element = soup.find('span', class_='student-name') or soup.find('div', class_='user-info')
            if name_element:
                student_info['name'] = name_element.get_text(strip=True)
            
            # إضافة المزيد من الحقول حسب هيكل الموقع
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
            row = soup.select_one("tbody tr")
            
            if not row:
                return None

            link_tag = row.select_one("td[col_4] a[href*='msgId=']")
            if not link_tag:
                return None

            msg_id = link_tag['href'].split('msgId=')[-1]
            full_link = urljoin(INBOX_URL, link_tag['href'])
            
            subject = link_tag.get_text(strip=True)
            sender = row.select_one("td[col_7]")
            sender_text = sender.get_text(strip=True) if sender else ''
            
            date = row.select_one("td[col_5]")
            date_text = date.get_text(strip=True) if date else ''

            # جلب محتوى الرسالة
            msg_resp = self.session.get(full_link, timeout=30)
            msg_resp.raise_for_status()
            soup_msg = BeautifulSoup(msg_resp.text, 'html.parser')

            body = soup_msg.find('div', class_='message-body')
            body_text = body.get_text(strip=True) if body else ''

            return {
                'msg_id': msg_id,
                'subject': subject,
                'sender': sender_text,
                'date': date_text,
                'body': body_text
            }
            
        except Exception as e:
            logger.error(f"Error fetching message for {self.student_id}: {str(e)}")
            return None

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
            table = soup.find('table', id='dataTable')
            
            if not table:
                return courses

            rows = table.find('tbody').find_all('tr')
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

    def fetch_lectures_schedule(self) -> List[Dict[str, Any]]:
        """جلب جدول المحاضرات"""
        if not self.ensure_login():
            return []
            
        try:
            self._simulate_human_delay()
            resp = self.session.get(WEEKLY_MEETINGS_URL, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            meetings = []
            table = soup.find('table', class_='table table-hover table-condensed table-striped table-curved')
            
            if not table:
                return meetings

            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 12:
                    continue

                meeting = {
                    'course_code': cols[0].get_text(strip=True),
                    'course_name': cols[1].get_text(strip=True),
                    'credit_hours': cols[2].get_text(strip=True),
                    'section': cols[3].get_text(strip=True),
                    'day': cols[4].get_text(strip=True),
                    'time': cols[5].get_text(strip=True),
                    'building': cols[6].get_text(strip=True),
                    'room': cols[7].get_text(strip=True),
                    'lecturer': cols[8].get_text(strip=True),
                    'office_hours': cols[9].get_text(strip=True),
                    'course_content_link': cols[10].find('a')['href'] if cols[10].find('a') else '',
                    'study_plan_link': cols[11].find('a')['href'] if cols[11].find('a') else ''
                }
                meetings.append(meeting)

            return meetings
            
        except Exception as e:
            logger.error(f"Error fetching lectures for {self.student_id}: {str(e)}")
            return []

    def fetch_grades(self) -> List[Dict[str, Any]]:
        """جلب الدرجات"""
        if not self.ensure_login():
            return []
            
        try:
            self._simulate_human_delay()
            resp = self.session.get(GRADES_URL, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            grades = []
            
            # البحث عن جدول الدرجات (يحتاج إلى تعديل حسب الهيكل الفعلي)
            table = soup.find('table', {'class': 'grades-table'}) or soup.find('table', id='dataTable')
            
            if table:
                rows = table.find_all('tr')[1:]  # تخطي رأس الجدول
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        grade = {
                            'course': cols[0].get_text(strip=True),
                            'grade': cols[1].get_text(strip=True),
                            'points': cols[2].get_text(strip=True),
                            'status': cols[3].get_text(strip=True)
                        }
                        grades.append(grade)
            
            return grades
            
        except Exception as e:
            logger.error(f"Error fetching grades for {self.student_id}: {str(e)}")
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

            text = "📌 الإجمالي الكلي للرصيد:\n\n"
            text += f"💰 المطلوب: {total_required:,.2f}\n"
            text += f"✅ المدفوع: {total_paid:,.2f}\n"
            text += f"🎓 المنح: {total_grants:,.2f}\n"
            text += f"📊 رصيد الفصل: {total_balance:,.2f}\n"

            return text
            
        except Exception as e:
            logger.error(f"Error fetching balance for {self.student_id}: {str(e)}")
            return "❌ خطأ في جلب بيانات الرصيد"

