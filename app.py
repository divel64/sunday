import os
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from groq import Groq
from gtts import gTTS

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.environ.get("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")
client = None

if GROQ_API_KEY:
    client = Groq(api_key=GROQ_API_KEY)
else:
    print("WARNING: GROQ_API_KEY environment variable not found.")

AUDIO_FILE = "response.mp3"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    user_message = request.form.get('message', '').strip()
    
    if not user_message:
        return jsonify({"text": "System core received an empty command, Sir."}), 400

    if not client:
        return jsonify({"text": "Configuration Error: Groq API key is missing on Render settings dashboard."}), 500

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are Sunday, a highly intelligent, sleek, and loyal AI assistant inspired by Jarvis. Respond concisely and professionally."
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            model="llama-3.3-70b-versatile",
        )
        
        response_text = chat_completion.choices[0].message.content

        map_link = None
        lower_message = user_message.lower()
        if "where is" in lower_message or "map of" in lower_message or "navigate to" in lower_message:
            place = user_message.replace("where is", "").replace("map of", "").replace("navigate to", "").strip()
            if place:
                map_link = f"https://www.google.com/maps?q={place}&output=embed"

        if os.path.exists(AUDIO_FILE):
            try:
                os.remove(AUDIO_FILE)
            except Exception:
                pass
            
        tts = gTTS(text=response_text, lang='en', tld='com')
        tts.save(AUDIO_FILE)

        return jsonify({
            "text": response_text,
            "map_link": map_link
        })

    except Exception as e:
        return jsonify({"text": f"Mainframe execution failure: {str(e)}"}), 500

@app.route('/get-audio')
def get_audio():
    if os.path.exists(AUDIO_FILE):
        return send_file(AUDIO_FILE, mimetype="audio/mp3")
    return "No audio file available", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
