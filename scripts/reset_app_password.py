#!/usr/bin/env python3
"""Check auth users and reset login password on PostgreSQL or SQLite."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import database, storage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Lister les utilisateurs et tester admin")
    parser.add_argument("--reset", action="store_true", help="Forcer un nouveau mot de passe")
    parser.add_argument("--user", default=os.environ.get("APP_DEFAULT_USER", "admin"))
    parser.add_argument("--password", default=os.environ.get("APP_DEFAULT_PASSWORD", "leadconnect"))
    args = parser.parse_args()

    if not args.check and not args.reset:
        parser.error("Indiquez --check ou --reset")

    backend = storage.backend_label()
    print(f"Backend : {backend}")
    print(f"URL     : {database._database_url_hint()}")

    users = database.list_app_users()
    print(f"Utilisateurs ({len(users)}): {', '.join(users) or '—'}")

    if args.check:
        ok = database.authenticate(args.user, args.password)
        print(f"Test login {args.user!r} / {args.password!r} : {'OK' if ok else 'ECHEC'}")
        if not ok:
            print("→ Lancez : python3 scripts/reset_app_password.py --reset --password VOTRE_MDP")

    if args.reset:
        database.force_set_app_password(args.user, args.password)
        ok = database.authenticate(args.user, args.password)
        print(f"Mot de passe mis à jour pour {args.user!r}. Test : {'OK' if ok else 'ECHEC'}")


if __name__ == "__main__":
    main()
