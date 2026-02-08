from flask import Flask, request, jsonify
from supabase import create_client, Client
import os

app = Flask(__name__)

# --- SUPABASE CONFIG ---
# Best practice: Use Environment Variables in Vercel settings later.
# For now, you can paste them here (keep them private!).
url: str = "https://qiofnjxwvysnoidggxoz.supabase.co"
key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFpb2Zuanh3dnlzbm9pZGdneG96Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzA0ODk4MDcsImV4cCI6MjA4NjA2NTgwN30.XuPKyrLtCfksGFVuw-dkpMW6tQ-dHQE8Hc2tF7X19ow"
supabase: Client = create_client(url, key)

@app.route('/')
def home():
    return "Global 2FA Server is Running!"

@app.route('/api/upload', methods=['POST'])
def upload_secret():
    data = request.json
    if not data or 'secret' not in data:
        return jsonify({"status": "error", "message": "Invalid data"}), 400

    # Insert into Supabase
    try:
        response = supabase.table('secrets').insert({
            "issuer": data.get('issuer', 'Unknown'),
            "name": data.get('name', 'Unknown'),
            "secret": data['secret']
        }).execute()
        return jsonify({"status": "success"}), 201
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/fetch', methods=['GET'])
def fetch_secrets():
    # Select all secrets from Supabase
    try:
        response = supabase.table('secrets').select("*").execute()
        # Supabase returns data in response.data
        return jsonify(response.data)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# Vercel needs this "app" object
if __name__ == '__main__':
    app.run()