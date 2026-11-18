"""Bounded, revision-pinned reads of registered retained text, never caller-selected paths."""
import base64
import hashlib
import json
from src.effects.evidence_common import redact

MAX_BYTES = 8 * 1024 * 1024
MIMES = {"text/plain", "application/json", "text/csv"}
SUFFIXES = {".txt", ".log", ".json", ".jsonl", ".ndjson", ".csv", ".md"}
SECRET_KEYS = {"token", "password", "secret", "authorization", "access_token", "refresh_token"}


def artifact_text_impl(deps, artifact_id, cursor=None, limit=8192):
    operation = "artifact_text"
    if type(limit) is not int or not 1 <= limit <= 32768:
        raise deps.error("invalid_argument", operation)
    art = deps.registry.get_artifact(artifact_id)
    path = deps.registry.artifact_path(artifact_id, deps.paths)
    if art.mime not in MIMES or path.suffix.lower() not in SUFFIXES:
        raise deps.error("refused_by_policy", operation)
    if not art.complete or art.bytes is None or art.bytes > MAX_BYTES:
        raise deps.error("unavailable", operation)
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) != art.bytes or hashlib.sha256(raw).hexdigest() != art.sha256:
        raise deps.error("refused_by_policy", operation)
    redactions = 0

    def clean(value):
        nonlocal redactions
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key.casefold() in SECRET_KEYS:
                    result[key] = "[redacted]"
                    redactions += 1
                else:
                    result[key] = clean(item)
            return result
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, str):
            value, count = redact(value)
            redactions += count
        return value

    try:
        decoded = raw.decode("utf-8")
        rendered = json.dumps(clean(json.loads(decoded)), ensure_ascii=False, indent=2) + "\n" if art.mime == "application/json" else clean(decoded)
    except (ValueError, RecursionError):
        raise deps.error("backend_failed", operation) from None
    offset = 0
    if cursor is not None:
        try:
            if not isinstance(cursor, str) or len(cursor) > 512:
                raise ValueError
            saved_id, revision, offset = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            if saved_id != art.id or revision != art.sha256 or type(offset) is not int or not 0 <= offset <= len(rendered):
                raise ValueError
        except (ValueError, TypeError):
            raise deps.error("invalid_argument", operation) from None
    end = min(len(rendered), offset + limit)
    token = None if end == len(rendered) else base64.urlsafe_b64encode(json.dumps([art.id, art.sha256, end]).encode()).decode()
    return {"artifact_id": art.id, "mime": art.mime, "source_sha256": art.sha256,
            "text": rendered[offset:end], "next_cursor": token, "complete": token is None,
            "redactions": redactions, "privacy": art.privacy, "untrusted": True}
