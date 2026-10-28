"""Telegram adapter for the reporting conversation (long polling, so no public URL is needed).

The bot runs INSIDE the web server process (started from app.py when TELEGRAM_BOT_TOKEN is set), so there is
one writer to the database and the hash-chained audit log stays in order.

Drafts are kept in memory only and expire after 2 hours of inactivity. Files are downloaded from Telegram,
fingerprinted immediately, and written to evidence storage only after the complainant consents.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import io
import logging
import time

from .config import get_settings
from .conversation import Conversation, Out

log = logging.getLogger("ubufakazi.bot")
TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024        # Telegram Bot API download limit
IDLE_SECONDS = 2 * 3600

_convs: dict[int, tuple[Conversation, float]] = {}
_sent: dict[int, list[int]] = {}             # message ids per chat, for best-effort quick exit


def _conv(chat_id: int) -> Conversation:
    now = time.time()
    for cid, (_, seen) in list(_convs.items()):
        if now - seen > IDLE_SECONDS:
            _convs.pop(cid, None)
            _sent.pop(cid, None)
    c = _convs.get(chat_id, (None, 0))[0] or Conversation(channel="telegram", contact_ref=f"tg:{chat_id}")
    _convs[chat_id] = (c, now)
    return c


STATE = {"running": False, "username": None, "error": None, "started_at": None}
_application = None


def build_application(token: str):
    from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
    from telegram.ext import Application, ContextTypes, MessageHandler, filters

    from .casepack import build_case_pack
    from .db import SessionLocal
    from .models import Report
    from . import services

    logging.getLogger("httpx").setLevel(logging.WARNING)   # the token appears in request URLs: keep it out of logs

    def keyboard(options):
        if not options:
            return ReplyKeyboardRemove()
        rows = [[KeyboardButton(o)] for o in options] if len(options) <= 4 else \
               [[KeyboardButton(o) for o in options[i:i + 2]] for i in range(0, len(options), 2)]
        return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=True)

    async def send_pack(update: Update, report_id: int, reference: str):
        await update.effective_chat.send_action("upload_document")
        db = SessionLocal()
        try:
            ready = db.get(Report, report_id).processing_status == "ready"
        finally:
            db.close()
        if not ready:
            await asyncio.to_thread(services.process_report, report_id)
        db = SessionLocal()
        try:
            r = db.get(Report, report_id)
            if r.processing_status != "ready":
                await update.effective_chat.send_message("Your report is saved, but the case pack could not be prepared "
                                                         "automatically. An investigator can re-run processing.")
                return
            pdf = await asyncio.to_thread(build_case_pack, db, r, "complainant")
        finally:
            db.close()
        m = await update.effective_chat.send_document(
            document=io.BytesIO(pdf), filename=f"Ubufakazi-{reference}.pdf",
            caption="Your draft statement and case pack. Check it. Your bank's fraud desk has your report and escalates the case to SAPS.")
        _sent.setdefault(update.effective_chat.id, []).append(m.message_id)

    async def reply(update: Update, outs: list[Out]):
        chat = update.effective_chat
        for o in outs:
            m = await chat.send_message(o.text, reply_markup=keyboard(o.options))
            _sent.setdefault(chat.id, []).append(m.message_id)
            a = o.action or {}
            if a.get("type") == "quick_exit":
                ids = _sent.pop(chat.id, [])
                for mid in ids[:-1]:            # keep the final "Stopped" message
                    try:
                        await chat.delete_message(mid)
                    except Exception:           # best effort: old messages cannot always be deleted
                        pass
            elif a.get("type") == "submitted" and not a.get("sensitive"):
                await send_pack(update, a["id"], a["reference"])
            elif a.get("type") == "send_pack":
                db = SessionLocal()
                try:
                    r = db.query(Report).filter_by(reference=a["reference"]).first()
                    rid = r.id if r else None
                finally:
                    db.close()
                if rid:
                    await send_pack(update, rid, a["reference"])
            elif a.get("type") == "submitted" and a.get("sensitive"):
                # Ask about the PDF straight away; prepare the report in the background meanwhile.
                asyncio.get_running_loop().run_in_executor(None, services.process_report, a["id"])

    async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = update.effective_message
        if not msg or update.effective_chat.type != "private":
            return
        chat_id = update.effective_chat.id
        _sent.setdefault(chat_id, []).append(msg.message_id)
        c = _conv(chat_id)
        file = None
        tg_file, name, mime = None, None, ""
        if msg.document:
            tg_file, name, mime = msg.document, msg.document.file_name or "document", msg.document.mime_type or ""
        elif msg.photo:
            tg_file, name, mime = msg.photo[-1], f"photo-{msg.date:%Y%m%d-%H%M%S}.jpg", "image/jpeg"
        elif msg.voice:
            tg_file, name, mime = msg.voice, f"voice-{msg.date:%Y%m%d-%H%M%S}.ogg", msg.voice.mime_type or "audio/ogg"
        elif msg.audio:
            tg_file, name, mime = msg.audio, msg.audio.file_name or "audio", msg.audio.mime_type or ""
        elif msg.video:
            tg_file, name, mime = msg.video, msg.video.file_name or f"video-{msg.date:%Y%m%d-%H%M%S}.mp4", msg.video.mime_type or ""
        if tg_file is not None:
            if c.step != "evidence":
                await reply(update, [Out("I can only accept files at the evidence step. Send /new to start a report.")])
                return
            if (getattr(tg_file, "file_size", 0) or 0) > TG_DOWNLOAD_LIMIT:
                await reply(update, [Out("That file is larger than 20 MB, which Telegram does not let bots download. "
                                         "Upload it on the Ubufakazi Track page after you submit.", ["Done"])])
                return
            f = await tg_file.get_file()
            data = bytes(await f.download_as_bytearray())
            file = (data, name, mime)
        location = (msg.location.latitude, msg.location.longitude) if msg.location else None
        text = msg.text or msg.caption or ""
        outs = await asyncio.to_thread(c.handle, text if not file else None, file=file, location=location)
        if file and text and c.step == "evidence":
            outs += await asyncio.to_thread(c.handle, text)      # a caption is kept as pasted text too
        await reply(update, outs)

    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.ALL, on_message))
    return app


async def start_bot() -> None:
    """Called from the server's startup. Never raises: failures are reported on /api/integrations."""
    global _application
    token = get_settings().telegram_token
    if not token:
        return
    try:
        _application = build_application(token)
        await _application.initialize()
        me = await _application.bot.get_me()
        await _application.start()
        await _application.updater.start_polling(drop_pending_updates=False)
        STATE.update(running=True, username=me.username, error=None,
                     started_at=dt.datetime.now(dt.timezone.utc).isoformat())
        log.info("Telegram bot @%s is running (long polling)", me.username)
    except Exception as e:      # wrong token, no network, ...
        STATE.update(running=False, error=f"{type(e).__name__}: could not start the bot (check the token and network).")
        log.warning("Telegram bot not started: %s", type(e).__name__)
        _application = None


async def stop_bot() -> None:
    global _application
    if _application is None:
        return
    try:
        await _application.updater.stop()
        await _application.stop()
        await _application.shutdown()
    finally:
        _application = None
        STATE["running"] = False


if __name__ == "__main__":
    print("The Telegram bot starts automatically with the server when TELEGRAM_BOT_TOKEN is set in server/.env:\n"
          "    uvicorn ubufakazi_server.app:app --port 8000")
