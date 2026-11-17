"""Vercel Python Function entrypoint for ``POST /api/chat``."""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("CHATBOT_RUNTIME", "deployment")

from backend import kb_engine  # noqa: E402
from backend.app import app  # noqa: E402,F401

# Vercel cold start: load the bundled vector index once per instance.
kb_engine.warm_up_kb()
