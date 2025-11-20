from main import app
from extensions import db

with app.app_context():
    conn = db.engine.connect()
    # Каждую команду в try, чтобы не падало, если колонка уже есть
    try:
        conn.exec_driver_sql("ALTER TABLE test ADD COLUMN title_kk TEXT")
    except Exception as e:
        print("title_kk:", e)

    try:
        conn.exec_driver_sql("ALTER TABLE test ADD COLUMN description_kk TEXT")
    except Exception as e:
        print("description_kk:", e)

    try:
        conn.exec_driver_sql("ALTER TABLE test ADD COLUMN test_type VARCHAR(20) DEFAULT 'classic'")
    except Exception as e:
        print("test_type:", e)

    conn.close()
