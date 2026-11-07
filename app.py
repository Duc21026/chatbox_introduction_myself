from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from chatbox import ask_ai, warm_up

app = Flask(__name__)

CORS(app)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/chat", methods=["POST"])
def chatbot():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Dữ liệu gửi lên phải là JSON"}), 400

    question = data.get("message")
    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Thiếu trường 'message'"}), 400

    try:
        answer = ask_ai(question)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"response": answer})


if __name__ == "__main__":
    warm_up()
    app.run(debug=True)
