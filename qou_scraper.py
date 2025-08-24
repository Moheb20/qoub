import requests
from bs4 import BeautifulSoup
import os
from typing import Optional, List
from datetime import datetime
import logging
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import arabic_reshaper
from bidi.algorithm import get_display
from io import BytesIO
from database import add_exam, get_all_users

font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'arial.ttf')
pdfmetrics.registerFont(TTFont('Arial', font_path))
LOGIN_URL = 'https://portal.qou.edu/login.do'
INBOX_URL = 'https://portal.qou.edu/student/inbox.do'
TERM_SUMMARY_URL = 'https://portal.qou.edu/student/showTermSummary.do'
WEEKLY_MEETINGS_URL = 'https://portal.qou.edu/student/showTermSchedule.do'
BALANCE_URL = 'https://portal.qou.edu/student/getSasStudFtermCardList.do'
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


    def fetch_discussion_sessions(self) -> List[dict]:
        resp = self.session.get(WEEKLY_MEETINGS_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
    
        sessions = []
        table = soup.find("table", {"id": "dataTable"})
        if not table:
            return sessions
    
        rows = table.find("tbody").find_all("tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue
            session = {
                "course_code": cols[0].get_text(strip=True),
                "course_name": cols[1].get_text(strip=True),
                "section": cols[2].get_text(strip=True),
                "date": cols[3].get_text(strip=True),  # 17/08/2025
                "time": cols[4].get_text(strip=True)   # 11:00 - 12:00
            }
            sessions.append(session)
        return sessions
    def fetch_balance_table_pdf(self) -> BytesIO:
        resp = self.session.get(BALANCE_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
    
        rows = soup.select("table#dataTable tbody tr")
        if not rows:
            return None
    
        # الأعمدة والبيانات
        columns = ["الفصل", " المطلوب", " المدفوع", " المنح", "المبلغ المتبقي"]
        data = [columns]
    
        for row in rows:
            cols = [c.get_text(strip=True).replace(',', '') for c in row.find_all("td")]
            if len(cols) < 7:
                continue
            data.append([cols[0], cols[1], cols[2], cols[4], cols[5]])
    
        if len(data) == 1:
            return None
    
        # معالجة النص العربي لكل خلية في الجدول
        for i in range(1, len(data)):
            for j in range(len(data[i])):
                data[i][j] = get_display(arabic_reshaper.reshape(data[i][j]))
    
        # معالجة عناوين الأعمدة
        data[0] = [get_display(arabic_reshaper.reshape(col)) for col in data[0]]
    
        output = BytesIO()
        pdf = SimpleDocTemplate(output, pagesize=A4)
        elements = []
    
        style_sheet = getSampleStyleSheet()
        arabic_style = style_sheet['Normal']
        arabic_style.fontName = 'Arial'
        arabic_style.fontSize = 12
    
        # عنوان الصفحة
        title_text = get_display(arabic_reshaper.reshape("رصيد الطالب"))
        elements.append(Paragraph(title_text, arabic_style))
        elements.append(Spacer(1, 12))
    
        # إنشاء الجدول
        table = Table(data, repeatRows=1, hAlign='CENTER')
        style = TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Arial'),
            ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BACKGROUND', (0,1), (-1,-1), colors.whitesmoke),
        ])
        table.setStyle(style)
    
        # تلوين الصفوف بالتناوب
        for i in range(1, len(data)):
            if i % 2 == 0:
                table.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), colors.lightgrey)]))
    
        elements.append(table)
        pdf.build(elements)
        output.seek(0)
        return output
    
    def fetch_balance_totals(self) -> str:
        """
        يحسب الإجمالي لكل الأعمدة ويعرضه بشكل مرتب على Telegram
        """
        resp = self.session.get(BALANCE_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
    
        rows = soup.select("table#dataTable tbody tr")
        if not rows:
            return "❌ لم يتم العثور على بيانات الرصيد"
    
        total_required = total_paid = total_grants = total_balance = 0.0
    
        for row in rows:
            cols = [c.get_text(strip=True).replace(',', '') for c in row.find_all("td")]
            if len(cols) < 7:
                continue
            total_required += float(cols[1])
            total_paid     += float(cols[2])
            total_grants   += float(cols[4])
            total_balance  += float(cols[5])
    
        text = "📌 الإجمالي الكلي للرصيد:\n\n"
        text += f"💰 المطلوب: {total_required}\n"
        text += f"✅ المدفوع: {total_paid}\n"
        text += f"🎓 المنح: {total_grants}\n"
        text += f"📊 رصيد الفصل: {total_balance}\n"
    
        return text

    def save_exams_to_db(self, student_id):
        from database import get_conn
        exams = []
        for exam_type_code in EXAM_TYPE_MAP.keys():
            exams += self.fetch_exam_schedule(term_no="current_term", exam_type=exam_type_code) or []
    
        with get_conn() as conn:
            with conn.cursor() as cur:
                for exam in exams:
                    cur.execute('''
                        INSERT INTO exam_schedule
                        (student_id, exam_type, course_code, course_name, date, from_time, to_time, lecturer, session, note)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (student_id, course_code, date, from_time) DO NOTHING
                    ''', (
                        student_id,
                        exam.get("exam_kind"),
                        exam.get("course_code"),
                        exam.get("course_name"),
                        exam.get("date"),
                        exam.get("from_time"),
                        exam.get("to_time"),
                        exam.get("lecturer"),
                        exam.get("session"),
                        exam.get("note")
                    ))
            conn.commit()


