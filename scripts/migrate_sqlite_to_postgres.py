#!/usr/bin/env python3
"""Migrate local SQLite store to PostgreSQL (Neon, Supabase, etc.)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text

from engine import storage

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


def _normalize_pg_url(url: str) -> str:
    url = url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


def _count_rows(engine, table: str) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())


def _truncate_target(engine) -> None:
    with engine.begin() as conn:
        for table in reversed(TABLES):
            conn.execute(text(f"DELETE FROM {table}"))


def _reset_identity_sequences(engine) -> None:
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        for table in DROP_ID_COLUMNS:
            conn.execute(
                text(
                    f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {table}), 1),
                        (SELECT MAX(id) IS NOT NULL FROM {table})
                    )
                    """
                )
            )


def migrate(
    *,
    sqlite_path: Path,
    database_url: str,
    dry_run: bool = False,
    chunk_size: int = 2000,
) -> None:
    import pandas as pd

    if not sqlite_path.is_file():
        raise FileNotFoundError(f"SQLite introuvable : {sqlite_path}")

    database_url = _normalize_pg_url(database_url)
    if not dry_run and not database_url.startswith("postgresql"):
        raise ValueError("DATABASE_URL doit être une URL PostgreSQL (postgresql://...).")

    src = create_engine(f"sqlite:///{sqlite_path}")

    print(f"Source : {sqlite_path} ({sqlite_path.stat().st_size / 1024 / 1024:.1f} MB)")

    if dry_run:
        print("\n[DRY RUN] Lignes SQLite :")
        for table in TABLES:
            print(f"  {table:16} {_count_rows(src, table):>10,}")
        return

    dst = create_engine(database_url, pool_pre_ping=True)
    print(f"Cible  : PostgreSQL")

    print("\nInitialisation schéma PostgreSQL…")
    storage.init_schema(dst)
    print("Vidage des tables PostgreSQL…")
    _truncate_target(dst)

    print("\nMigration en cours…")
    for table in TABLES:
        df = pd.read_sql(f"SELECT * FROM {table}", src)
        if table in DROP_ID_COLUMNS and "id" in df.columns:
            df = df.drop(columns=["id"])
        if df.empty:
            print(f"  {table:16} — vide, ignoré")
            continue
        df.to_sql(table, dst, if_exists="append", index=False, chunksize=chunk_size, method="multi")
        print(f"  {table:16} {len(df):>10,} lignes")

    _reset_identity_sequences(dst)

    print("\nVérification :")
    ok = True
    for table in TABLES:
        src_n = _count_rows(src, table)
        dst_n = _count_rows(dst, table)
        status = "OK" if src_n == dst_n else "DIFF"
        if status != "OK":
            ok = False
        print(f"  {table:16} sqlite={src_n:>10,}  postgres={dst_n:>10,}  [{status}]")

    if not ok:
        raise SystemExit("Migration terminée avec des écarts de comptage.")
    print("\nMigration réussie.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=DEFAULT_SQLITE,
        help=f"Chemin SQLite source (défaut: {DEFAULT_SQLITE})",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", "").strip(),
        help="URL PostgreSQL (ou variable d'environnement DATABASE_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Afficher les volumes sans migrer",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=2000,
        help="Taille des lots d'insertion",
    )
    args = parser.parse_args()

    if not args.database_url and not args.dry_run:
        parser.error("DATABASE_URL manquant. Exportez la variable ou passez --database-url.")

    migrate(
        sqlite_path=args.sqlite_path,
        database_url=args.database_url,
        dry_run=args.dry_run,
        chunk_size=args.chunk_size,
    )


if __name__ == "__main__":
    main()
