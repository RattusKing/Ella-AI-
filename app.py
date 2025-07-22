from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import groq

app = Flask(__name__)
CORS(app)

# Set Groq API key from environment variable
groq.api_key = os.getenv("GROQ_API_KEY")

@app.route("/")
def home():
    return "Ella backend (Groq) is running!"

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    user_message = data.get("message")

    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    try:
        response = groq.ChatCompletion.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "You are Ella, a kind, intelligent wellness companion."},
                {"role": "user", "content": user_message}
            ]
        )
        reply = response.choices[0].message["content"]
        return jsonify({"response": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
