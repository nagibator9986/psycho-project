import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid
from sqlalchemy import func
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics  # Добавлен импорт pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont  # Добавлен импорт TTFont
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
    question_type = db.Column(db.String(20), nullable=False)  # 'text', 'single_choice', 'multiple_choice'
    
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
    status = db.Column(db.String(20), default='pending')  # 'pending', 'confirmed', 'cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
class Meeting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    psychologist_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='planned')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MeetingRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    proposed_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Создаем таблицы
with app.app_context():
    db.create_all()

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

# Генерация PDF отчета
def generate_pdf_report(report):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()

    # Регистрация шрифта с поддержкой кириллицы
    font_path = "DejaVuSans.ttf"  # Укажите путь к файлу шрифта
    if not os.path.exists(font_path):
        # Если шрифта нет, можно попробовать использовать Arial из системы Windows
        font_path = "C:/Windows/Fonts/Arial.ttf" if os.name == 'nt' else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    
    pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
    
    # Обновляем стиль для использования нового шрифта
    styles['Title'].fontName = 'DejaVuSans'
    styles['Normal'].fontName = 'DejaVuSans'
    styles['BodyText'].fontName = 'DejaVuSans'

    elements = []

    # Проверка на None для report.student
    student_name = "Неизвестный студент"
    if report.student:
        student_name = report.student.full_name if report.student.full_name else report.student.username
    
    elements.append(Paragraph(f"Отчет о студенте: {student_name}", styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Проверка на None для психолога
    psychologist = User.query.get(report.psychologist_id)
    psychologist_name = "Неизвестный психолог"
    if psychologist:
        psychologist_name = psychologist.full_name if psychologist.full_name else psychologist.username
    
    # Проверка на None для created_at
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
        ('FONTNAME', (0, 0), (-1, -1), 'DejaVuSans'),  # Используем зарегистрированный шрифт
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
        
        return render_template('psychologist_dashboard.html', user=user, tests=tests, posts=posts, 
                             unread_messages=unread_messages, students_count=students_count, 
                             pending_appointments=pending_appointments)
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
    
    return render_template('student_analytics.html', 
                         student=student,
                         total_tests=total_tests,
                         avg_score=avg_score,
                         last_test=last_test,
                         scores_over_time=scores_over_time,
                         messages_sent=messages_sent,
                         posts_count=posts_count,
                         reports=reports)

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
            created_at=datetime.utcnow(),  # Явно устанавливаем created_at
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
        
        # Генерация PDF
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
    else:
        appointments = Appointment.query.filter_by(student_id=user.id).order_by(Appointment.appointment_date.asc()).all()
    
    return render_template('appointments.html', appointments=appointments)

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
        db.session.commit()
        
        # Отправляем уведомление студенту через чат
        message = Message(
            content=f"Назначена встреча с психологом на {appointment_date.strftime('%d.%m.%Y %H:%M')}. Цель: {purpose or 'Не указана'}",
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
        db.session.commit()
        
        # Уведомление через чат
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

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['REPORT_FOLDER'], exist_ok=True)
    app.run(debug=True)