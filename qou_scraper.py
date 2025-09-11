import requests
from bs4 import BeautifulSoup
import logging
import time
import random
from urllib.parse import urljoin
import cloudscraper
from typing import Optional, List, Dict, Any

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
BALANCE_URL = 'https://portal.qou.edu/student/getSasStudFtermCardList.do'

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
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'android', 'mobile': True, 'desktop': False},
            delay=10, interpreter='nodejs'
        )
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
        return random.choice(USER_AGENTS)

    def _simulate_human_delay(self):
        time.sleep(random.uniform(1, 3))

    def login(self) -> bool:
        try:
            self.session = self._create_session()
            self.is_logged_in = False
            self._simulate_human_delay()

            headers = {
                "User-Agent": self._get_random_user_agent(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://portal.qou.edu",
                "Referer": "https://portal.qou.edu/login.do",
                "Upgrade-Insecure-Requests": "1"
            }

            payload = {
                "uip": "172.68.234.77",
                "defaultUserSettingMode": "light",
                "userId": self.student_id,
                "password": self.password,
                "logBtn": "Login"
            }

            login_resp = self.session.post(LOGIN_URL, data=payload, headers=headers, timeout=30, allow_redirects=True)

            if self._check_login_success(login_resp.text):
                logger.info(f"✅ تسجيل الدخول ناجح لـ {self.student_id}")
                self.is_logged_in = True
                return True
            else:
                logger.warning(f"❌ فشل تسجيل الدخول لـ {self.student_id}")
                return False
        except Exception as e:
            logger.error(f"خطأ في التسجيل لـ {self.student_id}: {str(e)}")
            return False

    def _check_login_success(self, html_content: str) -> bool:
        success_indicators = ["studentPortal", "portalHome", "student/home", "مرحبا", "تسجيل الخروج", "الرصيد", "inbox"]
        error_indicators = ["الرجاء التأكد من اسم المستخدم و كلمة المرور", "خطأ", "غير مصرح", "failed", "invalid"]

        content_lower = html_content.lower()
        for error in error_indicators:
            if error.lower() in content_lower:
                return False
        for success in success_indicators:
            if success.lower() in content_lower:
                return True
        return False

    def ensure_login(self):
        if not self.is_logged_in:
            return self.login()
        return True

    def fetch_student_info(self) -> Optional[Dict[str, str]]:
        if not self.ensure_login():
            return None
        try:
            self._simulate_human_delay()
            resp = self.session.get(BASE_URL, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            name_element = (soup.find('span', class_='student-name') or 
                            soup.find('div', class_='user-info') or
                            soup.find('span', string=lambda text: text and 'مرحبا' in text))
            if name_element:
                return {"name": name_element.get_text(strip=True)}
            return None
        except Exception as e:
            logger.error(f"Error fetching student info: {str(e)}")
            return None

    def fetch_latest_message(self) -> Optional[Dict[str, Any]]:
        if not self.ensure_login():
            return None
        try:
            self._simulate_human_delay()
            resp = self.session.get(INBOX_URL, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find('table')
            if not table:
                return None
            rows = table.find_all('tr')
            if len(rows) < 2:
                return None
            first_row = rows[1]
            cols = first_row.find_all('td')
            if len(cols) < 5:
                return None
            link_tag = cols[3].find('a') if len(cols) > 3 else None
            if not link_tag or not link_tag.get('href'):
                return None
            msg_id = link_tag['href'].split('msgId=')[-1] if 'msgId=' in link_tag['href'] else 'unknown'
            full_link = urljoin(INBOX_URL, link_tag['href'])
            subject = link_tag.get_text(strip=True)
            sender = cols[6].get_text(strip=True) if len(cols) > 6 else ''
            date = cols[4].get_text(strip=True) if len(cols) > 4 else ''
            msg_resp = self.session.get(full_link, timeout=30)
            msg_resp.raise_for_status()
            soup_msg = BeautifulSoup(msg_resp.text, 'html.parser')
            body = soup_msg.find('div') or soup_msg.find('body')
            body_text = body.get_text(strip=True) if body else ''
            return {'msg_id': msg_id, 'subject': subject, 'sender': sender, 'date': date, 'body': body_text}
        except Exception as e:
            logger.error(f"Error fetching message: {str(e)}")
            return None

    def fetch_term_summary_courses(self) -> List[Dict[str, Any]]:
        if not self.ensure_login():
            return []
        try:
            self._simulate_human_delay()
            resp = self.session.get(TERM_SUMMARY_URL, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            courses = []
            table = soup.find('table')
            if not table:
                return courses
            rows = table.find_all('tr')[1:]
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
            logger.error(f"Error fetching courses: {str(e)}")
            return []

    def fetch_balance_totals(self) -> Dict[str, Any]:
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
                "formatted_text": f"📌 الإجمالي الكلي للرصيد:\n💰 المطلوب: {total_required:,.2f}\n✅ المدفوع: {total_paid:,.2f}\n🎓 المنح: {total_grants:,.2f}\n📊 رصيد الفصل: {total_balance:,.2f}"
            }
        except Exception as e:
            logger.error(f"Error fetching balance: {str(e)}")
            return {"error": "❌ خطأ في جلب بيانات الرصيد"}
