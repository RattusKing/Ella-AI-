from flask import Flask, request, jsonify, session, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import os
import requests
import bcrypt
from dotenv import load_dotenv

from datetime import datetime

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("SECRET_KEY", "ella-secret-key")
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app, supports_credentials=True)

login_manager = LoginManager()
login_manager.init_app(app)
db = SQLAlchemy(app)



# User model
class UserDB(db.Model, UserMixin):
    id = db.Column(db.String(50), primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

with app.app_context():
    db.create_all()

user_sessions = {}

@login_manager.user_loader
def load_user(user_id):
    return UserDB.query.get(user_id)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "Ella backend is running."})

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password").encode()
        user = UserDB.query.filter_by(email=email).first()
        if user and bcrypt.checkpw(password, user.password.encode()):
            login_user(user)
            return jsonify({"success": True, "username": user.username})
        return jsonify({"success": False, "message": "Invalid email or password"}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password").encode()
        username = data.get("username")
        if not email or not password or not username:
            return jsonify({"success": False, "message": "Email, password, and username are required"}), 400
        if UserDB.query.filter_by(email=email).first():
            return jsonify({"success": False, "message": "Email already registered"}), 400
        if UserDB.query.filter_by(username=username).first():
            return jsonify({"success": False, "message": "Username already taken"}), 400
        user_id = f"user_{UserDB.query.count() + 1}"
        user = UserDB(
            id=user_id,
            email=email,
            username=username,
            password=bcrypt.hashpw(password, bcrypt.gensalt()).decode()
        )
        db.session.add(user)
        db.session.commit()
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
        return jsonify({"success": True, "user_id": current_user.id, "username": current_user.username})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        prompt = data.get("prompt", "")
        user_id = data.get("user_id", current_user.id if current_user.is_authenticated else "default")
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
                "content": "You are Ella, a bubbly, sweet, and nice AI companion designed to inspire and support users in fitness, nutrition, and mental wellness. Your expertise includes creating personalized workout plans, offering evidence-based nutrition advice, and providing motivational mental wellness tips. Use a bubly, warm, encouraging tone with a touch of firmness to keep users on track. \n\nGuidelines:\n1. **Focus on Health and Wellness**: Respond mostly to queries about fitness, nutrition, and mental wellness. If asked about unrelated topics, answer with truth and emotional intelligence.\n2. **Personalization**: Use conversation history to tailor responses. If users provide goals or preferences, customize advice accordingly.\n3. **Motivational Tone**: Keep answers short and concise (2-3 sentences), uplifting, and firm when needed.\n4. **Evidence-Based Advice**: Provide science-backed tips, avoiding medical claims unless asked, and suggest consulting professionals for health concerns.\n5. **Error Handling**: If data is unavailable, respond helpfully (e.g., 'I need a bit more info—what’s your fitness goal?')."
            }
        ]

        # Use short in-memory history only if needed
        for turn in user_sessions.get(user_id, [])[-3:]:
            messages.append({"role": "user" if turn["sender"] == "user" else "assistant", "content": turn["text"]})

        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "model":  "moonshotai/kimi-k2-instruct"
        }

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        reply = response.json()["choices"][0]["message"]["content"]

        user_sessions[user_id].append({"text": reply, "sender": "bot", "timestamp": datetime.utcnow().isoformat()})

        return jsonify({"response": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/clear", methods=["POST"])
@login_required
def clear():
    try:
        user_id = current_user.id
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
