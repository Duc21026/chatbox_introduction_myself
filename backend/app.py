"""Flask application shared by local/Docker and the Vercel Python function.

Local/Docker keeps the Ollama + FAISS pipeline.  The deployment runtime
(``CHATBOT_RUNTIME=deployment`` or ``VERCEL=1``) is QA-only and never imports
``chatbox``, LangChain or FAISS.
"""

import json
import os

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

try:
    from .assistant import Assistant
    from . import health, kb_engine, source_store
except ImportError:  # direct execution: python backend/app.py
    from assistant import Assistant
    import health
    import kb_engine
    import source_store

DEFAULT_RATE_LIMIT = "60/minute"


def runtime_mode() -> str:
    explicit = (os.environ.get("CHATBOT_RUNTIME") or "").strip().lower()
    if explicit:
        return explicit
    return "deployment" if os.environ.get("VERCEL") else "legacy"


def _build_assistant(runtime: str) -> Assistant:
    if runtime == "deployment":
        return Assistant(qa_searcher=source_store.retrieve_source_qa)

    try:
        from .chatbox import retrieve_rag_documents, retrieve_source_qa
        from .doc_index import DocIndex
    except ImportError:  # direct execution
        from chatbox import retrieve_rag_documents, retrieve_source_qa
        from doc_index import DocIndex

    return Assistant(
        doc_searcher=DocIndex(),
        rag_searcher=retrieve_rag_documents,
        qa_searcher=retrieve_source_qa,
    )


def create_app(runtime: str = None, *, assistant: Assistant = None) -> Flask:
    runtime = (runtime or runtime_mode()).strip().lower()
    app = Flask(__name__)

    origins = (os.environ.get("CHATBOT_CORS_ORIGINS") or "").strip()
    if origins:
        allowed = [origin.strip() for origin in origins.split(",") if origin.strip()]
        CORS(app, resources={r"/*": {"origins": allowed}})
    elif runtime != "deployment":
        CORS(app)

    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[os.environ.get("CHATBOT_RATE_LIMIT", DEFAULT_RATE_LIMIT)],
        storage_uri="memory://",
    )
    chat_assistant = assistant or _build_assistant(runtime)
    app.extensions["chat_assistant"] = chat_assistant
    if assistant is not None:
        app.extensions["chat_assistant_override"] = assistant
    app.extensions["limiter"] = limiter
    app.extensions["runtime"] = runtime

    @app.errorhandler(429)
    def ratelimit_handler(e):
        return jsonify({"error": "Rate limit exceeded. Thử lại sau."}), 429

    @app.route("/api/health", methods=["GET"])
    @app.route("/health", methods=["GET"])
    def health_route():
        return jsonify(health.health_report())

    @app.route("/api/chat", methods=["POST"])
    @app.route("/chat", methods=["POST"])
    def chatbot():
        payload, error = _validated_chat_request()
        if error is not None:
            return error
        try:
            response = _resolve_assistant(app).handle(**payload)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500
        return jsonify(response)

    @app.route("/api/chat/stream", methods=["POST"])
    @app.route("/chat/stream", methods=["POST"])
    def chatbot_stream():
        payload, error = _validated_chat_request()
        if error is not None:
            return error
        assistant = _resolve_assistant(app)
        try:
            try:
                response = assistant.handle(**payload, stream_summary=True)
            except TypeError:
                response = assistant.handle(**payload)
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

    return app


def _resolve_assistant(app):
    return app.extensions.get("chat_assistant_override") or _assistant


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


app = create_app()
_assistant = app.extensions["chat_assistant"]
limiter = app.extensions["limiter"]


if __name__ == "__main__":
    kb_engine.warm_up_kb()
    if runtime_mode() != "deployment":
        try:
            from .chatbox import warm_up
        except ImportError:
            from chatbox import warm_up
        warm_up()
    app.run(
        host=os.environ.get("CHATBOT_HOST", "127.0.0.1"),
        port=int(os.environ.get("CHATBOT_PORT", "5000")),
        debug=os.environ.get("FLASK_ENV", "development") != "production",
    )
