import os
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import google.generativeai as genai
from gtts import gTTS

app = Flask(__name__)
CORS(app)

# Configure Gemini API using the environment variable set on Render
API_KEY = os.environ.get("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("WARNING: GEMINI_API_KEY environment variable not found.")

AUDIO_FILE = "response.mp3"

@app.route('/')
def index():
    # Serves the index.html file from the templates folder
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    user_message = request.form.get('message', '').strip()
    
    if not user_message:
        return jsonify({"text": "System core received an empty command, Sir."}), 400

    if not API_KEY:
        return jsonify({"text": "Configuration Error: Gemini API key is missing on the server mainframe."}), 500

    try:
        # Initializing the model configuration
        model = genai.GenerativeModel('gemini-pro')
        
        # Injecting Jarvis/Sunday identity context alongside the user's prompt
        system_context = f"You are Sunday, a highly intelligent, sleek, and loyal AI assistant inspired by Jarvis. Respond concisely and professionally to the following command: {user_message}"
        
        response = model.generate_content(system_context)
        response_text = response.text

        # Core logic to detect navigation or location keywords
        map_link = None
        lower_message = user_message.lower()
        if "where is" in lower_message or "map of" in lower_message or "navigate to" in lower_message:
            # Extract place name for the map overlay link
            place = user_message.replace("where is", "").replace("map of", "").replace("navigate to", "").strip()
            if place:
                map_link = f"https://www.google.com/maps?q={place}&output=embed"

        # Generate the voice synthesis file in the background
        if os.path.exists(AUDIO_FILE):
            os.remove(AUDIO_FILE)
            
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
