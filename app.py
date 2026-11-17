"""Compatibility entry point for the retained backend.

Run ``python app.py`` from the repository root while the Python service lives
under ``backend/``. Vercel's Flask service also detects this file.
"""

import os

from backend import kb_engine
from backend.app import app, runtime_mode

# Vercel service cold start: load the bundled vector index once per instance.
if runtime_mode() == "deployment":
    kb_engine.warm_up_kb()

if __name__ == "__main__":
    from backend.chatbox import warm_up

    if runtime_mode() != "deployment":
        warm_up()
    kb_engine.warm_up_kb()
    app.run(
        host=os.environ.get("CHATBOT_HOST", "127.0.0.1"),
        port=int(os.environ.get("CHATBOT_PORT", "5000")),
        debug=os.environ.get("FLASK_ENV", "development") != "production",
    )
