import requests
from bs4 import BeautifulSoup
from typing import Optional, List

LOGIN_URL = 'https://portal.qou.edu/login.do'
INBOX_URL = 'https://portal.qou.edu/student/inbox.do'
TERM_SUMMARY_URL = 'https://portal.qou.edu/student/showTermSummary.do'
WEEKLY_MEETINGS_URL = 'https://portal.qou.edu/student/showTermSchedule.do'  # رابط اللقاءات الأسبوعية
EXAMS_SCHEDULE_URL = 'https://portal.qou.edu/student/examsScheduleView.do'



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

    def fetch_term_summary_courses(self) -> List[dict]:
        resp = self.session.get(TERM_SUMMARY_URL)
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

    def fetch_lectures_schedule(self) -> List[dict]:
        resp = self.session.get(WEEKLY_MEETINGS_URL)
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

    def fetch_term_summary_stats(self) -> dict:
        resp = self.session.get(TERM_SUMMARY_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        stats_table = soup.find('table', id='dataTable3')
        if not stats_table:
            return {}

        rows = stats_table.find('tbody').find_all('tr')
        if len(rows) < 2:
            return {}

        def parse_row(row):
            cols = row.find_all('td')
            return {
                'type': cols[0].get_text(strip=True),  # فصلي أو تراكمي
                'registered_hours': cols[1].get_text(strip=True),
                'passed_hours': cols[2].get_text(strip=True),
                'counted_hours': cols[3].get_text(strip=True),
                'failed_hours': cols[4].get_text(strip=True),
                'withdrawn_hours': cols[5].get_text(strip=True),
                'points': cols[6].get_text(strip=True),
                'gpa': cols[7].get_text(strip=True),
                'honor_list': cols[8].get_text(strip=True)
            }

        return {
            'term': parse_row(rows[0]),
            'cumulative': parse_row(rows[1])
        }


    def fetch_term_and_exam_type(self) -> Tuple[Optional[str], Optional[str]]:
        resp = self.session.get(TERM_SUMMARY_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        term_no = None
        exam_type = None

        # استخراج رقم الفصل
        term_select = soup.find('select', {'name': 'termNo'})
        if term_select:
            option = term_select.find('option')
            if option:
                term_no = option['value']

        # استخراج نوع الامتحان
        exam_type_select = soup.find('select', {'name': 'examType'})
        if exam_type_select:
            option = exam_type_select.find('option')
            if option:
                exam_type = option['value']

        return term_no, exam_type

    def fetch_exam_schedule(self, term_no: str, exam_type: str) -> List[dict]:
        payload = {
            'termNo': term_no,
            'examType': exam_type
        }
        resp = self.session.post(EXAMS_SCHEDULE_URL, data=payload)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        table = soup.find('table', id='dataTable')
        if not table:
            return []

        exams = []
        rows = table.find('tbody').find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 11:
                continue
            exam = {
                'exam_kind': cols[0].get_text(strip=True),
                'course_code': cols[1].get_text(strip=True),
                'course_name': cols[2].get_text(strip=True),
                'lecturer': cols[3].get_text(strip=True),
                'section': cols[4].get_text(strip=True),
                'day': cols[5].get_text(strip=True),
                'date': cols[6].get_text(strip=True),
                'session': cols[7].get_text(strip=True),
                'from_time': cols[8].get_text(strip=True),
                'to_time': cols[9].get_text(strip=True),
                'note': cols[10].get_text(strip=True)
            }
            exams.append(exam)
        return exams

     
