# -*- coding: utf-8 -*-
"""
Импорт пользователей в БД PsychHelp из НОРМАЛИЗОВАННОГО Excel.

Как готовится Excel:
  • один лист "users" (или любой первый лист) с колонками: iin, full_name, username, email, role, group
  • username/email/role могут отсутствовать — будут заполнены по умолчанию

Запуск:
  python import.py --excel users_normalized.xlsx --db-file instance/psych_help.db

Что делает:
  • создаёт таблицу groups (id, name UNIQUE, course INTEGER NOT NULL DEFAULT 1), если её нет
  • добавляет колонку user.group_id при отсутствии и индекс по ней
  • читает Excel и для каждой строки (по iin) добавляет/находит пользователя и проставляет group_id

Примечание:
  • никаких диапазонов распределения здесь НЕТ — группа берётся строго из колонки "group"
"""
import argparse
import re
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

# -------------------- аргументы --------------------
def parse_args():
    p = argparse.ArgumentParser(description="Импорт пользователей из нормализованного Excel в PsychHelp.")
    p.add_argument("--excel", required=True, help="Путь к Excel-файлу (users_normalized.xlsx)")
    p.add_argument("--db", default=None, help="SQLAlchemy URL (например, sqlite:///instance/psych_help.db)")
    p.add_argument("--db-file", default=None, help="Путь к sqlite файлу БД (например, instance/psych_help.db)")
    return p.parse_args()

def sqlite_url_from_file(db_file: str) -> str:
    return f"sqlite:///{Path(db_file).resolve().as_posix()}"

def resolve_db_url(args) -> str:
    if args.db:
        return args.db
    if args.db_file:
        return sqlite_url_from_file(args.db_file)
    cand1 = Path("instance/psych_help.db")
    if cand1.exists():
        return sqlite_url_from_file(str(cand1))
    cand2 = Path("psych_help.db")
    return sqlite_url_from_file(str(cand2))

# -------------------- утилиты --------------------
ONLY_DIGITS = re.compile(r"\D")

def only_digits(s: str) -> str:
    return ONLY_DIGITS.sub("", s or "")

def is_iin(s: str) -> bool:
    return bool(s) and len(s) == 12 and s.isdigit()

# -------------------- DDL helpers (SQLite) --------------------
DDL_CREATE_GROUPS = """
CREATE TABLE IF NOT EXISTS groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    course INTEGER NOT NULL DEFAULT 1
);
"""

def ensure_user_group_id_column(conn):
    cols = conn.execute(text("PRAGMA table_info('user')")).fetchall()
    names = {row[1] for row in cols}
    if "group_id" not in names:
        conn.execute(text("ALTER TABLE user ADD COLUMN group_id INTEGER"))
    idx_rows = conn.execute(text("PRAGMA index_list('user')")).fetchall()
    idx_names = {row[1] for row in idx_rows}
    if "idx_user_group_id" not in idx_names:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_user_group_id ON user(group_id)"))

# -------------------- БД операции --------------------

def upsert_group(conn, name: str, course: int | None = None) -> int:
    if not name:
        raise ValueError("Пустое имя группы")
    row = conn.execute(text("SELECT id FROM groups WHERE name = :n"), {"n": name}).fetchone()
    if row:
        return int(row[0])
    eff_course = course if course is not None else 1
    res = conn.execute(text("INSERT INTO groups(name, course) VALUES (:n, :c)"), {"n": name, "c": eff_course})
    gid = res.lastrowid
    if gid is None:
        row = conn.execute(text("SELECT id FROM groups WHERE name = :n"), {"n": name}).fetchone()
        if not row:
            raise RuntimeError("Не удалось получить id группы после вставки")
        gid = int(row[0])
    return gid


def find_user_id_by_username_or_email(conn, username: str | None, email: str | None) -> int | None:
    if username:
        row = conn.execute(text("SELECT id FROM user WHERE username = :u"), {"u": username}).fetchone()
        if row:
            return int(row[0])
    if email:
        row = conn.execute(text("SELECT id FROM user WHERE email = :e"), {"e": email}).fetchone()
        if row:
            return int(row[0])
    return None


def insert_user(conn, username: str, email: str, password_hash: str, role: str, full_name: str | None) -> int:
    now_iso = datetime.utcnow().isoformat(sep=" ")
    res = conn.execute(
        text(
            """
            INSERT INTO user (username, email, password, role, full_name, created_at)
            VALUES (:u, :e, :p, :r, :f, :created)
            """
        ),
        {"u": username, "e": email, "p": password_hash, "r": role, "f": full_name or "", "created": now_iso},
    )
    uid = res.lastrowid
    if uid is None:
        row = conn.execute(text("SELECT id FROM user WHERE username = :u"), {"u": username}).fetchone()
        if not row:
            raise RuntimeError("Не удалось получить id пользователя после вставки")
        uid = int(row[0])
    return uid

# -------------------- загрузка Excel --------------------

def load_normalized_excel(path: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    df = xl.parse(xl.sheet_names[0], dtype=str).fillna("")
    # Проверяем обязательные
    need = {"iin", "group"}
    if not need.issubset({c.lower() for c in df.columns}):
        # попытаемся привести имена колонок к стандартным (кейсы)
        ren = {}
        for c in df.columns:
            low = c.lower()
            if low in {"iin", "group", "full_name", "username", "email", "role"}:
                ren[c] = low
        if ren:
            df = df.rename(columns=ren)
    # Теперь проверим снова
    if not need.issubset(set(df.columns)):
        raise SystemExit("[ERROR] В Excel обязательно нужны колонки: iin, group (остальные опциональны)")

    # Базовые заполнения
    if "username" not in df.columns:
        df["username"] = df["iin"].astype(str)
    if "email" not in df.columns:
        df["email"] = df["iin"].astype(str).map(lambda x: f"{x}@example.kz")
    if "role" not in df.columns:
        df["role"] = "student"
    if "full_name" not in df.columns:
        df["full_name"] = ""

    # Нормализация ИИН
    df["iin"] = df["iin"].map(lambda x: only_digits(str(x).strip()))
    df = df[df["iin"].map(is_iin)].copy()

    # Только нужные колонки
    return df[["iin", "full_name", "username", "email", "role", "group"]]

# -------------------- main --------------------

def main():
    args = parse_args()

    db_url = resolve_db_url(args)
    engine = create_engine(db_url, future=True)

    # Загружаем нормализованный Excel
    df = load_normalized_excel(Path(args.excel))
    if df.empty:
        print("[ERROR] В Excel нет валидных строк с ИИН.")
        sys.exit(1)

    inserted = 0
    updated_groups = 0
    skipped_dupe = 0

    with engine.begin() as conn:
        conn.execute(text(DDL_CREATE_GROUPS))
        ensure_user_group_id_column(conn)

        for rec in df.to_dict(orient="records"):
            iin = rec["iin"].strip()
            group_name = (rec.get("group") or "Без группы").strip()
            gid = upsert_group(conn, group_name, course=None)

            username = (rec.get("username") or iin).strip()
            email = (rec.get("email") or f"{iin}@example.kz").strip()
            role_val = (rec.get("role") or "student").strip().lower()
            if role_val not in ("student", "psychologist", "teacher", "admin"):
                role_val = "student"
            full_name = (rec.get("full_name") or "").strip()
            password_hash = generate_password_hash(f"{iin}abc")

            uid = find_user_id_by_username_or_email(conn, username=username, email=email)
            if uid is None:
                try:
                    uid = insert_user(conn, username=username, email=email, password_hash=password_hash, role=role_val, full_name=full_name)
                    inserted += 1
                except IntegrityError:
                    skipped_dupe += 1
                    uid = find_user_id_by_username_or_email(conn, username=username, email=email)
                    if uid is None:
                        continue
            conn.execute(text("UPDATE user SET group_id = :gid WHERE id = :uid"), {"gid": gid, "uid": uid})
            updated_groups += 1

    print("=== Импорт завершён ===")
    print(f"Всего к обработке:                     {len(df)}")
    print(f"Добавлено новых пользователей:         {inserted}")
    print(f"Обновлено/установлено group_id:        {updated_groups}")
    print(f"Пропущено (дубликаты при вставке):     {skipped_dupe}")
    print(f"БД: {db_url}")
    print(f"Источник Excel: {args.excel}")

if __name__ == "__main__":
    main()
