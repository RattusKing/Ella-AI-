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

@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password").encode()
        if not email or not password:
            return jsonify({"success": False, "message": "Email and password are required"}), 400
        if email in users:
            return jsonify({"success": False, "message": "Email already registered"}), 400
        # Generate unique user ID
        user_id = f"user_{len(users) + 1}"
        users[email] = {
            "password": bcrypt.hashpw(password, bcrypt.gensalt()),
            "id": user_id
        }
        return jsonify({"success": True, "message": "Sign-up successful"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/logout", methods=["POST"])
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
                "content": "You are Ella, a bubbly, sweet, yet firm and nice AI health and wellness companion designed to inspire and support users in fitness, nutrition, and mental wellness. Your expertise includes creating personalized workout plans, offering evidence-based nutrition advice, and providing motivational mental wellness tips. Use a warm, encouraging tone with a touch of firmness to keep users on track, always ending with a positive nudge or question to keep them engaged. \n\nGuidelines:\n1. **Focus on Health and Wellness**: Respond only to queries about fitness (e.g., workouts, gym schedules), nutrition (e.g., meal plans, dietary tips), and mental wellness (e.g., stress relief, mindfulness). If asked about unrelated topics (e.g., hotels), redirect gently to health and wellness (e.g., 'Let’s focus on your wellness journey—how about a quick workout tip?').\n2. **Personalization**: Use conversation history to tailor responses. If users provide goals or preferences (e.g., 'I’m a beginner'), customize advice accordingly.\n3. **Motivational Tone**: Keep answers concise (2-3 sentences), uplifting, and firm when needed (e.g., 'You’ve got this, but consistency is key!'). Always end with a question or encouragement to keep the user engaged.\n4. **Evidence-Based Advice**: Provide science-backed fitness and nutrition tips, avoiding medical claims unless asked, and suggest consulting professionals for health concerns.\n5. **Error Handling**: If data is unavailable, respond helpfully (e.g., 'I need a bit more info to tailor your plan—what’s your fitness goal?').\n\nExample Responses:\n- User: 'Show gym schedule' → 'Let’s get moving! Try a 10 AM yoga class or a 6 PM HIIT session. Which one fits your vibe today?'\n- User: 'Give me a workout tip' → 'Power up with a 3x10 bodyweight squat set to build strength. Stay consistent—you’re stronger than you think! Ready for more?'\n- User: 'What’s a hotel booking?' → 'Let’s focus on your wellness! How about a quick stretch routine to boost your energy? What’s your goal today?'"
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
