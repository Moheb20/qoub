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
import database 
from typing import Dict, Any
from database import save_student_stats, save_student_courses


font_path = os.path.join(os.path.dirname(__file__), 'fonts', 'arial.ttf')
pdfmetrics.registerFont(TTFont('Arial', font_path))
STUDY_PLAN_URL = "https://portal.qou.edu/student/showMajorSheet.do" 
LOGIN_URL = 'https://portal.qou.edu/login.do'
INBOX_URL = 'https://portal.qou.edu/student/inbox.do'
TERM_SUMMARY_URL = 'https://portal.qou.edu/student/showTermSummary.do'
WEEKLY_MEETINGS_URL = 'https://portal.qou.edu/student/showTermSchedule.do'
BALANCE_URL = 'https://portal.qou.edu/student/getSasStudFtermCardList.do'
EXAMS_SCHEDULE_URL = 'https://portal.qou.edu/student/examsScheduleView.do'
cel = 'https://portal.qou.edu/calendarProposed.do'
logger = logging.getLogger(__name__)
EXAM_TYPE_MAP = {
    "MT&IM": "📝 النصفي",
    "FT&IF": "🏁 النهائي النظري",
    "FP&FP": "🧪 النهائي العملي",
    "LE&LE": "📈 امتحان المستوى",
}

class QOUScraper:
    def __init__(self, student_id: str, password: str):
        self.session = requests.Session()
        self.student_id = student_id
        self.password = password
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/114.0.0.0 Safari/537.36",
            "Accept-Language": "ar,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Connection": "keep-alive"
        }

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

    def parse_exam_datetime(self, date_str, time_str):
        """يحوّل التاريخ + الوقت من النص إلى datetime جاهز"""
        try:
            # دعم 23-08-2025 بدل 23/08/2025
            dt = datetime.strptime(f"{date_str} {time_str}", "%d-%m-%Y %H:%M")
            return dt.replace(tzinfo=PALESTINE_TZ)
        except Exception:
            return None
    # ------------------- جلب آخر فصلين -------------------
    def get_last_two_terms(self):
        resp = self.session.get(EXAMS_SCHEDULE_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        select_term = soup.find("select", {"name": "termNo"})
        if not select_term:
            return []
        options = select_term.find_all("option")
        # عادةً يكون أول خيار هو الفصل الحالي، الثاني السابق
        last_two = options[:2]
        return [{'value': opt['value'], 'label': opt.get_text(strip=True)} for opt in last_two]

    # ------------------- جلب جدول الامتحانات من البوابة -------------------
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
        
        # تنظيف البيانات
        def clean_gpa_value(gpa):
            if not gpa or gpa in ['غير متوفر', 'N/A', '']:
                return "غير متوفر"
            try:
                # تحويل إلى رقم للتأكد من صحته
                float(gpa)
                return gpa
            except (ValueError, TypeError):
                return "غير متوفر"
        
        return {
            "term_gpa": clean_gpa_value(stats.get('term', {}).get('gpa')),
            "cumulative_gpa": clean_gpa_value(stats.get('cumulative', {}).get('gpa'))
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


    @staticmethod
    def get_active_calendar():
        res = requests.get(cel)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")
    
        # كل الصفوف اللي مش text-not-active
        active_rows = soup.find_all("tr", class_=lambda x: x != "text-not-active")
    
        if not active_rows:  # إذا ما في أي صف
            return "ما لقيت أحداث حالياً 🤷‍♂️"
    
        events = []
        for row in active_rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue
            subject = cols[0].get_text(strip=True)
            week = cols[1].get_text(strip=True)
            day = cols[2].get_text(strip=True)
            start = cols[3].get_text(strip=True)
            end = cols[4].get_text(strip=True)
    
            event_text = f"""🗓 {subject}
    📅 {day} {week}
    ⏳ {start} → {end}"""
            events.append(event_text)
    
        if not events:
            return "ما لقيت أحداث حالياً 🤷‍♂️"
    
        return events[0]  # أول حدث فعال
    
    def get_current_week_type():
        start_date = datetime.strptime("13/09/2025", "%d/%m/%Y")
        today = datetime.today()
        
        delta_days = (today - start_date).days
        if delta_days < 0:
            return "📅 الأسبوع الحالي: لم يبدأ بعد"
    
        week_number = delta_days // 7
        if week_number % 2 == 0:
            return "📅 الأسبوع الحالي: فردي"
        else:
            return "📅 الأسبوع الحالي: زوجي"

    @staticmethod
    def get_full_current_semester_calendar():
        try:
            res = requests.get(cel, timeout=10)
            res.raise_for_status()
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
        
            # البحث عن جميع الفصول
            semesters = soup.find_all("div", class_="text-warning")
            if not semesters:
                return "لم أتمكن من العثور على أي فصول."
        
            # تحديد الفصل الحالي بناءً على التاريخ الحالي (تحسين)
            current_date = datetime.now()
            current_semester_div = None
            
            for semester_div in semesters:
                # محاولة استخراج تاريخ بداية الفصل من الجدول التالي
                table = semester_div.find_next_sibling("table")
                if not table:
                    continue
                    
                # البحث عن تاريخ بداية الفصل في الجدول
                start_date_found = False
                for row in table.find_all("tr"):
                    cols = row.find_all("td")
                    if len(cols) >= 5:
                        date_text = cols[3].get_text(strip=True)
                        if date_text and date_text != "من :":
                            try:
                                event_date = datetime.strptime(date_text, "%d/%m/%Y")
                                if event_date <= current_date:
                                    start_date_found = True
                                    break
                            except ValueError:
                                continue
                
                if start_date_found:
                    current_semester_div = semester_div
                    break
            
            # إذا لم نجد فصلًا مناسبًا، نأخذ آخر فصل
            if not current_semester_div:
                current_semester_div = semesters[-1]
        
            # الحصول على الجدول التالي للفصل
            table = current_semester_div.find_next_sibling("table")
            if not table:
                return "لم أتمكن من العثور على جدول الأحداث للفصل الحالي."
        
            # استخراج الأحداث مع تصفية الصفوف غير النشطة
            events = []
            rows = table.find_all("tr")
            
            for row in rows:
                # تخطي الصفوف غير النشطة (المنتهية)
                if "text-not-active" in row.get("class", []):
                    continue
                    
                cols = row.find_all("td")
                if len(cols) < 5:
                    continue
                    
                subject = cols[0].get_text(strip=True).replace("الموضوع : ", "")
                week = cols[1].get_text(strip=True).replace("الاسبوع : ", "")
                day = cols[2].get_text(strip=True).replace("اليوم : ", "")
                start = cols[3].get_text(strip=True).replace("من : ", "")
                end = cols[4].get_text(strip=True).replace("الى : ", "")
    
                event_text = f"""🗓 {subject}
    📅 {day} {week}
    ⏳ {start} → {end}"""
                events.append(event_text)
        
            if not events:
                return "لا يوجد أحداث للفصل الحالي 🤷‍♂️"
        
            # إضافة عنوان الفصل
            semester_title = current_semester_div.get_text(strip=True)
            result = f"📚 {semester_title}\n\n" + "\n\n".join(events)
            
            return result
            
        except requests.RequestException:
            return "حدث خطأ في الاتصال بالخادم. يرجى المحاولة لاحقًا."
        except Exception as e:
            return f"حدث خطأ غير متوقع: {str(e)}"





    def update_student_data(self, chat_id: int) -> bool:


        """تحديث بيانات الطالب في قاعدة البيانات"""
        try:
            logger.info(f"Attempting to update data for student: {self.student_id}")
            
            # تسجيل الدخول
            if not self.login():
                logger.error(f"Login failed for student: {self.student_id}")
                return False
            
            # جلب البيانات
            study_plan_data = self.fetch_study_plan()
            
            if not study_plan_data:
                logger.error(f"No study plan data returned for student: {self.student_id}")
                return False
            
            if study_plan_data.get('status') != 'success':
                error_msg = study_plan_data.get('error', 'Unknown error')
                logger.error(f"Failed to fetch study plan for student {self.student_id}: {error_msg}")
                return False
            
            # حفظ في قاعدة البيانات
            save_student_stats(chat_id, study_plan_data.get('stats', {}))
            save_student_courses(chat_id, study_plan_data.get('courses', []))
            
            logger.info(f"Successfully updated data for student: {self.student_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error in update_student_data for student {self.student_id}: {str(e)}")
            return False

    def fetch_study_plan(self) -> Dict[str, Any]:
        """جلب الخطة الدراسية الكاملة للطالب"""
        try:
            # أولاً نحتاج إلى زيارة الصفحة الرئيسية للحصول على الجلسة الصحيحة
            self.session.get("https://portal.qou.edu/student/index.do", headers=self.headers)
            
            # الآن نجلب صفحة الخطة الدراسية
            response = self.session.get(STUDY_PLAN_URL, headers=self.headers, timeout=30)
            response.raise_for_status()
            
            # التحقق من أننا لسنا في صفحة الخطأ
            if "errorPage.jsp" in response.url or "الخطة الدراسية" not in response.text:
                logger.warning(f"Redirected to error page or invalid page for {self.student_id}")
                return {
                    'stats': {},
                    'courses': [],
                    'last_updated': datetime.now().isoformat(),
                    'status': 'error',
                    'error': 'Invalid or error page reached'
                }
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # استخراج الإحصائيات العامة
            stats = self._extract_study_stats(soup)
            
            # استخراج المقررات
            courses = self._extract_courses(soup)
            
            return {
                'stats': stats,
                'courses': courses,
                'last_updated': datetime.now().isoformat(),
                'status': 'success'
            }
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while fetching study plan for {self.student_id}")
            return {
                'stats': {},
                'courses': [],
                'last_updated': datetime.now().isoformat(),
                'status': 'error',
                'error': 'Request timeout'
            }
        except Exception as e:
            logger.error(f"Error fetching study plan for {self.student_id}: {e}")
            return {
                'stats': {},
                'courses': [],
                'last_updated': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e)
            }
    
    def _extract_study_stats(self, soup) -> Dict[str, Any]:
        """استخراج الإحصائيات الدراسية من الصفحة"""
        stats = {
            'total_hours_required': 0,
            'total_hours_completed': 0,
            'total_hours_transferred': 0,
            'semesters_count': 0,
            'plan_completed': False,
            'completion_percentage': 0
        }
        
        try:
            # البحث عن الإحصائيات في الهيكل
            stats_table = soup.find('table', class_='table')
            if not stats_table:
                # محاولة بديلة للعثور على الإحصائيات
                stats_elements = soup.select('.form-group .control-label, .form-group .col-sm-2')
                if stats_elements:
                    for i in range(0, len(stats_elements), 2):
                        if i+1 < len(stats_elements):
                            label = stats_elements[i].get_text(strip=True)
                            value = stats_elements[i+1].get_text(strip=True)
                            
                            if 'عدد الساعات المطلوبة' in label:
                                stats['total_hours_required'] = self._parse_number(value)
                            elif 'عدد الساعات المجتازة' in label:
                                stats['total_hours_completed'] = self._parse_number(value)
                            elif 'عدد الساعات المحتسبة' in label:
                                stats['total_hours_transferred'] = self._parse_number(value)
                            elif 'عدد الفصول' in label:
                                stats['semesters_count'] = self._parse_number(value)
                            elif 'انهى الخطة' in label:
                                stats['plan_completed'] = 'نعم' in value or 'yes' in value.lower()
                return stats
            
            # إذا وجدنا الجدول، نستخرج البيانات منه
            rows = stats_table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) == 2:
                    label = cols[0].get_text(strip=True)
                    value = cols[1].get_text(strip=True)
                    
                    if 'عدد الساعات المطلوبة' in label:
                        stats['total_hours_required'] = self._parse_number(value)
                    elif 'عدد الساعات المجتازة' in label:
                        stats['total_hours_completed'] = self._parse_number(value)
                    elif 'عدد الساعات المحتسبة' in label:
                        stats['total_hours_transferred'] = self._parse_number(value)
                    elif 'عدد الفصول' in label:
                        stats['semesters_count'] = self._parse_number(value)
                    elif 'انهى الخطة' in label:
                        stats['plan_completed'] = 'نعم' in value or 'yes' in value.lower()
        
            # حساب نسبة الإنجاز
            if stats['total_hours_required'] > 0:
                completed = stats['total_hours_completed'] + stats['total_hours_transferred']
                stats['completion_percentage'] = round((completed / stats['total_hours_required']) * 100, 2)
            
        except Exception as e:
            logger.error(f"Error extracting stats: {e}")
        
        return stats
    
    def _extract_courses(self, soup) -> List[Dict[str, Any]]:
        """استخراج المقررات الدراسية"""
        courses = []
        
        try:
            # البحث عن أقسام المقررات - تحسين انتقائية العناصر
            course_sections = soup.find_all('div', class_=lambda x: x and ('member-card' in x or 'panel' in x or 'card' in x))
            
            if not course_sections:
                # محاولة بديلة للعثور على المقررات
                course_tables = soup.find_all('table', class_='table')
                for table in course_tables:
                    # تخطي جدول الإحصائيات إذا كان موجوداً
                    if table.find_previous_sibling('h4') or table.find_previous_sibling('h3'):
                        section_title = table.find_previous_sibling('h4') or table.find_previous_sibling('h3')
                        category = section_title.get_text(strip=True) if section_title else 'غير مصنف'
                        
                        rows = table.find_all('tr')[1:]  # تخطي رأس الجدول
                        for row in rows:
                            cols = row.find_all('td')
                            if len(cols) >= 4:  # عدد أعمدة أقل قد يكون مقبولاً
                                course_data = self._parse_course_row(cols, category)
                                if course_data:
                                    courses.append(course_data)
                return courses
            
            for section in course_sections:
                # استخراج نوع القسم
                section_title = section.find('h4') or section.find('h3') or section.find('h2')
                category = section_title.get_text(strip=True) if section_title else 'غير مصنف'
                
                # استخراج جدول المقررات
                table = section.find('table')
                if table:
                    rows = table.find_all('tr')[1:]  # تخطي رأس الجدول
                    
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 4:  # تقليل الحد الأدنى للأعمدة
                            course_data = self._parse_course_row(cols, category)
                            if course_data:
                                courses.append(course_data)
        
        except Exception as e:
            logger.error(f"Error extracting courses: {e}")
        
        return courses
    
    def _parse_course_row(self, cols, category) -> Optional[Dict[str, Any]]:
        """تحليل صف المقرر"""
        try:
            # حالة المقرر (من الأيقونة أو النص)
            status = 'unknown'
            status_icon = cols[0].find('i')
            if status_icon:
                status_classes = status_icon.get('class', [])
                status = self._get_course_status(status_classes)  # التصحيح هنا
            else:
                # محاولة تحديد الحالة من النص إذا لم توجد أيقونة
                status_text = cols[0].get_text(strip=True).lower()
                if 'ناجح' in status_text or 'completed' in status_text:
                    status = 'completed'
                elif 'راسب' in status_text or 'failed' in status_text:
                    status = 'failed'
                elif 'مسجل' in status_text or 'in progress' in status_text:
                    status = 'in_progress'
            
            # رمز المقرر
            course_code = cols[1].get_text(strip=True)
            course_code_elem = cols[1].find('a')
            if course_code_elem:
                course_code = course_code_elem.get_text(strip=True)
            
            # اسم المقرر
            course_name = cols[2].get_text(strip=True) if len(cols) > 2 else ''
            
            # عدد الساعات
            hours_text = cols[3].get_text(strip=True) if len(cols) > 3 else '0'
            hours = self._parse_number(hours_text)
            
            # الحالة التفصيلية
            detailed_status = cols[4].get_text(strip=True) if len(cols) > 4 else ''
            
            return {
                'course_code': course_code,
                'course_name': course_name,
                'category': category,
                'hours': hours,
                'status': status,
                'detailed_status': detailed_status,
                'is_elective': 'اختياري' in category or 'elective' in category.lower()
            }
            
        except Exception as e:
            logger.error(f"Error parsing course row: {e}")
            return None


    def _get_course_status(self, class_list):
        """تحديد حالة المقرر بناءً على كلاسات الأيقونة"""
        if not class_list:
            return 'unknown'
        
        # تحويل القائمة إلى سلسلة نصية للبحث
        classes_str = ' '.join(str(cls) for cls in class_list).lower()
        
        status_map = {
            'completed': ['fa-check', 'text-success', 'success', 'ناجح', 'passed', 'مكتمل'],
            'failed': ['fa-times', 'text-danger', 'danger', 'راسب', 'failed', 'فاشل'],
            'in_progress': ['fa-spinner', 'text-warning', 'warning', 'active', 'مسجل', 'registered', 'قيد التقدم'],
            'not_taken': ['fa-circle', 'text-muted', 'muted', 'لم يؤخذ', 'not taken', 'غير مأخوذ'],
            'registered': ['fa-book', 'text-info', 'info', 'مسجل', 'registered']
        }
        
        for status, keywords in status_map.items():
            if any(keyword.lower() in classes_str for keyword in keywords):
                return status
        
        return 'unknown'
