import os
import psycopg2
import hashlib
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from flask_cors import CORS
from groq import Groq
from gtts import gTTS

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "sunday_mainframe_secure_key_101")
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    # Establishes a secure pipeline to Render's hosted database cluster
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

if DATABASE_URL:
    init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        action = request.form.get('action')

        if not username or not password:
            return render_template('login.html', error="All entry fields must be filled.")

        conn = get_db_connection()
        cursor = conn.cursor()

        if action == "register":
            try:
                hashed_pw = hash_password(password)
                cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_pw))
                conn.commit()
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                row = cursor.fetchone()
                session['user_id'] = row[0]
                session['username'] = username
                cursor.close()
                conn.close()
                return redirect(url_for('index'))
            except Exception:
                conn.rollback()
                cursor.close()
                conn.close()
                return render_template('login.html', error="Username already exists.")
        
        elif action == "login":
            cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
            user = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if user and user[1] == hash_password(password):
                session['user_id'] = user[0]
                session['username'] = username
                return redirect(url_for('index'))
            return render_template('login.html', error="Invalid credentials.")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/get-history', methods=['GET'])
def get_history():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM history WHERE user_id = %s ORDER BY id ASC", (session['user_id'],))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    history_list = [{"role": row[0], "content": row[1]} for row in rows]
    return jsonify(history_list)

@app.route('/ask', methods=['POST'])
def ask():
    if 'user_id' not in session:
        return jsonify({"text": "Sign-in required."}), 401
    
    user_message = request.form.get('message', '').strip()
    if not user_message:
        return jsonify({"text": "System received an empty command."}), 400

    if not client:
        return jsonify({"text": "Configuration Error: Groq API key missing on server."}), 500

    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO history (user_id, role, content) VALUES (%s, 'user', %s)", (user_id, user_message))
    conn.commit()

    cursor.execute("SELECT role, content FROM history WHERE user_id = %s ORDER BY id ASC LIMIT 20", (user_id,))
    past_rows = cursor.fetchall()
    cursor.close()
    conn.close()

    messages = [{"role": "system", "content": "You are Sunday, a highly intelligent, sleek, and loyal AI assistant inspired by Jarvis. Respond concisely and professionally."}]
    for row in past_rows:
        messages.append({"role": row[0], "content": row[1]})

    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
        )
        response_text = chat_completion.choices[0].message.content

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (user_id, role, content) VALUES (%s, 'assistant', %s)", (user_id, response_text))
        conn.commit()
        cursor.close()
        conn.close()

        map_link = None
        lower_message = user_message.lower()
        if "where is" in lower_message or "map of" in lower_message or "navigate to" in lower_message:
            place = user_message.replace("where is", "").replace("map of", "").replace("navigate to", "").strip()
            if place:
                map_link = f"https://www.google.com/maps?q={place}&output=embed"

        user_audio_path = f"/tmp/response_{user_id}.mp3"
        if os.path.exists(user_audio_path):
            try: os.remove(user_audio_path)
            except Exception: pass
            
        tts = gTTS(text=response_text, lang='en', tld='com')
        tts.save(user_audio_path)

        return jsonify({"text": response_text, "map_link": map_link})

    except Exception as e:
        return jsonify({"text": f"Execution failure: {str(e)}"}), 500

@app.route('/get-audio')
def get_audio():
    if 'user_id' not in session:
        return "Unauthorized", 401
    user_audio_path = f"/tmp/response_{session['user_id']}.mp3"
    if os.path.exists(user_audio_path):
        return send_file(user_audio_path, mimetype="audio/mp3")
    return "No audio available", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
