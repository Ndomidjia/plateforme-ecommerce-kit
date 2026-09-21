# Plateforme intelligente d'analyse comportementale et de recommandation marketing pour l'e-commerce

Projet de soutenance M2 — **Plan A** : 3 sources de données indépendantes, 3 modules d'analyse,
1 plateforme unifiée (API + dashboard).

## Architecture des données

| Schéma PostgreSQL | Source | Rôle |
|---|---|---|
| `olist` | Kaggle olistbr/brazilian-ecommerce (9 CSV) | Socle transactionnel : RFM, market basket, sentiment |
| `retailrocket` | Kaggle retailrocket/ecommerce-dataset | Comportemental : funnel, reco collaborative item-item |
| `churn` | ecommerce_customer_churn_dataset.csv | Scoring d'attrition + recommandation d'actions marketing |
| `analytics` | Calculé par les scripts de `analytics/` | Zone de convergence : résultats ML consommés par l'API |
| `app` | Interne | Comptes API (JWT/RBAC) + journal d'audit RGPD |

Les 3 populations de clients (Olist, Retailrocket, churn) sont **indépendantes** : aucune jointure
inter-datasets. Voir [docs/architecture.md](docs/architecture.md) pour le détail des décisions et
[docs/limitations-methodologiques.md](docs/limitations-methodologiques.md) pour les limites
identifiées sur chaque module (importantes à connaître avant la soutenance).

## Structure du repo

```
├── docker-compose.yml   # PostgreSQL 16 conteneurisé
├── .env.example         # variables d'environnement (jamais commiter .env)
├── sql/                 # DDL : schémas, tables, contrôles (01 à 10 + 99_controles)
├── etl/                 # Extract-Transform-Load des 3 sources brutes -> schémas olist/retailrocket/churn
├── analytics/           # Modules ML : RFM, market basket, funnel, reco collaborative,
│                         # scoring churn, sentiment (deep learning), vue client 360° -> écrivent dans analytics.*
├── api/                 # API FastAPI : auth JWT/RBAC, endpoints analytics, RGPD, administration
├── dashboard/            # Dashboard React (Vite) : consomme l'API, vues par rôle admin/analyst
├── data/raw/             # CSV bruts (ignorés par git)
├── notebooks/            # EDA et prototypage
└── docs/                 # Architecture, limitations, RGPD, journal de bord
```

## Démarrage

### 1. Base de données

```bash
copy .env.example .env        # puis éditer le mot de passe
docker compose up -d          # démarre PostgreSQL 16 et crée schémas/tables (sql/01 à 05)
```

Si la base existait déjà avant l'ajout d'un nouveau fichier SQL (06 à 09 — schéma `app`, table
sentiment, importance des variables, vue client 360°), l'appliquer manuellement :
```bash
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/06_app_tables.sql
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/07_sentiment_table.sql
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/08_churn_feature_importance.sql
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/09_customer_360.sql
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/10_model_metrics_history.sql
```

### 2. Environnement Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Données + ETL

Déposer les CSV Kaggle dans `data/raw/olist`, `data/raw/retailrocket`, `data/raw/churn`, puis :
```bash
cd etl && python run_all.py
```
Contrôles qualité : exécuter `sql/99_controles.sql`.

### 4. Modules d'analyse (dans cet ordre — chaque script est indépendant et ré-exécutable)

```bash
cd analytics
python rfm_olist.py              # segmentation RFM Olist
python market_basket_olist.py    # règles d'association (market basket)
python funnel_retailrocket.py    # funnel de conversion
python recommend_retailrocket.py # reco collaborative item-item
python churn_model.py            # scoring churn (Random Forest, ~5 min)
python sentiment_olist.py        # analyse de sentiment (deep learning, PyTorch, ~3 min)
python customer_360_olist.py     # vue client 360° : RFM + proxy de risque + sentiment + reco (~15 min)
```
`customer_360_olist.py` doit être lancé **après** `rfm_olist.py`, `sentiment_olist.py` et
`market_basket_olist.py` (il les réutilise). Voir
[docs/architecture.md](docs/architecture.md#ce-qui-a-été-fait-à-la-place--fusion-au-niveau-des-résultats-sur-olist-analyticscustomer_360)
pour le contexte de ce module et [docs/limitations-methodologiques.md](docs/limitations-methodologiques.md)
pour son évaluation honnête (résultat négatif assumé : AUC = 0,57).
Chaque script vide et recalcule sa table `analytics.*` — relançable à tout moment. Peuvent aussi
être relancés depuis le dashboard (page Administration, admin uniquement).

### 5. API

```bash
cd api
python create_admin.py <username> <password>   # premier compte admin (une seule fois)
uvicorn main:app --reload --port 8000
```
Documentation interactive : http://127.0.0.1:8000/docs

### 6. Dashboard

```bash
cd dashboard
npm install
npm run dev
```
http://localhost:5173 — se connecter avec le compte admin créé à l'étape 5.

## Rôles

- **`admin`** : accès complet — analytics, RGPD (export/anonymisation), gestion des comptes API,
  recalcul à la demande des modules ML.
- **`analyst`** : lecture des analytics (RFM, churn, funnel, reco, règles, sentiment) + calculateur
  de rétention. Pas d'accès RGPD ni administration.

## Documentation

- [docs/architecture.md](docs/architecture.md) — décisions d'architecture et pourquoi
- [docs/limitations-methodologiques.md](docs/limitations-methodologiques.md) — limites connues de
  chaque module (à citer en soutenance plutôt qu'à laisser découvrir)
- [docs/rgpd.md](docs/rgpd.md) — approche RGPD (droit d'accès, droit à l'oubli, audit)
- [docs/journal-de-bord.md](docs/journal-de-bord.md) — chronologie des décisions, incidents
  rencontrés et corrigés pendant le développement
