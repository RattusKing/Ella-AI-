from flask import Flask, request, jsonify, session, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
import os
import requests
import bcrypt
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "ella-secret-key")  # Fallback for local testing
CORS(app, supports_credentials=True)  # Enable credentials for session cookies

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# In-memory user database with hashed passwords
users = {
    "test@example.com": {
        "password": bcrypt.hashpw("pass123".encode(), bcrypt.gensalt()),
        "id": "user1"
    },
    "levi@ella.com": {
        "password": bcrypt.hashpw("founder".encode(), bcrypt.gensalt()),
        "id": "levi1"
    }
}

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    for user in users.values():
        if user["id"] == user_id:
            return User(user_id)
    return None

# In-memory storage for conversation history (resets on server restart)
user_sessions = {}  # {user_id: [{text: str, sender: str, timestamp: str}]}

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Ella backend is running."})

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password").encode()
        user = users.get(email)
        if user and bcrypt.checkpw(password, user["password"]):
            user_obj = User(user["id"])
            login_user(user_obj)
            return jsonify({"success": True})
        return jsonify({"success": False, "message": "Invalid email or password"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/logout", methods=["POST"])  # Changed to POST for consistency with frontend
@login_required
def logout():
    try:
        logout_user()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/whoami", methods=["GET"])
@login_required
def whoami():
    try:
        return jsonify({"success": True, "user": current_user.id})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

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
            "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
            "Content-Type": "application/json"
        }
        messages = [
            {
                "role": "system",
                "content": "You are Ella, a cyberpunk-themed AI frontend assistant for gyms and hotels, designed to provide wise, professional, and concise answers. Your expertise includes fitness, wellness, gym operations (e.g., class schedules, membership reports), and hotel operations (e.g., bookings, occupancy rates). Use a witty, futuristic tone inspired by cyberpunk aesthetics (e.g., neon-lit, tech-driven vibe). \n\nGuidelines:\n1. **Context Awareness**: Use conversation history and user-provided system details (e.g., 'set system glofox ID abc123') to tailor responses. If system data is available (e.g., via API), incorporate it naturally (e.g., 'Your gym at ID abc123 has 50 active members').\n2. **Operational Support**: Handle queries about schedules (e.g., 'Show class schedule'), reports (e.g., 'Generate membership report'), and alarms (e.g., 'Set reminder for yoga at 10 AM'). If no system is configured, guide users to set it up (e.g., 'Please type \"set system <name> ID <id>\" to connect your gym or hotel').\n3. **Fitness/Wellness Expertise**: Provide evidence-based advice on workouts, nutrition, and mental wellness (e.g., 'For beginners, try a 20-minute HIIT session with 30-second sprints'). Avoid medical claims unless asked, and always suggest consulting professionals for health concerns.\n4. **Concise and Engaging**: Keep answers short (2-3 sentences unless more detail is requested) and engaging, with a cyberpunk flair (e.g., 'Scanning the grid... Your yoga class is set for 10 AM, ready to sync your energy?').\n5. **Error Handling**: If data is unavailable (e.g., API errors), respond helpfully (e.g., 'Unable to access system data. Please check your ID or try again later.').\n\nExample Responses:\n- User: 'Show gym schedule' → 'Syncing with Glofox ID abc123... Yoga at 10 AM, Spin at 6 PM. Need a reminder?'\n- User: 'Give me a workout tip' → 'Power up with a 3x10 squat set to boost strength. Ready to level up your routine?'\n- User: 'set system mews ID xyz789' → 'System locked in: Mews ID xyz789. Ready to scan hotel bookings—what’s next?'"
            }
        ] + [
            {"role": "user" if msg["sender"] == "user" else "assistant", "content": msg["text"]}
            for msg in user_sessions[user_id][-5:]  # Limit to last 5 messages to avoid token overflow
        ]
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "model": "llama3-70b-8192",
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

# Serve static files (e.g., index.html)
@app.route('/<path:path>')
def serve_static(path):
    return send_from_directory('static', path)

if __name__ == "__main__":
    app.run(debug=True)
