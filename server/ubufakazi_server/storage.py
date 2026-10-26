"""Private evidence storage.

- Files are stored under a random name (uuid) in UBF_STORAGE_DIR, never under the user's filename,
  so path traversal through filenames is impossible.
- The real type is detected from the file's bytes (magic numbers), not from its extension.
- Originals are written once and made read-only. Verification re-hashes the stored bytes.
- Uploaded content is never executed or rendered by the server.
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import re
import stat
import uuid

from .config import get_settings

# detected type -> (category, mime)
TYPES = {
    "txt": ("text", "text/plain"),
    "pdf": ("document", "application/pdf"),
    "jpeg": ("image", "image/jpeg"),
    "png": ("image", "image/png"),
    "webp": ("image", "image/webp"),
    "gif": ("image", "image/gif"),
    "mp3": ("audio", "audio/mpeg"),
    "ogg": ("audio", "audio/ogg"),        # Telegram voice notes
    "wav": ("audio", "audio/wav"),
    "m4a": ("audio", "audio/mp4"),
    "mp4": ("video", "video/mp4"),
    "mov": ("video", "video/quicktime"),
    "webm": ("video", "video/webm"),
}


class RejectedFile(ValueError):
    pass


def sniff(data: bytes) -> str | None:
    """Return a detected type from the first bytes, or None if unsupported."""
    head = data[:64]
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "gif"
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "mp3"
    if head.startswith(b"OggS"):
        return "ogg"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"M4A ", b"M4B "):
            return "m4a"
        if brand == b"qt  ":
            return "mov"
        return "mp4"
    # text: valid UTF-8 (or UTF-16 with BOM) without NUL bytes and mostly printable
    sample = data[:65536]
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            sample.decode("utf-16")
            return "txt"
        except UnicodeDecodeError:
            return None
    if b"\x00" in sample:
        return None
    try:
        txt = sample.decode("utf-8")
    except UnicodeDecodeError:
        try:
            txt = sample[:-3].decode("utf-8")  # may be cut mid-character
        except UnicodeDecodeError:
            return None
    printable = sum(ch.isprintable() or ch in "\n\r\t" for ch in txt)
    return "txt" if txt and printable / len(txt) > 0.97 else None


_SAFE = re.compile(r"[^A-Za-z0-9._ ()+\-]")


def safe_display_name(name: str) -> str:
    name = pathlib.PurePath((name or "file").replace("\\", "/")).name  # drop any directory part
    name = _SAFE.sub("_", name).strip(" .") or "file"
    return name[:120]


def storage_dir() -> pathlib.Path:
    d = get_settings().storage_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _db_backend() -> bool:
    return get_settings().storage_backend == "db"


def store_original(data: bytes, original_name: str, db=None) -> dict:
    """Validate and store one original file. Returns metadata including SHA-256.
    With the database backend the bytes are added to `db` (the caller's transaction), insert-only."""
    s = get_settings()
    if not data:
        raise RejectedFile("The file is empty.")
    if len(data) > s.max_upload_bytes:
        raise RejectedFile(f"The file is larger than {s.max_upload_bytes // (1024 * 1024)} MB.")
    kind = sniff(data)
    if kind is None:
        raise RejectedFile("This file type is not supported. Send text, PDF, JPEG/PNG/WebP images, "
                           "MP3/OGG/WAV/M4A audio or MP4/MOV/WebM video.")
    uid = uuid.uuid4().hex
    meta = {"uid": uid, "detected_type": kind, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "original_name": safe_display_name(original_name)}
    if _db_backend():
        from .models import EvidenceBlob
        if db is None:
            raise RuntimeError("database storage needs the caller's session")
        db.add(EvidenceBlob(uid=uid, data=bytes(data)))
        return meta
    path = storage_dir() / uid
    with open(path, "xb") as fh:      # "x": never overwrite an existing file
        fh.write(data)
    os.chmod(path, stat.S_IRUSR)       # read-only original
    return meta


def path_for(uid: str) -> pathlib.Path:
    if not re.fullmatch(r"[0-9a-f]{32}", uid or ""):
        raise ValueError("bad id")
    return storage_dir() / uid


def _read_blob(uid: str) -> bytes | None:
    from .db import SessionLocal
    from .models import EvidenceBlob
    if not re.fullmatch(r"[0-9a-f]{32}", uid or ""):
        raise ValueError("bad id")
    db = SessionLocal()
    try:
        row = db.get(EvidenceBlob, uid)
        return bytes(row.data) if row else None
    finally:
        db.close()


def read_original(uid: str) -> bytes:
    if _db_backend():
        data = _read_blob(uid)
        if data is None:
            raise FileNotFoundError(uid)
        return data
    return path_for(uid).read_bytes()


def rehash(uid: str) -> str | None:
    if _db_backend():
        data = _read_blob(uid)
        return hashlib.sha256(data).hexdigest() if data is not None else None
    p = path_for(uid)
    if not p.exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
