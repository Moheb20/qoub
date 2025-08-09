import requests
from bs4 import BeautifulSoup
from typing import Optional, List
import telebot
import scheduler
import time
import threading

LOGIN_URL = 'https://portal.qou.edu/login.do'
INBOX_URL = 'https://portal.qou.edu/student/inbox.do'
TERM_SUMMARY_URL = 'https://portal.qou.edu/student/showTermSummary.do'
CALENDAR_URL = 'https://portal.qou.edu/calendarProposed.do'  # رابط تقريبي، استبدل بالرابط الصحيح

class QOUScraper:
    def __init__(self, student_id: str, password: str):
        self.session = requests.Session()
        self.student_id = student_id
        self.password = password

        self.academic_calendar = []

    def login(self) -> bool:
        self.session.get(LOGIN_URL)  # للحصول على الكوكيز
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
    def fetch_academic_calendar(self):
        resp = self.session.get(CALENDAR_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

    # نجد كل الفصول الدراسية (div يحمل النص "الفصل الأول" أو "الفصل الثاني" ... )
        semester_titles = soup.find_all('div', class_='text-warning')

    # نجد كل الجداول التي تحمل id="dataTable" (كل فصل جدول)
        tables = soup.find_all('table', id='dataTable')

        if not tables or not semester_titles or len(tables) != len(semester_titles):
            return "📭 لم يتم العثور على بيانات التقويم الأكاديمي حالياً."

        calendar_data = []
            for i in range(len(tables)):
            semester_name = semester_titles[i].get_text(strip=True)
            table = tables[i]

        # نجمع بيانات الصفوف
        rows = []
        for tr in table.tbody.find_all('tr'):
            cols = tr.find_all('td')
            if len(cols) >= 5:
                subject = cols[0].get_text(strip=True)
                week = cols[1].get_text(strip=True)
                day = cols[2].get_text(strip=True)
                start = cols[3].get_text(strip=True)
                end = cols[4].get_text(strip=True)
                rows.append({
                    'subject': subject,
                    'week': week,
                    'day': day,
                    'start': start,
                    'end': end,
                })

        calendar_data.append({
            'semester': semester_name,
            'events': rows,
        })

    return calendar_data
