#!/usr/bin/env bash
# Lance l'app en mode LOCAL — SQLite (data/store/recyclage.db).
# Le cloud utilise TiDB (MYSQL_* / DATABASE_URL) dans les secrets Streamlit.
set -euo pipefail
cd "$(dirname "$0")"
unset DATABASE_URL
exec streamlit run ui/streamlit_app.py "$@"
