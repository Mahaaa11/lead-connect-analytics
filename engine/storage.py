"""SQL-backed persistent storage (TiDB/MySQL or PostgreSQL cloud, SQLite local)."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError

STORE_DIR = Path(__file__).resolve().parents[1] / "data" / "store"

from engine.config_env import (
    bootstrap_env,
    is_mysql_backend,
    is_postgresql_backend,
    resolve_database_url,
)

bootstrap_env()

_engine: Engine | None = None
_schema_initialized = False
_engine_url: str | None = None


def _database_url() -> str:
    return resolve_database_url()


def _is_mysql_dialect(dialect: str) -> bool:
    return dialect in ("mysql", "mariadb")


def get_engine() -> Engine:
    global _engine, _engine_url
    url = _database_url()
    if _engine is None or _engine_url != url:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        if is_postgresql_backend():
            _engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=3,
                pool_recycle=300,
                connect_args={"connect_timeout": 15},
            )
        elif is_mysql_backend():
            connect_args: dict[str, Any] = {"connect_timeout": 15}
            # TiDB Cloud requires TLS
            if os.getenv("MYSQL_SSL", "").lower() in ("1", "true", "yes") or "tidbcloud.com" in url:
                connect_args["ssl"] = {"ssl": True}
            _engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=3,
                pool_recycle=300,
                connect_args=connect_args,
            )
        else:
            _engine = create_engine(url, pool_pre_ping=True)
        _engine_url = url
    return _engine


def backend_label() -> str:
    if is_mysql_backend():
        return "TiDB / MySQL"
    if is_postgresql_backend():
        return "PostgreSQL"
    return "SQLite"


def init_schema(engine: Engine | None = None) -> None:
    global _schema_initialized
    if _schema_initialized:
        return
    engine = engine or get_engine()
    dialect = engine.dialect.name

    if _is_mysql_dialect(dialect):
        # VARCHAR PKs + backticks for reserved `key` (MySQL/TiDB)
        ddl = """
        CREATE TABLE IF NOT EXISTS client_db (
            tel VARCHAR(64) PRIMARY KEY,
            data LONGTEXT NOT NULL,
            updated_at VARCHAR(64) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS history_rows (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            tel VARCHAR(64) NOT NULL,
            row_hash VARCHAR(255) NOT NULL,
            data LONGTEXT NOT NULL,
            created_at VARCHAR(64) NOT NULL,
            UNIQUE KEY uq_history_row_hash (row_hash)
        );
        CREATE TABLE IF NOT EXISTS history_compact (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            tel VARCHAR(64) NOT NULL,
            kind VARCHAR(16) NOT NULL,
            status VARCHAR(32) NULL,
            date_val VARCHAR(32) NULL,
            heure VARCHAR(32) NULL,
            lib_status VARCHAR(255) NULL,
            tv VARCHAR(255) NULL,
            duree VARCHAR(64) NULL,
            UNIQUE KEY uq_history_compact (kind, tel, date_val, heure, status)
        );
        CREATE TABLE IF NOT EXISTS onoff_calls (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            tel VARCHAR(64) NOT NULL,
            duration_seconds INT NOT NULL DEFAULT 0,
            call_date VARCHAR(32) NULL,
            call_time VARCHAR(32) NULL,
            direction VARCHAR(32) NULL,
            row_hash VARCHAR(255) NOT NULL,
            created_at VARCHAR(64) NOT NULL,
            UNIQUE KEY uq_onoff_row_hash (row_hash)
        );
        CREATE TABLE IF NOT EXISTS onoff_totals (
            tel VARCHAR(64) PRIMARY KEY,
            total_duration_seconds INT NOT NULL DEFAULT 0,
            total_duration VARCHAR(64) NULL,
            call_count INT NOT NULL DEFAULT 0,
            updated_at VARCHAR(64) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_meta (
            `key` VARCHAR(64) PRIMARY KEY,
            value LONGTEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vente_baseline (
            tel VARCHAR(64) PRIMARY KEY,
            statut VARCHAR(128) NOT NULL,
            couleur VARCHAR(64) NULL,
            updated_at VARCHAR(64) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vente_results (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            tel VARCHAR(64) NOT NULL,
            jour_vente VARCHAR(32) NOT NULL,
            statut_origine VARCHAR(128) NULL,
            couleur_origine VARCHAR(64) NULL,
            source_baseline VARCHAR(128) NULL,
            matched INT NOT NULL DEFAULT 0,
            nom VARCHAR(128) NULL,
            prenom VARCHAR(128) NULL,
            analyzed_at VARCHAR(64) NOT NULL,
            batch_id VARCHAR(64) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_users (
            username VARCHAR(64) PRIMARY KEY,
            password_hash VARCHAR(255) NOT NULL,
            updated_at VARCHAR(64) NOT NULL
        );
        CREATE INDEX idx_history_tel ON history_rows (tel);
        CREATE INDEX idx_onoff_tel ON onoff_calls (tel);
        CREATE INDEX idx_onoff_totals_tel ON onoff_totals (tel);
        CREATE INDEX idx_vente_results_batch ON vente_results (batch_id);
        CREATE INDEX idx_vente_results_jour ON vente_results (jour_vente);
        """
    else:
        ddl = """
        CREATE TABLE IF NOT EXISTS client_db (
            tel TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS history_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tel TEXT NOT NULL,
            row_hash TEXT NOT NULL UNIQUE,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS history_compact (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tel TEXT NOT NULL,
            kind TEXT NOT NULL,
            status TEXT,
            date_val TEXT,
            heure TEXT,
            lib_status TEXT,
            tv TEXT,
            duree TEXT
        );
        CREATE TABLE IF NOT EXISTS onoff_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tel TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0,
            call_date TEXT,
            call_time TEXT,
            direction TEXT,
            row_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS onoff_totals (
            tel TEXT PRIMARY KEY,
            total_duration_seconds INTEGER NOT NULL DEFAULT 0,
            total_duration TEXT,
            call_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vente_baseline (
            tel TEXT PRIMARY KEY,
            statut TEXT NOT NULL,
            couleur TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS vente_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tel TEXT NOT NULL,
            jour_vente TEXT NOT NULL,
            statut_origine TEXT,
            couleur_origine TEXT,
            source_baseline TEXT,
            matched INTEGER NOT NULL DEFAULT 0,
            nom TEXT,
            prenom TEXT,
            analyzed_at TEXT NOT NULL,
            batch_id TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS app_users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_history_tel ON history_rows (tel);
        CREATE INDEX IF NOT EXISTS idx_onoff_tel ON onoff_calls (tel);
        CREATE INDEX IF NOT EXISTS idx_onoff_totals_tel ON onoff_totals (tel);
        CREATE INDEX IF NOT EXISTS idx_vente_results_batch ON vente_results (batch_id);
        CREATE INDEX IF NOT EXISTS idx_vente_results_jour ON vente_results (jour_vente);
        """
        if dialect == "postgresql":
            ddl = ddl.replace("AUTOINCREMENT", "GENERATED BY DEFAULT AS IDENTITY")

    with engine.begin() as conn:
        for statement in ddl.strip().split(";"):
            stmt = statement.strip()
            if not stmt:
                continue
            try:
                conn.execute(text(stmt))
            except Exception as exc:
                # MySQL/TiDB: CREATE INDEX may fail if index already exists
                msg = str(exc).lower()
                if _is_mysql_dialect(dialect) and (
                    "duplicate key name" in msg
                    or "already exists" in msg
                    or "1061" in msg
                ):
                    continue
                raise
    _schema_initialized = True


def _row_hash(parts: list[str]) -> str:
    return "|".join(str(p) for p in parts)


def _df_row_to_json(row: pd.Series) -> str:
    payload = row.to_dict()
    cleaned = {}
    for key, value in payload.items():
        if pd.isna(value):
            cleaned[key] = None
        elif isinstance(value, (pd.Timestamp, datetime)):
            cleaned[key] = value.isoformat()
        else:
            cleaned[key] = value
    return json.dumps(cleaned, default=str)


def _json_rows_to_df(rows: list[dict[str, str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    records = [json.loads(row["data"]) for row in rows]
    return pd.DataFrame(records)


def store_has_data(engine: Engine | None = None) -> bool:
    counts = get_store_counts(engine)
    return counts["db_rows"] > 0 and counts["hist_rows"] > 0


def current_schema_name(engine: Engine | None = None) -> str:
    engine = engine or get_engine()
    dialect = engine.dialect.name
    with engine.connect() as conn:
        if dialect in ("mysql", "mariadb"):
            return str(conn.execute(text("SELECT DATABASE()")).scalar() or "")
        if dialect == "postgresql":
            return str(conn.execute(text("SELECT current_schema()")).scalar() or "")
    return "sqlite"


def get_store_counts(engine: Engine | None = None) -> dict[str, int]:
    """Cheap COUNT(*) per table. Avoid COUNT(DISTINCT) — TiDB Serverless kills it on memory."""
    engine = engine or get_engine()
    init_schema(engine)

    def _n(conn, table: str) -> int:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one() or 0)

    with engine.connect() as conn:
        db_rows = _n(conn, "client_db")
        hist_rows = _n(conn, "history_rows")
        onoff_rows = _n(conn, "onoff_calls")
        onoff_totals_rows = _n(conn, "onoff_totals")
        conn.commit()
    return {
        "db_rows": db_rows,
        "hist_rows": hist_rows,
        "hist_tels": hist_rows,
        "onoff_rows": onoff_rows,
        "onoff_tels": onoff_rows,
        "onoff_totals_rows": onoff_totals_rows,
    }


def list_client_tels(engine: Engine | None = None) -> set[str]:
    """Return known TEL keys without deserializing client JSON payloads."""
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        result = conn.execute(text("SELECT tel FROM client_db"))
        return {str(row[0]).strip() for row in result.fetchall() if row[0]}


def load_meta(engine: Engine | None = None) -> dict[str, Any]:
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        if _is_mysql_dialect(engine.dialect.name):
            row = conn.execute(
                text("SELECT value FROM app_meta WHERE `key` = 'meta'")
            ).fetchone()
        else:
            row = conn.execute(
                text("SELECT value FROM app_meta WHERE key = 'meta'")
            ).fetchone()
    if not row:
        return {"updates": []}
    return json.loads(row[0])


def save_meta(meta: dict[str, Any], engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    init_schema(engine)
    payload = json.dumps(meta, default=str)
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(
                text(
                    """
                    INSERT INTO app_meta (key, value) VALUES ('meta', :value)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """
                ),
                {"value": payload},
            )
        elif _is_mysql_dialect(dialect):
            conn.execute(
                text(
                    """
                    INSERT INTO app_meta (`key`, value) VALUES ('meta', :value)
                    ON DUPLICATE KEY UPDATE value = VALUES(value)
                    """
                ),
                {"value": payload},
            )
        else:
            conn.execute(text("DELETE FROM app_meta WHERE key = 'meta'"))
            conn.execute(
                text("INSERT INTO app_meta (key, value) VALUES ('meta', :value)"),
                {"value": payload},
            )


def _dedupe_client_rows(df: pd.DataFrame) -> pd.DataFrame:
    """One row per canonical TEL (last wins). Handles int/str duplicates."""
    if df.empty or "TEL" not in df.columns:
        return df
    out = df.copy()
    out["TEL"] = out["TEL"].astype(str).str.strip()
    out = out[out["TEL"].notna() & (out["TEL"] != "") & (out["TEL"].str.lower() != "nan")]
    return out.drop_duplicates(subset=["TEL"], keep="last").reset_index(drop=True)


def _client_db_insert_sql(dialect: str, *, replace_all: bool) -> str:
    if dialect == "postgresql":
        if replace_all:
            return (
                "INSERT INTO client_db (tel, data, updated_at) "
                "VALUES (:tel, :data, :updated_at)"
            )
        return (
            """
            INSERT INTO client_db (tel, data, updated_at)
            VALUES (:tel, :data, :updated_at)
            ON CONFLICT (tel) DO UPDATE SET
                data = EXCLUDED.data,
                updated_at = EXCLUDED.updated_at
            """
        )
    if _is_mysql_dialect(dialect):
        if replace_all:
            return (
                "INSERT INTO client_db (tel, data, updated_at) "
                "VALUES (:tel, :data, :updated_at)"
            )
        return (
            """
            INSERT INTO client_db (tel, data, updated_at)
            VALUES (:tel, :data, :updated_at)
            ON DUPLICATE KEY UPDATE
                data = VALUES(data),
                updated_at = VALUES(updated_at)
            """
        )
    if replace_all:
        return (
            "INSERT OR REPLACE INTO client_db (tel, data, updated_at) "
            "VALUES (:tel, :data, :updated_at)"
        )
    return (
        "INSERT OR REPLACE INTO client_db (tel, data, updated_at) "
        "VALUES (:tel, :data, :updated_at)"
    )


def _rows_from_df(df: pd.DataFrame, *, now: str) -> list[dict[str, str]]:
    df = _dedupe_client_rows(df)
    by_tel: dict[str, dict[str, str]] = {}
    for _, row in df.iterrows():
        tel = str(row["TEL"]).strip()
        by_tel[tel] = {"tel": tel, "data": _df_row_to_json(row), "updated_at": now}
    return list(by_tel.values())


def _execute_client_rows(
    conn,
    rows: list[dict[str, str]],
    *,
    dialect: str,
    replace_all: bool,
    chunk_size: int = 500,
) -> None:
    if not rows:
        return
    sql = text(_client_db_insert_sql(dialect, replace_all=replace_all))
    for start in range(0, len(rows), chunk_size):
        conn.execute(sql, rows[start : start + chunk_size])
def replace_client_db(df: pd.DataFrame, engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    init_schema(engine)
    now = datetime.now().isoformat(timespec="seconds")
    if df.empty:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM client_db"))
        return
    rows = _rows_from_df(df, now=now)
    dialect = engine.dialect.name
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM client_db"))
        _execute_client_rows(conn, rows, dialect=dialect, replace_all=True)


def upsert_client_db(df: pd.DataFrame, engine: Engine | None = None) -> int:
    """Insert or update client rows keyed by TEL."""
    engine = engine or get_engine()
    init_schema(engine)
    if df.empty:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    rows = _rows_from_df(df, now=now)
    dialect = engine.dialect.name
    with engine.begin() as conn:
        _execute_client_rows(conn, rows, dialect=dialect, replace_all=False)
    return len(rows)


def load_client_db(engine: Engine | None = None) -> pd.DataFrame:
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        result = conn.execute(text("SELECT data FROM client_db"))
        records = [json.loads(row[0]) for row in result.fetchall()]
    return pd.DataFrame(records)


def replace_history(df: pd.DataFrame, engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    init_schema(engine)
    now = datetime.now().isoformat(timespec="seconds")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM history_rows"))
        if df.empty:
            conn.execute(text("DELETE FROM history_compact"))
            return
        _insert_history_rows(conn, df, now)
    _sync_history_compact_after_write(df, engine, replaced=True)


def append_history(
    df: pd.DataFrame,
    engine: Engine | None = None,
    *,
    return_inserted_count: bool = True,
) -> int:
    engine = engine or get_engine()
    init_schema(engine)
    if df.empty:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    with engine.begin() as conn:
        before = 0
        if return_inserted_count:
            before = int(conn.execute(text("SELECT COUNT(*) FROM history_rows")).scalar_one())
        attempted = _insert_history_rows(conn, df, now)
        after = before
        if return_inserted_count:
            after = int(conn.execute(text("SELECT COUNT(*) FROM history_rows")).scalar_one())
        inserted = max(0, after - before) if return_inserted_count else attempted
    if inserted:
        _sync_history_compact_after_write(df, engine, replaced=False)
    return inserted if return_inserted_count else attempted


def _hash_part_series(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series([""] * len(df), index=df.index, dtype="object")
    return (
        df[col]
        .where(df[col].notna(), "")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .replace({"nan": "", "None": "", "<NA>": ""})
    )


def _history_row_hashes(df: pd.DataFrame) -> pd.Series:
    """One hash per dialer event.

    Legacy rows (daily fusion) only have TEL|DATE|HEURE|STATUS.
    Full WeKiwi histo dumps also have INDICE + STATUS_DATE + STATUS_STARTTIME
    — without those, 1.5M call lines collapse to ~89k keys.
    """
    tel = _hash_part_series(df, "TEL")
    date = _hash_part_series(df, "DATE")
    heure = _hash_part_series(df, "HEURE")
    status = _hash_part_series(df, "STATUS")
    base = tel + "|" + date + "|" + heure + "|" + status
    indice = _hash_part_series(df, "INDICE")
    status_date = _hash_part_series(df, "STATUS_DATE")
    start = _hash_part_series(df, "STATUS_STARTTIME")
    status_id = _hash_part_series(df, "STATUS_ID")
    extra = indice + "|" + status_date + "|" + start + "|" + status_id
    has_event = extra.str.replace("|", "", regex=False).str.len() > 0
    return base.where(~has_event, base + "|" + extra)


def _insert_history_rows(conn, df: pd.DataFrame, now: str) -> int:
    if df.empty or "TEL" not in df.columns:
        return 0

    work = df.copy()
    work["_row_hash"] = _history_row_hashes(work)
    work = work.drop_duplicates(subset=["_row_hash"], keep="first")
    hashes = work["_row_hash"].tolist()
    payload = work.drop(columns=["_row_hash"])
    records = json.loads(payload.to_json(orient="records", date_format="iso"))

    rows = []
    for rec, row_hash in zip(records, hashes):
        tel = rec.get("TEL")
        rows.append(
            {
                "tel": "" if tel is None else str(tel),
                "row_hash": row_hash,
                "data": json.dumps(rec, default=str, separators=(",", ":")),
                "created_at": now,
            }
        )

    if not rows:
        return 0

    dialect = conn.dialect.name
    chunk_size = 800 if _is_mysql_dialect(dialect) else 4000
    if dialect == "postgresql":
        sql = text(
            """
            INSERT INTO history_rows (tel, row_hash, data, created_at)
            VALUES (:tel, :row_hash, :data, :created_at)
            ON CONFLICT (row_hash) DO NOTHING
            """
        )
    elif _is_mysql_dialect(dialect):
        sql = text(
            """
            INSERT IGNORE INTO history_rows (tel, row_hash, data, created_at)
            VALUES (:tel, :row_hash, :data, :created_at)
            """
        )
    else:
        sql = text(
            """
            INSERT OR IGNORE INTO history_rows (tel, row_hash, data, created_at)
            VALUES (:tel, :row_hash, :data, :created_at)
            """
        )
    for start in range(0, len(rows), chunk_size):
        conn.execute(sql, rows[start : start + chunk_size])
    return len(rows)


COMPACT_HISTORY_THRESHOLD = 250_000
COMPACT_RECENT_DAYS = 180


def _event_sort_tuple(date_s: object, heure_s: object, row_id: int = 0) -> tuple[str, str, int]:
    date_d = "".join(ch for ch in str(date_s or "") if ch.isdigit())[:8].ljust(8, "0")
    heure_d = "".join(ch for ch in str(heure_s or "") if ch.isdigit())[:6].ljust(4, "0")
    return (date_d, heure_d, int(row_id or 0))


def _status_code(status: object) -> str:
    return str(status or "").replace(".0", "").strip()


def _slim_rec(
    tel: object,
    status: object,
    date_s: object,
    heure_s: object,
    lib_status: object = None,
    tv: object = None,
    duree: object = None,
) -> dict[str, Any]:
    return {
        "TEL": "" if tel is None else str(tel),
        "STATUS": status,
        "DATE": date_s,
        "HEURE": heure_s,
        "LIB_STATUS": lib_status,
        "TV": tv,
        "DUREE": duree,
    }


def _ensure_history_compact_table(engine: Engine) -> None:
    dialect = engine.dialect.name
    if _is_mysql_dialect(dialect):
        stmt = """
            CREATE TABLE IF NOT EXISTS history_compact (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                tel VARCHAR(64) NOT NULL,
                kind VARCHAR(16) NOT NULL,
                status VARCHAR(32) NULL,
                date_val VARCHAR(32) NULL,
                heure VARCHAR(32) NULL,
                lib_status VARCHAR(255) NULL,
                tv VARCHAR(255) NULL,
                duree VARCHAR(64) NULL,
                UNIQUE KEY uq_history_compact (kind, tel, date_val, heure, status)
            )
        """
    else:
        stmt = """
            CREATE TABLE IF NOT EXISTS history_compact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tel TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT,
                date_val TEXT,
                heure TEXT,
                lib_status TEXT,
                tv TEXT,
                duree TEXT
            )
        """
        if dialect == "postgresql":
            stmt = stmt.replace("AUTOINCREMENT", "GENERATED BY DEFAULT AS IDENTITY")
    with engine.begin() as conn:
        conn.execute(text(stmt))


def _compact_payload(rec: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "tel": str(rec.get("TEL") or ""),
        "kind": kind,
        "status": None if rec.get("STATUS") is None else str(rec.get("STATUS")),
        "date_val": None if rec.get("DATE") is None else str(rec.get("DATE")),
        "heure": None if rec.get("HEURE") is None else str(rec.get("HEURE")),
        "lib_status": None if rec.get("LIB_STATUS") is None else str(rec.get("LIB_STATUS")),
        "tv": None if rec.get("TV") is None else str(rec.get("TV")),
        "duree": None if rec.get("DUREE") is None else str(rec.get("DUREE")),
    }


def _insert_compact_rows(conn, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    dialect = conn.dialect.name
    if dialect == "postgresql":
        sql = text(
            """
            INSERT INTO history_compact
                (tel, kind, status, date_val, heure, lib_status, tv, duree)
            VALUES
                (:tel, :kind, :status, :date_val, :heure, :lib_status, :tv, :duree)
            ON CONFLICT DO NOTHING
            """
        )
    elif _is_mysql_dialect(dialect):
        sql = text(
            """
            INSERT IGNORE INTO history_compact
                (tel, kind, status, date_val, heure, lib_status, tv, duree)
            VALUES
                (:tel, :kind, :status, :date_val, :heure, :lib_status, :tv, :duree)
            """
        )
    else:
        sql = text(
            """
            INSERT OR IGNORE INTO history_compact
                (tel, kind, status, date_val, heure, lib_status, tv, duree)
            VALUES
                (:tel, :kind, :status, :date_val, :heure, :lib_status, :tv, :duree)
            """
        )
    chunk = 800 if _is_mysql_dialect(dialect) else 4000
    for start in range(0, len(rows), chunk):
        conn.execute(sql, rows[start : start + chunk])


def _heure_from_start(start: object, fallback: object = None) -> object:
    raw = "".join(ch for ch in str(start or "") if ch.isdigit())
    if len(raw) >= 4:
        return raw[:4]
    return fallback


def _records_from_compact_scan(
    engine: Engine,
) -> tuple[list[dict[str, Any]], int, int]:
    """Stream slim JSON fields. Keep latest per TEL, every vente, recent events.

    Dialer dumps store the call outcome in STATUS_STATUS / STATUS_DATE, while
    STATUS / DATE are the current fiche. Both code-1 sources are ventes.
    """
    latest: dict[str, tuple[tuple[str, str, int], dict[str, Any]]] = {}
    extra: dict[tuple[Any, ...], dict[str, Any]] = {}
    cutoff = (datetime.now() - timedelta(days=COMPACT_RECENT_DAYS)).strftime("%Y%m%d")
    sql = text(
        """
        SELECT id, tel,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.STATUS')) AS status,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.DATE')) AS date,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.HEURE')) AS heure,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.LIB_STATUS')) AS lib_status,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.TV')) AS tv,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.DUREE')) AS duree,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.STATUS_STATUS')) AS status_status,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.STATUS_DATE')) AS status_date,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.STATUS_STARTTIME')) AS status_start,
            JSON_UNQUOTE(JSON_EXTRACT(data, '$.STATUS_ID')) AS status_id
        FROM history_rows
        WHERE id > :lo AND id <= :hi
        """
    )
    scanned = 0
    lo = 0
    max_id: int | None = None
    step = 40_000
    while True:
        try:
            with engine.connect() as conn:
                if max_id is None:
                    max_id = int(
                        conn.execute(
                            text("SELECT COALESCE(MAX(id), 0) FROM history_rows")
                        ).scalar_one()
                    )
                while lo < max_id:
                    hi = min(lo + step, max_id)
                    rows = conn.execute(sql, {"lo": lo, "hi": hi}).fetchall()
                    scanned += len(rows)
                    for row in rows:
                        (
                            row_id,
                            tel,
                            status,
                            date_s,
                            heure_s,
                            lib_status,
                            tv,
                            duree,
                            status_status,
                            status_date,
                            status_start,
                            status_id,
                        ) = row
                        rec = _slim_rec(
                            tel, status, date_s, heure_s, lib_status, tv, duree
                        )
                        tel_s = rec["TEL"]
                        key = _event_sort_tuple(date_s, heure_s, row_id)
                        prev = latest.get(tel_s)
                        if prev is None or key >= prev[0]:
                            latest[tel_s] = (key, rec)
                        status_s = _status_code(status)
                        css = _status_code(status_status)
                        date_d = key[0]
                        keep_extra = status_s == "1" or date_d >= cutoff
                        if keep_extra:
                            sig = (tel_s, str(date_s), str(heure_s), str(status), "extra")
                            extra[sig] = rec
                        if css == "1":
                            sale_date = status_date or date_s
                            sale_heure = _heure_from_start(status_start, heure_s)
                            sale_rec = _slim_rec(
                                tel,
                                "1",
                                sale_date,
                                sale_heure,
                                lib_status or "Vente",
                                tv,
                                duree,
                            )
                            sid = str(status_id or "") or str(sale_date)
                            extra[(tel_s, sid, "ss1")] = sale_rec
                    lo = hi
            break
        except OperationalError:
            time.sleep(2)
            engine = get_engine()

    out = [item[1] for item in latest.values()]
    seen = {
        (r.get("TEL"), str(r.get("DATE")), str(r.get("HEURE")), str(r.get("STATUS")))
        for r in out
    }
    extra_n = 0
    for rec in extra.values():
        sig = (rec.get("TEL"), str(rec.get("DATE")), str(rec.get("HEURE")), str(rec.get("STATUS")))
        if sig in seen:
            continue
        out.append(rec)
        seen.add(sig)
        extra_n += 1
    return out, scanned, extra_n


def _replace_history_compact(engine: Engine, records: list[dict[str, Any]]) -> None:
    _ensure_history_compact_table(engine)
    cutoff = (datetime.now() - timedelta(days=COMPACT_RECENT_DAYS)).strftime("%Y%m%d")
    latest_by_tel: dict[str, tuple[tuple[str, str, int], dict[str, Any]]] = {}
    for rec in records:
        tel = str(rec.get("TEL") or "")
        key = _event_sort_tuple(rec.get("DATE"), rec.get("HEURE"), 0)
        prev = latest_by_tel.get(tel)
        if prev is None or key >= prev[0]:
            latest_by_tel[tel] = (key, rec)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for rec in (item[1] for item in latest_by_tel.values()):
        payload = _compact_payload(rec, "latest")
        sig = ("latest", payload["tel"], payload["date_val"], payload["heure"], payload["status"])
        if sig in seen:
            continue
        seen.add(sig)
        rows.append(payload)
    for rec in records:
        status_s = _status_code(rec.get("STATUS"))
        date_d = _event_sort_tuple(rec.get("DATE"), rec.get("HEURE"), 0)[0]
        kind = "vente" if status_s == "1" else "recent"
        if kind == "recent" and date_d < cutoff:
            continue
        payload = _compact_payload(rec, kind)
        sig = (kind, payload["tel"], payload["date_val"], payload["heure"], payload["status"])
        if sig in seen:
            continue
        seen.add(sig)
        rows.append(payload)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM history_compact"))
        _insert_compact_rows(conn, rows)
    meta = load_meta(engine)
    meta["history_compact_source_count"] = count_history_rows(engine)
    meta["history_compact_rows"] = len(rows)
    meta["history_compact_built_at"] = datetime.now().isoformat(timespec="seconds")
    save_meta(meta, engine)


def _load_history_from_compact(engine: Engine) -> pd.DataFrame:
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT tel, status, date_val, heure, lib_status, tv, duree
                FROM history_compact
                """
            )
        )
        rows = result.fetchall()
    records = [
        _slim_rec(tel, status, date_s, heure_s, lib_status, tv, duree)
        for tel, status, date_s, heure_s, lib_status, tv, duree in rows
    ]
    return pd.DataFrame(records)


def _compact_is_fresh(engine: Engine, hist_n: int) -> bool:
    _ensure_history_compact_table(engine)
    with engine.begin() as conn:
        compact_n = int(conn.execute(text("SELECT COUNT(*) FROM history_compact")).scalar_one())
    if compact_n <= 0:
        return False
    meta = load_meta(engine)
    return int(meta.get("history_compact_source_count") or 0) == hist_n


def _load_history_all(engine: Engine) -> pd.DataFrame:
    with engine.begin() as conn:
        result = conn.execute(text("SELECT data FROM history_rows"))
        records = [json.loads(row[0]) for row in result.fetchall()]
    return pd.DataFrame(records)


def refresh_history_compact(engine: Engine | None = None) -> pd.DataFrame:
    """Rebuild the slim history cache used by Streamlit Cloud."""
    engine = engine or get_engine()
    init_schema(engine)
    _ensure_history_compact_table(engine)
    records, _scanned, _extra_n = _records_from_compact_scan(engine)
    _replace_history_compact(engine, records)
    return pd.DataFrame(records)


def _sync_history_compact_after_write(
    df: pd.DataFrame,
    engine: Engine,
    *,
    replaced: bool,
) -> None:
    if not _is_mysql_dialect(engine.dialect.name):
        return
    n = count_history_rows(engine)
    _ensure_history_compact_table(engine)
    if n <= COMPACT_HISTORY_THRESHOLD:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM history_compact"))
        meta = load_meta(engine)
        meta["history_compact_source_count"] = n
        save_meta(meta, engine)
        return
    if replaced:
        meta = load_meta(engine)
        meta["history_compact_source_count"] = -1
        save_meta(meta, engine)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM history_compact"))
        return
    if not _compact_has_rows(engine):
        return
    records = _slim_records_from_frame(df)
    if not records:
        return
    _merge_compact_from_records(engine, records)
    meta = load_meta(engine)
    meta["history_compact_source_count"] = n
    save_meta(meta, engine)


def _compact_has_rows(engine: Engine) -> bool:
    with engine.begin() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM history_compact")).scalar_one()) > 0


def _slim_records_from_frame(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "TEL" not in df.columns:
        return []
    records: list[dict[str, Any]] = []
    for rec in json.loads(df.to_json(orient="records", date_format="iso")):
        records.append(
            _slim_rec(
                rec.get("TEL"),
                rec.get("STATUS"),
                rec.get("DATE"),
                rec.get("HEURE"),
                rec.get("LIB_STATUS"),
                rec.get("TV"),
                rec.get("DUREE"),
            )
        )
    return records


def _merge_compact_from_records(engine: Engine, records: list[dict[str, Any]]) -> None:
    cutoff = (datetime.now() - timedelta(days=COMPACT_RECENT_DAYS)).strftime("%Y%m%d")
    latest_by_tel: dict[str, tuple[tuple[str, str, int], dict[str, Any]]] = {}
    extra_rows: list[dict[str, Any]] = []
    for rec in records:
        tel = str(rec.get("TEL") or "")
        key = _event_sort_tuple(rec.get("DATE"), rec.get("HEURE"), 0)
        prev = latest_by_tel.get(tel)
        if prev is None or key >= prev[0]:
            latest_by_tel[tel] = (key, rec)
        status_s = _status_code(rec.get("STATUS"))
        date_d = key[0]
        if status_s == "1":
            extra_rows.append(_compact_payload(rec, "vente"))
        elif date_d >= cutoff:
            extra_rows.append(_compact_payload(rec, "recent"))
    tels = [tel for tel in latest_by_tel if tel]
    existing: dict[str, tuple[str, str]] = {}
    if tels:
        with engine.begin() as conn:
            for start in range(0, len(tels), 400):
                chunk = tels[start : start + 400]
                placeholders = ", ".join(f":t{i}" for i in range(len(chunk)))
                params = {f"t{i}": tel for i, tel in enumerate(chunk)}
                rows = conn.execute(
                    text(
                        f"""
                        SELECT tel, date_val, heure
                        FROM history_compact
                        WHERE kind = 'latest' AND tel IN ({placeholders})
                        """
                    ),
                    params,
                ).fetchall()
                for tel, date_s, heure_s in rows:
                    existing[str(tel)] = (str(date_s or ""), str(heure_s or ""))
    replace_tels: list[str] = []
    latest_rows: list[dict[str, Any]] = []
    for tel, packed in latest_by_tel.items():
        rec = packed[1]
        new_key = packed[0]
        old = existing.get(tel)
        if old is None or new_key >= _event_sort_tuple(old[0], old[1], 0):
            replace_tels.append(tel)
            latest_rows.append(_compact_payload(rec, "latest"))
    with engine.begin() as conn:
        if replace_tels:
            for start in range(0, len(replace_tels), 400):
                chunk = replace_tels[start : start + 400]
                placeholders = ", ".join(f":t{i}" for i in range(len(chunk)))
                params = {f"t{i}": tel for i, tel in enumerate(chunk)}
                conn.execute(
                    text(
                        f"DELETE FROM history_compact WHERE kind = 'latest' AND tel IN ({placeholders})"
                    ),
                    params,
                )
            _insert_compact_rows(conn, latest_rows)
        _insert_compact_rows(conn, extra_rows)


def load_history(engine: Engine | None = None, *, full: bool = False) -> pd.DataFrame:
    engine = engine or get_engine()
    init_schema(engine)
    n = count_history_rows(engine)
    if (
        full
        or n <= COMPACT_HISTORY_THRESHOLD
        or not _is_mysql_dialect(engine.dialect.name)
    ):
        return _load_history_all(engine)
    if _compact_is_fresh(engine, n):
        return _load_history_from_compact(engine)
    records, _scanned, _extra_n = _records_from_compact_scan(engine)
    _replace_history_compact(engine, records)
    return pd.DataFrame(records)


def count_history_rows(engine: Engine | None = None) -> int:
    engine = engine or get_engine()
    with engine.begin() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM history_rows")).scalar_one())


def count_history_tels(engine: Engine | None = None) -> int:
    engine = engine or get_engine()
    with engine.begin() as conn:
        return int(
            conn.execute(text("SELECT COUNT(DISTINCT tel) FROM history_rows")).scalar_one()
        )


def count_onoff_tels(engine: Engine | None = None) -> int:
    engine = engine or get_engine()
    with engine.begin() as conn:
        return int(
            conn.execute(text("SELECT COUNT(DISTINCT tel) FROM onoff_calls")).scalar_one()
        )


def replace_onoff_calls(df: pd.DataFrame, engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    init_schema(engine)
    now = datetime.now().isoformat(timespec="seconds")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM onoff_calls"))
        if df.empty:
            return
        _insert_onoff_rows(conn, df, now)


def append_onoff_calls(df: pd.DataFrame, engine: Engine | None = None) -> int:
    engine = engine or get_engine()
    init_schema(engine)
    if df.empty:
        return 0
    before = count_onoff_rows(engine)
    now = datetime.now().isoformat(timespec="seconds")
    with engine.begin() as conn:
        _insert_onoff_rows(conn, df, now)
    return count_onoff_rows(engine) - before


def _insert_onoff_rows(conn, df: pd.DataFrame, now: str) -> None:
    rows = []
    seen: set[str] = set()
    for _, row in df.iterrows():
        call_date = str(row.get("CALL_DATE", "") or "")
        call_time = str(row.get("CALL_TIME", "") or "")
        direction = str(row.get("DIRECTION", "") or "")
        duration = int(row.get("Duration_Seconds", 0) or 0)
        tel = str(row["TEL"])
        row_hash = _row_hash([tel, duration, call_date, call_time, direction])
        if row_hash in seen:
            continue
        seen.add(row_hash)
        rows.append(
            {
                "tel": tel,
                "duration_seconds": duration,
                "call_date": call_date or None,
                "call_time": call_time or None,
                "direction": direction or None,
                "row_hash": row_hash,
                "created_at": now,
            }
        )

    if not rows:
        return

    dialect = conn.dialect.name
    if dialect == "postgresql":
        sql = """
            INSERT INTO onoff_calls
            (tel, duration_seconds, call_date, call_time, direction, row_hash, created_at)
            VALUES (:tel, :duration_seconds, :call_date, :call_time, :direction, :row_hash, :created_at)
            ON CONFLICT (row_hash) DO NOTHING
        """
    elif _is_mysql_dialect(dialect):
        sql = """
            INSERT IGNORE INTO onoff_calls
            (tel, duration_seconds, call_date, call_time, direction, row_hash, created_at)
            VALUES (:tel, :duration_seconds, :call_date, :call_time, :direction, :row_hash, :created_at)
        """
    else:
        sql = """
            INSERT OR IGNORE INTO onoff_calls
            (tel, duration_seconds, call_date, call_time, direction, row_hash, created_at)
            VALUES (:tel, :duration_seconds, :call_date, :call_time, :direction, :row_hash, :created_at)
        """
    conn.execute(text(sql), rows)


def load_onoff_calls(engine: Engine | None = None) -> pd.DataFrame:
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT tel, duration_seconds, call_date, call_time, direction
                FROM onoff_calls
                """
            )
        )
        rows = result.fetchall()
    if not rows:
        return pd.DataFrame(columns=["TEL", "Duration_Seconds"])
    from engine.processor import _clean_tel_db

    df = pd.DataFrame(
        [
            {
                "TEL": row[0],
                "Duration_Seconds": row[1],
                "CALL_DATE": row[2],
                "CALL_TIME": row[3],
                "DIRECTION": row[4],
            }
            for row in rows
        ]
    )
    df["TEL"] = _clean_tel_db(df["TEL"])
    return df


def replace_onoff_totals(df: pd.DataFrame, engine: Engine | None = None) -> None:
    """Replace per-TEL Onoff duration totals (from merged exports / totals sheets)."""
    from engine.processor import _clean_tel_db, _format_duration

    engine = engine or get_engine()
    init_schema(engine)
    now = datetime.now().isoformat(timespec="seconds")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM onoff_totals"))
        if df.empty:
            return

        out = df.copy()
        if "TEL" not in out.columns:
            return
        out["TEL"] = _clean_tel_db(out["TEL"])
        if "Total_Duration_Seconds" not in out.columns:
            return
        out["Total_Duration_Seconds"] = (
            pd.to_numeric(out["Total_Duration_Seconds"], errors="coerce").fillna(0).astype(int)
        )
        if "Total_Duration" not in out.columns:
            out["Total_Duration"] = out["Total_Duration_Seconds"].map(_format_duration)
        if "Call_Count" not in out.columns:
            out["Call_Count"] = 0
        out = out.drop_duplicates(subset=["TEL"], keep="last")

        rows = [
            {
                "tel": str(row["TEL"]),
                "total_duration_seconds": int(row["Total_Duration_Seconds"]),
                "total_duration": str(row["Total_Duration"]),
                "call_count": int(row.get("Call_Count", 0) or 0),
                "updated_at": now,
            }
            for _, row in out.iterrows()
        ]
        if rows:
            dialect = engine.dialect.name
            if dialect == "postgresql":
                sql = """
                    INSERT INTO onoff_totals
                    (tel, total_duration_seconds, total_duration, call_count, updated_at)
                    VALUES (:tel, :total_duration_seconds, :total_duration, :call_count, :updated_at)
                    ON CONFLICT (tel) DO UPDATE SET
                        total_duration_seconds = EXCLUDED.total_duration_seconds,
                        total_duration = EXCLUDED.total_duration,
                        call_count = EXCLUDED.call_count,
                        updated_at = EXCLUDED.updated_at
                """
            elif _is_mysql_dialect(dialect):
                sql = """
                    INSERT INTO onoff_totals
                    (tel, total_duration_seconds, total_duration, call_count, updated_at)
                    VALUES (:tel, :total_duration_seconds, :total_duration, :call_count, :updated_at)
                    ON DUPLICATE KEY UPDATE
                        total_duration_seconds = VALUES(total_duration_seconds),
                        total_duration = VALUES(total_duration),
                        call_count = VALUES(call_count),
                        updated_at = VALUES(updated_at)
                """
            else:
                sql = """
                    INSERT OR REPLACE INTO onoff_totals
                    (tel, total_duration_seconds, total_duration, call_count, updated_at)
                    VALUES (:tel, :total_duration_seconds, :total_duration, :call_count, :updated_at)
                """
            conn.execute(text(sql), rows)


def load_onoff_totals(engine: Engine | None = None) -> pd.DataFrame:
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT tel, total_duration_seconds, total_duration, call_count
                FROM onoff_totals
                """
            )
        )
        rows = result.fetchall()
    if not rows:
        return pd.DataFrame(columns=["TEL", "Total_Duration_Seconds", "Total_Duration", "Call_Count"])
    from engine.processor import _clean_tel_db

    return pd.DataFrame(
        [
            {
                "TEL": row[0],
                "Total_Duration_Seconds": row[1],
                "Total_Duration": row[2],
                "Call_Count": row[3],
            }
            for row in rows
        ]
    ).assign(TEL=lambda d: _clean_tel_db(d["TEL"]))


def count_onoff_totals(engine: Engine | None = None) -> int:
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM onoff_totals")).scalar_one())


def count_onoff_rows(engine: Engine | None = None) -> int:
    engine = engine or get_engine()
    with engine.begin() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM onoff_calls")).scalar_one())


def count_client_rows(engine: Engine | None = None) -> int:
    engine = engine or get_engine()
    with engine.begin() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM client_db")).scalar_one())


def count_client_tels(engine: Engine | None = None) -> int:
    return count_client_rows(engine)


def migrate_pickle_store_if_needed(engine: Engine | None = None) -> bool:
    """One-time migration from legacy .pkl files to SQL storage."""
    engine = engine or get_engine()
    if store_has_data(engine):
        return False

    db_pkl = STORE_DIR / "client_db.pkl"
    hist_pkl = STORE_DIR / "history.pkl"
    onoff_pkl = STORE_DIR / "onoff_calls.pkl"
    if not db_pkl.exists() or not hist_pkl.exists():
        return False

    replace_client_db(pd.read_pickle(db_pkl), engine)
    replace_history(pd.read_pickle(hist_pkl), engine)
    if onoff_pkl.exists():
        replace_onoff_calls(pd.read_pickle(onoff_pkl), engine)

    meta_path = STORE_DIR / "meta.json"
    if meta_path.exists():
        save_meta(json.loads(meta_path.read_text(encoding="utf-8")), engine)
    return True


def replace_vente_baseline(df: pd.DataFrame, engine: Engine | None = None) -> int:
    """Replace the active vente baseline snapshot (TEL → statut avant ventes)."""
    engine = engine or get_engine()
    init_schema(engine)
    now = datetime.now().isoformat(timespec="seconds")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM vente_baseline"))
        if df.empty:
            return 0
        rows = []
        for _, row in df.iterrows():
            rows.append(
                {
                    "tel": str(row["TEL"]),
                    "statut": str(row.get("Statut", row.get("statut", ""))),
                    "couleur": str(row.get("Couleur", row.get("couleur", "")) or ""),
                    "updated_at": now,
                }
            )
        conn.execute(
            text(
                "INSERT INTO vente_baseline (tel, statut, couleur, updated_at) "
                "VALUES (:tel, :statut, :couleur, :updated_at)"
            ),
            rows,
        )
    return len(df)


def load_vente_baseline(engine: Engine | None = None) -> pd.DataFrame:
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        result = conn.execute(
            text("SELECT tel, statut, couleur, updated_at FROM vente_baseline")
        )
        rows = result.mappings().all()
    if not rows:
        return pd.DataFrame(columns=["TEL", "Statut", "Couleur", "updated_at"])
    df = pd.DataFrame(rows)
    return df.rename(
        columns={"tel": "TEL", "statut": "Statut", "couleur": "Couleur"}
    )


def count_vente_baseline(engine: Engine | None = None) -> int:
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        return int(conn.execute(text("SELECT COUNT(*) FROM vente_baseline")).scalar_one())


def append_vente_results(
    df: pd.DataFrame,
    *,
    batch_id: str,
    analyzed_at: str | None = None,
    engine: Engine | None = None,
) -> int:
    """Persist analyzed vente rows for daily history."""
    engine = engine or get_engine()
    init_schema(engine)
    if df.empty:
        return 0
    ts = analyzed_at or datetime.now().isoformat(timespec="seconds")
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "tel": str(row.get("TEL", "")),
                "jour_vente": str(row.get("Jour_Vente", "")),
                "statut_origine": str(row.get("Statut_origine", "")),
                "couleur_origine": str(row.get("Couleur_origine", "")),
                "source_baseline": str(row.get("Source_baseline", "")),
                "matched": 1 if bool(row.get("Matched", False)) else 0,
                "nom": str(row.get("NOM", "") or ""),
                "prenom": str(row.get("PRENOM", "") or ""),
                "analyzed_at": ts,
                "batch_id": batch_id,
            }
        )
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM vente_results WHERE batch_id = :batch_id"),
            {"batch_id": batch_id},
        )
        conn.execute(
            text(
                """
                INSERT INTO vente_results (
                    tel, jour_vente, statut_origine, couleur_origine, source_baseline,
                    matched, nom, prenom, analyzed_at, batch_id
                ) VALUES (
                    :tel, :jour_vente, :statut_origine, :couleur_origine, :source_baseline,
                    :matched, :nom, :prenom, :analyzed_at, :batch_id
                )
                """
            ),
            rows,
        )
    return len(rows)


def load_vente_results(engine: Engine | None = None) -> pd.DataFrame:
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
                SELECT tel, jour_vente, statut_origine, couleur_origine, source_baseline,
                       matched, nom, prenom, analyzed_at, batch_id
                FROM vente_results
                ORDER BY analyzed_at DESC, jour_vente DESC
                """
            )
        )
        rows = result.mappings().all()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.rename(
        columns={
            "tel": "TEL",
            "jour_vente": "Jour_Vente",
            "statut_origine": "Statut_origine",
            "couleur_origine": "Couleur_origine",
            "source_baseline": "Source_baseline",
            "matched": "Matched",
            "nom": "NOM",
            "prenom": "PRENOM",
            "analyzed_at": "Analyzed_at",
            "batch_id": "Batch_id",
        }
    )


def ensure_default_user(engine: Engine | None = None) -> None:
    from engine.auth import default_credentials, hash_password

    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM app_users")).scalar() or 0
        if count > 0:
            return
        username, password = default_credentials()
        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            text(
                """
                INSERT INTO app_users (username, password_hash, updated_at)
                VALUES (:username, :password_hash, :updated_at)
                """
            ),
            {
                "username": username,
                "password_hash": hash_password(password),
                "updated_at": now,
            },
        )


def verify_app_login(username: str, password: str, engine: Engine | None = None) -> bool:
    from engine.auth import verify_password

    engine = engine or get_engine()
    ensure_default_user(engine)
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT password_hash FROM app_users WHERE username = :username"),
            {"username": username.strip()},
        ).fetchone()
    if not row:
        return False
    return verify_password(password, row[0])


def update_app_password(
    username: str,
    current_password: str,
    new_password: str,
    engine: Engine | None = None,
) -> tuple[bool, str]:
    from engine.auth import hash_password, verify_password

    user = username.strip()
    if len(new_password) < 6:
        return False, "Le nouveau mot de passe doit contenir au moins 6 caractères."

    engine = engine or get_engine()
    ensure_default_user(engine)
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT password_hash FROM app_users WHERE username = :username"),
            {"username": user},
        ).fetchone()
        if not row:
            return False, "Utilisateur introuvable."
        if not verify_password(current_password, row[0]):
            return False, "Mot de passe actuel incorrect."

        now = datetime.now().isoformat(timespec="seconds")
        conn.execute(
            text(
                """
                UPDATE app_users
                SET password_hash = :password_hash, updated_at = :updated_at
                WHERE username = :username
                """
            ),
            {
                "username": user,
                "password_hash": hash_password(new_password),
                "updated_at": now,
            },
        )
    return True, "Mot de passe mis à jour."


def force_set_app_password(
    username: str,
    new_password: str,
    engine: Engine | None = None,
) -> None:
    """Set password without current password (deploy recovery). Creates user if missing."""
    from engine.auth import hash_password

    user = username.strip()
    if len(new_password) < 6:
        raise ValueError("Le mot de passe doit contenir au moins 6 caractères.")

    engine = engine or get_engine()
    init_schema(engine)
    now = datetime.now().isoformat(timespec="seconds")
    password_hash = hash_password(new_password)

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT username FROM app_users WHERE username = :username"),
            {"username": user},
        ).fetchone()
        if row:
            conn.execute(
                text(
                    """
                    UPDATE app_users
                    SET password_hash = :password_hash, updated_at = :updated_at
                    WHERE username = :username
                    """
                ),
                {"username": user, "password_hash": password_hash, "updated_at": now},
            )
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO app_users (username, password_hash, updated_at)
                    VALUES (:username, :password_hash, :updated_at)
                    """
                ),
                {"username": user, "password_hash": password_hash, "updated_at": now},
            )


def list_app_users(engine: Engine | None = None) -> list[str]:
    engine = engine or get_engine()
    init_schema(engine)
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT username FROM app_users ORDER BY username")).fetchall()
    return [str(row[0]) for row in rows]
