"""Vercel entry point: the record service (no AI model) in cloud mode.

Vercel runs this ASGI app for every request (see vercel.json). The model
stays on the Mac; here journal parsing falls back to rules and chat is not
served (the website sends chat to the Mac gateway instead).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("RUAMWAN_CLOUD", "1")

from app.main import app  # noqa: E402  (path set above)
