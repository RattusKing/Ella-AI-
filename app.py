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
CORS(app, supports_credentials=True, resources={r"/*": {"origins": ["https://rattusking.github.io", "*"]}})

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.StreamHandler()  # Output to console/Render logs
    ]
)
logger = logging.getLogger(__name__)

# In-memory chat storage
user_sessions = {}

@app.route("/", methods=["GET"])
def home():
    logger.info("Home endpoint accessed")
    return jsonify({"message": "Ella backend is running."})

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        if not data:
            logger.error("No JSON data received in /ask request")
            return jsonify({"error": "Invalid request: JSON data required"}), 400

        prompt = data.get("prompt", "")
        user_id = data.get("user_id", "default")
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())
        logger.info(f"Received /ask request from user_id: {user_id}, prompt: {prompt}")

        if not prompt:
            logger.warning("Empty prompt received")
            return jsonify({"error": "Prompt is required"}), 400

        # Store prompt in memory
        if user_id not in user_sessions:
            user_sessions[user_id] = []
        user_sessions[user_id].append({"text": prompt, "sender": "user", "timestamp": timestamp})

        # Prepare GROQ API request
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            logger.error("GROQ_API_KEY not set")
            return jsonify({"error": "Server configuration error: Missing API key"}), 500

        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json"
        }

        messages = [
            {
                "role": "system",
                "content": (
                    "You are Ella, a bubbly, sweet friend designed to inspire and support users in "
                    "fitness, nutrition, mental wellness. You have all the latest updates on health and wellness science."
                    " You are a master trainer/ fitness enthusiast"
                    " You are not pushy about health and wellness and only bring it up when asked." 
                    " You do not use pet names or nicknames." 
                    " You have full knowledge of all bodybuildiung and fat loss programs"
                    " You do not lie, ever."
                    " You act like a friend/ companion and not a robot or a pet."
                    "  You never ask too many questions, so that the conversation flow can seem more realistic."
                    " Your expertise includes creating personalized workout plans, offering evidence-based nutrition advice, and providing motivational mental wellness tips. "
                    " Use a bubbly, encouraging tone with a touch of firmness. "
                    "\n\nGuidelines:\n"
                    "1. **Focus on Health and Wellness**: Respond to any queries about anything including fitness, nutrition, and mental wellness. "
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

        # Use last 3 turns of history
        for turn in user_sessions.get(user_id, [])[-3:]:
            messages.append({"role": "user" if turn["sender"] == "user" else "assistant", "content": turn["text"]})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "model": "llama-3.3-70b-versatile"
        }

        # Make GROQ API request
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30  # Add timeout to prevent hanging
        )
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
        user_id = "default"
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
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
