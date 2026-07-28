#!/usr/bin/env bash
# Lance l'app en mode LOCAL — SQLite (data/store/recyclage.db)
set -euo pipefail
cd "$(dirname "$0")"
unset DATABASE_URL
export FORCE_SQLITE=1
exec streamlit run ui/streamlit_app.py "$@"
