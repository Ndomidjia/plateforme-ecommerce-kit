# Gouvernance du projet

Ce document formalise l'organisation du projet : qui décide quoi, qui est responsable de quel
module, et comment une décision ou un changement remonte jusqu'à validation. Il complète
[architecture.md](architecture.md) (le *quoi* et le *pourquoi* techniques) avec le *qui* et le
*comment organisationnel*, en termes de postes et de responsabilités plutôt que de personnes.

## Organigramme

```
                        Comité de pilotage
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

### Comité de pilotage

- Valide les orientations méthodologiques majeures (ex. : stratégie de fusion des données —
  voir [architecture.md](architecture.md#pourquoi-je-nai-pas-fait-de-fusion-brute-des-3-datasets),
  choix du modèle de scoring churn).
- Revoit les livrables aux jalons (soutenance intermédiaire, soutenance finale) et formule des
  retours contraignants — voir les 5 remarques traitées dans
  [journal-de-bord.md](journal-de-bord.md#retours-de-soutenance-que-jai-traités-21092026).
- Arbitre en dernier ressort en cas de désaccord méthodologique.

### Chef de projet / Product Owner

- Définit le périmètre (Plan A : 3 sources indépendantes convergeant vers une zone de résultats
  unique).
- Priorise les modules et arbitre les choix temps/bénéfice (ex. : analyse de survie Kaplan-Meier
  non retenue pour le seuil de non-réachat, documentée comme limite assumée plutôt que traitée).
- Rend compte au comité de pilotage et répercute ses retours vers les autres rôles.

### Data Engineer

- **Responsable de** : `sql/` (schémas et migrations 01 à 11), `etl/` (`load_olist.py`,
  `load_retailrocket.py`, `load_churn.py`, `run_all.py`).
- Garantit l'intégrité référentielle et les volumes de données (contrôles de
  `sql/99_controles.sql`, repris et automatisés dans `tests/test_data_quality.py`).

### Data Scientist / ML Engineer

- **Responsable de** : `analytics/` (RFM, market basket, funnel, recommandation collaborative,
  scoring churn, sentiment, vue client 360°, `model_registry.py`, `analyse_seuil_bot.py`).
- Garant de la rigueur méthodologique : validation croisée, comparaison de plusieurs
  configurations avant de choisir un modèle, documentation honnête des limites (voir
  [limitations-methodologiques.md](limitations-methodologiques.md)).
- Décide de la promotion ou du rejet d'une nouvelle version de modèle (processus formalisé dans
  `analytics/model_registry.py`), avec traçabilité dans `analytics.model_metrics_history`.

### Backend Developer

- **Responsable de** : `api/` (routers FastAPI, authentification JWT, RBAC, endpoints RGPD et
  administration, `config.py`, `security.py`).
- Garant de la cohérence des contrats d'API consommés par le dashboard.

### Frontend Developer

- **Responsable de** : `dashboard/` (React + Vite, pages par module, composants partagés,
  cohérence visuelle et accessibilité).

### QA / DevOps

- **Responsable de** : `tests/` (suite pytest), `.github/workflows/ci.yml`, `docker-compose.yml`,
  et de la documentation de déploiement ([deploiement.md](deploiement.md)).
- Valide qu'une CI verte est une condition nécessaire avant toute fusion sur `main` (voir
  "Workflow de contribution" ci-dessous).

### Référent RGPD & Sécurité (rôle transverse)

- Garantit la conformité RGPD (droit d'accès, droit à l'oubli, base légale, analyse de
  k-anonymat — voir [rgpd.md](rgpd.md)) et la sécurité applicative (authentification, révocation de
  jeton, anti-bruteforce, gestion des secrets via Vault — voir [securite.md](securite.md)).
- Ce rôle n'est pas rattaché à un dossier du dépôt : il s'applique transversalement à `api/`
  (endpoints RGPD), `analytics/` (anonymisation) et à la configuration (`.gitignore`, `.env.example`).

## Qui est responsable de quoi, en un coup d'œil

| Rôle | Dossiers / périmètre dont il est responsable |
|---|---|
| Comité de pilotage | — (supervision) |
| Chef de projet | — (arbitrage transverse) |
| Data Engineer | `sql/`, `etl/` |
| Data Scientist / ML Engineer | `analytics/` |
| Backend Developer | `api/` |
| Frontend Developer | `dashboard/` |
| QA / DevOps | `tests/`, `.github/`, `docker-compose.yml` |
| Référent RGPD & Sécurité | transverse |

Mapping technique correspondant : [`.github/CODEOWNERS`](../.github/CODEOWNERS).

## Matrice RACI — qui décide, qui est consulté, qui est informé

RACI est un découpage classique de gestion de projet qui dit, pour chaque décision, qui fait quoi.
Chaque lettre du tableau ci-dessous correspond à un rôle vis-à-vis de cette décision précise (une
même personne/poste peut avoir des lettres différentes selon la ligne) :

| Code | Signification | Ce que ça veut dire concrètement |
|:---:|---|---|
| **R** | Responsable | Exécute la tâche — celui qui met réellement la main à la pâte |
| **A** | Approbateur | Valide ou refuse la décision finale — un seul A par ligne, c'est lui qui rend des comptes si ça tourne mal |
| **C** | Consulté | Sollicité pour avis **avant** que la décision soit prise (dialogue à double sens) |
| **I** | Informé | Tenu au courant **après** la décision, sans être consulté avant (information à sens unique) |

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
   été le cas pour la vue client 360° (voir
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
   rencontré) est consignée dans [journal-de-bord.md](journal-de-bord.md) au fil du projet plutôt
   qu'en fin de parcours.
5. **Jalons** : revue par le comité de pilotage à chaque soutenance (intermédiaire, finale) ;
   les retours sont tracés et traités un par un (voir le modèle appliqué aux 5 retours du
   21/09/2026 dans le journal de bord), pas laissés sans suite.

## Répartition des rôles

Les rôles ci-dessus sont découpés pour pouvoir être distribués sans réorganisation : chacun
correspond à un périmètre de dossiers étanche (voir la table "qui est responsable de quoi"), ce
qui permet d'affecter chaque rôle à un poste distinct sans toucher à l'architecture. Les postes les
plus chargés — Data Scientist / ML Engineer (le plus gros volume de code et la responsabilité
méthodologique la plus engageante) et QA/DevOps (industrialisation au-delà de la CI actuelle, voir
"Ce qu'un vrai déploiement demanderait" dans [deploiement.md](deploiement.md)) — sont les premiers
candidats à un renfort dédié si le périmètre du projet s'élargit.
