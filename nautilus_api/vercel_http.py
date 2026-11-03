"""Shared request/response helpers for the Vercel Python functions under api/.

Deliberately stdlib-only and free of Nautilus imports so a function can use it before importing
the scientific stack, and so nothing here can pull a credential path into an unrelated route.
"""
import json
import os

MAX_BODY = 4096


def _allowed_origin(handler):
    allowed = os.environ.get("NAUTILUS_ALLOWED_ORIGIN", "").strip()
    origin = handler.headers.get("Origin", "")
    return allowed if allowed and origin == allowed else ""


def cors(handler):
    origin = _allowed_origin(handler)
    if origin:
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        handler.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")


def send_json(handler, status, payload):
    body = json.dumps(payload, sort_keys=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    cors(handler)
    handler.end_headers()
    handler.wfile.write(body)


def preflight(handler):
    handler.send_response(204)
    cors(handler)
    handler.send_header("Content-Length", "0")
    handler.end_headers()


class BodyError(Exception):
    """A request body that cannot be read safely; reported to the client as 400."""


def read_json(handler, limit=MAX_BODY):
    raw_length = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        raise BodyError("Invalid Content-Length") from None
    if length < 0:
        raise BodyError("Invalid Content-Length")
    if length > limit:
        raise BodyError(f"Request body exceeds {limit} bytes")
    raw = handler.rfile.read(length) if length else b""
    if len(raw) != length:
        raise BodyError("Incomplete request body")
    try:
        return json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise BodyError("Invalid JSON") from None
