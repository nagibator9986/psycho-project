# models.py
from datetime import datetime
from sqlalchemy.schema import UniqueConstraint
from extensions import db

# Совпадаем с существующей таблицей user (см. ошибки UNIQUE constraint failed: user.email)
class User(db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)      # уникальный логин
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)  # СНОВА уникальный email
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student | psychologist | admin | superadmin
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
    __tablename__ = 'post'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade='all, delete-orphan')
    author = db.relationship('User', backref='posts', lazy=True)


class Comment(db.Model):
    __tablename__ = 'comment'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_anonymous = db.Column(db.Boolean, default=False)


class Test(db.Model):
    __tablename__ = 'test'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    questions = db.relationship('Question', backref='test', lazy=True, cascade='all, delete-orphan')
    results = db.relationship('TestResult', backref='test', lazy=True, cascade='all, delete-orphan')
    interpretations = db.relationship('TestInterpretation', backref='test', lazy=True, cascade='all, delete-orphan', order_by='TestInterpretation.min_score')


class Question(db.Model):
    __tablename__ = 'question'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    question_type = db.Column(db.String(20), nullable=False)  # text | single_choice | multiple_choice | scale_choice
    options = db.relationship('QuestionOption', backref='question', lazy=True, cascade='all, delete-orphan')


class QuestionOption(db.Model):
    __tablename__ = 'question_option'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    score = db.Column(db.Integer)


class TestResult(db.Model):
    __tablename__ = 'test_result'
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
    __tablename__ = 'test_answer'
    id = db.Column(db.Integer, primary_key=True)
    test_result_id = db.Column(db.Integer, db.ForeignKey('test_result.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    answer_text = db.Column(db.Text)
    option_id = db.Column(db.Integer, db.ForeignKey('question_option.id'))
    option = db.relationship('QuestionOption')
    question = db.relationship('Question', backref='answers')


class Message(db.Model):
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)


class Article(db.Model):
    __tablename__ = 'article'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    image_url = db.Column(db.String(200))
    user = db.relationship('User', backref='authored_articles', lazy=True)


class StudentReport(db.Model):
    __tablename__ = 'student_report'
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
    __tablename__ = 'appointment'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    psychologist_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    purpose = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('student_id', 'psychologist_id', 'appointment_date', name='uq_appointment_unique_slot'),)


class Meeting(db.Model):
    __tablename__ = 'meeting'
    id = db.Column(db.Integer, primary_key=True)
    psychologist_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    scheduled_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='planned')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    protocols = db.relationship('MeetingProtocol', backref='meeting', lazy=True, cascade='all, delete-orphan')
    student = db.relationship('User', foreign_keys=[student_id], backref='student_meetings', lazy='joined')
    psychologist = db.relationship('User', foreign_keys=[psychologist_id], backref='psychologist_meetings', lazy='joined')
    __table_args__ = (UniqueConstraint('student_id', 'psychologist_id', 'scheduled_at', name='uq_meeting_unique_slot'),)


class MeetingRequest(db.Model):
    __tablename__ = 'meeting_request'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    proposed_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MeetingProtocol(db.Model):
    __tablename__ = 'meeting_protocol'
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
