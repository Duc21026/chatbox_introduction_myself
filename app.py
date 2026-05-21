from flask import Flask, request, jsonify
from flask_cors import CORS

from chatbox import ask_ai

app = Flask(__name__)

CORS(app)


@app.route("/chat", methods=["POST"])
def chatbot():

    data = request.json

    question = data["message"]

    answer = ask_ai(question)

    return jsonify({
        "response": answer
    })


if __name__ == "__main__":

    app.run(debug=True)