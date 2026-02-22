from flask import Flask, request, jsonify
from supabase import create_client, Client
import bcrypt
import jwt
import datetime
import os

app = Flask(__name__)

# --- SUPABASE CONFIG ---
# Best practice: Use Environment Variables in Vercel settings later.
# For now, you can paste them here (keep them private!).
SUPABASE_URL: str = "https://qiofnjxwvysnoidggxoz.supabase.co"
SUPABASE_KEY: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFpb2Zuanh3dnlzbm9pZGdneG96Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA0ODk4MDcsImV4cCI6MjA4NjA2NTgwN30.XuPKyrLtCfksGFVuw-dkpMW6tQ-dHQE8Hc2tF7X19ow"
JWT_SECRET   = "1476ba3a43aae90f8e0cb5ec46edf0f6551656867077135d7e77e4f3be304682"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- HELPER: Verify JWT Token ---
def verify_token(request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload["user_id"]
    except:
        return None

# --- ROUTES ---

@app.route('/')
def home():
    return "Global 2FA Server is Running!"

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"status": "error", "message": "Username and password required"}), 400

    username = data['username'].strip().lower()
    password = data['password']

    # Hash the password
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    try:
        supabase.table('users').insert({
            "username": username,
            "password_hash": password_hash
        }).execute()
        return jsonify({"status": "success", "message": "Account created!"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": "Username already exists"}), 409

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"status": "error", "message": "Username and password required"}), 400

    username = data['username'].strip().lower()
    password = data['password']

    # Fetch user from Supabase
    try:
        result = supabase.table('users').select("*").eq("username", username).execute()
        if not result.data:
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401

        user = result.data[0]

        # Verify password
        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return jsonify({"status": "error", "message": "Invalid credentials"}), 401

        # Generate JWT token (expires in 30 days)
        token = jwt.encode({
            "user_id": user['id'],
            "username": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
        }, JWT_SECRET, algorithm="HS256")

        return jsonify({"status": "success", "token": token, "username": username}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/upload', methods=['POST'])
def upload_secret():
    user_id = verify_token(request)
    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.json
    if not data or 'secret' not in data:
        return jsonify({"status": "error", "message": "Invalid data"}), 400

    try:
        supabase.table('secrets').insert({
            "issuer": data.get('issuer', 'Unknown'),
            "name": data.get('name', 'Unknown'),
            "secret": data['secret'],
            "user_id": user_id
        }).execute()
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/fetch', methods=['GET'])
def fetch_secrets():
    user_id = verify_token(request)
    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    try:
        response = supabase.table('secrets').select("*").eq("user_id", user_id).execute()
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete', methods=['DELETE'])
def delete_secret():
    user_id = verify_token(request)
    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401

    data = request.json
    if not data or 'id' not in data:
        return jsonify({"status": "error", "message": "Secret ID required"}), 400

    try:
        supabase.table('secrets').delete().eq("id", data['id']).eq("user_id", user_id).execute()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run()