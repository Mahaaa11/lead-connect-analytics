#!/usr/bin/env python3
"""Diagnose why analytics pages may be empty (PostgreSQL / SQLite)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import database, storage


def main() -> None:
    print(f"Backend : {storage.backend_label()}")
    print(f"URL     : {database._database_url_hint()}")
    print()

    counts = {
        "client_db": storage.count_client_rows(),
        "history_rows": storage.count_history_rows(),
        "onoff_calls": storage.count_onoff_rows(),
        "vente_baseline": _count("vente_baseline"),
        "app_users": _count("app_users"),
    }
    print("Lignes par table :")
    for table, n in counts.items():
        print(f"  {table:16} {n:>10,}")

    ready = database.store_exists()
    print()
    print(f"store_exists() : {'OUI' if ready else 'NON'}")
    print("  → requis : client_db > 0 ET history_rows > 0")

    users = database.list_app_users()
    print(f"Utilisateurs login : {', '.join(users) or '—'}")

    if not ready:
        print()
        print("CAUSE PROBABLE DES PAGES VIDES :")
        if counts["app_users"] > 0 and counts["client_db"] == 0:
            print("  Login OK mais client_db vide — migration incomplète ou mauvaise DATABASE_URL.")
        elif counts["app_users"] > 0 and counts["history_rows"] == 0:
            print("  Login OK mais history_rows vide — relancez migrate_sqlite_to_postgres.py.")
        else:
            print("  Base métier vide. Migrez SQLite ou importez via « Base de données ».")
        print()
        print("Fix :")
        print('  export DATABASE_URL="postgresql://..."')
        print("  python3 scripts/migrate_sqlite_to_postgres.py")
        return

    print()
    print("Test chargement + analytics (peut prendre ~30 s)…")
    t0 = time.time()
    db = database.load_db()
    t1 = time.time()
    hist = database.load_history()
    t2 = time.time()
    print(f"  load_db()      {len(db):>7,} lignes en {t1 - t0:.1f}s")
    print(f"  load_history() {len(hist):>7,} lignes en {t2 - t1:.1f}s")

    import engine.data_client_dashboard as dc
    import engine.ventes_analytics as va

    year = int(os.environ.get("CHECK_YEAR", "2026"))
    m = dc.compute_data_client_dashboard(db, hist, year=year)
    v = va.compute_ventes_analytics(db, hist, year=year)
    print(f"  Data Client    total_fiches={m['total_fiches']:,}")
    print(f"  Ventes {year}   total_ventes={v['total_ventes']:,}")
    print()
    print("OK — les pages devraient afficher des données si « base persistante » est cochée.")


def _count(table: str) -> int:
    from sqlalchemy import text

    engine = storage.get_engine()
    with engine.begin() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one())


if __name__ == "__main__":
    main()
