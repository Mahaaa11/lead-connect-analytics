#!/usr/bin/env python3
"""Migrate local SQLite store to TiDB Cloud (MySQL protocol)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text

from engine import storage
from engine.config_env import bootstrap_env, require_mysql_database_url

DEFAULT_SQLITE = storage.STORE_DIR / "recyclage.db"

TABLES = [
    "app_meta",
    "app_users",
    "client_db",
    "history_rows",
    "onoff_calls",
    "onoff_totals",
    "vente_baseline",
    "vente_results",
]

DROP_ID_COLUMNS = {"history_rows", "onoff_calls", "vente_results"}


def _normalize_mysql_url(url: str) -> str:
    url = url.strip()
    if url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)
    return url


def _count_rows(engine, table: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())


def _reset_target(engine) -> None:
    """Drop + recreate instead of DELETE (TiDB Serverless kills large DELETEs on memory)."""
    with engine.connect() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        conn.commit()
        for table in reversed(TABLES):
            conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
            conn.commit()
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        conn.commit()
    storage._schema_initialized = False  # noqa: SLF001
    storage.init_schema(engine)


def _copy_table(src, dst, table: str, chunk_size: int) -> int:
    import pandas as pd

    total = _count_rows(src, table)
    if total == 0:
        print(f"  {table:16} — vide, ignoré")
        return 0
    copied = 0
    for chunk in pd.read_sql(f"SELECT * FROM {table}", src, chunksize=chunk_size):
        if table in DROP_ID_COLUMNS and "id" in chunk.columns:
            chunk = chunk.drop(columns=["id"])
        chunk.to_sql(
            table,
            dst,
            if_exists="append",
            index=False,
            method="multi",
        )
        copied += len(chunk)
        print(f"  {table:16} {copied:>10,} / {total:,}", flush=True)
    return copied


def _mysql_connect_args(url: str) -> dict:
    args: dict = {"connect_timeout": 30}
    if os.getenv("MYSQL_SSL", "").lower() in ("1", "true", "yes") or "tidbcloud.com" in url:
        args["ssl"] = {"ssl": True}
    return args


def migrate(
    *,
    sqlite_path: Path,
    database_url: str,
    dry_run: bool = False,
    chunk_size: int = 200,
) -> None:
    if not sqlite_path.is_file():
        raise FileNotFoundError(f"SQLite introuvable : {sqlite_path}")

    database_url = _normalize_mysql_url(database_url)
    if not dry_run and not database_url.startswith("mysql+pymysql://"):
        raise ValueError("DATABASE_URL doit être mysql+pymysql://... (TiDB).")

    src = create_engine(f"sqlite:///{sqlite_path}")

    print(f"Source : {sqlite_path} ({sqlite_path.stat().st_size / 1024 / 1024:.1f} MB)")

    if dry_run:
        print("\n[DRY RUN] Lignes SQLite :")
        for table in TABLES:
            print(f"  {table:16} {_count_rows(src, table):>10,}")
        return

    dst = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=_mysql_connect_args(database_url),
    )
    print("Cible  : TiDB / MySQL")

    # Reset storage schema flag so init_schema runs on this engine
    print("\nReset schéma TiDB (DROP + CREATE, pas de DELETE)…")
    _reset_target(dst)

    print("\nMigration en cours…")
    for table in TABLES:
        _copy_table(src, dst, table, chunk_size)

    print("\nVérification :")
    ok = True
    for table in TABLES:
        src_n = _count_rows(src, table)
        dst_n = _count_rows(dst, table)
        status = "OK" if src_n == dst_n else "DIFF"
        if status != "OK":
            ok = False
        print(f"  {table:16} sqlite={src_n:>10,}  tidb={dst_n:>10,}  [{status}]")

    if not ok:
        raise SystemExit("Migration terminée avec des écarts de comptage.")
    print("\nMigration réussie.")


def main() -> None:
    bootstrap_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=DEFAULT_SQLITE,
        help=f"Chemin SQLite source (défaut: {DEFAULT_SQLITE})",
    )
    parser.add_argument(
        "--database-url",
        default="",
        help="URL mysql+pymysql://... (sinon DATABASE_URL / MYSQL_*)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Volumes seulement")
    parser.add_argument("--chunk-size", type=int, default=200)
    args = parser.parse_args()

    url = args.database_url.strip()
    if not url and not args.dry_run:
        url = require_mysql_database_url()
    elif not url:
        url = os.environ.get("DATABASE_URL", "").strip()

    migrate(
        sqlite_path=args.sqlite_path,
        database_url=url,
        dry_run=args.dry_run,
        chunk_size=args.chunk_size,
    )


if __name__ == "__main__":
    main()
