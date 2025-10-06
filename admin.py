from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash
from sqlalchemy import or_, asc, desc
import csv, io, uuid
from datetime import datetime
from functools import wraps

from extensions import db
from models import User, Group  # <-- берём модели отсюда

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
ALLOWED_ROLES = ['student', 'psychologist', 'admin', 'superadmin']


# --- Декоратор доступа ---
def superadmin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        uid = session.get('user_id')
        if not uid:
            flash('Нужно войти в систему', 'warning')
            return redirect(url_for('login'))
        u = User.query.get(uid)
        if not u or u.role not in ('admin', 'superadmin'):
            flash('Доступ запрещен', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper

# --- Вспомогательные функции ---
def ensure_group(name: str, course: int | None = None):
    if not name:
        return None
    g = Group.query.filter_by(name=name).first()
    if not g:
        g = Group(name=name, course=course or 1)
        db.session.add(g)
        db.session.flush()
    return g

# --- Главная страница админки: мониторинг + инструменты ---
@admin_bp.route('/', methods=['GET'])
@superadmin_required
def superadmin_home():
    # Фильтры/поиск/сортировка/страницы
    q = request.args.get('q', '').strip()
    role = request.args.get('role', '').strip()
    group = request.args.get('group', '').strip()
    sort = request.args.get('sort', 'date_desc')  # date_desc | date_asc | name_asc | name_desc | group_asc | group_desc | role_asc | role_desc
    page = max(int(request.args.get('page', 1) or 1), 1)
    per_page = min(max(int(request.args.get('per_page', 20) or 20), 5), 100)

    query = User.query

    # Поиск по username/email/full_name
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.username.ilike(like), User.email.ilike(like), User.full_name.ilike(like)))

    # Фильтр по роли
    if role:
        query = query.filter(User.role == role)

    # Фильтр по группе
    if group:
        query = query.join(Group, isouter=True).filter(Group.name == group)

    # Сортировка
    if sort == 'date_asc':
        query = query.order_by(asc(User.created_at))
    elif sort == 'name_asc':
        query = query.order_by(asc(User.full_name), asc(User.username))
    elif sort == 'name_desc':
        query = query.order_by(desc(User.full_name), desc(User.username))
    elif sort == 'group_asc':
        query = query.join(Group, isouter=True).order_by(asc(Group.name.nullslast()))
    elif sort == 'group_desc':
        query = query.join(Group, isouter=True).order_by(desc(Group.name.nullslast()))
    elif sort == 'role_asc':
        query = query.order_by(asc(User.role))
    elif sort == 'role_desc':
        query = query.order_by(desc(User.role))
    else:  # date_desc
        query = query.order_by(desc(User.created_at))

    total = query.count()
    users = query.limit(per_page).offset((page - 1) * per_page).all()

    # Данные для фильтров
    roles = ALLOWED_ROLES
    groups = [g.name for g in Group.query.order_by(asc(Group.name)).all()]

    return render_template(
        'superadmin.html',
        users=users,
        total=total,
        page=page,
        per_page=per_page,
        q=q,
        role=role,
        group=group,
        sort=sort,
        roles=roles,
        groups=groups
    )

# --- Создание одиночного пользователя ---
@admin_bp.route('/users/create', methods=['POST'])
@superadmin_required
def create_user():
    username = (request.form.get('username') or '').strip()
    email = (request.form.get('email') or '').strip()
    password = (request.form.get('password') or '').strip()
    role = (request.form.get('role') or 'student').strip()
    full_name = (request.form.get('full_name') or '').strip()
    group_name = (request.form.get('group') or '').strip()
    course = request.form.get('course', type=int)

    if not username or not email:
        flash('Нужно указать username и email', 'warning')
        return redirect(url_for('admin.superadmin_home'))

    if role not in ALLOWED_ROLES:
        flash('Неверная роль', 'danger')
        return redirect(url_for('admin.superadmin_home'))

    if User.query.filter_by(username=username).first():
        flash('Имя пользователя занято', 'danger')
        return redirect(url_for('admin.superadmin_home'))
    if User.query.filter_by(email=email).first():
        flash('Email уже используется', 'danger')
        return redirect(url_for('admin.superadmin_home'))

    if not password:
        password = uuid.uuid4().hex[:10]  # временный

    grp = ensure_group(group_name, course)
    u = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        role=role,
        full_name=full_name,
        group_id=grp.id if grp else None,
        created_at=datetime.utcnow()
    )
    db.session.add(u)
    db.session.commit()

    flash(f'Пользователь {username} создан', 'success')
    return redirect(url_for('admin.superadmin_home'))

# --- Обновление пользователя: роль/группа/ФИО/email/пароль ---
@admin_bp.route('/users/<int:user_id>/update', methods=['POST'])
@superadmin_required
def update_user(user_id):
    u = User.query.get_or_404(user_id)

    new_role = (request.form.get('role') or u.role).strip()
    new_full = (request.form.get('full_name') or u.full_name or '').strip()
    new_email = (request.form.get('email') or u.email).strip()
    new_group = (request.form.get('group') or '').strip()
    course = request.form.get('course', type=int)
    new_password = (request.form.get('password') or '').strip()

    if new_role not in ALLOWED_ROLES:
        flash('Неверная роль', 'danger')
        return redirect(url_for('admin.superadmin_home'))

    # Проверка уникальности email (если меняем)
    if new_email != u.email and User.query.filter_by(email=new_email).first():
        flash('Этот email уже используется другим аккаунтом', 'danger')
        return redirect(url_for('admin.superadmin_home'))

    u.role = new_role
    u.full_name = new_full or None
    u.email = new_email

    grp = ensure_group(new_group, course)
    u.group_id = grp.id if grp else None

    if new_password:
        u.password = generate_password_hash(new_password)

    db.session.commit()
    flash('Профиль обновлен', 'success')
    return redirect(url_for('admin.superadmin_home'))

# --- Удаление одного пользователя ---
@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@superadmin_required
def delete_user(user_id):
    u = User.query.get_or_404(user_id)
    # Не позволяем удалить себя (чтобы не отрезать доступ)
    if u.id == session.get('user_id'):
        flash('Нельзя удалить собственный аккаунт супер-админа', 'warning')
        return redirect(url_for('admin.superadmin_home'))
    db.session.delete(u)
    db.session.commit()
    flash('Пользователь удален', 'success')
    return redirect(url_for('admin.superadmin_home'))

# --- Массовое удаление ---
@admin_bp.route('/users/bulk_delete', methods=['POST'])
@superadmin_required
def bulk_delete():
    ids = request.form.getlist('user_ids[]')
    if not ids:
        flash('Не выбраны пользователи', 'warning')
        return redirect(url_for('admin.superadmin_home'))

    # Защита от удаления себя
    sid = str(session.get('user_id'))
    ids = [i for i in ids if i != sid]

    deleted = 0
    for s in ids:
        try:
            u = User.query.get(int(s))
            if u:
                db.session.delete(u)
                deleted += 1
        except ValueError:
            continue
    db.session.commit()
    flash(f'Удалено пользователей: {deleted}', 'success')
    return redirect(url_for('admin.superadmin_home'))

# --- Массовая загрузка CSV (создание/обновление) ---
"""
Ожидаемый CSV (UTF-8, с заголовком):
username,email,full_name,role,group,course,password
role: student|psychologist|admin|superadmin (по умолчанию student)
group: имя группы; если нет — создастся
course: целое (по умолчанию 1)
password: если пусто — сгенерируется
"""
@admin_bp.route('/users/bulk_upload', methods=['POST'])
@superadmin_required
def bulk_upload():
    file = request.files.get('csv')
    mode = (request.form.get('mode') or 'create_only').strip()  # create_only | upsert

    if not file or file.filename == '':
        flash('Прикрепи CSV-файл', 'warning')
        return redirect(url_for('admin.superadmin_home'))

    # 1) Читаем байты и пытаемся декодировать в текст
    raw = file.read()
    text = None
    tried_enc = []
    for enc in ('utf-8-sig', 'utf-8', 'cp1251', 'windows-1251'):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            tried_enc.append(enc)

    if text is None:
        flash(f'Не удалось прочитать CSV. Пробовал кодировки: {", ".join(tried_enc)}', 'danger')
        return redirect(url_for('admin.superadmin_home'))

    # 2) Определяем разделитель
    import csv, io
    sample = '\n'.join(text.splitlines()[:10])  # небольшой фрагмент для сниффера
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t'])
        delimiter = dialect.delimiter
    except Exception:
        # fallback по содержимому
        header = text.splitlines()[0] if text else ''
        if header.count(';') > header.count(','):
            delimiter = ';'
        elif '\t' in header:
            delimiter = '\t'
        else:
            delimiter = ','

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    # Проверим наличие необходимых полей (с учётом кейсов)
    normalized_fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]
    required = ['username','email','full_name','role','group','course','password']
    missing = [r for r in required if r not in normalized_fieldnames]
    if missing:
        flash('Неверные заголовки CSV. Нужны: ' + ', '.join(required), 'danger')
        return redirect(url_for('admin.superadmin_home'))

    # 3) Импорт
    from werkzeug.security import generate_password_hash
    created = updated = skipped = errors = 0

    for i, row in enumerate(reader, start=2):  # строка 1 — заголовок
        try:
            # доступ по нижнему регистру (на всякий случай)
            row_l = { (k or '').strip().lower(): (v or '').strip() for k, v in row.items() }

            username = row_l.get('username', '')
            email    = row_l.get('email', '').lower()
            fullnm   = row_l.get('full_name', '')
            role     = row_l.get('role', 'student')
            groupnm  = row_l.get('group', '')
            course_s = row_l.get('course', '')
            password = row_l.get('password', '')

            # Валидация минимальная
            if not username or not email:
                skipped += 1
                continue
            if role not in ALLOWED_ROLES:
                role = 'student'

            # Курс к int
            try:
                course = int(float(course_s)) if course_s else 1
                if course <= 0: course = 1
            except Exception:
                course = 1

            # Группа (создадим, если нет)
            grp = ensure_group(groupnm, course) if groupnm else None

            # Upsert/Создание
            existing = User.query.filter((User.username == username) | (User.email == email)).first()
            if existing:
                if mode == 'upsert':
                    # обновляем частично
                    existing.full_name = fullnm or existing.full_name
                    existing.role = role
                    existing.group_id = grp.id if grp else None
                    if password:
                        existing.password = generate_password_hash(password)
                    updated += 1
                else:
                    skipped += 1
            else:
                if not password:
                    # в твоём файле уже username+abc, но на всякий случай
                    password = f'{username}abc'
                u = User(
                    username=username,
                    email=email,
                    password=generate_password_hash(password),
                    role=role,
                    full_name=fullnm or None,
                    group_id=grp.id if grp else None,
                    created_at=datetime.utcnow()
                )
                db.session.add(u)
                created += 1

        except Exception as e:
            errors += 1
            # можно раскомментировать для отладки в консоли:
            # print(f'row {i} error:', e)
            continue

    db.session.commit()
    flash(f'CSV импорт: создано {created}, обновлено {updated}, пропущено {skipped}, ошибок {errors}', 'info')
    return redirect(url_for('admin.superadmin_home'))


# --- Смена роли одним кликом (AJAX) ---
@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@superadmin_required
def change_role(user_id):
    role = (request.form.get('role') or '').strip()
    if role not in ALLOWED_ROLES:
        return jsonify({'ok': False, 'error': 'bad role'}), 400
    u = User.query.get_or_404(user_id)
    u.role = role
    db.session.commit()
    return jsonify({'ok': True})
