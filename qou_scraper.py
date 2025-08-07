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
        for idx, item in enumerate(course_titles):
            full_text = item.get_text(strip=True)
            match = re.match(r"\d+/(\d+)\s+(.*)", full_text)
            if match:
                code = match.group(1)
                title = match.group(2)
                tab_id = f"tab{idx+1}"  # tab1, tab2, ...
                # crsSeq غالباً هو 1 كما بالمثال
                crsSeq = '1'
                courses.append({'code': code, 'title': title, 'tab_id': tab_id, 'crsSeq': crsSeq})

        return courses

    def fetch_course_marks(self, crsNo: str, tab_id: str, crsSeq: str = '1') -> dict:
        base_url = "https://portal.qou.edu/student/loadCourseServices"

        def fetch_tab(tab: str) -> BeautifulSoup:
            url = f"{base_url}?tabId={tab_id}&dataType={tab}&crsNo={crsNo}&crsSeq={crsSeq}"
            resp = self.session.post(url)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, 'html.parser')

        def get_label_value(soup: BeautifulSoup, label_text_pattern: str) -> str:
            label_tags = soup.find_all('label', string=re.compile(label_text_pattern.strip(), re.I))
            for label in label_tags:
                parent_div = label.find_parent('div', class_='form-group')
                if parent_div:
                    # كل div بداخل form-group
                    divs = parent_div.find_all('div', recursive=False)
                    # ابحث في هذه الـ divs عن قيمة بعد div الذي يحتوي label
                    for i, div in enumerate(divs):
                        if label in div.descendants:
                        # غالبًا القيمة في الـ div التالي
                        if i + 1 < len(divs):
                            value = divs[i + 1].get_text(strip=True)
                            if value and value != '-':
                                return value
        return "-"


        

        def get_direct_label_value(soup: BeautifulSoup, label_text_pattern: str) -> str:
            label = soup.find('label', string=re.compile(label_text_pattern, re.I))
            if label and label.next_sibling:
                value = str(label.next_sibling).strip().replace("&nbsp;", "")
                return value if value else "-"
            return "-"

        def get_instructor(soup: BeautifulSoup) -> str:
            instructor_div = soup.find('a', href=re.compile("createMessage"))
            if instructor_div:
                return instructor_div.get_text(strip=True)
            return "-"

        # 🟢 Step 1: Fetch marks tab
        marks_soup = fetch_tab("marks")

        marks_data = {
            'assignment1': get_label_value(marks_soup, 'التعيين الأول'),
            'midterm': get_label_value(marks_soup, 'نصفي نظري'),
            'midterm_date': get_label_value(marks_soup, 'تاريخ وضع الامتحان النصفي'),
            'assignment2': get_label_value(marks_soup, 'التعيين الثاني'),
            'final_mark': get_label_value(marks_soup, 'العلامة النهائية'),
            'final_date': get_label_value(marks_soup, 'تاريخ وضع العلامة النهائية'),
            'status': get_label_value(marks_soup, 'الحالة'),
        }

        # 🟢 Step 2: Fetch schedule tab
        schedule_soup = fetch_tab("tSchedule")
        marks_data.update({
            'instructor': get_instructor(schedule_soup),
            'lecture_day': get_direct_label_value(schedule_soup, 'اليوم'),
            'lecture_time': get_direct_label_value(schedule_soup, 'الموعد'),
            'building': get_direct_label_value(schedule_soup, 'البناية'),
            'hall': get_direct_label_value(schedule_soup, 'القاعة'),
        })

        return marks_data

    def fetch_courses_with_marks(self) -> List[dict]:
        courses = self.fetch_courses()
        for course in courses:
            course['marks'] = self.fetch_course_marks(course['code'], course['tab_id'], course['crsSeq'])
        return courses
