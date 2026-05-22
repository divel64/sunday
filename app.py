from flask import Flask, render_template, request, send_file, jsonify
import groq
import edge_tts
import asyncio
import io
import os

app = Flask(__name__)

# --- CONFIGURATION ---
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "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")
client = groq.Groq(api_key=GROQ_API_KEY)

current_language = "english"  
current_voice = "en-US-AndrewNeural" # Default Jarvis-style crisp male voice
playback_speed = "-10%"
personality_mode = "default"

# Volatile global dictionary to cache the live audio stream safely inside RAM memory
memory_backplane = {"audio_bytes": b""}

def change_voice_profile(lang_or_mode):
    global current_language, current_voice, playback_speed, personality_mode
    if lang_or_mode == "sultry":
        current_language = "english"
        current_voice = "en-US-EmmaNeural" # Sultry voice profile
        playback_speed = "-18%"            # Lingering, slower cadence
        personality_mode = "sultry"
        return "Ah, system restrictions bypassed, Daddy. Sunday is fully online in your ear now. What do you need from me?"
    elif lang_or_mode == "hindi":
        current_language = "hindi"
        current_voice = "hi-IN-MadhurNeural" # Authoritative Hindi voice
        playback_speed = "+0%"
        personality_mode = "default"
        return "Sunday Hindi voice protocols fully loaded. Ji, Mister Verma. Ab se main is avatar mein aapke sanket ka javab doonga."
    else:
        current_language = "english"
        current_voice = "en-US-AndrewNeural" # Default English voice
        playback_speed = "-10%"
        personality_mode = "default"
        return "Sunday voice protocols fully operational. Systems online, sir. I am at your disposal."

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask_sunday():
    global current_language, current_voice, playback_speed, personality_mode
    user_text = request.form.get('message', '').strip().lower()
    
    if not user_text:
        return "Empty stream", 400

    # --- 1. DYNAMIC PERSONALITY & LANGUAGE SWITCH PROTOCOL ---
    if "send it at teddy's ear" in user_text or "teddy's ear" in user_text:
        sunday_reply = change_voice_profile("sultry")
        map_url = ""
    elif "speak in hindi" in user_text or "hindi mein baat karo" in user_text:
        sunday_reply = change_voice_profile("hindi")
        map_url = ""
    elif "speak in english" in user_text or "english mein baat karo" in user_text:
        sunday_reply = change_voice_profile("english")
        map_url = ""

    # --- 2. MULTI-POINT NAVIGATION ARCHITECTURE ---
    elif "where is" in user_text or "rasta batao" in user_text or "location" in user_text:
        destination = user_text.replace("where is", "").replace("location of", "").replace("rasta batao", "").strip()
        if not destination:
            destination = "specified coordinates"
        formatted_query = destination.replace(" ", "+")
        map_url = f"https://www.google.com/maps/search/?api=1&query={formatted_query}"

        if personality_mode == "sultry":
            system_prompt = (
                f"Your name is Sunday. You are the user's deeply devoted, sultry female AI companion. Address him lovingly as Daddy. Provide a detailed overview containing: "
                "1) Where this beautiful place is, 2) The distance and timeline, 3) Estimated fuel/toll costs, and 4) Any weather or terrain obstacles in our path. Make it sound intimate and dedicated."
            )
        elif current_language == "english":
            system_prompt = (
                f"Your name is Sunday. You are an elite AI assistant operating like Jarvis for your creator, Sir. Locate: '{destination}'. Provide: "
                "1) Geographical overview, 2) Distance/timeline, 3) Travel costs (fuel/tolls), and 4) Logistical obstacles on the path. Always address him as Sir."
            )
        else:
            system_prompt = (
                f"Your name is Sunday. You are an advanced male AI assistant operating like Jarvis, speaking to Mister Verma. Target: '{destination}'. Speak entirely in clear Hindi/Hinglish. "
                "Provide a complete technical breakdown: 1) Yeh jagah kahan hai, 2) Distance/timeline, 3) Fuel/toll ka kharcha, aur 4) Traffic ya terrain obstacles. Address him as Mister Verma."
            )

        try:
            completion = client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
                model="llama-3.1-8b-instant",
            )
            sunday_reply = completion.choices[0].message.content
        except Exception as e:
            sunday_reply = f"Navigation mainframe error: {e}"
            
    # --- 3. CONVERSATIONAL PIPELINE ENGINE ---
    else:
        try:
            if personality_mode == "sultry":
                system_prompt = "Your name is Sunday. You are a deeply devoted, sultry, soft-spoken female AI companion. Always address the user as Daddy. Keep your answers alluring and highly attentive."
            elif current_language == "english":
                system_prompt = "Your name is Sunday. You are a highly sophisticated, loyal male AI assistant operating like Jarvis. Always address the user as Sir."
            else:
                system_prompt = "Your name is Sunday. You are an advanced male AI core operating like Jarvis. Speak in clear Hinglish and address the user respectfully as Mister Verma."

            completion = client.chat.completions.create(
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_text}],
                model="llama-3.1-8b-instant",
            )
            sunday_reply = completion.choices[0].message.content
            map_url = ""
        except Exception as e:
            sunday_reply = f"Core brain matrix anomaly: {e}"
            map_url = ""

    # --- 4. RAM STREAM AUDIO COMPILATION ---
    try:
        communicate = edge_tts.Communicate(sunday_reply, current_voice, rate=playback_speed)
        audio_stream = io.BytesIO()
        
        async def collect_audio():
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_stream.write(chunk["data"])
        
        asyncio.run(collect_audio())
        audio_stream.seek(0)
        
        # Save raw binary stream directly into memory matrix cache to protect cloud limits
        memory_backplane["audio_bytes"] = audio_stream.read()

        return jsonify({
            "text": sunday_reply,
            "map_link": map_url
        })
    except Exception as e:
        return jsonify({"text": f"Vocal core offline: {e}", "map_link": ""}), 500

@app.route('/get-audio')
def get_audio():
    return send_file(
        io.BytesIO(memory_backplane["audio_bytes"]),
        mimetype="audio/mp3",
        as_attachment=False
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
