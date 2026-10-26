"""WhatsApp adapter (Meta WhatsApp Cloud API) for the same reporting conversation as the Telegram bot.

Meta calls our webhook (POST /api/whatsapp/webhook) for every incoming message; replies go out through the
Graph API. Configured only through environment variables (never in code or the repository):

  WHATSAPP_TOKEN            access token (temporary 24-hour token, or a permanent System User token)
  WHATSAPP_PHONE_NUMBER_ID  the ID of the sending number (Meta: WhatsApp > API Setup)
  WHATSAPP_VERIFY_TOKEN     a random string you choose, typed again into Meta's webhook form
  WHATSAPP_APP_SECRET       Meta: App settings > Basic > App secret. Every webhook call is signature-checked with it,
                            so nobody else can post fake messages into the system.

Privacy: the sender's number is used in memory to reply, but a report stores only a keyed hash of it.
Drafts live in memory only and expire after 2 hours. WhatsApp gives a business no way to delete messages it has
sent, so /stop clears the draft but cannot erase the chat itself (the bot says so).
"""
from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import hmac
import io
import logging
import time

import httpx

from .config import get_settings
from .conversation import Conversation, Out

log = logging.getLogger("ubufakazi.whatsapp")
GRAPH = "https://graph.facebook.com"
MEDIA_LIMIT = 20 * 1024 * 1024
IDLE_SECONDS = 2 * 3600
SYNC = False                     # tests: handle webhook messages before the HTTP response

STATE = {"checked": False, "ok": False, "phone": None, "name": None, "error": None, "last_message_at": None}
MEDIA_TYPES = ("image", "document", "audio", "video", "sticker")
EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "application/pdf": "pdf", "audio/ogg": "ogg",
       "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/aac": "aac", "audio/amr": "amr", "video/mp4": "mp4",
       "video/3gpp": "3gp", "text/plain": "txt", "application/zip": "zip"}


def configured() -> bool:
    s = get_settings()
    return all((s.whatsapp_token, s.whatsapp_phone_id, s.whatsapp_verify_token, s.whatsapp_app_secret))


def missing() -> list[str]:
    s = get_settings()
    return [n for n, v in (("WHATSAPP_TOKEN", s.whatsapp_token), ("WHATSAPP_PHONE_NUMBER_ID", s.whatsapp_phone_id),
                           ("WHATSAPP_VERIFY_TOKEN", s.whatsapp_verify_token),
                           ("WHATSAPP_APP_SECRET", s.whatsapp_app_secret)) if not v]


def contact_ref(wa_id: str) -> str:
    key = get_settings().hmac_key.encode()
    return "wa:" + hmac.new(key, f"whatsapp:{wa_id}".encode(), hashlib.sha256).hexdigest()[:16]


def verify_signature(raw: bytes, header: str | None) -> bool:
    secret = get_settings().whatsapp_app_secret
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


def verify_challenge(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Meta's one-time webhook check. Returns the challenge to echo, or None."""
    want = get_settings().whatsapp_verify_token
    if mode != "subscribe" or not want or not token or not challenge or not challenge.isdigit():
        return None
    return challenge if hmac.compare_digest(token, want) else None


def status() -> dict:
    s = get_settings()
    hook = f"{s.public_base_url}/api/whatsapp/webhook"
    if not configured():
        return {"configured": False, "running": False,
                "note": "Not configured: set " + ", ".join(missing()) + " (Meta WhatsApp Cloud API)."}
    if STATE["ok"]:
        last = f" Last message received {STATE['last_message_at'][:16]} UTC." if STATE["last_message_at"] else ""
        warn = f" Last send problem: {STATE['error']}" if STATE["error"] else ""
        return {"configured": True, "running": True, "phone": STATE["phone"], "name": STATE["name"],
                "note": f"Connected as {STATE['name'] or 'WhatsApp Business'} ({STATE['phone']}). Webhook: {hook}.{last}{warn}"}
    if not STATE["checked"]:
        return {"configured": True, "running": False, "note": "Settings present; checking the connection with Meta…"}
    return {"configured": True, "running": False, "note": STATE["error"] or "Meta did not accept the settings."}


# ---------------------------------------------------------------------------------------------- Graph API calls
def _url(path: str) -> str:
    return f"{GRAPH}/{get_settings().whatsapp_api_version}/{path}"


def _auth() -> dict:
    return {"Authorization": f"Bearer {get_settings().whatsapp_token}"}


def _meta_error(r: httpx.Response) -> str:
    try:
        e = r.json().get("error", {})
        msg = f"HTTP {r.status_code}, Meta error {e.get('code')}: {e.get('message', '')}"
    except ValueError:
        msg = f"HTTP {r.status_code}"
    if r.status_code == 401 or "190" in msg:
        msg += " (the access token is wrong or has expired: temporary tokens last 24 hours)"
    if "131030" in msg:
        msg += " (add this phone number to the allowed recipients in Meta: WhatsApp > API Setup)"
    return msg[:300]


async def check_connection() -> None:
    """Called at startup. Never raises: the result is shown on /api/integrations."""
    if not configured():
        return
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(_url(get_settings().whatsapp_phone_id), headers=_auth(),
                            params={"fields": "display_phone_number,verified_name"})
        if r.status_code == 200:
            d = r.json()
            STATE.update(ok=True, phone=d.get("display_phone_number"), name=d.get("verified_name"), error=None)
            log.info("WhatsApp connected as %s", d.get("verified_name"))
        else:
            STATE.update(ok=False, error="Meta rejected the settings: " + _meta_error(r))
            log.warning("WhatsApp check failed: HTTP %s", r.status_code)
    except httpx.HTTPError as e:
        STATE.update(ok=False, error=f"Could not reach Meta ({type(e).__name__}).")
    finally:
        STATE["checked"] = True


async def _post_json(path: str, body: dict) -> dict | None:
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(_url(path), headers=_auth(), json=body)
    if r.status_code != 200:
        STATE["error"] = _meta_error(r)
        log.warning("WhatsApp send failed: %s", STATE["error"])
        return None
    return r.json()


async def _upload(data: bytes, filename: str, mime: str) -> str | None:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(_url(f"{get_settings().whatsapp_phone_id}/media"), headers=_auth(),
                         data={"messaging_product": "whatsapp", "type": mime},
                         files={"file": (filename, io.BytesIO(data), mime)})
    if r.status_code != 200:
        STATE["error"] = _meta_error(r)
        return None
    return r.json().get("id")


async def _download_media(media_id: str) -> tuple[bytes | None, str]:
    """Returns (data, problem). Media URLs need the same bearer token."""
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
        r = await c.get(_url(media_id), headers=_auth())
        if r.status_code != 200:
            return None, "I couldn't fetch that file from WhatsApp. Please try sending it again."
        meta = r.json()
        if int(meta.get("file_size") or 0) > MEDIA_LIMIT:
            return None, "That file is larger than 20 MB. Upload it on the Ubufakazi Track page after you submit."
        f = await c.get(meta["url"], headers=_auth())
        if f.status_code != 200:
            return None, "I couldn't fetch that file from WhatsApp. Please try sending it again."
        if len(f.content) > MEDIA_LIMIT:
            return None, "That file is larger than 20 MB. Upload it on the Ubufakazi Track page after you submit."
        return f.content, ""


# ---------------------------------------------------------------------------------------------- chats
class _Chat:
    def __init__(self, wa_id: str):
        self.conv = Conversation(channel="whatsapp", contact_ref=contact_ref(wa_id))
        self.options: list[str] = []
        self.numbered = False
        self.lock = asyncio.Lock()
        self.seen = time.time()


_chats: dict[str, _Chat] = {}
_seen_ids: dict[str, float] = {}
_tasks: set = set()


def _chat(wa_id: str) -> _Chat:
    now = time.time()
    for k, c in list(_chats.items()):
        if now - c.seen > IDLE_SECONDS and not c.lock.locked():
            _chats.pop(k, None)
    for k, t in list(_seen_ids.items()):
        if now - t > 3600:
            _seen_ids.pop(k, None)
    c = _chats.get(wa_id) or _Chat(wa_id)
    c.seen = now
    _chats[wa_id] = c
    return c


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def build_messages(out: Out) -> tuple[list[dict], list[str], bool]:
    """Turns one conversation reply into WhatsApp message bodies. Returns (bodies, options, numbered)."""
    text, opts = out.text, out.options or []
    if not opts:
        return [{"type": "text", "text": {"body": text[:4096]}}], [], False
    bodies: list[dict] = []
    if len(opts) > 10:                               # more than WhatsApp lists allow: numbered text
        lines = "\n".join(f"{i + 1}. {o}" for i, o in enumerate(opts))
        return [{"type": "text", "text": {"body": f"{text}\n\nReply with a number:\n{lines}"[:4096]}}], opts, True
    body = text
    if len(text) > 1024:                             # interactive bodies are limited to 1 024 characters
        bodies.append({"type": "text", "text": {"body": text[:4096]}})
        body = "Please choose:"
    if len(opts) <= 3 and all(len(o) <= 20 for o in opts):
        inter = {"type": "button", "body": {"text": body},
                 "action": {"buttons": [{"type": "reply", "reply": {"id": f"opt:{i}", "title": o}}
                                        for i, o in enumerate(opts)]}}
    else:
        rows = []
        for i, o in enumerate(opts):
            row = {"id": f"opt:{i}", "title": _clip(o, 24)}
            if len(o) > 24:
                row["description"] = _clip(o, 72)
            rows.append(row)
        inter = {"type": "list", "body": {"text": body},
                 "action": {"button": "Choose", "sections": [{"title": "Options", "rows": rows}]}}
    bodies.append({"type": "interactive", "interactive": inter})
    return bodies, opts, False


def resolve_choice(chat: _Chat, text: str, reply_id: str | None = None) -> str:
    """Maps a tapped button/list row (or a number typed after a numbered list) back to the full option text."""
    if reply_id and reply_id.startswith("opt:"):
        try:
            i = int(reply_id[4:])
            if 0 <= i < len(chat.options):
                return chat.options[i]
        except ValueError:
            pass
    t = (text or "").strip()
    if chat.numbered and t.isdigit() and 1 <= int(t) <= len(chat.options):
        return chat.options[int(t) - 1]
    return text


async def send(to: str, body: dict) -> dict | None:
    return await _post_json(f"{get_settings().whatsapp_phone_id}/messages",
                            {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, **body})


async def _send_pack(to: str, report_id: int, reference: str) -> None:
    from .casepack import build_case_pack
    from .db import SessionLocal
    from .models import Report
    from . import services
    await asyncio.to_thread(services.process_report, report_id)
    db = SessionLocal()
    try:
        r = db.get(Report, report_id)
        if r.processing_status != "ready":
            await send(to, {"type": "text", "text": {"body": "Your report is saved, but the case pack could not be prepared "
                                                             "automatically. An officer can re-run processing."}})
            return
        pdf = await asyncio.to_thread(build_case_pack, db, r, "complainant")
    finally:
        db.close()
    media_id = await _upload(pdf, f"Ubufakazi-{reference}.pdf", "application/pdf")
    if not media_id:
        await send(to, {"type": "text", "text": {"body": "I couldn't attach the case pack here. Download it on the Ubufakazi "
                                                         "Track page with your reference and receipt key."}})
        return
    await send(to, {"type": "document", "document": {
        "id": media_id, "filename": f"Ubufakazi-{reference}.pdf",
        "caption": "Your draft statement and case pack. Check it, then take it to a police station to register the case."}})


async def _reply(to: str, chat: _Chat, outs: list[Out]) -> None:
    from .db import SessionLocal
    from .models import Report
    from . import services
    for o in outs:
        bodies, opts, numbered = build_messages(o)
        for b in bodies:
            await send(to, b)
        chat.options, chat.numbered = opts, numbered
        a = o.action or {}
        if a.get("type") == "quick_exit":
            await send(to, {"type": "text", "text": {"body": "WhatsApp does not let Ubufakazi delete this chat. If someone "
                                                             "else might see this phone, delete the chat yourself: press and "
                                                             "hold it in your chat list, then Delete."}})
        elif a.get("type") == "submitted" and not a.get("sensitive"):
            await _send_pack(to, a["id"], a["reference"])
        elif a.get("type") == "send_pack":
            db = SessionLocal()
            try:
                r = db.query(Report).filter_by(reference=a["reference"]).first()
                rid = r.id if r else None
            finally:
                db.close()
            if rid:
                await _send_pack(to, rid, a["reference"])
        elif a.get("type") == "submitted" and a.get("sensitive"):
            await asyncio.to_thread(services.process_report, a["id"])


def messages_from(payload: dict) -> list[dict]:
    """Incoming user messages for OUR number from a webhook payload (delivery statuses are ignored)."""
    pid = get_settings().whatsapp_phone_id
    found = []
    for entry in payload.get("entry") or []:
        for ch in entry.get("changes") or []:
            v = ch.get("value") or {}
            if (v.get("metadata") or {}).get("phone_number_id") != pid:
                continue
            found.extend(m for m in v.get("messages") or [] if isinstance(m, dict))
    return found


async def handle_message(m: dict) -> None:
    try:
        await _handle(m)
    except Exception:                   # never let one bad message break the webhook
        log.exception("WhatsApp message could not be handled")


async def _handle(m: dict) -> None:
    mid, wa_id, typ = m.get("id"), str(m.get("from") or ""), m.get("type")
    if not wa_id.isdigit():
        return
    if mid:
        if mid in _seen_ids:            # Meta retries deliveries: handle each message once
            return
        _seen_ids[mid] = time.time()
    STATE["last_message_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    chat = _chat(wa_id)
    async with chat.lock:
        conv = chat.conv
        text, file, location, caption = "", None, None, ""
        if typ == "text":
            text = resolve_choice(chat, (m.get("text") or {}).get("body", ""))
        elif typ == "interactive":
            it = m.get("interactive") or {}
            r = it.get("button_reply") or it.get("list_reply") or {}
            text = resolve_choice(chat, r.get("title", ""), r.get("id"))
        elif typ == "button":
            text = (m.get("button") or {}).get("text", "")
        elif typ == "location":
            loc = m.get("location") or {}
            try:
                location = (float(loc["latitude"]), float(loc["longitude"]))
            except (KeyError, TypeError, ValueError):
                location = None
        elif typ in MEDIA_TYPES:
            media = m.get(typ) or {}
            if conv.step != "evidence":
                await _reply(wa_id, chat, [Out("I can only accept files at the evidence step. Send 'hi' or /new to start a report.")])
                return
            data, problem = await _download_media(str(media.get("id", "")))
            if data is None:
                await _reply(wa_id, chat, [Out(problem, ["Done"])])
                return
            mime = (media.get("mime_type") or "").split(";")[0].strip()
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            name = media.get("filename") or f"{'voice' if media.get('voice') else typ}-{stamp}.{EXT.get(mime, 'bin')}"
            file = (data, name[:120], mime)
            caption = media.get("caption") or ""
        else:
            await _reply(wa_id, chat, [Out("I can read text messages, files, photos, voice notes and locations. "
                                           "Send /help to see what I can do.")])
            return
        outs = await asyncio.to_thread(conv.handle, text if not file else None, file=file, location=location)
        if file and caption and conv.step == "evidence":
            outs += await asyncio.to_thread(conv.handle, caption)    # a caption is kept as pasted text too
        await _reply(wa_id, chat, outs)


def dispatch(payload: dict) -> list:
    """Schedules each incoming message; returns coroutines to await directly when SYNC (tests)."""
    coros = [handle_message(m) for m in messages_from(payload)]
    if SYNC:
        return coros
    for c in coros:
        t = asyncio.get_running_loop().create_task(c)
        _tasks.add(t)
        t.add_done_callback(_tasks.discard)
    return []
