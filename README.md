# Plateforme intelligente d'analyse comportementale et de recommandation marketing pour l'e-commerce

Mon projet de soutenance M2 — **Plan A** : 3 sources de données indépendantes, 3 modules d'analyse,
1 plateforme unifiée (API + dashboard).

## Architecture des données

| Schéma PostgreSQL | Source | Rôle |
|---|---|---|
| `olist` | Kaggle olistbr/brazilian-ecommerce (9 CSV) | Socle transactionnel : RFM, market basket, sentiment |
| `retailrocket` | Kaggle retailrocket/ecommerce-dataset | Comportemental : funnel, reco collaborative item-item |
| `churn` | ecommerce_customer_churn_dataset.csv | Scoring d'attrition + recommandation d'actions marketing |
| `analytics` | Calculé par mes scripts de `analytics/` | Zone de convergence : résultats ML consommés par l'API |
| `app` | Interne | Comptes API (JWT/RBAC) + journal d'audit RGPD |

J'ai gardé les 3 populations de clients (Olist, Retailrocket, churn) **indépendantes** : aucune
jointure inter-datasets. Voir [docs/architecture.md](docs/architecture.md) pour le détail de mes
décisions et [docs/limitations-methodologiques.md](docs/limitations-methodologiques.md) pour les
limites que j'ai identifiées sur chaque module (importantes à connaître avant ma soutenance).

## Structure de mon repo

```
├── .github/workflows/   # CI (tests automatiques à chaque push, voir docs/deploiement.md)
├── docker-compose.yml   # PostgreSQL 16 conteneurisé
├── .env.example         # variables d'environnement (jamais commiter .env)
├── sql/                 # DDL : schémas, tables, contrôles (01 à 11 + 99_controles)
├── etl/                 # Extract-Transform-Load des 3 sources brutes -> schémas olist/retailrocket/churn
├── analytics/           # Mes modules ML : RFM, market basket, funnel, reco collaborative,
│                         # scoring churn, sentiment (deep learning), vue client 360° -> écrivent dans analytics.*
│                         # + model_registry.py (versioning/rollback) et analyse_seuil_bot.py (diagnostic)
├── api/                 # Mon API FastAPI : auth JWT/RBAC, endpoints analytics, RGPD, administration
├── dashboard/            # Mon dashboard React (Vite) : consomme l'API, vues par rôle admin/analyst
├── data/raw/             # CSV bruts (ignorés par git)
├── notebooks/            # Mes EDA et prototypages
├── tests/                # Mes tests pytest : RBAC, qualité de données, versioning de modèle (voir docs/tests.md)
└── docs/                 # Mon architecture, limites, RGPD, tests, déploiement, journal de bord
```

## Comment je démarre le projet

### 1. Base de données

```bash
copy .env.example .env        # puis éditer le mot de passe
docker compose up -d          # démarre PostgreSQL 16 et crée schémas/tables (sql/01 à 05)
```

Si ma base existait déjà avant l'ajout d'un nouveau fichier SQL (06 à 11 — schéma `app`, table
sentiment, importance des variables, vue client 360°, historique des métriques, registre de
versions de modèles), je l'applique manuellement :
```bash
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/06_app_tables.sql
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/07_sentiment_table.sql
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/08_churn_feature_importance.sql
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/09_customer_360.sql
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/10_model_metrics_history.sql
docker exec -i ecommerce_db psql -U ecommerce_admin -d ecommerce_platform < sql/11_model_registry.sql
```

### 2. Mon environnement Python

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Données + ETL

Je dépose les CSV Kaggle dans `data/raw/olist`, `data/raw/retailrocket`, `data/raw/churn`, puis :
```bash
cd etl && python run_all.py
```
Mes contrôles qualité : j'exécute `sql/99_controles.sql`.

### 4. Mes modules d'analyse (dans cet ordre — chaque script est indépendant et ré-exécutable)

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
Je dois lancer `customer_360_olist.py` **après** `rfm_olist.py`, `sentiment_olist.py` et
`market_basket_olist.py` (il les réutilise). Voir
[docs/architecture.md](docs/architecture.md#ce-que-jai-fait-à-la-place--fusion-au-niveau-des-résultats-sur-olist-analyticscustomer_360)
pour le contexte de ce module et [docs/limitations-methodologiques.md](docs/limitations-methodologiques.md)
pour mon évaluation honnête (résultat négatif assumé : AUC = 0,58).
Chaque script recalcule sa table `analytics.*` — je peux le relancer à tout moment. `churn_model.py`
et `customer_360_olist.py` passent par
[`analytics/model_registry.py`](docs/architecture.md#versioning-et-rollback-des-modèles-analyticsmodel_registrypy) :
un nouveau modèle n'écrase la version active que s'il n'est pas significativement moins bon, avec
un rollback d'un niveau possible depuis mon dashboard. Je peux tous les relancer depuis le dashboard
(page Administration, admin uniquement).

Diagnostic optionnel (ne modifie aucune table) : `python analyse_seuil_bot.py` documente comment
j'ai choisi le seuil de filtrage bot de `recommend_retailrocket.py` — voir
[docs/limitations-methodologiques.md](docs/limitations-methodologiques.md#reco-collaborative-item-item-retailrocket).

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
http://localhost:5173 — je me connecte avec le compte admin créé à l'étape 5.

### 7. Mes tests

```bash
pytest                              # depuis la racine, base de données démarrée (étape 1)
cd dashboard && npm test            # tests du dashboard React (Vitest)
```
J'ai écrit 76 tests Python (RBAC, qualité de données, versioning de modèle, logique interne des
scripts `analytics/*.py`) et 45 tests dashboard. Les tests Python se lancent automatiquement à
chaque push (`.github/workflows/ci.yml`) — voir [docs/tests.md](docs/tests.md) et
[docs/deploiement.md](docs/deploiement.md). J'ai aussi un test de charge manuel (Locust) — voir
[docs/performance.md](docs/performance.md).

## Mes rôles

- **`admin`** : accès complet — analytics, RGPD (export/anonymisation), gestion des comptes API,
  recalcul à la demande des modules ML.
- **`analyst`** : lecture des analytics (RFM, churn, funnel, reco, règles, sentiment) + calculateur
  de rétention. Pas d'accès RGPD ni administration.

## Ma documentation

- [docs/gouvernance.md](docs/gouvernance.md) — organisation du projet : rôles, responsabilités par
  dossier, matrice RACI, workflow de contribution
- [docs/architecture.md](docs/architecture.md) — mes décisions d'architecture et pourquoi
- [docs/limitations-methodologiques.md](docs/limitations-methodologiques.md) — les limites que je
  connais pour chaque module (à citer moi-même en soutenance plutôt qu'à laisser découvrir)
- [docs/securite.md](docs/securite.md) — authentification, révocation de jeton, anti-bruteforce,
  gestion des secrets (Vault)
- [docs/rgpd.md](docs/rgpd.md) — mon approche RGPD (droit d'accès, droit à l'oubli et sa base
  légale, analyse de k-anonymat, audit)
- [docs/tests.md](docs/tests.md) — ce que je teste automatiquement (et ce que je ne teste pas
  encore)
- [docs/performance.md](docs/performance.md) — mon test de charge (Locust) et le vrai problème de
  pool de connexions qu'il a révélé
- [docs/deploiement.md](docs/deploiement.md) — ma CI en place, ce qu'un vrai déploiement continu me
  demanderait
- [docs/journal-de-bord.md](docs/journal-de-bord.md) — chronologie de mes décisions, incidents que
  j'ai rencontrés et corrigés pendant mon développement
