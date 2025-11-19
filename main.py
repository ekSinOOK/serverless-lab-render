from flask import Flask, request, jsonify
import os
import psycopg2
from urllib.parse import urlparse

app = Flask(__name__)

def get_db_connection():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        raise RuntimeError("❌ Missing DATABASE_URL")

    url = urlparse(DATABASE_URL)
    # Убедимся, что все поля есть
    if not url.hostname:
        raise ValueError("❌ Invalid DATABASE_URL: missing host")

    return psycopg2.connect(
        database=url.path[1:] or "postgres",  # fallback
        user=url.username or "",
        password=url.password or "",
        host=url.hostname,
        port=url.port or 5432,
        sslmode="require"  # важно для Render PostgreSQL!
    )

def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()
    finally:
        conn.close()

# Инициализация БД при первом запросе или отдельно — НЕ при импорте!
# Для простоты вызовем init_db() вручную один раз после запуска (опционально),
# но безопаснее — делать её внутри роутов или при первом подключении.

@app.before_first_request
def setup():
    try:
        init_db()
        print("✅ DB initialized")
    except Exception as e:
        print("⚠️ DB init failed, will retry on demand:", repr(e))

@app.route('/save', methods=['POST'])
def save_message():
    try:
        conn = get_db_connection()
        try:
            data = request.get_json()
            message = data.get('message', '') if data else ''
            with conn.cursor() as cur:
                cur.execute("INSERT INTO messages (content) VALUES (%s)", (message,))
                conn.commit()
            return jsonify({"status": "saved", "message": message})
        finally:
            conn.close()
    except Exception as e:
        print("❌ /save error:", repr(e))
        return jsonify({"error": str(e)}), 500

@app.route('/messages')
def get_messages():
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT id, content, created_at FROM messages ORDER BY id DESC LIMIT 10")
                rows = cur.fetchall()
            messages = [{"id": r[0], "text": r[1], "time": r[2].isoformat()} for r in rows]
            return jsonify(messages)
        finally:
            conn.close()
    except Exception as e:
        print("❌ /messages error:", repr(e))
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)