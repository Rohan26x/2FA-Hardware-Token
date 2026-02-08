from flask import Flask, request, jsonify
import sqlite3
import os

app = Flask(__name__)
DB_NAME = "cloud_secrets.db"


# --- DATABASE SETUP ---
def init_db():
    """Initializes the database if it doesn't exist."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute('''
                     CREATE TABLE IF NOT EXISTS secrets
                     (
                         id
                         INTEGER
                         PRIMARY
                         KEY
                         AUTOINCREMENT,
                         issuer
                         TEXT,
                         name
                         TEXT,
                         secret
                         TEXT
                         UNIQUE
                     )
                     ''')
    print(f"[SERVER] Database '{DB_NAME}' initialized.")


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn


# --- API ENDPOINTS ---

@app.route('/')
def home():
    return "ESP32 2FA Cloud Server is Running! Access /fetch to see data."


@app.route('/upload', methods=['POST'])
def upload_secret():
    """
    Endpoint for Desktop App to upload a new secret.
    Expects JSON: {"issuer": "Google", "name": "alice@gmail.com", "secret": "XYZ..."}
    """
    data = request.json
    if not data or 'secret' not in data:
        return jsonify({"status": "error", "message": "Invalid data"}), 400

    issuer = data.get('issuer', 'Unknown')
    name = data.get('name', 'Unknown')
    secret = data['secret']

    try:
        conn = get_db_connection()
        conn.execute('INSERT INTO secrets (issuer, name, secret) VALUES (?, ?, ?)',
                     (issuer, name, secret))
        conn.commit()
        conn.close()
        print(f"[SERVER] Received & Saved: {issuer} ({name})")
        return jsonify({"status": "success", "message": "Secret saved!"}), 201
    except sqlite3.IntegrityError:
        print(f"[SERVER] Duplicate Secret Skipped: {issuer} ({name})")
        return jsonify({"status": "error", "message": "Secret already exists"}), 409
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/fetch', methods=['GET'])
def fetch_secrets():
    """
    Endpoint for ESP32 to download ALL secrets.
    Returns JSON list: [{"issuer": "Google", "secret": "XYZ..."}, ...]
    """
    conn = get_db_connection()
    rows = conn.execute('SELECT issuer, name, secret FROM secrets').fetchall()
    conn.close()

    secrets_list = []
    for row in rows:
        secrets_list.append({
            "issuer": row['issuer'],
            "name": row['name'],
            "secret": row['secret']
        })

    print(f"[SERVER] ESP32 fetched {len(secrets_list)} secrets.")
    return jsonify(secrets_list)


if __name__ == '__main__':
    init_db()
    # Host='0.0.0.0' allows external devices (like ESP32) to connect
    print("[SERVER] Starting Flask Server on port 5000...")
    app.run(host='0.0.0.0', port=5000, debug=True)