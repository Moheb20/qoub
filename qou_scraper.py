import requests
from bs4 import BeautifulSoup
from typing import Optional, List
import re

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
        for item in course_titles:
            full_text = item.get_text(strip=True)
            match = re.match(r"\d+/(\d+)\s+(.*)", full_text)
            if match:
                code = match.group(1)
                title = match.group(2)
                courses.append({'code': code, 'title': title})

        return courses

    def fetch_course_marks(self, crsNo: str, crsSeq: str = '0') -> dict:
        marks_url = f"https://portal.qou.edu/student/loadCourseServices?tabId=tab1&dataType=marks&crsNo={crsNo}&crsSeq={crsSeq}"
        resp = self.session.post(marks_url, data={})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        def get_label_value(label_text):
            label = soup.find('label', string=re.compile(label_text))
            if label:
                parent_div = label.find_parent('div')
                if parent_div:
                    return parent_div.get_text(strip=True).replace(label_text, '').strip()
            return "غير متوفر"

        def get_instructor_name():
            label = soup.find('label', string=re.compile("عضو هيئة التدريس"))
            if label:
                parent = label.find_parent('div')
                if parent:
                    return parent.get_text(strip=True).replace("عضو هيئة التدريس:", '').strip()
            return "غير متوفر"

        marks_data = {
            'assignment1': get_label_value('التعيين الأول'),
            'midterm': get_label_value('نصفي نظري'),
            'midterm_date': get_label_value('تاريخ وضع الامتحان النصفي'),
            'assignment2': get_label_value('التعيين الثاني'),
            'final_mark': get_label_value('العلامة النهائية'),
            'final_date': get_label_value('تاريخ وضع العلامة النهائية'),
            'status': get_label_value('الحالة'),
            'instructor': get_instructor_name(),
            'lecture_day': get_label_value('اليوم:'),
            'lecture_time': get_label_value('الموعد:')
        }

        return marks_data


    def fetch_courses_with_marks(self) -> List[dict]:
        courses = self.fetch_courses()
        for course in courses:
            course['marks'] = self.fetch_course_marks(course['code'], crsSeq='0')
        return courses
