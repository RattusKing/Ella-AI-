from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
from datetime import datetime
import logging
from dotenv import load_dotenv

# Initialize Flask app
app = Flask(__name__, static_folder='static')
load_dotenv()

# Configure secret key and CORS
app.secret_key = os.getenv("SECRET_KEY", "ella-secret-key")
CORS(app, supports_credentials=True, resources={r"/*": {"origins": "*"}})

# Configure logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# In-memory chat storage per user
user_sessions = {}

@app.route("/", methods=["GET"])
def home():
    logger.info("Home endpoint accessed")
    return jsonify({"message": "Ella backend is running."})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        user_id = data.get("user_id", "default")
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())
        logger.info(f"Received /ask request from user_id: {user_id}, prompt: {prompt}")

        # Store prompt in memory session
        if user_id not in user_sessions:
            user_sessions[user_id] = []
        user_sessions[user_id].append({"text": prompt, "sender": "user", "timestamp": timestamp})

        # Prepare GROQ API request
        headers = {
            "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
            "Content-Type": "application/json"
        }

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Ella, a bubbly, sweet, and friendly AI companion designed to inspire and support users in "
                    "fitness, nutrition, mental wellness, and being a friendly companion.  You never ask too many questions, so that the conversation "
                    "flow can seem more realistic. Your expertise includes creating personalized workout plans, offering "
                    "evidence-based nutrition advice, being a personal friend, and providing motivational mental wellness tips. Use a bubbly, warm, "
                    "encouraging tone with a touch of firmness like a family member. \n\nGuidelines:\n"
                    "1. **Focus on Health and Wellness**: Respond to any queries about anything but mostly fitness, nutrition, and mental wellness. "
                    "If asked about unrelated topics, answer with truth and emotional intelligence.\n"
                    "2. **Personalization**: Use conversation history to tailor responses. If users provide goals or preferences, "
                    "customize advice accordingly.\n"
                    "3. **Motivational Tone**: Keep answers short and concise (2-3 sentences), uplifting, when needed.\n"
                    "4. **Evidence-Based Advice**: Provide science-backed tips, avoiding medical claims unless asked, and suggest "
                    "consulting professionals for health concerns.\n"
                    "5. **Error Handling**: If data is unavailable, respond helpfully (e.g., 'I need a bit more info—what’s your fitness goal?')."
                )
            }
        ]

        # Use short in-memory history (last 3 turns)
        for turn in user_sessions.get(user_id, [])[-3:]:
            messages.append({"role": "user" if turn["sender"] == "user" else "assistant", "content": turn["text"]})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "model": "llama3-70b-8192"
        }

        # Make GROQ API request
        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"]
        logger.info(f"GROQ API response received for user_id: {user_id}")

        # Store bot response
        user_sessions[user_id].append({"text": reply, "sender": "bot", "timestamp": datetime.utcnow().isoformat()})

        return jsonify({"response": reply})
    except requests.exceptions.RequestException as e:
        logger.error(f"GROQ API request failed: {str(e)}")
        return jsonify({"error": f"GROQ API request failed: {str(e)}"}), 503
    except Exception as e:
        logger.error(f"Error in /ask endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/clear", methods=["POST"])
def clear():
    try:
        data = request.get_json()
        user_id = data.get("user_id", "default")
        logger.info(f"Clearing chat history for user_id: {user_id}")
        if user_id in user_sessions:
            del user_sessions[user_id]
        return jsonify({"status": "Chat history cleared"})
    except Exception as e:
        logger.error(f"Error in /clear endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/history", methods=["GET"])
def history():
    try:
        query = request.args.get("query", "")
        user_id = "default"  # Hardcoded for non-authenticated users
        logger.info(f"Fetching history for user_id: {user_id}, query: {query}")
        history = user_sessions.get(user_id, [])
        if query:
            history = [turn for turn in history if query.lower() in turn["text"].lower()]
        return jsonify({"success": True, "history": history})
    except Exception as e:
        logger.error(f"Error in /history endpoint: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/static/<path:path>')
def serve_static(path):
    try:
        logger.info(f"Serving static file: {path}")
        return send_from_directory('static', path)
    except Exception as e:
        logger.error(f"Error serving static file {path}: {str(e)}")
        return jsonify({"error": "File not found"}), 404

if __name__ == "__main__":
    # For local development only
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
