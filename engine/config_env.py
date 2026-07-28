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
DEFAULT_SQLITE_PATH = ROOT / "data" / "store" / "recyclage.db"


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
    except ImportError:
        return

    for key in _ENV_KEYS:
        try:
            value = st.secrets[key]
        except Exception:
            continue
        if value is None or str(value).strip() == "":
            continue
        os.environ.setdefault(key, str(value).strip())

    try:
        import streamlit as st

        for section in st.secrets:
            block = st.secrets[section]
            if not isinstance(block, dict):
                continue
            for key, value in block.items():
                env_key = str(key).upper()
                if env_key not in _ENV_KEYS:
                    continue
                if value is None or str(value).strip() == "":
                    continue
                os.environ.setdefault(env_key, str(value).strip())
    except Exception:
        return


def resolve_database_url() -> str:
    """Return PostgreSQL URL from DATABASE_URL (required)."""
    bootstrap_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL manquant. Configurez PostgreSQL dans .env ou les secrets Streamlit.\n"
            "Exemple : DATABASE_URL=postgresql://user:pass@host/db?sslmode=require"
        )
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql"):
        return url
    raise RuntimeError(
        "DATABASE_URL non reconnu. Utilisez une URL PostgreSQL (postgresql://...)."
    )


def is_postgresql_backend() -> bool:
    return resolve_database_url().startswith("postgresql")


def require_database_url() -> str:
    """Return PostgreSQL URL only — for migration scripts."""
    bootstrap_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "DATABASE_URL manquant. Requis pour la migration vers PostgreSQL.\n"
            "export DATABASE_URL=\"postgresql://...?sslmode=require\""
        )
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if not url.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL doit être une URL PostgreSQL (postgresql://...).")
    return url
