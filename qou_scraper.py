import requests
from bs4 import BeautifulSoup
from typing import Optional, List
import re
import json

LOGIN_URL = 'https://portal.qou.edu/login.do'
INBOX_URL = 'https://portal.qou.edu/student/inbox.do'
COURSES_URL = 'https://portal.qou.edu/student/courseServices.do'


class QOUScraper:
    def __init__(self, student_id: str, password: str):
        self.session = requests.Session()
        self.student_id = student_id
        self.password = password

    def login(self) -> bool:
        self.session.get(LOGIN_URL)
        params = {
            'userId': self.student_id,
            'password': self.password,
            'logBtn': 'Login'
        }
        resp = self.session.post(LOGIN_URL, data=params, allow_redirects=True)
        return 'student' in resp.url

    def fetch_latest_message(self) -> Optional[dict]:
        resp = self.session.get(INBOX_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        row = soup.select_one("tbody tr")
        if not row:
            print("[❌] لا يوجد صفوف رسائل.")
            return None

        link_tag = row.select_one("td[col_4] a[href*='msgId=']")
        if not link_tag:
            print("[❌] لم يتم العثور على الرابط داخل الموضوع.")
            return None

        msg_id = link_tag['href'].split('msgId=')[-1]
        full_link = requests.compat.urljoin(INBOX_URL, link_tag['href'])
        subject = link_tag.get_text(strip=True)

        sender = row.select_one("td[col_7]")
        sender_text = sender.get_text(strip=True) if sender else ''

        date = row.select_one("td[col_5]")
        date_text = date.get_text(strip=True) if date else ''

        resp_msg = self.session.get(full_link)
        resp_msg.raise_for_status()
        soup_msg = BeautifulSoup(resp_msg.text, 'html.parser')
        body = soup_msg.find('div', class_='message-body')
        body_text = body.get_text(strip=True) if body else ''

        return {
            'msg_id': msg_id,
            'subject': subject,
            'sender': sender_text,
            'date': date_text,
            'body': body_text
        }

    def fetch_courses(self) -> List[dict]:
        resp = self.session.get(COURSES_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        courses = []
        course_titles = soup.select("div.pull-right.text-warning")
        for idx, item in enumerate(course_titles):
            full_text = item.get_text(strip=True)
            match = re.match(r"\d+/(\d+)\s+(.*)", full_text)
            if match:
                code = match.group(1)
                title = match.group(2)
                tab_id = f"tab{idx+1}"  # tab1, tab2, ...
                crsSeq = '0'  # عادة 0 حسب طلبك
                courses.append({'code': code, 'title': title, 'tab_id': tab_id, 'crsSeq': crsSeq})

        return courses

    def fetch_course_marks(self, crsNo: str, tab_id: str, crsSeq: str = '0') -> dict:
        base_url = "https://portal.qou.edu/student/loadCourseServices"

        def fetch_tab_raw(tab: str) -> str:
            url = f"{base_url}?tabId={tab_id}&dataType={tab}&crsNo={crsNo}&crsSeq={crsSeq}"
            resp = self.session.post(url)
            resp.raise_for_status()
            print(f"--- المحتوى الخام للتاب {tab} للكورس {crsNo} ---")
            print(resp.text)  # اطبع المحتوى الكامل
            return resp.text

        # جلب البيانات الخام
        marks_raw = fetch_tab_raw("marks")
        schedule_raw = fetch_tab_raw("tSchedule")

        # محاولة تحويل النص إلى JSON
        try:
            marks_data_json = json.loads(marks_raw)
        except Exception:
            marks_data_json = None

        try:
            schedule_data_json = json.loads(schedule_raw)
        except Exception:
            schedule_data_json = None

        # استخراج المعلم من جدول المواعيد (لو JSON)
        def get_instructor_from_json(data) -> str:
            if isinstance(data, dict) and 'createMessage' in str(data):
                # ممكن تحتاج تعديل حسب شكل JSON الحقيقي
                for item in data.get('items', []):
                    if 'createMessage' in item.get('href', ''):
                        return item.get('text', '-')
            return "-"

        # دالة استخراج العلامات من JSON أو النص الخام
        def extract_marks(data) -> dict:
            default = {
                'assignment1': "-",
                'midterm': "-",
                'midterm_date': "-",
                'assignment2': "-",
                'final_mark': "-",
                'final_date': "-",
                'status': "-"
            }
            if not data:
                return default

            # لو JSON dict:
            if isinstance(data, dict):
                # هنا تحتاج تعديل حسب شكل JSON
                # مؤقتاً نرجع الافتراض
                return default

            # لو نص HTML (غير JSON) – تحتاج معالجته بالـ BeautifulSoup أو Regex
            # اتركها هنا للآن كما هي
            return default

        marks = extract_marks(marks_data_json)
        instructor = get_instructor_from_json(schedule_data_json) if schedule_data_json else "-"
        
        # استخراج قيم أخرى من جدول المواعيد: ضع قيم "-" مؤقتًا
        # لأنك محتاج تعرف شكل البيانات الحقيقية لتعالجها
        lecture_day = "-"
        lecture_time = "-"
        building = "-"
        hall = "-"

        return {
            **marks,
            'instructor': instructor,
            'lecture_day': lecture_day,
            'lecture_time': lecture_time,
            'building': building,
            'hall': hall,
        }

    def fetch_courses_with_marks(self) -> List[dict]:
        courses = self.fetch_courses()
        for course in courses:
            course['marks'] = self.fetch_course_marks(course['code'], course['tab_id'], course['crsSeq'])
        return courses
