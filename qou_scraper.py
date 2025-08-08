import requests
from bs4 import BeautifulSoup
from typing import Optional, List
import re
import html

LOGIN_URL = 'https://portal.qou.edu/login.do'
INBOX_URL = 'https://portal.qou.edu/student/inbox.do'
COURSES_URL = 'https://portal.qou.edu/student/courseServices.do'

class QOUScraper:
    def __init__(self, student_id: str, password: str):
        self.session = requests.Session()
        self.student_id = student_id
        self.password = password

    def login(self) -> bool:
        self.session.get(LOGIN_URL)  # الحصول على الكوكيز
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
            return None

        link_tag = row.select_one("td[col_4] a[href*='msgId=']")
        if not link_tag:
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
        # استخراج محتوى .html("...") أو .html('...')
        match = re.search(r'\.html\(\s*([\'"])(.*?)\1\s*\);', js_text, re.DOTALL)
        if not match:
            return ""

        raw_html = match.group(2)

        # فك ترميز HTML entities والهروب
        html_unescaped = html.unescape(raw_html)
        html_clean = (html_unescaped
                      .replace("\\'", "'")
                      .replace('\\"', '"')
                      .replace("\\n", "")
                      .replace("\\r", "")
                      .replace("\\t", "")
                      .replace("\\\\", "\\"))

        return html_clean.strip()

    def _extract_next_sibling_text(self, label_tag) -> str:
        parent_div = label_tag.find_parent('div', class_='col-sm-4') or label_tag.find_parent('div')
        if not parent_div:
            return "-"
        next_node = label_tag.next_sibling
        while next_node and (not isinstance(next_node, str) or not next_node.strip()):
            next_node = next_node.next_sibling
        if isinstance(next_node, str):
            text = next_node.strip()
            if text:
                return text
        sibling_div = parent_div.find_next_sibling('div')
        if sibling_div:
            text = sibling_div.get_text(strip=True)
            if text:
                return text
        return "-"

    def find_field_value_by_label(self, soup: BeautifulSoup, field_name: str) -> str:
        label = soup.find('label', string=re.compile(field_name))
        if not label:
            return "-"
        parent = label.find_parent('div', class_='form-group')
        if not parent:
            return "-"
        texts = [t for t in parent.stripped_strings if field_name not in t]
        for text in texts:
            if text and re.search(r'\d', text):
                return text
        return texts[0] if texts else "-"

    def fetch_course_marks(self, crsNo: str, tab_id: str, crsSeq: str = '0') -> dict:
        base_url = "https://portal.qou.edu/student/loadCourseServices"

        def fetch_tab_raw(tab: str) -> str:
            url = f"{base_url}?tabId={tab_id}&dataType={tab}&crsNo={crsNo}&crsSeq={crsSeq}"
            headers = {
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": COURSES_URL
            }
            resp = self.session.post(url, headers=headers)
            resp.raise_for_status()
            return resp.text

        marks_js = fetch_tab_raw("marks")
        marks_html = self.extract_html_from_js(marks_js)

        schedule_js = fetch_tab_raw("tSchedule")
        schedule_html = self.extract_html_from_js(schedule_js)

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

        if marks_html and "العلامات غير متوفرة حاليا" not in marks_html:
            soup = BeautifulSoup(marks_html, "html.parser")
            for fg in soup.select('div.form-group'):
                for label in fg.find_all('label'):
                    label_text = label.get_text(strip=True)
                    if re.search(r"^التعيين الاول:?$", label_text):
                        data['assignment1'] = self._extract_next_sibling_text(label)
                    elif re.search(r"^نصفي نظري:?$", label_text):
                        data['midterm'] = self._extract_next_sibling_text(label)
                    elif re.search(r"^تاريخ وضع الامتحان النصفي:?$", label_text):
                        data['midterm_date'] = self._extract_next_sibling_text(label)
                    elif re.search(r"^التعيين الثاني:?$", label_text):
                        data['assignment2'] = self._extract_next_sibling_text(label)
                    elif re.search(r"^العلامة النهائية:?$", label_text):
                        data['final_mark'] = self._extract_next_sibling_text(label)
                    elif re.search(r"^تاريخ وضع العلامة النهائية:?$", label_text):
                        data['final_date'] = self._extract_next_sibling_text(label)
                    elif re.search(r"^الحالة:?$", label_text):
                        data['status'] = self._extract_next_sibling_text(label)

        if schedule_html:
            schedule_soup = BeautifulSoup(schedule_html, "html.parser")
            data['lecture_day'] = self.find_field_value_by_label(schedule_soup, "اليوم")
            data['lecture_time'] = self.find_field_value_by_label(schedule_soup, "الموعد")
            data['building'] = self.find_field_value_by_label(schedule_soup, "البناية")
            data['hall'] = self.find_field_value_by_label(schedule_soup, "القاعة")

            instructor_a = schedule_soup.select_one('div.form-group a[href*="createMessage"]')
            if instructor_a:
                data['instructor'] = instructor_a.get_text(strip=True)

        return data

    def fetch_courses_with_marks(self) -> List[dict]:
        courses = self.fetch_courses()
        for course in courses:
            course['marks'] = self.fetch_course_marks(course['code'], course['tab_id'], course['crsSeq'])
        return courses
