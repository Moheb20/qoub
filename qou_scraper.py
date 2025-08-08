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

    def fetch_course_marks(self, crsNo: str, tab_id: str, crsSeq: str = '0') -> dict:
        base_url = "https://portal.qou.edu/student/loadCourseServices"

        def fetch_tab_raw(tab: str) -> str:
            url = f"{base_url}?tabId={tab_id}&dataType={tab}&crsNo={crsNo}&crsSeq={crsSeq}"
            resp = self.session.post(url)
            resp.raise_for_status()
            return resp.text

        def extract_html_from_js(js_text: str) -> str:
            m = re.search(r"html\(['\"](.+?)['\"]\);", js_text, re.DOTALL)
            if m:
                html_content = m.group(1)
                html_content = (html_content
                                .replace("\\'", "'")
                                .replace('\\"', '"')
                                .replace("\\n", "")
                                .replace("\\t", "")
                                .replace("\\r", ""))
                return html_content
            return ""

        marks_js = fetch_tab_raw("marks")
        schedule_js = fetch_tab_raw("tSchedule")

        print(f"--- المحتوى الخام للتاب marks للكورس {crsNo} ---")
        print(marks_js[:1000])
        print(f"--- المحتوى الخام للتاب tSchedule للكورس {crsNo} ---")
        print(schedule_js[:1000])

        marks_html = extract_html_from_js(marks_js)

        # شرط لتخطي الكورسات التي لا تحتوي علامات متوفرة
        if "العلامات غير متوفرة حاليا" in marks_html:
            return {
                'assignment1': "-",
                'midterm': "-",
                'midterm_date': "-",
                'assignment2': "-",
                'final_mark': "-",
                'final_date': "-",
                'status': "-",
                'instructor': "-",
                'lecture_day': "-",
                'lecture_time': "-",
                'building': "-",
                'hall': "-"
            }

        schedule_html = extract_html_from_js(schedule_js)

        marks_soup = BeautifulSoup(marks_html, "html.parser")
        schedule_soup = BeautifulSoup(schedule_html, "html.parser")

        data = {
            'assignment1': "-",
            'midterm': "-",
            'midterm_date': "-",
            'assignment2': "-",
            'final_mark': "-",
            'final_date': "-",
            'status': "-",
            'instructor': "-",
            'lecture_day': "-",
            'lecture_time': "-",
            'building': "-",
            'hall': "-"
        }

        for fg in marks_soup.select('div.form-group'):
            divs = fg.find_all('div')
            labels_text = [div.get_text(strip=True) for div in divs if div.find('label')]

            if any("التعيين الاول" in text for text in labels_text):
                # لا يوجد قيمة ظاهرة، غالبًا فارغة حسب البيانات
                pass

            if any("نصفي نظري" in text for text in labels_text):
                val = divs[-1].get_text(strip=True)
                if val:
                    data['midterm'] = val

            if any("تاريخ وضع الامتحان النصفي" in text for text in labels_text):
                if len(divs) > 1:
                    val = divs[1].get_text(strip=True)
                    if val:
                        data['midterm_date'] = val

            if any("التعيين الثاني" in text for text in labels_text):
                # غالبًا فارغة حسب البيانات
                pass

            if any("العلامة النهائية" in text for text in labels_text):
                val = divs[-1].get_text(strip=True)
                if val:
                    data['final_mark'] = val

            if any("تاريخ وضع العلامة النهائية" in text for text in labels_text):
                if len(divs) > 1:
                    val = divs[1].get_text(strip=True)
                    if val:
                        data['final_date'] = val

            if any("الحالة" in text for text in labels_text):
                if len(divs) > 1:
                    val = divs[1].get_text(strip=True)
                    if val:
                        data['status'] = val

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
            return "-"

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
