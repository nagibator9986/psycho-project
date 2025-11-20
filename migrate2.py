# migrate_full_tests_i18n.py
from main import app
from extensions import db

def safe_exec(conn, sql):
    try:
        conn.exec_driver_sql(sql)
        print("OK:", sql)
    except Exception as e:
        print("SKIP:", sql, "->", e)

with app.app_context():
    conn = db.engine.connect()

    # --- test ---
    safe_exec(conn, "ALTER TABLE test ADD COLUMN title_kk TEXT")
    safe_exec(conn, "ALTER TABLE test ADD COLUMN description_kk TEXT")
    safe_exec(conn, "ALTER TABLE test ADD COLUMN test_type VARCHAR(20) DEFAULT 'classic'")

    # --- question ---
    safe_exec(conn, "ALTER TABLE question ADD COLUMN text_kk TEXT")

    # --- question_option ---
    safe_exec(conn, "ALTER TABLE question_option ADD COLUMN text_kk TEXT")

    # --- test_result ---
    safe_exec(conn, "ALTER TABLE test_result ADD COLUMN language VARCHAR(5) DEFAULT 'ru'")

    conn.close()

    # создаст новые таблицы (например, test_scale_option), если их ещё нет
    db.create_all()
    print("db.create_all() done")
