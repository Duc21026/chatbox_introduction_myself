import json
import os

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

try:
    from .assistant import Assistant
    from .chatbox import retrieve_rag_documents, retrieve_source_qa, warm_up
    from .doc_index import DocIndex
    from . import kb_engine
except ImportError:  # direct execution: python backend/app.py
    from assistant import Assistant
    from chatbox import retrieve_rag_documents, retrieve_source_qa, warm_up
    from doc_index import DocIndex
    import kb_engine

app = Flask(__name__)
CORS(app)

# Load the derived document index once at startup.  Missing/broken index is
# non-fatal: the assistant simply behaves as if no documents were ingested.
_doc_index = DocIndex()
_assistant = Assistant(
    doc_searcher=_doc_index,
    rag_searcher=retrieve_rag_documents,
    qa_searcher=retrieve_source_qa,
)

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


def _validated_chat_request():
    """Validate ChatRequest fields shared by /chat and /chat/stream."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None, (jsonify({"error": "Dữ liệu gửi lên phải là JSON"}), 400)

    action = data.get("action")
    if action is not None:
        if not isinstance(action, str) or action.strip().lower() not in {
            "other",
            "topic",
            "rephrase",
            "retry",
        }:
            return None, (jsonify({"error": "Trường 'action' không hợp lệ"}), 400)
        action = action.strip().lower()
    else:
        action = None

    topic = data.get("topic")
    if topic is not None and not isinstance(topic, str):
        return None, (jsonify({"error": "Trường 'topic' phải là chuỗi"}), 400)
    if action == "topic" and (not topic or not topic.strip()):
        return None, (
            jsonify({"error": "Thiếu trường 'topic' khi action='topic'"}),
            400,
        )
    if isinstance(topic, str):
        topic = topic.strip()
        if len(topic) > 120:
            return None, (
                jsonify({"error": "Trường 'topic' không được vượt quá 120 ký tự"}),
                422,
            )

    session_id = data.get("session_id")
    if session_id is not None and not isinstance(session_id, str):
        return None, (jsonify({"error": "Trường 'session_id' phải là chuỗi"}), 400)
    if isinstance(session_id, str):
        session_id = session_id.strip()[:100] or None

    message = data.get("message")
    if message is None:
        if action is None:
            return None, (jsonify({"error": "Thiếu trường 'message'"}), 400)
        message = ""
    if not isinstance(message, str):
        return None, (jsonify({"error": "Trường 'message' phải là chuỗi"}), 400)
    message = message.strip()
    if action is None:
        if not message:
            return None, (
                jsonify({"error": "Trường 'message' không được để trống"}),
                422,
            )
        if len(message) > 200:
            return None, (
                jsonify({"error": "Trường 'message' không được vượt quá 200 ký tự"}),
                422,
            )
    elif message and len(message) > 200:
        return None, (
            jsonify({"error": "Trường 'message' không được vượt quá 200 ký tự"}),
            422,
        )

    return {
        "question": message or None,
        "session_id": session_id,
        "action": action,
        "topic": topic,
    }, None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/chat", methods=["POST"])
def chatbot():
    payload, error = _validated_chat_request()
    if error is not None:
        return error
    try:
        response = _assistant.handle(**payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify(response)


@app.route("/chat/stream", methods=["POST"])
def chatbot_stream():
    payload, error = _validated_chat_request()
    if error is not None:
        return error
    try:
        try:
            response = _assistant.handle(**payload, stream_summary=True)
        except TypeError:
            response = _assistant.handle(**payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    def generate():
        chunks = response.get("_summary_chunks") or []
        if chunks:
            for chunk in chunks:
                yield _sse({"type": "chunk", "content": chunk})
        else:
            response_text = response.get("response", "")
            if response_text:
                yield _sse({"type": "chunk", "content": response_text})
        if response.get("type") in {"suggest", "clarify"}:
            yield _sse({"type": "result", "data": response})
        yield _sse({"type": "done"})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    warm_up()
    kb_engine.warm_up_kb()
    app.run(
        host=os.environ.get("CHATBOT_HOST", "127.0.0.1"),
        port=int(os.environ.get("CHATBOT_PORT", "5000")),
        debug=os.environ.get("FLASK_ENV", "development") != "production",
    )
