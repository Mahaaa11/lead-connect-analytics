"""Load environment: .env file, then Streamlit Cloud secrets."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote_plus

_ENV_KEYS = (
    "DATABASE_URL",
    "MYSQL_HOST",
    "MYSQL_PORT",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DATABASE",
    "MYSQL_SSL",
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


def _mysql_url_from_parts() -> str | None:
    """Build mysql+pymysql URL from MYSQL_* env vars (Streamlit / TiDB style)."""
    host = os.environ.get("MYSQL_HOST", "").strip()
    if not host:
        return None
    user = os.environ.get("MYSQL_USER", "").strip() or "root"
    password = os.environ.get("MYSQL_PASSWORD", "")
    port = os.environ.get("MYSQL_PORT", "").strip() or "4000"
    database = os.environ.get("MYSQL_DATABASE", "").strip() or "test"
    return (
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}"
    )


def resolve_database_url() -> str:
    """Cloud: TiDB/MySQL or PostgreSQL via DATABASE_URL / MYSQL_*. Local: SQLite."""
    bootstrap_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        built = _mysql_url_from_parts()
        if built:
            url = built
        else:
            DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{DEFAULT_SQLITE_PATH}"

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    if url.startswith(("postgresql", "mysql+pymysql://", "mysql://", "sqlite:")):
        return url
    raise RuntimeError(
        "DATABASE_URL non reconnu. Utilisez mysql+pymysql://... (TiDB), "
        "postgresql://..., MYSQL_* secrets, ou laissez vide pour SQLite local."
    )


def is_postgresql_backend() -> bool:
    return resolve_database_url().startswith("postgresql")


def is_mysql_backend() -> bool:
    url = resolve_database_url()
    return url.startswith("mysql+pymysql://") or url.startswith("mysql://")


def is_cloud_sql_backend() -> bool:
    return is_postgresql_backend() or is_mysql_backend()


def require_mysql_database_url() -> str:
    """Return MySQL/TiDB URL only — for migration scripts."""
    bootstrap_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        url = _mysql_url_from_parts() or ""
    if not url:
        raise RuntimeError(
            "DATABASE_URL / MYSQL_* manquant. Requis pour la migration vers TiDB.\n"
            'export DATABASE_URL="mysql+pymysql://USER:PASS@HOST:4000/DB"\n'
            "ou MYSQL_HOST / MYSQL_USER / MYSQL_PASSWORD / MYSQL_DATABASE"
        )
    if url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    if not url.startswith("mysql+pymysql://"):
        raise RuntimeError(
            "Pour TiDB, DATABASE_URL doit être mysql+pymysql://... "
            "(pas postgresql://)."
        )
    return url
