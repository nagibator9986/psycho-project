import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import uuid
from sqlalchemy import func
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///psych_help.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['REPORT_FOLDER'] = 'static/reports'

db = SQLAlchemy(app)

# Модели базы данных
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' или 'psychologist'
    full_name = db.Column(db.String(100))
    bio = db.Column(db.Text)
    profile_pic = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    comments = db.relationship('Comment', backref='author', lazy=True)
    tests = db.relationship('Test', backref='creator', lazy=True)
    test_results = db.relationship('TestResult', backref='user', lazy=True)
    messages_sent = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    messages_received = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy=True)
    reports = db.relationship('StudentReport', foreign_keys='StudentReport.student_id', backref='student', lazy=True)
    appointments = db.relationship('Appointment', foreign_keys='Appointment.student_id', backref='student', lazy=True)
    psychologist_appointments = db.relationship('Appointment', foreign_keys='Appointment.psychologist_id', backref='psychologist', lazy=True)
    meeting_protocols = db.relationship('MeetingProtocol', foreign_keys='MeetingProtocol.student_id', backref='student', lazy=True)
    psychologist_protocols = db.relationship('MeetingProtocol', foreign_keys='MeetingProtocol.psychologist_id', backref='psychologist', lazy=True)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    author = db.relationship('User', backref='posts', lazy=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_anonymous = db.Column(db.Boolean, default=False)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    questions = db.relationship('Question', backref='test', lazy=True, cascade='all, delete-orphan')
    results = db.relationship('TestResult', backref='test', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    question_type = db.Column(db.String(20), nullable=False)
    
    options = db.relationship('QuestionOption', backref='question', lazy=True, cascade='all, delete-orphan')

class QuestionOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    score = db.Column(db.Integer)

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    score = db.Column(db.Integer)
    result_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    answers = db.relationship('TestAnswer', backref='test_result', lazy=True, cascade='all, delete-orphan')

class TestAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_result_id = db.Column(db.Integer, db.ForeignKey('test_result.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer_text = db.Column(db.Text)
    option_id = db.Column(db.Integer, db.ForeignKey('question_option.id'))
    
    option = db.relationship('QuestionOption')
    question = db.relationship('Question', backref='answers')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    image_url = db.Column(db.String(200))
    user = db.relationship('User', backref='authored_articles', lazy=True)

class StudentReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    psychologist_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    academic_performance = db.Column(db.Text)
    emotional_state = db.Column(db.Text)
    social_interaction = db.Column(db.Text)
    stress_level = db.Column(db.Text)
    sleep_quality = db.Column(db.Text)
    motivation = db.Column(db.Text)
    behavior_patterns = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    additional_notes = db.Column(db.Text)
    pdf_filename = db.Column(db.String(100))

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    psychologist_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    purpose = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    psychologist_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='planned')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    protocols = db.relationship('MeetingProtocol', backref='meeting', lazy=True, cascade='all, delete-orphan')
    student = db.relationship('User', foreign_keys=[student_id], backref='student_meetings', lazy='joined')
    psychologist = db.relationship('User', foreign_keys=[psychologist_id], backref='psychologist_meetings', lazy='joined')
class MeetingRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    proposed_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MeetingProtocol(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    psychologist_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    session_date = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer)  # В минутах
    topics_discussed = db.Column(db.Text)
    emotional_state = db.Column(db.Text)
    progress_notes = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    homework = db.Column(db.Text)
    additional_comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    pdf_filename = db.Column(db.String(100))

# Создаем таблицы и тестовые данные
with app.app_context():
    db.drop_all()
    db.create_all()

    users = [
        User(username="anna_s", email="anna_s@example.com", password=generate_password_hash("password123"), role="student", full_name="Анна Смирнова", bio="Студентка 3 курса, интересуюсь психологией и саморазвитием.", created_at=datetime.utcnow() - timedelta(days=30)),
        User(username="mike_p", email="mike_p@example.com", password=generate_password_hash("password123"), role="student", full_name="Михаил Петров", bio="Учусь на инженера, иногда чувствую стресс из-за учебы.", created_at=datetime.utcnow() - timedelta(days=25)),
        User(username="lena_k", email="lena_k@example.com", password=generate_password_hash("password123"), role="student", full_name="Елена Козлова", bio="Люблю читать и узнавать новое о ментальном здоровье.", created_at=datetime.utcnow() - timedelta(days=20)),
        User(username="dr_ivanov", email="ivanov@example.com", password=generate_password_hash("password123"), role="psychologist", full_name="Игорь Иванов", bio="Психолог с 10-летним опытом, специализируюсь на студентах.", created_at=datetime.utcnow() - timedelta(days=40)),
        User(username="dr_sokolova", email="sokolova@example.com", password=generate_password_hash("password123"), role="psychologist", full_name="Марина Соколова", bio="Помогаю справляться с тревогой и стрессом.", created_at=datetime.utcnow() - timedelta(days=35)),
    ]
    db.session.add_all(users)
    db.session.commit()

    posts = [
        Post(title="Как справляться с экзаменационным стрессом?", content="Чувствую сильное волнение перед экзаменами. Какие техники помогут успокоиться?", user_id=1, created_at=datetime.utcnow() - timedelta(days=10)),
        Post(title="Советы по тайм-менеджменту", content="Кто-нибудь знает, как лучше планировать время, чтобы все успевать?", user_id=2, created_at=datetime.utcnow() - timedelta(days=8)),
        Post(title="Почему я так быстро устаю?", content="Последнее время быстро устаю, даже если не делаю ничего сложного. Это нормально?", user_id=3, created_at=datetime.utcnow() - timedelta(days=5)),
    ]
    db.session.add_all(posts)
    db.session.commit()

    comments = [
        Comment(content="Попробуй дыхательные упражнения, они реально помогают!", user_id=4, post_id=1, created_at=datetime.utcnow() - timedelta(days=9), is_anonymous=False),
        Comment(content="Мне помогает медитация перед сном.", user_id=3, post_id=1, created_at=datetime.utcnow() - timedelta(days=8), is_anonymous=True),
        Comment(content="Планируй задачи на день с вечера, так легче.", user_id=5, post_id=2, created_at=datetime.utcnow() - timedelta(days=7), is_anonymous=False),
        Comment(content="Это может быть связано с недостатком сна.", user_id=4, post_id=3, created_at=datetime.utcnow() - timedelta(days=4), is_anonymous=False),
    ]
    db.session.add_all(comments)
    db.session.commit()

    tests = [
        Test(title="Тест на уровень стресса", description="Оцените ваш уровень стресса за последние две недели.", user_id=4, created_at=datetime.utcnow() - timedelta(days=15), is_active=True),
        Test(title="Тест на тревожность", description="Проверьте, насколько вы склонны к тревоге.", user_id=5, created_at=datetime.utcnow() - timedelta(days=12), is_active=True),
        Test(title="Тест на эмоциональное выгорание", description="Узнайте, есть ли у вас признаки выгорания.", user_id=4, created_at=datetime.utcnow() - timedelta(days=10), is_active=False),
    ]
    db.session.add_all(tests)
    db.session.commit()

    questions = [
        Question(text="Как часто вы чувствовали себя раздраженным в последнее время?", test_id=1, question_type="single_choice"),
        Question(text="Как часто вы испытывали трудности с засыпанием?", test_id=1, question_type="single_choice"),
        Question(text="Опишите, что вызывает у вас стресс.", test_id=1, question_type="text"),
        Question(text="Чувствуете ли вы беспричинное беспокойство?", test_id=2, question_type="single_choice"),
        Question(text="Как часто вы беспокоитесь о будущем?", test_id=2, question_type="single_choice"),
        Question(text="Чувствуете ли вы усталость даже после отдыха?", test_id=3, question_type="single_choice"),
        Question(text="Сложно ли вам сосредоточиться на задачах?", test_id=3, question_type="single_choice"),
    ]
    db.session.add_all(questions)
    db.session.commit()

    options = [
        QuestionOption(text="Никогда", question_id=1, score=0),
        QuestionOption(text="Иногда", question_id=1, score=2),
        QuestionOption(text="Часто", question_id=1, score=4),
        QuestionOption(text="Постоянно", question_id=1, score=6),
        QuestionOption(text="Никогда", question_id=2, score=0),
        QuestionOption(text="Редко", question_id=2, score=2),
        QuestionOption(text="Иногда", question_id=2, score=4),
        QuestionOption(text="Часто", question_id=2, score=6),
        QuestionOption(text="Никогда", question_id=4, score=0),
        QuestionOption(text="Редко", question_id=4, score=2),
        QuestionOption(text="Иногда", question_id=4, score=4),
        QuestionOption(text="Часто", question_id=4, score=6),
        QuestionOption(text="Никогда", question_id=5, score=0),
        QuestionOption(text="Редко", question_id=5, score=2),
        QuestionOption(text="Иногда", question_id=5, score=4),
        QuestionOption(text="Часто", question_id=5, score=6),
        QuestionOption(text="Нет", question_id=6, score=0),
        QuestionOption(text="Иногда", question_id=6, score=3),
        QuestionOption(text="Часто", question_id=6, score=6),
        QuestionOption(text="Нет", question_id=7, score=0),
        QuestionOption(text="Иногда", question_id=7, score=3),
        QuestionOption(text="Часто", question_id=7, score=6),
    ]
    db.session.add_all(options)
    db.session.commit()

    test_results = [
        TestResult(user_id=1, test_id=1, score=8, result_text="Средний уровень. Есть некоторые проблемы, но в целом ситуация под контролем.", created_at=datetime.utcnow() - timedelta(days=5)),
        TestResult(user_id=2, test_id=1, score=12, result_text="Средний уровень. Есть некоторые проблемы, но в целом ситуация под контролем.", created_at=datetime.utcnow() - timedelta(days=4)),
        TestResult(user_id=3, test_id=2, score=6, result_text="Низкий уровень. Рекомендуется консультация психолога.", created_at=datetime.utcnow() - timedelta(days=3)),
    ]
    db.session.add_all(test_results)
    db.session.commit()

    test_answers = [
        TestAnswer(test_result_id=1, question_id=1, option_id=2),
        TestAnswer(test_result_id=1, question_id=2, option_id=7),
        TestAnswer(test_result_id=1, question_id=3, answer_text="Учеба и экзамены."),
        TestAnswer(test_result_id=2, question_id=1, option_id=3),
        TestAnswer(test_result_id=2, question_id=2, option_id=8),
        TestAnswer(test_result_id=2, question_id=3, answer_text="Дедлайны по проектам."),
        TestAnswer(test_result_id=3, question_id=4, option_id=10),
        TestAnswer(test_result_id=3, question_id=5, option_id=14),
    ]
    db.session.add_all(test_answers)
    db.session.commit()

    messages = [
        Message(content="Здравствуйте, можно записаться на консультацию?", sender_id=1, recipient_id=4, is_anonymous=False, created_at=datetime.utcnow() - timedelta(days=7)),
        Message(content="Конечно, выберите удобное время.", sender_id=4, recipient_id=1, is_anonymous=False, created_at=datetime.utcnow() - timedelta(days=6), is_read=True),
        Message(content="У меня проблемы со сном, что делать?", sender_id=2, recipient_id=5, is_anonymous=True, created_at=datetime.utcnow() - timedelta(days=5)),
        Message(content="Попробуйте расслабляющую медитацию перед сном.", sender_id=5, recipient_id=2, is_anonymous=False, created_at=datetime.utcnow() - timedelta(days=4), is_read=False),
    ]
    db.session.add_all(messages)
    db.session.commit()

    articles = [
        Article(title="Как справляться с тревогой", content="Тревога — нормальная реакция на стресс, но иногда она выходит из-под контроля. Попробуйте техники дыхания и ведение дневника.", user_id=4, created_at=datetime.utcnow() - timedelta(days=14)),
        Article(title="Почему важен сон для студентов", content="Недостаток сна влияет на концентрацию и настроение. Старайтесь спать 7-8 часов.", user_id=5, created_at=datetime.utcnow() - timedelta(days=10)),
    ]
    db.session.add_all(articles)
    db.session.commit()

    reports = [
        StudentReport(
            student_id=1,
            psychologist_id=4,
            created_at=datetime.utcnow() - timedelta(days=3),
            academic_performance="Хорошая успеваемость, но иногда пропускает дедлайны.",
            emotional_state="Часто испытывает тревогу перед экзаменами.",
            social_interaction="Активно общается с друзьями, но иногда избегает больших групп.",
            stress_level="Средний уровень стресса.",
            sleep_quality="Проблемы с засыпанием из-за мыслей об учебе.",
            motivation="Высокая, но снижается при неудачах.",
            behavior_patterns="Склонность к прокрастинации.",
            recommendations="Рекомендуется практика mindfulness и планирование задач.",
            additional_notes="Студентка заинтересована в самопознании.",
            pdf_filename="report_1_sample.pdf"
        ),
        StudentReport(
            student_id=2,
            psychologist_id=5,
            created_at=datetime.utcnow() - timedelta(days=2),
            academic_performance="Средняя успеваемость, трудно справляется с математикой.",
            emotional_state="Чувствует себя подавленным из-за давления.",
            social_interaction="Мало общается, предпочитает одиночество.",
            stress_level="Высокий уровень стресса.",
            sleep_quality="Спит 5-6 часов, часто просыпается.",
            motivation="Низкая, трудно найти цель.",
            behavior_patterns="Избегает сложных задач.",
            recommendations="Рекомендуется консультация и упражнения на релаксацию.",
            additional_notes="Нуждается в поддержке.",
            pdf_filename="report_2_sample.pdf"
        ),
    ]
    db.session.add_all(reports)
    db.session.commit()

    appointments = [
        Appointment(student_id=1, psychologist_id=4, appointment_date=datetime.utcnow() + timedelta(days=2), purpose="Обсуждение тревожности", status="pending", created_at=datetime.utcnow() - timedelta(days=1)),
        Appointment(student_id=2, psychologist_id=5, appointment_date=datetime.utcnow() + timedelta(days=3), purpose="Работа со стрессом", status="confirmed", created_at=datetime.utcnow() - timedelta(days=2)),
    ]
    db.session.add_all(appointments)
    db.session.commit()

    meetings = [
        Meeting(student_id=1, psychologist_id=4, scheduled_at=datetime.utcnow() - timedelta(days=1), status="completed", created_at=datetime.utcnow() - timedelta(days=2)),
        Meeting(student_id=3, psychologist_id=5, scheduled_at=datetime.utcnow() + timedelta(days=4), status="planned", created_at=datetime.utcnow() - timedelta(days=1)),
    ]
    db.session.add_all(meetings)
    db.session.commit()

    meeting_requests = [
        MeetingRequest(sender_id=3, receiver_id=4, proposed_time=datetime.utcnow() + timedelta(days=5), status="pending", message="Хочу обсудить проблемы с концентрацией.", created_at=datetime.utcnow() - timedelta(days=1)),
        MeetingRequest(sender_id=2, receiver_id=5, proposed_time=datetime.utcnow() + timedelta(days=6), status="accepted", message="Нужна помощь с мотивацией.", created_at=datetime.utcnow() - timedelta(days=2)),
    ]
    db.session.add_all(meeting_requests)
    db.session.commit()

    protocols = [
        MeetingProtocol(
            meeting_id=1,
            student_id=1,
            psychologist_id=4,
            session_date=datetime.utcnow() - timedelta(days=1),
            duration=60,
            topics_discussed="Тревожность перед экзаменами, стратегии релаксации",
            emotional_state="Студентка выглядела напряженной, но открытой к обсуждению",
            progress_notes="Начали работу над дыхательными упражнениями, заметен небольшой прогресс",
            recommendations="Продолжать дыхательные упражнения, начать вести дневник мыслей",
            homework="Ежедневно практиковать 5 минут дыхательной гимнастики",
            additional_comments="Анна заинтересована в дальнейшем сотрудничестве",
            pdf_filename="protocol_1_sample.pdf"
        ),
    ]
    db.session.add_all(protocols)
    db.session.commit()

# Вспомогательные функции
def is_psychologist():
    return 'user_id' in session and User.query.get(session['user_id']).role == 'psychologist'

def is_student():
    return 'user_id' in session and User.query.get(session['user_id']).role == 'student'

def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

app.jinja_env.globals.update(
    get_current_user=get_current_user,
    is_psychologist=is_psychologist,
    is_student=is_student
)

def generate_pdf_report(report):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    font_path = "C:/Windows/Fonts/Arial.ttf" if os.name == 'nt' else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    pdfmetrics.registerFont(TTFont('Arial', font_path))
    styles['Title'].fontName = 'Arial'
    styles['Normal'].fontName = 'Arial'
    styles['BodyText'].fontName = 'Arial'

    elements = []
    student_name = report.student.full_name if report.student and report.student.full_name else "Неизвестный студент"
    elements.append(Paragraph(f"Отчет о студенте: {student_name}", styles['Title']))
    elements.append(Spacer(1, 12))
    
    psychologist = User.query.get(report.psychologist_id)
    psychologist_name = psychologist.full_name if psychologist and psychologist.full_name else "Неизвестный психолог"
    
    created_at_str = report.created_at.strftime('%d.%m.%Y %H:%M') if report.created_at else "Дата не указана"
    
    data = [
        ["Параметр", "Описание"],
        ["Дата создания", created_at_str],
        ["Психолог", psychologist_name],
        ["Учебная успеваемость", report.academic_performance or "Не указано"],
        ["Эмоциональное состояние", report.emotional_state or "Не указано"],
        ["Социальное взаимодействие", report.social_interaction or "Не указано"],
        ["Уровень стресса", report.stress_level or "Не указано"],
        ["Качество сна", report.sleep_quality or "Не указано"],
        ["Мотивация", report.motivation or "Не указано"],
        ["Поведенческие паттерны", report.behavior_patterns or "Не указано"],
        ["Рекомендации", report.recommendations or "Не указано"],
        ["Дополнительные заметки", report.additional_notes or "Не указано"],
    ]
    
    table = Table(data, colWidths=[150, 400])
    table.setStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ])
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_protocol_pdf(protocol):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    font_path = "C:/Windows/Fonts/Arial.ttf" if os.name == 'nt' else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    pdfmetrics.registerFont(TTFont('Arial', font_path))
    styles['Title'].fontName = 'Arial'
    styles['Normal'].fontName = 'Arial'
    styles['BodyText'].fontName = 'Arial'

    elements = []
    student_name = protocol.student.full_name if protocol.student and protocol.student.full_name else "Неизвестный студент"
    elements.append(Paragraph(f"Протокол встречи: {student_name}", styles['Title']))
    elements.append(Spacer(1, 12))
    
    psychologist = User.query.get(protocol.psychologist_id)
    psychologist_name = psychologist.full_name if psychologist and psychologist.full_name else "Неизвестный психолог"
    
    session_date_str = protocol.session_date.strftime('%d.%m.%Y %H:%M') if protocol.session_date else "Дата не указана"
    
    data = [
        ["Параметр", "Описание"],
        ["Дата встречи", session_date_str],
        ["Психолог", psychologist_name],
        ["Продолжительность (мин)", str(protocol.duration or "Не указано")],
        ["Обсуждаемые темы", protocol.topics_discussed or "Не указано"],
        ["Эмоциональное состояние", protocol.emotional_state or "Не указано"],
        ["Заметки о прогрессе", protocol.progress_notes or "Не указано"],
        ["Рекомендации", protocol.recommendations or "Не указано"],
        ["Домашнее задание", protocol.homework or "Не указано"],
        ["Дополнительные комментарии", protocol.additional_comments or "Не указано"],
    ]
    
    table = Table(data, colWidths=[150, 400])
    table.setStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Arial'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ])
    elements.append(table)
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Маршруты
@app.route('/')
def index():
    posts = Post.query.order_by(Post.created_at.desc()).limit(3).all()
    psychologists = User.query.filter_by(role='psychologist').order_by(func.random()).limit(3).all()
    articles = Article.query.order_by(Article.created_at.desc()).limit(3).all()
    return render_template('index.html', posts=posts, psychologists=psychologists, articles=articles)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        full_name = request.form.get('full_name', '')

        if User.query.filter_by(username=username).first():
            flash('Это имя пользователя уже занято', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Этот email уже используется', 'danger')
            return redirect(url_for('register'))

        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            role=role,
            full_name=full_name
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Регистрация прошла успешно! Теперь вы можете войти.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            flash('Вы успешно вошли в систему!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    
    if user.role == 'psychologist':
        tests = Test.query.filter_by(user_id=user.id).order_by(Test.created_at.desc()).limit(5).all()
        posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).limit(5).all()
        unread_messages = Message.query.filter_by(recipient_id=user.id, is_read=False).count()
        students_count = User.query.filter_by(role='student').count()
        pending_appointments = Appointment.query.filter_by(psychologist_id=user.id, status='pending').count()
        
        upcoming_meetings = Meeting.query.filter_by(psychologist_id=user.id, status='planned').order_by(Meeting.scheduled_at.asc()).limit(5).all()
        past_meetings = Meeting.query.filter_by(psychologist_id=user.id, status='completed').order_by(Meeting.scheduled_at.desc()).limit(5).all()
        
        return render_template('psychologist_dashboard.html', user=user, tests=tests, posts=posts, 
                             unread_messages=unread_messages, students_count=students_count, 
                             pending_appointments=pending_appointments, 
                             upcoming_meetings=upcoming_meetings, past_meetings=past_meetings)
    else:
        available_tests = Test.query.filter_by(is_active=True).order_by(func.random()).limit(3).all()
        recent_results = TestResult.query.filter_by(user_id=user.id).order_by(TestResult.created_at.desc()).limit(3).all()
        unread_messages = Message.query.filter_by(recipient_id=user.id, is_read=False).count()
        upcoming_appointments = Appointment.query.filter_by(student_id=user.id, status='confirmed').order_by(Appointment.appointment_date.asc()).limit(3).all()
        
        return render_template('student_dashboard.html', user=user, available_tests=available_tests, 
                             recent_results=recent_results, unread_messages=unread_messages, 
                             upcoming_appointments=upcoming_appointments)

@app.route('/profile/<username>')
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()).limit(5).all()
    
    can_edit = 'user_id' in session and session['user_id'] == user.id
    
    return render_template('profile.html', user=user, posts=posts, can_edit=can_edit)

@app.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    
    if request.method == 'POST':
        user.full_name = request.form.get('full_name', user.full_name)
        user.bio = request.form.get('bio', user.bio)
        
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                user.profile_pic = filename
        
        db.session.commit()
        flash('Профиль успешно обновлен', 'success')
        return redirect(url_for('profile', username=user.username))
    
    return render_template('edit_profile.html', user=user)

@app.route('/tests')
def tests():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_current_user()
    
    if user.role == 'psychologist':
        tests = Test.query.filter_by(user_id=user.id).order_by(Test.created_at.desc()).all()
        total_students = User.query.filter_by(role='student').count()
        total_results = TestResult.query.join(Test).filter(Test.user_id==user.id).count()
        return render_template('psychologist_tests.html', tests=tests, 
                             total_students=total_students, total_results=total_results)
    else:
        available_tests = Test.query.filter_by(is_active=True).order_by(Test.created_at.desc()).all()
        my_results = {result.test_id: result for result in TestResult.query.filter_by(user_id=user.id).all()}
        return render_template('student_tests.html', tests=available_tests, my_results=my_results)

@app.route('/tests/create', methods=['GET', 'POST'])
def create_test():
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form.get('description', '')
        
        test = Test(
            title=title,
            description=description,
            user_id=session['user_id']
        )
        
        db.session.add(test)
        db.session.commit()
        
        flash('Тест создан! Теперь добавьте вопросы.', 'success')
        return redirect(url_for('add_questions', test_id=test.id))
    
    return render_template('create_test.html')

@app.route('/tests/<int:test_id>/add_questions', methods=['GET', 'POST'])
def add_questions(test_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    test = Test.query.get_or_404(test_id)
    
    if test.user_id != session['user_id']:
        flash('У вас нет прав для редактирования этого теста', 'danger')
        return redirect(url_for('tests'))
    
    if request.method == 'POST':
        question_type = request.form['question_type']
        text = request.form['text']
        
        question = Question(
            text=text,
            question_type=question_type,
            test_id=test_id
        )
        
        db.session.add(question)
        db.session.commit()
        
        if question_type in ['single_choice', 'multiple_choice']:
            options = zip(
                request.form.getlist('option_text[]'),
                request.form.getlist('option_score[]')
            )
            
            for opt_text, opt_score in options:
                if opt_text.strip():
                    option = QuestionOption(
                        text=opt_text,
                        score=int(opt_score) if opt_score else 0,
                        question_id=question.id
                    )
                    db.session.add(option)
            
            db.session.commit()
        
        flash('Вопрос добавлен!', 'success')
        return redirect(url_for('add_questions', test_id=test_id))
    
    return render_template('add_questions.html', test=test)

@app.route('/tests/<int:test_id>/edit', methods=['GET', 'POST'])
def edit_test(test_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    test = Test.query.get_or_404(test_id)
    
    if test.user_id != session['user_id']:
        flash('У вас нет прав для редактирования этого теста', 'danger')
        return redirect(url_for('tests'))
    
    if request.method == 'POST':
        test.title = request.form['title']
        test.description = request.form.get('description', '')
        test.is_active = 'is_active' in request.form
        
        db.session.commit()
        flash('Тест обновлен', 'success')
        return redirect(url_for('tests'))
    
    return render_template('edit_test.html', test=test)

@app.route('/tests/<int:test_id>/delete', methods=['POST'])
def delete_test(test_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    test = Test.query.get_or_404(test_id)
    
    if test.user_id != session['user_id']:
        flash('У вас нет прав для удаления этого теста', 'danger')
        return redirect(url_for('tests'))
    
    db.session.delete(test)
    db.session.commit()
    
    flash('Тест удален', 'success')
    return redirect(url_for('tests'))

@app.route('/tests/<int:test_id>/take', methods=['GET', 'POST'])
def take_test(test_id):
    if 'user_id' not in session or not is_student():
        return redirect(url_for('login'))

    test = Test.query.get_or_404(test_id)
    
    if not test.is_active:
        flash('Этот тест сейчас недоступен', 'danger')
        return redirect(url_for('tests'))
    
    existing_result = TestResult.query.filter_by(user_id=session['user_id'], test_id=test_id).first()
    if existing_result:
        flash('Вы уже проходили этот тест', 'info')
        return redirect(url_for('test_result', result_id=existing_result.id))
    
    if request.method == 'POST':
        test_result = TestResult(
            user_id=session['user_id'],
            test_id=test_id,
            created_at=datetime.utcnow()
        )
        
        db.session.add(test_result)
        db.session.commit()
        
        total_score = 0
        
        for question in test.questions:
            answer_text = None
            option_id = None
            
            if question.question_type == 'text':
                answer_text = request.form.get(f'answer_{question.id}')
            elif question.question_type == 'single_choice':
                option_id = int(request.form.get(f'answer_{question.id}'))
                option = QuestionOption.query.get(option_id)
                total_score += option.score if option else 0
            elif question.question_type == 'multiple_choice':
                option_ids = request.form.getlist(f'answer_{question.id}')
                for opt_id in option_ids:
                    option = QuestionOption.query.get(int(opt_id))
                    total_score += option.score if option else 0
                option_id = None
            
            answer = TestAnswer(
                test_result_id=test_result.id,
                question_id=question.id,
                answer_text=answer_text,
                option_id=option_id
            )
            db.session.add(answer)
        
        test_result.score = total_score
        
        if total_score < 20:
            test_result.result_text = "Низкий уровень. Рекомендуется консультация психолога."
        elif 20 <= total_score < 40:
            test_result.result_text = "Средний уровень. Есть некоторые проблемы, но в целом ситуация под контролем."
        else:
            test_result.result_text = "Высокий уровень. Ваше психологическое состояние в норме."
        
        db.session.commit()
        
        return redirect(url_for('test_result', result_id=test_result.id))
    
    return render_template('take_test.html', test=test)

@app.route('/test_result/<int:result_id>')
def test_result(result_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    result = TestResult.query.get_or_404(result_id)
    
    if result.user_id != session['user_id'] and not is_psychologist():
        flash('У вас нет прав для просмотра этого результата', 'danger')
        return redirect(url_for('tests'))
    
    return render_template('test_result.html', result=result)

@app.route('/analytics/students')
def student_list():
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    students = User.query.filter_by(role='student').order_by(User.created_at.desc()).all()
    return render_template('student_list.html', students=students)

@app.route('/analytics/students/<int:student_id>')
def student_analytics(student_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        flash('Это не студент', 'danger')
        return redirect(url_for('student_list'))
    
    test_results = TestResult.query.filter_by(user_id=student_id).order_by(TestResult.created_at.asc()).all()
    total_tests = len(test_results)
    avg_score = db.session.query(func.avg(TestResult.score)).filter_by(user_id=student_id).scalar() or 0
    last_test = test_results[-1] if test_results else None
    scores_over_time = [(result.created_at, result.score) for result in test_results]
    messages_sent = Message.query.filter_by(sender_id=student_id).count()
    posts_count = Post.query.filter_by(user_id=student_id).count()
    reports = StudentReport.query.filter_by(student_id=student_id).order_by(StudentReport.created_at.desc()).all()
    protocols = MeetingProtocol.query.filter_by(student_id=student_id).order_by(MeetingProtocol.created_at.desc()).all()
    
    return render_template('student_analytics.html', 
                         student=student,
                         total_tests=total_tests,
                         avg_score=avg_score,
                         last_test=last_test,
                         scores_over_time=scores_over_time,
                         messages_sent=messages_sent,
                         posts_count=posts_count,
                         reports=reports,
                         protocols=protocols)

@app.route('/analytics/students/<int:student_id>/report', methods=['GET', 'POST'])
def create_report(student_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        flash('Это не студент', 'danger')
        return redirect(url_for('student_list'))
    
    if request.method == 'POST':
        report = StudentReport(
            student_id=student_id,
            psychologist_id=session['user_id'],
            created_at=datetime.utcnow(),
            academic_performance=request.form.get('academic_performance'),
            emotional_state=request.form.get('emotional_state'),
            social_interaction=request.form.get('social_interaction'),
            stress_level=request.form.get('stress_level'),
            sleep_quality=request.form.get('sleep_quality'),
            motivation=request.form.get('motivation'),
            behavior_patterns=request.form.get('behavior_patterns'),
            recommendations=request.form.get('recommendations'),
            additional_notes=request.form.get('additional_notes')
        )
        
        pdf_buffer = generate_pdf_report(report)
        filename = f"report_{student_id}_{uuid.uuid4().hex}.pdf"
        filepath = os.path.join(app.config['REPORT_FOLDER'], filename)
        os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        report.pdf_filename = filename
        
        db.session.add(report)
        db.session.commit()
        
        flash('Отчет успешно создан!', 'success')
        return redirect(url_for('student_analytics', student_id=student_id))
    
    return render_template('create_report.html', student=student)

@app.route('/analytics/students/<int:student_id>/report/<int:report_id>/download')
def download_report(student_id, report_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    report = StudentReport.query.get_or_404(report_id)
    if report.student_id != student_id or report.psychologist_id != session['user_id']:
        flash('У вас нет доступа к этому отчету', 'danger')
        return redirect(url_for('student_list'))
    
    filepath = os.path.join(app.config['REPORT_FOLDER'], report.pdf_filename)
    return send_file(filepath, as_attachment=True, download_name=f"report_{report.student.username}_{report.created_at.strftime('%Y%m%d')}.pdf")

@app.route('/appointments')
def appointments():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = get_current_user()
    if user.role == 'psychologist':
        appointments = Appointment.query.filter_by(psychologist_id=user.id).order_by(Appointment.appointment_date.asc()).all()
        meetings = Meeting.query.filter_by(psychologist_id=user.id).order_by(Meeting.scheduled_at.asc()).all()
        protocols = MeetingProtocol.query.filter_by(psychologist_id=user.id).order_by(MeetingProtocol.session_date.desc()).all()
    else:
        appointments = Appointment.query.filter_by(student_id=user.id).order_by(Appointment.appointment_date.asc()).all()
        meetings = Meeting.query.filter_by(student_id=user.id).order_by(Meeting.scheduled_at.asc()).all()
        protocols = MeetingProtocol.query.filter_by(student_id=user.id).order_by(MeetingProtocol.session_date.desc()).all()
    
    return render_template('appointments.html', appointments=appointments, meetings=meetings, protocols=protocols)

@app.route('/appointments/create/<int:student_id>', methods=['GET', 'POST'])
def create_appointment(student_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    student = User.query.get_or_404(student_id)
    if student.role != 'student':
        flash('Это не студент', 'danger')
        return redirect(url_for('appointments'))
    
    if request.method == 'POST':
        appointment_date = datetime.strptime(request.form['appointment_date'], '%Y-%m-%dT%H:%M')
        purpose = request.form.get('purpose')
        
        appointment = Appointment(
            student_id=student_id,
            psychologist_id=session['user_id'],
            appointment_date=appointment_date,
            purpose=purpose
        )
        db.session.add(appointment)
        
        meeting = Meeting(
            student_id=student_id,
            psychologist_id=session['user_id'],
            scheduled_at=appointment_date,
            status='planned'
        )
        db.session.add(meeting)
        
        message = Message(
            content=f"Назначена встреча на {appointment_date.strftime('%d.%m.%Y %H:%M')}. Цель: {purpose or 'Не указана'}",
            sender_id=session['user_id'],
            recipient_id=student_id,
            is_anonymous=False
        )
        db.session.add(message)
        db.session.commit()
        
        flash('Встреча успешно назначена!', 'success')
        return redirect(url_for('appointments'))
    
    return render_template('create_appointment.html', student=student)

@app.route('/appointments/<int:appointment_id>/update', methods=['POST'])
def update_appointment(appointment_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    appointment = Appointment.query.get_or_404(appointment_id)
    if (is_psychologist() and appointment.psychologist_id != session['user_id']) or \
       (is_student() and appointment.student_id != session['user_id']):
        flash('У вас нет прав для изменения этой встречи', 'danger')
        return redirect(url_for('appointments'))
    
    status = request.form.get('status')
    if status in ['confirmed', 'cancelled']:
        appointment.status = status
        meeting = Meeting.query.filter_by(student_id=appointment.student_id, psychologist_id=appointment.psychologist_id, scheduled_at=appointment.appointment_date).first()
        if meeting:
            meeting.status = 'completed' if status == 'confirmed' and meeting.scheduled_at <= datetime.utcnow() else status
        db.session.commit()
        
        recipient_id = appointment.student_id if is_psychologist() else appointment.psychologist_id
        message_content = f"Статус встречи на {appointment.appointment_date.strftime('%d.%m.%Y %H:%M')} изменен на: {status}"
        message = Message(
            content=message_content,
            sender_id=session['user_id'],
            recipient_id=recipient_id,
            is_anonymous=False
        )
        db.session.add(message)
        db.session.commit()
        
        flash(f'Статус встречи обновлен на "{status}"', 'success')
    
    return redirect(url_for('appointments'))

@app.route('/meetings/<int:meeting_id>/create_protocol', methods=['GET', 'POST'])
def create_protocol(meeting_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    meeting = Meeting.query.get_or_404(meeting_id)
    if meeting.psychologist_id != session['user_id']:
        flash('У вас нет прав для создания протокола этой встречи', 'danger')
        return redirect(url_for('appointments'))
    
    if request.method == 'POST':
        protocol = MeetingProtocol(
            meeting_id=meeting_id,
            student_id=meeting.student_id,
            psychologist_id=session['user_id'],
            session_date=meeting.scheduled_at,
            duration=request.form.get('duration', type=int),
            topics_discussed=request.form.get('topics_discussed'),
            emotional_state=request.form.get('emotional_state'),
            progress_notes=request.form.get('progress_notes'),
            recommendations=request.form.get('recommendations'),
            homework=request.form.get('homework'),
            additional_comments=request.form.get('additional_comments'),
            created_at=datetime.utcnow()
        )
        
        pdf_buffer = generate_protocol_pdf(protocol)
        filename = f"protocol_{meeting_id}_{uuid.uuid4().hex}.pdf"
        filepath = os.path.join(app.config['REPORT_FOLDER'], filename)
        os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(pdf_buffer.getvalue())
        protocol.pdf_filename = filename
        
        db.session.add(protocol)
        db.session.commit()
        
        flash('Протокол встречи успешно создан!', 'success')
        return redirect(url_for('appointments'))
    
    return render_template('create_protocol.html', meeting=meeting)

@app.route('/protocols/<int:protocol_id>/download')
def download_protocol(protocol_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    protocol = MeetingProtocol.query.get_or_404(protocol_id)
    if protocol.psychologist_id != session['user_id']:
        flash('У вас нет доступа к этому протоколу', 'danger')
        return redirect(url_for('appointments'))
    
    filepath = os.path.join(app.config['REPORT_FOLDER'], protocol.pdf_filename)
    return send_file(filepath, as_attachment=True, download_name=f"protocol_{protocol.student.username}_{protocol.session_date.strftime('%Y%m%d')}.pdf")

@app.route('/posts')
def posts():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('posts.html', posts=posts)

@app.route('/posts/create', methods=['GET', 'POST'])
def create_post():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        post = Post(
            title=title,
            content=content,
            user_id=session['user_id']
        )
        
        db.session.add(post)
        db.session.commit()
        
        flash('Пост создан!', 'success')
        return redirect(url_for('posts'))
    
    return render_template('create_post.html')

@app.route('/posts/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('view_post.html', post=post)

@app.route('/posts/<int:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    post = Post.query.get_or_404(post_id)
    content = request.form['content']
    is_anonymous = 'is_anonymous' in request.form
    
    comment = Comment(
        content=content,
        user_id=session['user_id'],
        post_id=post_id,
        is_anonymous=is_anonymous
    )
    
    db.session.add(comment)
    db.session.commit()
    
    flash('Комментарий добавлен!', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/messages')
def messages():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    
    if user.role == 'student':
        contacts = User.query.filter_by(role='psychologist').all()
    else:
        contacts = User.query.filter_by(role='student').all()
    
    conversations = []
    for contact in contacts:
        last_message = Message.query.filter(
            ((Message.sender_id == user.id) & (Message.recipient_id == contact.id)) |
            ((Message.sender_id == contact.id) & (Message.recipient_id == user.id))
        ).order_by(Message.created_at.desc()).first()
        
        if last_message:
            unread_count = Message.query.filter_by(
                sender_id=contact.id,
                recipient_id=user.id,
                is_read=False
            ).count()
            
            conversations.append({
                'contact': contact,
                'last_message': last_message,
                'unread_count': unread_count
            })
    
    return render_template('messages.html', conversations=conversations)

@app.route('/messages/<int:contact_id>', methods=['GET', 'POST'])
def chat(contact_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    contact = User.query.get_or_404(contact_id)
    
    if (user.role == 'student' and contact.role != 'psychologist') or \
       (user.role == 'psychologist' and contact.role != 'student'):
        flash('Вы можете общаться только с пользователями другой роли', 'danger')
        return redirect(url_for('messages'))
    
    if request.method == 'POST':
        if 'content' in request.form:
            content = request.form['content']
            is_anonymous = 'is_anonymous' in request.form
            
            message = Message(
                content=content,
                sender_id=user.id,
                recipient_id=contact.id,
                is_anonymous=is_anonymous
            )
            db.session.add(message)
        
        elif 'appointment_date' in request.form:
            appointment_date = datetime.strptime(request.form['appointment_date'], '%Y-%m-%dT%H:%M')
            purpose = request.form.get('purpose')
            
            appointment = Appointment(
                student_id=user.id if is_student() else contact.id,
                psychologist_id=user.id if is_psychologist() else contact.id,
                appointment_date=appointment_date,
                purpose=purpose
            )
            db.session.add(appointment)
            
            meeting = Meeting(
                student_id=user.id if is_student() else contact.id,
                psychologist_id=user.id if is_psychologist() else contact.id,
                scheduled_at=appointment_date,
                status='planned'
            )
            db.session.add(meeting)
            
            message = Message(
                content=f"Предложена встреча на {appointment_date.strftime('%d.%m.%Y %H:%M')}. Цель: {purpose or 'Не указана'}",
                sender_id=user.id,
                recipient_id=contact.id,
                is_anonymous=False
            )
            db.session.add(message)
        
        Message.query.filter_by(sender_id=contact.id, recipient_id=user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        
        return redirect(url_for('chat', contact_id=contact_id))
    
    messages = Message.query.filter(
        ((Message.sender_id == user.id) & (Message.recipient_id == contact.id)) |
        ((Message.sender_id == contact.id) & (Message.recipient_id == user.id))
    ).order_by(Message.created_at.asc()).all()
    
    Message.query.filter_by(sender_id=contact.id, recipient_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    
    return render_template('chat.html', contact=contact, messages=messages)

@app.route('/articles')
def articles():
    articles = Article.query.order_by(Article.created_at.desc()).all()
    return render_template('articles.html', articles=articles)

@app.route('/articles/create', methods=['GET', 'POST'])
def create_article():
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        article = Article(
            title=title,
            content=content,
            user_id=session['user_id']
        )
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                article.image_url = filename
        
        db.session.add(article)
        db.session.commit()
        
        flash('Статья создана!', 'success')
        return redirect(url_for('articles'))
    
    return render_template('create_article.html')

@app.route('/articles/<int:article_id>')
def view_article(article_id):
    article = Article.query.get_or_404(article_id)
    return render_template('view_article.html', article=article)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    
    if not query:
        return redirect(url_for('index'))
    
    tests = Test.query.filter(
        (Test.title.contains(query)) | (Test.description.contains(query))
    ).filter_by(is_active=True).all()
    
    articles = Article.query.filter(
        (Article.title.contains(query)) | (Article.content.contains(query))
    ).all()
    
    posts = Post.query.filter(
        (Post.title.contains(query)) | (Post.content.contains(query))
    ).all()
    
    psychologists = User.query.filter(
        (User.full_name.contains(query)) | (User.bio.contains(query))
    ).filter_by(role='psychologist').all()
    
    return render_template('search_results.html', 
                         query=query,
                         tests=tests,
                         articles=articles,
                         posts=posts,
                         psychologists=psychologists)

@app.route('/emergency')
def emergency():
    return render_template('emergency.html')

@app.route('/api/messages/unread_count')
def unread_messages_count():
    if 'user_id' not in session:
        return jsonify({'count': 0})
    
    count = Message.query.filter_by(recipient_id=session['user_id'], is_read=False).count()
    return jsonify({'count': count})

@app.route('/api/meetings/calendar')
def meetings_calendar():
    if 'user_id' not in session or not is_psychologist():
        return jsonify({'error': 'Unauthorized'}), 401
    
    meetings = Meeting.query.filter_by(psychologist_id=session['user_id']).all()
    events = [
        {
            'id': meeting.id,
            'title': f"Встреча с {meeting.student.full_name or meeting.student.username}",
            'start': meeting.scheduled_at.isoformat(),
            'status': meeting.status,
            'student_id': meeting.student_id
        }
        for meeting in meetings
    ]
    return jsonify(events)

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
    app.run(debug=True)