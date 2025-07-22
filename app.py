from flask import Flask, request, jsonify
from flask_cors import CORS
import groq

app = Flask(__name__)
CORS(app)

client = groq.Groq(api_key="your_groq_api_key")

@app.route("/api/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")

    try:
        chat_completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": "You are Ella, a warm and helpful fitness and mental wellness assistant."},
                {"role": "user", "content": user_input}
            ]
        )
        response = chat_completion.choices[0].message.content
        return jsonify({"response": response})

    except Exception as e:
        return jsonify({"response": "Sorry, something went wrong."}), 500

if __name__ == "__main__":
    app.run(debug=True)
