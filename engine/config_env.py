"""Load environment: .env file, then Streamlit Cloud secrets."""

from __future__ import annotations

import os
from pathlib import Path

_ENV_KEYS = (
    "DATABASE_URL",
    "APP_DEFAULT_USER",
    "APP_DEFAULT_PASSWORD",
    "APP_RESET_PASSWORD_ON_START",
)

ROOT = Path(__file__).resolve().parents[1]


def bootstrap_env() -> None:
    """Load .env (local) and Streamlit secrets (cloud) into os.environ."""
    _load_dotenv()
    _load_streamlit_secrets()


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path)
    except ImportError:
        # Minimal parser if python-dotenv is not installed yet.
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _load_streamlit_secrets() -> None:
    try:
        import streamlit as st
        from streamlit.errors import StreamlitSecretNotFoundError
    except ImportError:
        return

    try:
        secrets = st.secrets
        _ = secrets.keys()
    except Exception:
        return

    for key in _ENV_KEYS:
        try:
            if key in secrets:
                os.environ.setdefault(key, str(secrets[key]))
        except StreamlitSecretNotFoundError:
            return
        except Exception:
            continue

    try:
        for section in secrets:
            block = secrets[section]
            if not isinstance(block, dict):
                continue
            for key, value in block.items():
                env_key = str(key).upper()
                if env_key in _ENV_KEYS:
                    os.environ.setdefault(env_key, str(value))
    except Exception:
        return


def require_database_url() -> str:
    """Return a normalized PostgreSQL DATABASE_URL or raise with setup instructions."""
    bootstrap_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL manquant. L'application utilise PostgreSQL uniquement.\n"
            "• Streamlit Cloud : Settings → Secrets → DATABASE_URL\n"
            "• Local : copiez .env.example vers .env et renseignez votre URL Neon."
        )
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if not url.startswith("postgresql"):
        raise RuntimeError(
            "DATABASE_URL doit être une URL PostgreSQL (postgresql://...). "
            "SQLite n'est plus utilisé par l'application."
        )
    return url
