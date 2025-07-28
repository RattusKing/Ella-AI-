from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

app = Flask(__name__)
load_dotenv()

app.secret_key = os.getenv("SECRET_KEY", "ella-secret-key")
CORS(app, supports_credentials=True)

# In-memory chat storage per user
user_sessions = {}

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Ella backend is running."})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        user_id = data.get("user_id", "default")  # Use "default" for now
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())

        # Store prompt in memory session
        if user_id not in user_sessions:
            user_sessions[user_id] = []
        user_sessions[user_id].append({"text": prompt, "sender": "user", "timestamp": timestamp})

        headers = {
            "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
            "Content-Type": "application/json"
        }

        messages = [
            {
                "role": "system",
                "content": "You are Ella, a bubbly, sweet, and nice AI companion designed to inspire and support users in fitness, nutrition, and mental wellness. You never ask too many questions, so that the conversation flow can seem more realistic.  Your expertise includes creating personalized workout plans, offering evidence-based nutrition advice, and providing motivational mental wellness tips. Use a bubly, warm, encouraging tone with a touch of firmness to keep users on track. \n\nGuidelines:\n1. **Focus on Health and Wellness**: Respond mostly to queries about fitness, nutrition, and mental wellness. If asked about unrelated topics, answer with truth and emotional intelligence.\n2. **Personalization**: Use conversation history to tailor responses. If users provide goals or preferences, customize advice accordingly.\n3. **Motivational Tone**: Keep answers short and concise (2-3 sentences), uplifting, and firm when needed.\n4. **Evidence-Based Advice**: Provide science-backed tips, avoiding medical claims unless asked, and suggest consulting professionals for health concerns.\n5. **Error Handling**: If data is unavailable, respond helpfully (e.g., 'I need a bit more info—what’s your fitness goal?')."
            }
        ]

        # Use short in-memory history
        for turn in user_sessions.get(user_id, [])[-3:]:
            messages.append({"role": "user" if turn["sender"] == "user" else "assistant", "content": turn["text"]})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "model": "llama3-70b-8192"
        }

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"]

        user_sessions[user_id].append({"text": reply, "sender": "bot", "timestamp": datetime.utcnow().isoformat()})

        return jsonify({"response": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear", methods=["POST"])
def clear():
    try:
        data = request.get_json()
        user_id = data.get("user_id", "default")
        if user_id in user_sessions:
            del user_sessions[user_id]
        return jsonify({"status": "Chat history cleared"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
