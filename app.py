from flask import Flask, request, jsonify
import os
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama3-70b-8192"

# In-memory storage for conversation history (resets on server restart)
user_sessions = {}  # {user_id: [{text: str, sender: str, timestamp: str}]}

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Ella backend is running."})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        history = data.get("history", [])
        user_id = data.get("user_id", "default")

        # Load or initialize session history
        if user_id not in user_sessions:
            user_sessions[user_id] = history
        else:
            user_sessions[user_id] = history  # Update with frontend-provided history

        # Prepare messages for Groq
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        messages = [
            {
                "role": "system",
                "content": "You are Ella, a wellness and mental health AI assistant. Use the conversation history to provide context-aware, concise, and encouraging answers. Prioritize evidence-based advice."
            }
        ] + [
            {"role": "user" if msg["sender"] == "user" else "assistant", "content": msg["text"]}
            for msg in user_sessions[user_id][-5:]  # Limit to last 5 messages to avoid token overflow
        ]
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "model": GROQ_MODEL,
        }

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()  # Raise exception for non-200 responses
        result = response.json()

        reply = result["choices"][0]["message"]["content"]

        # Update session history
        user_sessions[user_id].append({"text": prompt, "sender": "user", "timestamp": data.get("timestamp", "")})
        user_sessions[user_id].append({"text": reply, "sender": "bot", "timestamp": ""})

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

if __name__ == "__main__":
    app.run(debug=True)
