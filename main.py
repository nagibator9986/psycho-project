import os
import io
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from sqlalchemy.schema import UniqueConstraint
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.pagesizes import letter
from sqlalchemy import and_
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///psych_help.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['REPORT_FOLDER'] = 'static/reports'

db = SQLAlchemy(app)

# =========================
#          MODELS
# =========================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' | 'psychologist'
    full_name = db.Column(db.String(100))
    bio = db.Column(db.Text)
    profile_pic = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    group_id = db.Column(db.Integer, db.ForeignKey('groups.id'))
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
class Group(db.Model):
    __tablename__ = 'groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    course = db.Column(db.Integer, nullable=False, default=1)

    users = db.relationship('User', backref='group', lazy=True)
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
    results = db.relationship('TestResult', backref='test', lazy=True, cascade='all, delete-orphan')
    interpretations = db.relationship('TestInterpretation', backref='test', lazy=True, cascade='all, delete-orphan')
    interpretations = db.relationship(
        'TestInterpretation',
        backref='test',
        lazy=True,
        cascade='all, delete-orphan',
        order_by='TestInterpretation.min_score'
    )

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    question_type = db.Column(db.String(20), nullable=False)  # text | single_choice | multiple_choice | scale_choice

    options = db.relationship('QuestionOption', backref='question', lazy=True, cascade='all, delete-orphan')


class QuestionOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    score = db.Column(db.Integer)  # может быть None для текстовых

class TestResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    score = db.Column(db.Integer)
    result_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    answers = db.relationship('TestAnswer', backref='test_result', lazy=True, cascade='all, delete-orphan')

class TestInterpretation(db.Model):
    __tablename__ = 'test_interpretation'
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False, index=True)
    min_score = db.Column(db.Integer, nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)

    

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

    __table_args__ = (
        UniqueConstraint('student_id', 'psychologist_id', 'appointment_date', name='uq_appointment_unique_slot'),
    )

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

    __table_args__ = (
        UniqueConstraint('student_id', 'psychologist_id', 'scheduled_at', name='uq_meeting_unique_slot'),
    )

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
    duration = db.Column(db.Integer)  # minutes
    topics_discussed = db.Column(db.Text)
    emotional_state = db.Column(db.Text)
    progress_notes = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    homework = db.Column(db.Text)
    additional_comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    pdf_filename = db.Column(db.String(100))

# =========================
#     DB INIT (NO SEEDS)
# =========================
with app.app_context():
    db.create_all()

# =========================
#       HELPERS
# =========================

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

# =========================
#         ROUTES
# =========================

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
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
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
        total_results = TestResult.query.join(Test).filter(Test.user_id == user.id).count()
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
        test = Test(title=title, description=description, user_id=session['user_id'])
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
        # 1) УДАЛЕНИЕ ВОПРОСА — обрабатываем ПЕРВЫМ
        if 'delete_question' in request.form:
            q_id = int(request.form['delete_question'])
            q = Question.query.get_or_404(q_id)
            if q.test_id != test.id:
                flash('Нельзя удалить вопрос из другого теста', 'danger')
            else:
                db.session.delete(q)  # options удалятся каскадом
                db.session.commit()
                flash('Вопрос удалён', 'info')
            return redirect(url_for('add_questions', test_id=test_id))

        # 2) ДОБАВЛЕНИЕ ВОПРОСА
        question_type = request.form.get('question_type')
        if not question_type:
            flash("Не выбран тип вопроса", "danger")
            return redirect(url_for('add_questions', test_id=test_id))

        text = request.form['text'].strip()
        if not text:
            flash("Введите текст вопроса", "danger")
            return redirect(url_for('add_questions', test_id=test_id))

        question = Question(text=text, question_type=question_type, test_id=test_id)
        db.session.add(question)
        db.session.commit()

        if question_type in ['single_choice', 'multiple_choice', 'scale_choice']:
            options = zip(request.form.getlist('option_text[]'), request.form.getlist('option_score[]'))
            for opt_text, opt_score in options:
                opt_text = (opt_text or '').strip()
                if opt_text:
                    db.session.add(QuestionOption(
                        text=opt_text,
                        score=int(opt_score) if opt_score not in (None, "") else 0,
                        question_id=question.id
                    ))
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

def get_cyr_styles_simple():
    # Берём TTF из корня проекта
    font_path = os.path.join(app.root_path, "DejaVuSans.ttf")
    pdfmetrics.registerFont(TTFont("DejaVuSans", font_path))

    base = getSampleStyleSheet()
    H = ParagraphStyle('H', parent=base['Heading3'], fontName='DejaVuSans')
    T = ParagraphStyle('T', parent=base['Title'],    fontName='DejaVuSans')
    P = ParagraphStyle('P', parent=base['BodyText'], fontName='DejaVuSans')
    return T, H, P
def generate_test_results_pdf(test):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)

    # Берём три простых стиля на базе DejaVuSans
    T, H, P = get_cyr_styles_simple()

    elements = []
    elements.append(Paragraph(f"Результаты теста: {test.title}", T))
    elements.append(Spacer(1, 12))

    # Грузим данные с группами (как у тебя)
    from sqlalchemy import asc
    rows = (
        db.session.query(
            User.full_name,
            User.username,
            TestResult.score,
            TestResult.result_text,
            Group.name
        )
        .join(TestResult, TestResult.user_id == User.id)
        .outerjoin(Group, User.group_id == Group.id)
        .filter(TestResult.test_id == test.id)
        .order_by(asc(Group.name), asc(User.full_name), asc(User.username))
        .all()
    )

    # Группируем
    grouped = {}
    for full_name, username, score, interp_text, group_name in rows:
        g = group_name or "Без группы"
        grouped.setdefault(g, []).append((
            full_name or "—",
            username or "—",
            score if score is not None else 0,
            interp_text or "—"
        ))

    # Рисуем по группам
    for gname, items in grouped.items():
        elements.append(Paragraph(f"Группа: {gname}", H))
        elements.append(Spacer(1, 6))

        data = [["ФИО", "Логин", "Баллы", "Интерпретация"]]
        for full_name, username, score, interp_text in items:
            data.append([full_name, username, str(score), interp_text])

        table = Table(data, colWidths=[170, 120, 60, 230])
        table.setStyle([
            ('FONTNAME',(0,0),(-1,-1),'DejaVuSans'),  # <<< ВАЖНО
            ('FONTSIZE',(0,0),(-1,-1),10),
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('ALIGN',(0,0),(-1,-1),'LEFT'),
            ('GRID',(0,0),(-1,-1),1,colors.black),
            ('BACKGROUND',(0,1),(-1,-1),colors.white),
        ])
        elements.append(table)
        elements.append(Spacer(1, 12))

    doc.build(elements)
    buffer.seek(0)
    return buffer


@app.route('/tests/<int:test_id>/download_results')
def download_test_results(test_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    test = Test.query.get_or_404(test_id)

    if test.user_id != session['user_id']:
        flash('У вас нет прав на выгрузку этого теста', 'danger')
        return redirect(url_for('tests'))

    pdf_buffer = generate_test_results_pdf(test)
    filename = f"test_results_{test.id}.pdf"
    return send_file(pdf_buffer, as_attachment=True, download_name=filename)

@app.route('/tests/<int:test_id>/add_interpretation', methods=['POST'])
def add_interpretation(test_id):
    if 'user_id' not in session or not is_psychologist():
        return redirect(url_for('login'))

    test = Test.query.get_or_404(test_id)
    if test.user_id != session['user_id']:
        flash('Нет прав для изменения этого теста', 'danger')
        return redirect(url_for('tests'))

    # Удаление
    if 'delete_interpretation' in request.form:
        interp = TestInterpretation.query.get_or_404(request.form['delete_interpretation'])
        db.session.delete(interp)
        db.session.commit()
        flash('Интерпретация удалена', 'info')
        return redirect(url_for('add_questions', test_id=test_id))

    # Добавление
    min_score = int(request.form['min_score'])
    max_score = int(request.form['max_score'])
    text = request.form['text']

    interp = TestInterpretation(test_id=test_id, min_score=min_score, max_score=max_score, text=text)
    db.session.add(interp)
    db.session.commit()

    flash('Интерпретация добавлена!', 'success')
    return redirect(url_for('add_questions', test_id=test_id))

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
        db.session.flush()  # чтобы test_result.id появился сразу

        total_score = 0

        for question in test.questions:
            answer_text = None
            option_id = None

            if question.question_type == 'text':
                answer_text = request.form.get(f'answer_{question.id}')
            elif question.question_type in ['single_choice', 'scale_choice']:
                selected = request.form.get(f'answer_{question.id}')
                if selected:
                    option_id = int(selected)
                    option = QuestionOption.query.get(option_id)
                    total_score += option.score if option else 0
            elif question.question_type == 'multiple_choice':
                option_ids = request.form.getlist(f'answer_{question.id}')
                for opt_id in option_ids:
                    option = QuestionOption.query.get(int(opt_id))
                    total_score += option.score if option else 0
                option_id = None  # храним по одному ответу в строке

            db.session.add(TestAnswer(
                test_result_id=test_result.id,
                question_id=question.id,
                answer_text=answer_text,
                option_id=option_id
            ))

        # --- сохраняем баллы ---
        test_result.score = total_score

        # --- ПОДСТАВЛЯЕМ ИНТЕРПРЕТАЦИЮ ИЗ БД ---
        interp = TestInterpretation.query.filter(
            and_(
                TestInterpretation.test_id == test.id,
                TestInterpretation.min_score <= total_score,
                TestInterpretation.max_score >= total_score
            )
        ).order_by(TestInterpretation.min_score.desc()).first()

        if interp:
            test_result.result_text = interp.text
        else:
            # запасной вариант, если интерпретации не заданы
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
    return send_file(filepath, as_attachment=True,
                     download_name=f"report_{report.student.username}_{report.created_at.strftime('%Y%m%d')}.pdf")

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

        # ПРОВЕРКИ на существование
        exists_a = Appointment.query.filter_by(
            student_id=student_id,
            psychologist_id=session['user_id'],
            appointment_date=appointment_date
        ).first()
        if exists_a:
            flash('Такая встреча уже существует для указанного времени.', 'info')
            return redirect(url_for('appointments'))

        exists_m = Meeting.query.filter_by(
            student_id=student_id,
            psychologist_id=session['user_id'],
            scheduled_at=appointment_date
        ).first()

        appointment = Appointment(
            student_id=student_id,
            psychologist_id=session['user_id'],
            appointment_date=appointment_date,
            purpose=purpose
        )
        db.session.add(appointment)

        if not exists_m:
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
        meeting = Meeting.query.filter_by(
            student_id=appointment.student_id,
            psychologist_id=appointment.psychologist_id,
            scheduled_at=appointment.appointment_date
        ).first()
        if meeting:
            meeting.status = 'completed' if status == 'confirmed' and meeting.scheduled_at <= datetime.utcnow() else status
        db.session.commit()

        recipient_id = appointment.student_id if is_psychologist() else appointment.psychologist_id
        message_content = f"Статус встречи на {appointment.appointment_date.strftime('%d.%m.%Y %H:%M')} изменен на: {status}"
        message = Message(content=message_content, sender_id=session['user_id'], recipient_id=recipient_id, is_anonymous=False)
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
    return send_file(filepath, as_attachment=True,
                     download_name=f"protocol_{protocol.student.username}_{protocol.session_date.strftime('%Y%m%d')}.pdf")

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
        post = Post(title=title, content=content, user_id=session['user_id'])
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

    comment = Comment(content=content, user_id=session['user_id'], post_id=post_id, is_anonymous=is_anonymous)
    db.session.add(comment)
    db.session.commit()
    flash('Комментарий добавлен!', 'success')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/messages')
def messages():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    contacts = User.query.filter_by(role='psychologist').all() if user.role == 'student' else User.query.filter_by(role='student').all()

    conversations = []
    for contact in contacts:
        last_message = Message.query.filter(
            ((Message.sender_id == user.id) & (Message.recipient_id == contact.id)) |
            ((Message.sender_id == contact.id) & (Message.recipient_id == user.id))
        ).order_by(Message.created_at.desc()).first()

        if last_message:
            unread_count = Message.query.filter_by(sender_id=contact.id, recipient_id=user.id, is_read=False).count()
            conversations.append({'contact': contact, 'last_message': last_message, 'unread_count': unread_count})

    return render_template('messages.html', conversations=conversations)

@app.route('/messages/<int:contact_id>', methods=['GET', 'POST'])
def chat(contact_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    contact = User.query.get_or_404(contact_id)

    if (user.role == 'student' and contact.role != 'psychologist') or (user.role == 'psychologist' and contact.role != 'student'):
        flash('Вы можете общаться только с пользователями другой роли', 'danger')
        return redirect(url_for('messages'))

    if request.method == 'POST':
        if 'content' in request.form:
            content = request.form['content']
            is_anonymous = 'is_anonymous' in request.form
            message = Message(content=content, sender_id=user.id, recipient_id=contact.id, is_anonymous=is_anonymous)
            db.session.add(message)

        elif 'appointment_date' in request.form:
            appointment_date = datetime.strptime(request.form['appointment_date'], '%Y-%m-%dT%H:%M')
            purpose = request.form.get('purpose')

            student_id = user.id if is_student() else contact.id
            psychologist_id = user.id if is_psychologist() else contact.id

            # ПРОВЕРКИ
            exists_a = Appointment.query.filter_by(
                student_id=student_id, psychologist_id=psychologist_id, appointment_date=appointment_date
            ).first()
            if exists_a:
                flash('Такая встреча уже существует для указанного времени.', 'info')
                return redirect(url_for('chat', contact_id=contact_id))

            exists_m = Meeting.query.filter_by(
                student_id=student_id, psychologist_id=psychologist_id, scheduled_at=appointment_date
            ).first()

            appointment = Appointment(
                student_id=student_id,
                psychologist_id=psychologist_id,
                appointment_date=appointment_date,
                purpose=purpose
            )
            db.session.add(appointment)

            if not exists_m:
                meeting = Meeting(
                    student_id=student_id,
                    psychologist_id=psychologist_id,
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

        # пометить входящие как прочитанные
        Message.query.filter_by(sender_id=contact.id, recipient_id=user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        return redirect(url_for('chat', contact_id=contact_id))

    msgs = Message.query.filter(
        ((Message.sender_id == user.id) & (Message.recipient_id == contact.id)) |
        ((Message.sender_id == contact.id) & (Message.recipient_id == user.id))
    ).order_by(Message.created_at.asc()).all()

    Message.query.filter_by(sender_id=contact.id, recipient_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()

    return render_template('chat.html', contact=contact, messages=msgs)

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
        article = Article(title=title, content=content, user_id=session['user_id'])

        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
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

    tests = Test.query.filter((Test.title.contains(query)) | (Test.description.contains(query))).filter_by(is_active=True).all()
    articles = Article.query.filter((Article.title.contains(query)) | (Article.content.contains(query))).all()
    posts = Post.query.filter((Post.title.contains(query)) | (Post.content.contains(query))).all()
    psychologists = User.query.filter((User.full_name.contains(query)) | (User.bio.contains(query))).filter_by(role='psychologist').all()

    return render_template('search_results.html',
                           query=query, tests=tests, articles=articles, posts=posts, psychologists=psychologists)

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
    events = [{
        'id': meeting.id,
        'title': f"Встреча с {meeting.student.full_name or meeting.student.username}",
        'start': meeting.scheduled_at.isoformat(),
        'status': meeting.status,
        'student_id': meeting.student_id
    } for meeting in meetings]
    return jsonify(events)

# =========================
#        ENTRYPOINT
# =========================

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
    app.run(debug=True)
