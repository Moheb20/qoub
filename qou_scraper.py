import requests
from bs4 import BeautifulSoup
from typing import Optional, List
from datetime import datetime

LOGIN_URL = 'https://portal.qou.edu/login.do'
INBOX_URL = 'https://portal.qou.edu/student/inbox.do'
TERM_SUMMARY_URL = 'https://portal.qou.edu/student/showTermSummary.do'
WEEKLY_MEETINGS_URL = 'https://portal.qou.edu/student/showTermSchedule.do'
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



    def send_latest_due_date_reminder():
        print("🚀 [STARTED] send_latest_due_date_reminder")
        notified_users = {}
    
        while True:
            now = datetime.now()
            users = get_all_users()
    
            for user in users:
                chat_id = user['chat_id']
                student_id = user['student_id']
                password = user['password']
    
                scraper = QOUScraper(student_id, password)
                if scraper.login():
                    try:
                        activity = scraper.get_last_activity_due_date()
                        print(f"👤 [{chat_id}] Checked activity: {activity}")
    
                        if not activity:
                            print(f"⚠️ [{chat_id}] لا يوجد موعد تسليم قادم حالياً")
                            continue
    
                        due_dt = activity['date']
                        link = activity['link']
    
                        user_state = notified_users.get(chat_id, {})
    
                        # تم تغيير الموعد أو أول مرة
                        if 'due' not in user_state:
                            print(f"📌 [{chat_id}] تم تحديد موعد تسليم جديد: {due_dt} | {link}")
                            user_state = {
                                'due': due_dt,
                                'last_12h_notify': None,
                                'sent_hour_left': False,
                                'sent_due': False
                            }
                            notified_users[chat_id] = user_state
                        elif due_dt != user_state['due']:
                            print(f"🔁 [{chat_id}] تم تمديد أو تغيير موعد التسليم: {due_dt} | {link}")
                            user_state = {
                                'due': due_dt,
                                'last_12h_notify': None,
                                'sent_hour_left': False,
                                'sent_due': False
                            }
                            notified_users[chat_id] = user_state
    
                        diff_minutes = (due_dt - now).total_seconds() / 60
    
                        # تذكير كل 12 ساعة
                        last_notify = user_state.get('last_12h_notify')
                        if diff_minutes > 0:
                            if not last_notify or (now - last_notify).total_seconds() >= 12 * 3600:
                                print(f"⏰ [{chat_id}] تذكير: لا تنسى تسليم النشاط! (كل 12 ساعة)")
                                user_state['last_12h_notify'] = now
    
                        # تبقى ساعة
                        if 0 < diff_minutes <= 60 and not user_state.get('sent_hour_left', False):
                            print(f"⚠️ [{chat_id}] تبقى ساعة واحدة فقط على التسليم")
                            user_state['sent_hour_left'] = True
    
                        # الموعد انتهى
                        if now >= due_dt and not user_state.get('sent_due', False):
                            print(f"✅ [{chat_id}] انتهى موعد التسليم: {due_dt}")
                            user_state['sent_due'] = True
    
                    except Exception as e:
                        print(f"❌ [{chat_id}] خطأ أثناء التحقق من موعد التسليم: {e}")
    
            time.sleep(5 * 60)  # التحقق كل 5 دقائق
