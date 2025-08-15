import requests
from bs4 import BeautifulSoup
from typing import Optional, List
from datetime import datetime

LOGIN_URL = 'https://portal.qou.edu/login.do'
INBOX_URL = 'https://portal.qou.edu/student/inbox.do'
TERM_SUMMARY_URL = 'https://portal.qou.edu/student/showTermSummary.do'
WEEKLY_MEETINGS_URL = 'https://portal.qou.edu/student/showTermSchedule.do'
EXAMS_SCHEDULE_URL = 'https://portal.qou.edu/student/examsScheduleView.do'
logger = logging.getLogger(__name__)
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
                'type': cols[0].get_text(strip=True),
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

    def get_last_two_terms(self) -> List[dict]:
        resp = self.session.get(EXAMS_SCHEDULE_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        select_term = soup.find("select", {"name": "termNo"})
        options = select_term.find_all("option")
        last_two = options[:2]  # آخر فصلين
        return [{'value': opt['value'], 'label': opt.get_text(strip=True)} for opt in last_two]

    def fetch_exam_schedule(self, term_no, exam_type) -> List[dict]:
        payload = {
            "termNo": term_no,
            "examType": exam_type
        }
        resp = self.session.post(EXAMS_SCHEDULE_URL, data=payload)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", id="dataTable")
        if not table:
            return []
        exams = []
        rows = table.find("tbody").find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 11:
                continue
            exam = {
                "exam_kind": cols[0].get_text(strip=True),
                "course_code": cols[1].get_text(strip=True),
                "course_name": cols[2].get_text(strip=True),
                "lecturer": cols[3].get_text(strip=True),
                "section": cols[4].get_text(strip=True),
                "day": cols[5].get_text(strip=True),
                "date": cols[6].get_text(strip=True),
                "session": cols[7].get_text(strip=True),
                "from_time": cols[8].get_text(strip=True),
                "to_time": cols[9].get_text(strip=True),
                "note": cols[10].get_text(strip=True)
            }
            exams.append(exam)
        return exams
    def fetch_gpa(self):
        stats = self.fetch_term_summary_stats()
        if not stats:
            return None
        return {
            "term_gpa": stats.get('term', {}).get('gpa', 'غير متوفر'),
            "cumulative_gpa": stats.get('cumulative', {}).get('gpa', 'غير متوفر')

        }



    
    def get_last_activity_due_date(self):
        login_page = self.session.get("https://activity.qou.edu/login/index.php", timeout=10)
        if login_page.status_code != 200:
            logger.error("❌ فشل في تحميل صفحة تسجيل الدخول")
            return None
    
        soup_login = BeautifulSoup(login_page.text, "html.parser")
        logintoken_input = soup_login.find("input", {"name": "logintoken"})
        logintoken = logintoken_input['value'] if logintoken_input else ""
    
        payload = {
            "username": self.student_id,
            "password": self.password,
            "logintoken": logintoken,
            "anchor": ""
        }
    
        login_response = self.session.post(
            "https://activity.qou.edu/login/index.php", data=payload, timeout=10
        )
        if login_response.status_code != 200 or "login" in login_response.url:
            logger.error(f"❌ فشل تسجيل الدخول للطالب {self.student_id}")
            return None
    
        url = "https://activity.qou.edu/calendar/view.php?view=month"
        res = self.session.get(url, timeout=10)
        if res.status_code != 200:
            logger.error("❌ فشل في تحميل صفحة التقويم")
            return None
    
        soup = BeautifulSoup(res.text, "html.parser")
        due_cells = soup.select('td.duration_finish')
    
        if not due_cells:
            logger.warning("⚠️ لم يتم العثور على أي مواعيد تسليم (duration_finish)")
            return None
        else:
            logger.info(f"🔍 تم العثور على {len(due_cells)} موعد/مواعيد تسليم")
    
        now = datetime.now()
        nearest_due = None
    
        for cell in due_cells:
            timestamp = cell.get("data-day-timestamp")
            if not timestamp:
                continue
    
            try:
                date = datetime.fromtimestamp(int(timestamp))
            except Exception as e:
                logger.warning(f"⚠️ خطأ في تحويل التاريخ: {e}")
                continue
    
            a_tag = cell.find("a")
            link = a_tag.get("href") if a_tag else url
    
            logger.info(f"📅 تم العثور على موعد: {date.strftime('%Y-%m-%d %H:%M')}")
    
            if date > now:
                logger.info("✅ هذا الموعد قادم وسيتم استخدامه")
                if not nearest_due or date < nearest_due['date']:
                    nearest_due = {
                        "date": date,
                        "link": link
                    }
            else:
                logger.info("⛔ هذا الموعد منتهي وسيتم تجاهله")
    
        if nearest_due:
            return nearest_due
    
        logger.error("❌ لم يتم العثور على موعد تسليم قادم")
        return None

