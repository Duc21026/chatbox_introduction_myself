import json
import os

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

try:
    from .chatbox import ask_ai, ask_ai_stream, warm_up
    from . import kb_engine
except ImportError:  # direct execution: python backend/app.py
    from chatbox import ask_ai, ask_ai_stream, warm_up
    import kb_engine

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Rate limiter (60 req/minute per IP by default)
# ---------------------------------------------------------------------------

_rate_limit = os.environ.get("CHATBOT_RATE_LIMIT", "60/minute")

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[_rate_limit],
    storage_uri="memory://",
)


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "Rate limit exceeded. Thử lại sau."}), 429


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(payload):
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _validated_question():
    """Extract and validate 'message' from JSON body.

    Returns (question_str, None) on success or (None, error_response) on failure.
    HTTP 400 for missing/non-JSON, HTTP 422 for blank or too-long message.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "Dữ liệu gửi lên phải là JSON"}), 400)

    question = data.get("message")
    if not isinstance(question, str):
        return None, (jsonify({"error": "Thiếu trường 'message'"}), 400)

    question = question.strip()
    if not question:
        return None, (jsonify({"error": "Trường 'message' không được để trống"}), 422)
    if len(question) > 200:
        return None, (
            jsonify({"error": "Trường 'message' không được vượt quá 200 ký tự"}),
            422,
        )

    return question, None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/chat", methods=["POST"])
def chatbot():
    question, error = _validated_question()
    if error is not None:
        return error

    # 1. KB Engine (structured Q&A from kb.json)
    try:
        kb_response = kb_engine.query(question)
    except Exception:
        kb_response = None  # non-fatal: fall through to RAG

    if kb_response is not None:
        return jsonify(kb_response)

    # 2. RAG fallback (FAISS + Ollama)
    try:
        answer = ask_ai(question)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({
        "type": "answer",
        "score": None,
        "response": answer,
        "answer_bullets": None,
    })


@app.route("/chat/stream", methods=["POST"])
def chatbot_stream():
    question, error = _validated_question()
    if error is not None:
        return error

    # KB Engine — if it has a crisp answer, emit it as a single chunk
    try:
        kb_response = kb_engine.query(question)
    except Exception:
        kb_response = None

    if kb_response is not None:
        def _kb_stream():
            response_text = kb_response.get("response", "")
            if response_text:
                yield _sse({"type": "chunk", "content": response_text})
            yield _sse({"type": "done"})

        return Response(
            stream_with_context(_kb_stream()),
            mimetype="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # RAG streaming fallback
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
    kb_engine.warm_up_kb()
    warm_up()
    app.run(debug=True)
