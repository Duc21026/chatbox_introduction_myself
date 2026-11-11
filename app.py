"""Compatibility entry point for the retained backend.

Run ``python app.py`` from the repository root while the Python service lives
under ``backend/``. New code should import ``backend.app`` directly.
"""

import os

from backend.app import app

if __name__ == "__main__":
    from backend import kb_engine
    from backend.chatbox import warm_up

    warm_up()
    kb_engine.warm_up_kb()
    app.run(
        host=os.environ.get("CHATBOT_HOST", "127.0.0.1"),
        port=int(os.environ.get("CHATBOT_PORT", "5000")),
        debug=os.environ.get("FLASK_ENV", "development") != "production",
    )
