# Gouvernance du projet

Ce document formalise l'organisation du projet : qui décide quoi, qui est responsable de quel
module, et comment une décision ou un changement remonte jusqu'à validation. Il complète
[architecture.md](architecture.md) (le *quoi* et le *pourquoi* techniques) avec le *qui* et le
*comment organisationnel*.

**Note de transparence** : ce projet est mené en autonomie dans le cadre d'une soutenance M2. La
structure ci-dessous est la structure **formelle et cible** du projet — celle qu'on documenterait
pour une équipe complète — avec, pour chaque rôle, qui le tient **actuellement**. Dans les faits,
je cumule aujourd'hui la totalité des rôles opérationnels ; les décrire séparément sert à montrer
clairement la répartition des responsabilités et ce qu'il faudrait pourvoir si le projet
s'ouvrait à une équipe.

## Organigramme

```
                        Comité de pilotage
                     (Encadrant académique M2)
                                |
                                | validation des orientations majeures
                                | revue aux jalons (soutenances)
                                v
                         Chef de projet
                    (scope, priorités, arbitrages)
                                |
        +------------+---------+---------+------------+------------+
        |            |                   |            |            |
   Data Engineer  Data Scientist   Backend Developer  Frontend   QA / DevOps
   (sql/, etl/)   (analytics/)     (api/)             Developer  (tests/,
        |            |                   |            (dashboard/) CI/CD)
        |            |                   |                 |           |
        +------------+-------------------+-----------------+-----------+
                                |
                      Référent RGPD & Sécurité
                      (rôle transverse, pas un dossier)
```

## Rôles et responsabilités

### Comité de pilotage — Encadrant académique

- Valide les orientations méthodologiques majeures (ex. : stratégie de fusion des données —
  voir [architecture.md](architecture.md#pourquoi-je-nai-pas-fait-de-fusion-brute-des-3-datasets),
  choix du modèle de scoring churn).
- Revoit les livrables aux jalons (soutenance intermédiaire, soutenance finale) et formule des
  retours contraignants — voir les 5 remarques traitées dans
  [journal-de-bord.md](journal-de-bord.md#retours-de-soutenance-que-jai-traités-21092026).
- Arbitre en dernier ressort en cas de désaccord méthodologique.
- **Titulaire actuel** : mon encadrant de M2.

### Chef de projet / Product Owner

- Définit le périmètre (Plan A : 3 sources indépendantes convergeant vers une zone de résultats
  unique).
- Priorise les modules et arbitre les choix temps/bénéfice (ex. : analyse de survie Kaplan-Meier
  non retenue pour le seuil de non-réachat, documentée comme limite assumée plutôt que traitée).
- Rend compte au comité de pilotage et répercute ses retours vers les autres rôles.
- **Titulaire actuel** : moi.

### Data Engineer

- **Responsable de** : `sql/` (schémas et migrations 01 à 11), `etl/` (`load_olist.py`,
  `load_retailrocket.py`, `load_churn.py`, `run_all.py`).
- Garantit l'intégrité référentielle et les volumes de données (contrôles de
  `sql/99_controles.sql`, repris et automatisés dans `tests/test_data_quality.py`).
- **Titulaire actuel** : moi.

### Data Scientist / ML Engineer

- **Responsable de** : `analytics/` (RFM, market basket, funnel, recommandation collaborative,
  scoring churn, sentiment, vue client 360°, `model_registry.py`, `analyse_seuil_bot.py`).
- Garant de la rigueur méthodologique : validation croisée, comparaison de plusieurs
  configurations avant de choisir un modèle, documentation honnête des limites (voir
  [limitations-methodologiques.md](limitations-methodologiques.md)).
- Décide de la promotion ou du rejet d'une nouvelle version de modèle (processus formalisé dans
  `analytics/model_registry.py`), avec traçabilité dans `analytics.model_metrics_history`.
- **Titulaire actuel** : moi.

### Backend Developer

- **Responsable de** : `api/` (routers FastAPI, authentification JWT, RBAC, endpoints RGPD et
  administration, `config.py`, `security.py`).
- Garant de la cohérence des contrats d'API consommés par le dashboard.
- **Titulaire actuel** : moi.

### Frontend Developer

- **Responsable de** : `dashboard/` (React + Vite, pages par module, composants partagés,
  cohérence visuelle et accessibilité).
- **Titulaire actuel** : moi.

### QA / DevOps

- **Responsable de** : `tests/` (suite pytest), `.github/workflows/ci.yml`, `docker-compose.yml`,
  et de la documentation de déploiement ([deploiement.md](deploiement.md)).
- Valide qu'une CI verte est une condition nécessaire avant toute fusion sur `main` (voir
  "Workflow de contribution" ci-dessous).
- **Titulaire actuel** : moi.

### Référent RGPD & Sécurité (rôle transverse)

- Garantit la conformité RGPD (droit d'accès, droit à l'oubli et sa base légale — voir
  [rgpd.md](rgpd.md)) et la gestion des secrets (mots de passe hashés, clé JWT, `.env` jamais
  commité).
- Ce rôle n'est pas rattaché à un dossier du dépôt : il s'applique transversalement à `api/`
  (endpoints RGPD), `analytics/` (anonymisation) et à la configuration (`.gitignore`, `.env.example`).
- **Titulaire actuel** : moi.

## Qui tient quoi, en un coup d'œil

| Rôle | Dossiers dont il/elle est responsable | Titulaire actuel |
|---|---|---|
| Comité de pilotage | — (supervision) | Encadrant académique |
| Chef de projet | — (arbitrage transverse) | Moi |
| Data Engineer | `sql/`, `etl/` | Moi |
| Data Scientist / ML Engineer | `analytics/` | Moi |
| Backend Developer | `api/` | Moi |
| Frontend Developer | `dashboard/` | Moi |
| QA / DevOps | `tests/`, `.github/`, `docker-compose.yml` | Moi |
| Référent RGPD & Sécurité | transverse | Moi |

Mapping technique correspondant : [`.github/CODEOWNERS`](../.github/CODEOWNERS).

## Matrice RACI — qui décide, qui est consulté, qui est informé

R = Responsable (exécute) · A = Approbateur (valide, un seul par ligne) · C = Consulté · I = Informé

| Décision / livrable | Comité de pilotage | Chef de projet | Data Engineer | Data Scientist | Backend Dev | Frontend Dev | QA/DevOps | Réf. RGPD |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Choix d'architecture (Plan A, pas de fusion brute) | A | R | C | C | I | I | I | I |
| Schéma de données / migration SQL (`sql/0X_*.sql`) | I | A | R | C | C | I | C | I |
| Choix d'un modèle ML / seuil méthodologique (ex. seuil bot, seuil de réachat) | I | A | I | R | I | I | I | I |
| Promotion ou rollback d'une version de modèle | I | I | I | R/A | I | I | C | I |
| Ajout/modification d'un endpoint API, RBAC | I | A | I | C | R | C | C | C |
| Évolution du dashboard (nouvelle page, UX) | I | A | I | C | C | R | I | I |
| Pipeline CI, déploiement | I | A | I | I | C | C | R | I |
| Traitement RGPD (export, anonymisation, base légale) | I | A | I | I | C | I | I | R |
| Revue aux jalons de soutenance | A | R | I | I | I | I | I | I |

## Workflow de contribution

1. **Avant de coder** : un changement qui touche au périmètre (nouvelle source de données,
   nouvelle fonctionnalité transverse) est d'abord discuté avec le comité de pilotage — comme ça a
   été le cas pour la vue client 360° (remarque de l'encadrant, voir
   [architecture.md](architecture.md#ce-que-jai-fait-à-la-place--fusion-au-niveau-des-résultats-sur-olist-analyticscustomer_360)).
2. **Développement** : chaque rôle travaille dans son périmètre de dossiers (voir table
   ci-dessus). Un changement qui traverse plusieurs dossiers (ex. : nouvel endpoint + nouvelle page
   dashboard) implique les deux rôles concernés.
3. **Avant de fusionner sur `main`** :
   - `pytest` doit passer localement (voir [tests.md](tests.md)) ;
   - la CI GitHub Actions doit être verte (`.github/workflows/ci.yml`) ;
   - toute limite méthodologique nouvelle ou modifiée est documentée dans
     [limitations-methodologiques.md](limitations-methodologiques.md) plutôt que laissée
     implicite.
4. **Traçabilité** : chaque décision significative (choix retenu, alternative écartée, incident
   rencontré) est consignée dans [journal-de-bord.md](journal-de-bord.md), que je tiens à jour au
   fil du projet plutôt qu'en fin de parcours.
5. **Jalons** : revue par le comité de pilotage à chaque soutenance (intermédiaire, finale) ;
   les retours sont tracés et traités un par un (voir le modèle appliqué aux 5 retours du
   21/09/2026 dans le journal de bord), pas laissés sans suite.

## Si le projet s'ouvrait à une équipe

Les rôles ci-dessus sont déjà découpés pour être distribués sans réorganisation : chacun
correspond à un périmètre de dossiers étanche (voir la table "qui tient quoi"), ce qui permettrait
d'affecter chaque rôle à une personne différente sans toucher à l'architecture. Postes qui seraient
à pourvoir en priorité pour soulager le cumul actuel : Data Scientist / ML Engineer (le plus gros
volume de code et la responsabilité méthodologique la plus engageante) et QA/DevOps (pour
industrialiser au-delà de la CI actuelle — voir "Ce qu'un vrai déploiement demanderait" dans
[deploiement.md](deploiement.md)).
