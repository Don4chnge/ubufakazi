"""Settings, read from environment variables (and an optional .env file).

Secrets never have defaults that would work in production: if UBF_SECRET_KEY or
UBF_HMAC_KEY is missing the server refuses to start (tests set their own).
"""
from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass

SERVER_DIR = pathlib.Path(__file__).resolve().parent.parent
REPO_DIR = SERVER_DIR.parent
SITE_DIR = REPO_DIR / "site"
WEB_DIR = pathlib.Path(__file__).resolve().parent / "web"


def data_dir() -> pathlib.Path:
    """Where the database, evidence and generated secrets live. On a host, point UBF_DATA_DIR at a persistent volume."""
    d = os.environ.get("UBF_DATA_DIR")
    return pathlib.Path(d).resolve() if d else SERVER_DIR / "data"


def _load_dotenv(path: pathlib.Path) -> None:
    """Minimal .env loader (KEY=VALUE lines). Real environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


@dataclass
class Settings:
    secret_key: str
    hmac_key: str
    database_url: str
    storage_dir: pathlib.Path
    public_base_url: str
    cookie_secure: bool
    telegram_token: str
    gemini_api_key: str
    gemini_model: str
    max_upload_bytes: int = 25 * 1024 * 1024       # per file
    max_files_per_report: int = 20
    session_hours: int = 8
    demo_mode: bool = True                           # all data fictional; UI shows DEMO banners
    storage_backend: str = "file"                   # file (local disk) | db (inside the database, for hosts without disks)
    demo_seed: str = ""                              # optional: derive demo passwords/2FA secrets (see creds.py)
    whatsapp_token: str = ""                         # Meta WhatsApp Cloud API (see whatsapp.py)
    whatsapp_phone_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v23.0"
    whatsapp_waba_id: str = ""                       # optional: WhatsApp Business Account ID, to subscribe the app at startup


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _load_dotenv(SERVER_DIR / ".env")
        _load_dotenv(data_dir() / ".env")             # secrets generated on a persistent volume survive restarts
        secret = os.environ.get("UBF_SECRET_KEY", "")
        hkey = os.environ.get("UBF_HMAC_KEY", "")
        if len(secret) < 32 or len(hkey) < 32 or "change-me" in (secret, hkey):
            raise RuntimeError(
                "UBF_SECRET_KEY and UBF_HMAC_KEY must be set to random values of 32+ characters. "
                "Run:  python -m ubufakazi_server.setup"
            )
        storage = pathlib.Path(os.environ.get("UBF_STORAGE_DIR") or str(data_dir() / "evidence"))
        if not storage.is_absolute():
            storage = (SERVER_DIR / storage).resolve()
        db_url = os.environ.get("DATABASE_URL") or f"sqlite:///{data_dir() / 'ubufakazi.db'}"
        for prefix in ("postgres://", "postgresql://"):       # Neon/Supabase/Render style URLs -> psycopg 3 driver
            if db_url.startswith(prefix):
                db_url = "postgresql+psycopg://" + db_url[len(prefix):]
        if db_url.startswith("sqlite:///./"):
            db_url = "sqlite:///" + str((SERVER_DIR / db_url[len("sqlite:///./"):]).resolve())
        _settings = Settings(
            secret_key=secret,
            hmac_key=hkey,
            database_url=db_url,
            storage_dir=storage,
            public_base_url=(os.environ.get("UBF_PUBLIC_BASE_URL") or "http://localhost:8000").rstrip("/"),
            cookie_secure=os.environ.get("UBF_COOKIE_SECURE", "0") == "1"
            or (os.environ.get("UBF_PUBLIC_BASE_URL") or "").startswith("https://"),
            telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            gemini_model=os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash",
            demo_seed=os.environ.get("UBF_DEMO_SEED", ""),
            whatsapp_token=os.environ.get("WHATSAPP_TOKEN", "").strip(),
            whatsapp_phone_id=os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
            whatsapp_verify_token=os.environ.get("WHATSAPP_VERIFY_TOKEN", "").strip(),
            whatsapp_app_secret=os.environ.get("WHATSAPP_APP_SECRET", "").strip(),
            whatsapp_waba_id=os.environ.get("WHATSAPP_BUSINESS_ACCOUNT_ID", "").strip(),
            whatsapp_api_version=os.environ.get("WHATSAPP_API_VERSION", "").strip() or "v23.0",
            storage_backend=(os.environ.get("UBF_STORAGE") or ("db" if db_url.startswith("postgresql") else "file")).lower(),
        )
    return _settings


def reset_settings() -> None:
    """Used by tests."""
    global _settings
    _settings = None
