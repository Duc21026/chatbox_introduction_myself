"""Compatibility entry point for the retained backend.

Run ``python app.py`` from the repository root while the Python service lives
under ``backend/``. New code should import ``backend.app`` directly.
"""

from backend.app import app

if __name__ == "__main__":
    from backend.chatbox import warm_up

    warm_up()
    app.run(debug=True)
