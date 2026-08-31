#!/usr/bin/env bash
# Lance l'app en mode LOCAL — SQLite (data/store/recyclage.db).
# Le cloud utilise TiDB (MYSQL_* / DATABASE_URL) dans les secrets Streamlit.
set -euo pipefail
cd "$(dirname "$0")"
unset DATABASE_URL MYSQL_HOST MYSQL_PORT MYSQL_USER MYSQL_PASSWORD MYSQL_DATABASE MYSQL_SSL
export FORCE_SQLITE=1
exec streamlit run ui/streamlit_app.py "$@"
