"""Vercel Python Function entrypoint for ``GET /api/health``."""

import os
import sys

from flask import Flask, jsonify

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("CHATBOT_RUNTIME", "deployment")

from backend.health import health_report  # noqa: E402

app = Flask(__name__)


@app.route("/", methods=["GET"])
def health():
    return jsonify(health_report())
