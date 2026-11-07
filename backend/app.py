import json

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

try:
    from .chatbox import ask_ai, ask_ai_stream, warm_up
except ImportError:  # direct execution: python backend/app.py
    from chatbox import ask_ai, ask_ai_stream, warm_up

app = Flask(__name__)

CORS(app)


def _sse(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _validated_question():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "Dữ liệu gửi lên phải là JSON"}), 400)

    question = data.get("message")
    if not isinstance(question, str) or not question.strip():
        return None, (jsonify({"error": "Thiếu trường 'message'"}), 400)
    return question, None


@app.route("/chat", methods=["POST"])
def chatbot():
    question, error = _validated_question()
    if error is not None:
        return error

    try:
        answer = ask_ai(question)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"response": answer})


@app.route("/chat/stream", methods=["POST"])
def chatbot_stream():
    question, error = _validated_question()
    if error is not None:
        return error

    def generate():
        try:
            for chunk in ask_ai_stream(question):
                if chunk:
                    yield _sse({"type": "chunk", "content": chunk})
        except Exception:
            yield _sse(
                {
                    "type": "error",
                    "message": "Không thể tạo câu trả lời. Vui lòng thử lại.",
                }
            )
            return
        yield _sse({"type": "done"})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    warm_up()
    app.run(debug=True)
