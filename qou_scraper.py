import requests
from bs4 import BeautifulSoup
from typing import Optional, List
import re
import os

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
        print("Login redirect URL:", resp.url)
        return 'student' in resp.url

    def fetch_latest_message(self) -> Optional[dict]:
        resp = self.session.get(INBOX_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        row = soup.select_one("tbody tr")
        if not row:
            print("[❌] لا يوجد رسائل.")
            return None

        link_tag = row.select_one("td[col_4] a[href*='msgId=']")
        if not link_tag:
            print("[❌] لم يتم العثور على رابط الرسالة.")
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
                tab_id = f"tab{idx+1}"
                crsSeq = '0'
                courses.append({'code': code, 'title': title, 'tab_id': tab_id, 'crsSeq': crsSeq})

        return courses

    def extract_html_from_js(self, js_text: str) -> str:
        match = re.search(r'\$\("#tab1"\)\.html\(\s*[\'"](.+)[\'"]\s*\);', js_text, re.DOTALL)
        if match:
            html_raw = match.group(1)
            html_unescaped = (html_raw
                              .replace("\\'", "'")
                              .replace('\\"', '"')
                              .replace("\\n", "")
                              .replace("\\r", "")
                              .replace("\\t", "")
                              .replace("\\\\", "\\"))
            return html_unescaped
        return ""

    def fetch_course_marks(self, crsNo: str, tab_id: str, crsSeq: str = '0') -> dict:
        base_url = "https://portal.qou.edu/student/loadCourseServices"

        def fetch_tab_raw(tab: str) -> str:
            url = f"{base_url}?tabId={tab_id}&dataType={tab}&crsNo={crsNo}&crsSeq={crsSeq}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": COURSES_URL
            }
            resp = self.session.post(url, headers=headers)
            resp.raise_for_status()
            return resp.text

        # Marks
        marks_js = fetch_tab_raw("marks")
        marks_html = self.extract_html_from_js(marks_js)

        # حفظ HTML للـ Marks
        os.makedirs("debug_html", exist_ok=True)
        with open(f"debug_html/marks_{crsNo}.html", "w", encoding="utf-8") as f:
            f.write(marks_html)

        # Schedule
        schedule_js = fetch_tab_raw("tSchedule")
        schedule_html = self.extract_html_from_js(schedule_js)

        # حفظ HTML للـ Schedule
        with open(f"debug_html/schedule_{crsNo}.html", "w", encoding="utf-8") as f:
            f.write(schedule_html)

        # البيانات الفارغة الافتراضية
        data = {
            'assignment1': "",
            'midterm': "",
            'midterm_date': "",
            'assignment2': "",
            'final_mark': "",
            'final_date': "",
            'status': "",
            'instructor': "",
            'lecture_day': "",
            'lecture_time': "",
            'building': "",
            'hall': ""
        }

        if marks_html and "العلامات غير متوفرة حاليا" not in marks_html:
            soup = BeautifulSoup(marks_html, "html.parser")

            for fg in soup.select('div.form-group'):
                divs = fg.find_all('div')
                labels_text = [div.get_text(strip=True) for div in divs if div.find('label')]

                if any("التعيين الاول" in text for text in labels_text):
                    data['assignment1'] = divs[-1].get_text(strip=True)

                if any("نصفي نظري" in text for text in labels_text):
                    data['midterm'] = divs[-1].get_text(strip=True)

                if any("تاريخ وضع الامتحان النصفي" in text for text in labels_text):
                    if len(divs) > 1:
                        data['midterm_date'] = divs[1].get_text(strip=True)

                if any("التعيين الثاني" in text for text in labels_text):
                    data['assignment2'] = divs[-1].get_text(strip=True)

                if any("العلامة النهائية" in text for text in labels_text):
                    data['final_mark'] = divs[-1].get_text(strip=True)

                if any("تاريخ وضع العلامة النهائية" in text for text in labels_text):
                    if len(divs) > 1:
                        data['final_date'] = divs[1].get_text(strip=True)

                if any("الحالة" in text for text in labels_text):
                    if len(divs) > 1:
                        data['status'] = divs[1].get_text(strip=True)

        # استخراج بيانات الجدول الزمني
        if schedule_html:
            schedule_soup = BeautifulSoup(schedule_html, "html.parser")

            def extract_schedule_field(field_name):
                label = schedule_soup.find('label', string=re.compile(field_name))
                if label:
                    parent = label.find_parent('div', class_='form-group')
                    if parent:
                        divs = parent.find_all('div')
                        for d in divs:
                            text = d.get_text(strip=True)
                            if text and text != field_name and text != "&nbsp;&nbsp;":
                                return text
                return ""

            data['lecture_day'] = extract_schedule_field("اليوم")
            data['lecture_time'] = extract_schedule_field("الموعد")
            data['building'] = extract_schedule_field("البناية")
            data['hall'] = extract_schedule_field("القاعة")

            instructor_a = schedule_soup.select_one('div.form-group a[href*="createMessage"]')
            if instructor_a:
                data['instructor'] = instructor_a.get_text(strip=True)

        return data

    def fetch_courses_with_marks(self) -> List[dict]:
        courses = self.fetch_courses()
        for course in courses:
            course['marks'] = self.fetch_course_marks(course['code'], course['tab_id'], course['crsSeq'])
        return courses
