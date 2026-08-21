# Recyclage Exporter — Lead & Connect Analytics

Plateforme Streamlit d’analyse et d’export pour le centre d’appels **Lead & Connect** (Fès) : data client, ventes, performance agents, prévisionnel, export recyclage, et suivi quotidien (cohorte + rapports PDF).

## Transférer sur un autre laptop

1. Copier `Recyclage_Exporter.zip` (clé USB, AirDrop, Drive, etc.)
2. Décompresser → dossier `Recyclage_Exporter`
3. Installer Python 3.10+ puis :

```bash
cd Recyclage_Exporter
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optionnel
./run.sh                           # Windows: streamlit run ui/streamlit_app.py
```

4. Ouvrir l’URL Streamlit affichée (souvent `http://localhost:8501`)
5. Login : valeurs de `.env.example` (`APP_DEFAULT_USER` / `APP_DEFAULT_PASSWORD`) sauf si tu as changé le mot de passe

## Version déployée (Streamlit Cloud)

Repo GitHub : [ogenies/LC-analytics](https://github.com/ogenies/LC-analytics)

L’app cloud utilise **TiDB Cloud** (MySQL protocol via `MYSQL_*` ou `DATABASE_URL`), pas le fichier SQLite local.

### Accéder à l’app

1. Ouvre ton app sur [share.streamlit.io](https://share.streamlit.io) (ou l’URL `*.streamlit.app` déjà déployée)
2. Login avec le user/password configurés dans les **Secrets** Streamlit

### Secrets Streamlit Cloud (App settings → Secrets)

```toml
MYSQL_HOST = "gateway01.eu-central-1.prod.aws.tidbcloud.com"
MYSQL_PORT = 4000
MYSQL_USER = "xxxxxxxx.root"
MYSQL_PASSWORD = "ton_password_tidb"
MYSQL_DATABASE = "test"
MYSQL_SSL = "true"

APP_DEFAULT_USER = "admin"
APP_DEFAULT_PASSWORD = "ton_mot_de_passe"
```

# Alternative URL unique :
# DATABASE_URL = "mysql+pymysql://USER:PASSWORD@HOST:4000/test"

# Uniquement si login cassé (remet le password au démarrage, puis retire) :
# APP_RESET_PASSWORD_ON_START = "true"
```

### Mettre à jour le déploiement depuis un autre laptop

```bash
git clone https://github.com/Mahaaa11/lead-connect-analytics.git
cd lead-connect-analytics
# …faire tes changements…
git add -A
git commit -m "…"
git push origin main
```

Streamlit Cloud redéploie automatiquement depuis `main` (si le repo est lié à l’app).

### Première fois / migrer la data locale → Postgres

Sur une machine qui a le `recyclage.db` local :

```bash
export DATABASE_URL="postgresql://...?sslmode=require"
python3 scripts/migrate_sqlite_to_postgres.py
python3 scripts/check_store_health.py
```

### Déploiement Docker (alternative)

```bash
docker build -t lead-connect-analytics .
docker run --rm -p 8501:8501 \
  -e DATABASE_URL="postgresql://...?sslmode=require" \
  -e APP_DEFAULT_USER=admin \
  -e APP_DEFAULT_PASSWORD='…' \
  lead-connect-analytics
```

Puis ouvrir `http://localhost:8501`.

### Local vs déployé

| | Local (`./run.sh`) | Déployé (Cloud / Docker) |
|--|--------------------|---------------------------|
| Base | SQLite `data/store/recyclage.db` | PostgreSQL (`DATABASE_URL`) |
| Config | `.env` | Secrets Streamlit / env Docker |
| Code | dossier / ZIP | GitHub `main` → redeploy auto |

## Modules (navigation)

| Section | Rôle |
|---------|------|
| **Vue d’ensemble** | Hub analytics |
| **Data Client** | Parcours, couleurs, statuts avant vente |
| **Ventes** | Analyse des ventes + **Suivi quotidien** |
| **Performance** | Dashboard agents / production |
| **Prévisionnel** | Projection J+1…J+7, quotas, export coloré |
| **Export recyclage** | Sélection statut/couleur, durées Onoff, masque Excel |
| **Base de données** | Init / MAJ persistée (DB, histo, Onoff) |

## Suivi quotidien (Ventes)

Workflow typique chaque jour :

1. Baseline du matin (snapshot base ou export recyclage / Book1)
2. Upload **export_histo** + **export_data_client** + **b2b/Onoff** du jour
3. **Lancer le suivi du jour**

Livrables :

- Évolution de cohorte (ex. Injoignables → statut devenu)
- Ventes → statut d’origine sur le baseline
- **2 PDF agents** :
  1. Origines des conversions (statut précédent → vente)
  2. Mix des statuts + Pas de collab / Refus + durées Onoff
- Export Excel du suivi

## Structure du dépôt

```
Recyclage_Exporter/
├── ui/
│   ├── streamlit_app.py      # App principale
│   ├── app_shell.py          # Navigation & shell
│   ├── login_page.py
│   ├── brand_theme.py
│   └── *_board.py            # Vues (ventes, data client, agents…)
├── engine/
│   ├── processor.py          # Lecture Excel, Onoff, exports
│   ├── database.py / storage.py
│   ├── daily_tracking.py     # Suivi quotidien cohorte / ventes
│   ├── daily_agent_reports.py# PDF agents du jour
│   ├── ventes_analytics.py
│   ├── agent_analytics.py
│   ├── forecast.py
│   └── status_labels.py
├── scripts/                  # Utilitaires (migration, exports one-shot)
├── data/                     # Store local & exports
├── requirements.txt
├── run.sh
├── Dockerfile
└── .env.example
```

## Données attendues (uploads)

| Fichier | Usage |
|---------|--------|
| `export_data_client_…-par-jour.xls` | Statuts / ventes du jour |
| `export_histo_data_client_…-par-jour.xls` | Historique d’appels du jour |
| `b2b-statistics-calls-users-report-….xlsx` | Durées Onoff (dernier appel / totaux) |
| Export recyclage / Book1 | Baseline matin |

Les commentaires libres du dialer **ne sont pas conservés** dans le pipeline de traitement : seuls statut, couleur et colonnes structurées de l’export comptent.

## Auth

Identifiants par défaut (voir `.env.example`) :

- `APP_DEFAULT_USER`
- `APP_DEFAULT_PASSWORD`

En cloud, configurer les secrets Streamlit (et `DATABASE_URL` si Postgres).

## Scripts utiles

```bash
# Santé du store
python3 scripts/check_store_health.py

# Migration SQLite → PostgreSQL
export DATABASE_URL="postgresql://..."
python3 scripts/migrate_sqlite_to_postgres.py
```

## Version

La version affichée dans l’app est définie dans `ui/streamlit_app.py` (`APP_VERSION`).
