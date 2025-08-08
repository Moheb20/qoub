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
        self.session.get(LOGIN_URL)  # لتحميل الكوكيز وغيرها
        params = {
            'userId': self.student_id,
            'password': self.password,
            'logBtn': 'Login'
        }
        resp = self.session.post(LOGIN_URL, data=params, allow_redirects=True)
        return 'student' in resp.url

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
                tab_id = f"tab{idx + 1}"  # tab1, tab2, ...
                crsSeq = '0'  # حسب بيانات الموقع غالباً 0
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
            # استخراج المحتوى داخل html('...')
            # قد يكون داخل علامات ' أو "
            m = re.search(r"html\((['\"])(.*?)\1\);", js_text, re.DOTALL)
            if m:
                html_content = m.group(2)
                # إزالة علامات الهروب
                html_content = html_content.encode('utf-8').decode('unicode_escape')
                # إزالة بعض escapes الزائدة مثل \n \r
                html_content = html_content.replace('\r', '').replace('\n', '').replace('\\\'', '\'')
                return html_content
            return ""

        marks_js = fetch_tab_raw("marks")
        schedule_js = fetch_tab_raw("tSchedule")

        marks_html = extract_html_from_js(marks_js)
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

        # استخراج بيانات العلامات من marks_soup
        for fg in marks_soup.select('div.form-group'):
            labels = fg.find_all('label')
            # جمع كل نصوص div مباشرة داخل form-group (لا تشمل العناوين الفرعية)
            div_texts = [div.get_text(strip=True) for div in fg.find_all('div', recursive=False)]
            for label in labels:
                text = label.get_text(strip=True)
                if "التعيين الاول" in text:
                    if len(div_texts) > 1 and div_texts[1]:
                        data['assignment1'] = div_texts[1]
                elif "نصفي نظري" in text:
                    # عادة يكون في div الرابع (index 3)
                    if len(div_texts) > 3 and div_texts[3]:
                        data['midterm'] = div_texts[3]
                elif "تاريخ وضع الامتحان النصفي" in text:
                    if len(div_texts) > 1 and div_texts[1]:
                        data['midterm_date'] = div_texts[1]
                elif "التعيين الثاني" in text:
                    if len(div_texts) > 1 and div_texts[1]:
                        data['assignment2'] = div_texts[1]
                elif "العلامة النهائية" in text:
                    if len(div_texts) > 3 and div_texts[3]:
                        data['final_mark'] = div_texts[3]
                elif "تاريخ وضع العلامة النهائية" in text:
                    if len(div_texts) > 1 and div_texts[1]:
                        data['final_date'] = div_texts[1]
                elif "الحالة" in text:
                    if len(div_texts) > 1 and div_texts[1]:
                        data['status'] = div_texts[1]

        # استخراج بيانات الجدول من schedule_soup
        def extract_schedule_field(field_name):
            label = schedule_soup.find('label', string=re.compile(field_name))
            if label:
                parent = label.find_parent('div', class_='form-group')
                if parent:
                    divs = parent.find_all('div', recursive=False)
                    if len(divs) > 1:
                        val = divs[1].get_text(strip=True)
                        if val and val != "&nbsp;&nbsp;":
                            return val.strip()
            return "-"

        data['lecture_day'] = extract_schedule_field("اليوم")
        data['lecture_time'] = extract_schedule_field("الموعد")
        data['building'] = extract_schedule_field("البناية")
        data['hall'] = extract_schedule_field("القاعة")

        # استخراج اسم عضو هيئة التدريس
        instructor_a = schedule_soup.select_one('div.form-group a[href*="createMessage"]')
        if instructor_a:
            data['instructor'] = instructor_a.get_text(strip=True)

        return data

    def fetch_courses_with_marks(self) -> List[dict]:
        courses = self.fetch_courses()
        for course in courses:
            course['marks'] = self.fetch_course_marks(course['code'], course['tab_id'], course['crsSeq'])
        return courses
