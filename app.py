import os
import sqlite3
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from groq import Groq
from gtts import gTTS

app = Flask(__name__)
# Secure encryption key for user sessions
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "sunday_mainframe_encryption_key_99")
CORS(app)

# Saving to /tmp guarantees Render has permissions to read/write the database file
DB_FILE = "/tmp/sunday.db"
AUDIO_FILE = "/tmp/response.mp3"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# Initialize tables immediately on boot up
init_db()

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
            return render_template('login.html', error="All entry arrays must be populated.")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        if action == "register":
            try:
                hashed_pw = generate_password_hash(password)
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
                conn.commit()
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                session['user_id'] = cursor.fetchone()[0]
                session['username'] = username
                conn.close()
                return redirect(url_for('index'))
            except sqlite3.IntegrityError:
                conn.close()
                return render_template('login.html', error="Username designated string already exists.")
        
        elif action == "login":
            cursor.execute("SELECT id, password FROM users WHERE username = ?", (username,))
            user = cursor.fetchone()
            conn.close()
            
            # FIXED: Accessing tuple index [0] and [1] directly to stop the 500 error crash
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                return redirect(url_for('index'))
            return render_template('login.html', error="Invalid identity verification matrix.")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/get-history', methods=['GET'])
def get_history():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content FROM history WHERE user_id = ? ORDER BY id ASC", (session['user_id'],))
    rows = cursor.fetchall()
    conn.close()
    
    history_list = [{"role": row[0], "content": row[1]} for row in rows]
    return jsonify(history_list)

@app.route('/ask', methods=['POST'])
def ask():
    if 'user_id' not in session:
        return jsonify({"text": "Access denied. Sign-in required."}), 401
    
    user_message = request.form.get('message', '').strip()
    if not user_message:
        return jsonify({"text": "System core received an empty command, Sir."}), 400

    if not client:
        return jsonify({"text": "Configuration Error: Groq API key missing on server."}), 500

    user_id = session['user_id']

    # Log user message entry
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO history (user_id, role, content) VALUES (?, 'user', ?)", (user_id, user_message))
    conn.commit()

    # Build historical content stream context for Groq memory tracking
    cursor.execute("SELECT role, content FROM history WHERE user_id = ? ORDER BY id ASC LIMIT 20", (user_id,))
    past_rows = cursor.fetchall()
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

        # Save assistant text message response
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (user_id, role, content) VALUES (?, 'assistant', ?)", (user_id, response_text))
        conn.commit()
        conn.close()

        map_link = None
        lower_message = user_message.lower()
        if "where is" in lower_message or "map of" in lower_message or "navigate to" in lower_message:
            place = user_message.replace("where is", "").replace("map of", "").replace("navigate to", "").strip()
            if place:
                map_link = f"https://www.google.com/maps?q={place}&output=embed"

        if os.path.exists(AUDIO_FILE):
            try: os.remove(AUDIO_FILE)
            except Exception: pass
            
        tts = gTTS(text=response_text, lang='en', tld='com')
        tts.save(AUDIO_FILE)

        return jsonify({"text": response_text, "map_link": map_link})

    except Exception as e:
        return jsonify({"text": f"Mainframe execution failure: {str(e)}"}), 500

@app.route('/get-audio')
def get_audio():
    if os.path.exists(AUDIO_FILE):
        return send_file(AUDIO_FILE, mimetype="audio/mp3")
    return "No audio file available", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
