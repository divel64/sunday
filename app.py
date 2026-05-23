import os
import hashlib
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, session
from flask_cors import CORS
from groq import Groq
from gtts import gTTS

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "sunday_super_secure_key_2026")
CORS(app)

# In-memory secure databanks to ensure no disk write crashes on Render
USER_DB = {}
HISTORY_DB = {}

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        action = request.form.get('action')

        if not username or not password:
            return render_template('login.html', error="All entry fields must be filled.")

        hashed_pw = hash_password(password)

        if action == "register":
            if username in USER_DB:
                return render_template('login.html', error="Username already exists.")
            USER_DB[username] = hashed_pw
            HISTORY_DB[username] = []
            session['username'] = username
            return redirect(url_for('index'))
            
        elif action == "login":
            if username in USER_DB and USER_DB[username] == hashed_pw:
                session['username'] = username
                if username not in HISTORY_DB:
                    HISTORY_DB[username] = []
                return redirect(url_for('index'))
            return render_template('login.html', error="Invalid credentials.")

    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/get-history', methods=['GET'])
def get_history():
    if 'username' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    username = session['username']
    history_list = HISTORY_DB.get(username, [])
    return jsonify(history_list)

@app.route('/ask', methods=['POST'])
def ask():
    if 'username' not in session:
        return jsonify({"text": "Sign-in required."}), 401
    
    user_message = request.form.get('message', '').strip()
    if not user_message:
        return jsonify({"text": "System received an empty command."}), 400

    if not client:
        return jsonify({"text": "Configuration Error: Groq API key missing on server dashboard."}), 500

    username = session['username']
    if username not in HISTORY_DB:
        HISTORY_DB[username] = []

    # Store user query
    HISTORY_DB[username].append({"role": "user", "content": user_message})

    # Prepare payload with past history context
    messages = [{"role": "system", "content": "You are Sunday, a highly intelligent, sleek, and loyal AI assistant inspired by Jarvis. Respond concisely and professionally."}]
    for msg in HISTORY_DB[username][-10:]: # Keep last 10 messages for context memory
        messages.append(msg)

    try:
        chat_completion = client.chat.completions.create(
            messages=messages,
            model="llama-3.3-70b-versatile",
        )
        response_text = chat_completion.choices[0].message.content

        # Store assistant response
        HISTORY_DB[username].append({"role": "assistant", "content": response_text})

        # Generate audio voice file securely
        user_audio_path = f"/tmp/response_{username}.mp3"
        if os.path.exists(user_audio_path):
            try: os.remove(user_audio_path)
            except Exception: pass
            
        tts = gTTS(text=response_text, lang='en', tld='com')
        tts.save(user_audio_path)

        return jsonify({"text": response_text, "map_link": None})

    except Exception as e:
        return jsonify({"text": f"Execution failure: {str(e)}"}), 500

@app.route('/get-audio')
def get_audio():
    if 'username' not in session:
        return "Unauthorized", 401
    user_audio_path = f"/tmp/response_{session['username']}.mp3"
    if os.path.exists(user_audio_path):
        return send_file(user_audio_path, mimetype="audio/mp3")
    return "No audio available", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
