# Déploiement et intégration continue

## Avant ce document : le retour de soutenance

*"Absence de CI/CD confirmée en fin de document : le processus de déploiement des mises à jour
reste flou."* Exact. Je réponds aux deux volets séparément, parce que ce sont deux choses
différentes pour moi :

- **CI (intégration continue)** : je l'ai maintenant mise en place (`.github/workflows/ci.yml`) —
  voir plus bas.
- **CD (déploiement continu)** : **toujours absent, je l'assume.** Je n'ai pas d'environnement
  hébergé (serveur, cloud) vers lequel déployer pour ce projet — c'est un projet de soutenance que
  j'exécute en local (`docker compose` + `uvicorn --reload` + `npm run dev`), pas un service en
  production. Un vrai pipeline de déploiement continu n'aurait pas de cible concrète tant que je
  n'ai pas tranché cette question (héberger où, avec quel budget, quelle disponibilité) — ajouter un
  CD pour un déploiement qui n'existe pas serait de la complexité gratuite de ma part, pas une
  amélioration. Je documente ce que ça impliquerait, sans le faire, dans la section "Ce qu'un vrai
  déploiement demanderait" ci-dessous.

## Ce que j'ai mis en place : intégration continue (CI)

`.github/workflows/ci.yml` s'exécute à chaque `push`/`pull request` :

1. je démarre un conteneur PostgreSQL 16 propre (service GitHub Actions) ;
2. j'applique le schéma SQL complet (`sql/01_schemas.sql` → `sql/11_model_registry.sql`) — **sans
   les données** : je n'ai pas commité les CSV Kaggle sources (`data/raw/`, volumineux,
   redistribution hors périmètre de licence — voir `.gitignore`), donc aucun ETL ne peut tourner sur
   le runner ;
3. j'installe les dépendances (`requirements.txt`, qui inclut désormais `pytest`) ;
4. je lance `pytest` — voir [tests.md](tests.md) pour ce que je teste. Mes tests de qualité de
   données (`tests/test_data_quality.py`) se `skip` proprement sur un schéma vide (normal en CI) ;
   mes tests RBAC et mon garde-fou de versioning de modèle (`tests/test_auth_rbac.py`,
   `tests/test_model_registry.py`), eux, tournent réellement à chaque push ;
5. je démarre l'API (`uvicorn`) et vérifie que `/health` répond — un test de fumée minimal qui
   m'aurait, par exemple, permis d'attraper une erreur d'import ou de configuration avant que la
   question ne se pose en soutenance.

**Effet de bord positif direct** : en mettant en place cette CI, j'ai fait tourner l'API pour la
première fois contre un schéma sans aucune donnée. Ça a immédiatement révélé un bug réel que
j'avais jusque-là laissé passer (non lié aux points ci-dessus) : `/analytics/overview` renvoyait une
erreur 500 quand `analytics.rfm_segments` ou `analytics.funnel_stats` étaient vides
(`GROUP BY`/`ORDER BY ... LIMIT 1` renvoie zéro ligne sur une table vide, pas une ligne de `NULL`
comme un agrégat simple) — je ne l'avais jamais remarqué en développement parce que ma base de
travail a toujours eu des données dès mes premiers tests manuels. Je l'ai corrigé dans
`api/routers/analytics.py` (garde-fous + champs `Optional` sur les KPIs qui peuvent légitimement
manquer avant qu'un module ait tourné). C'est exactement le genre de régression que l'absence de CI
me laissait passer silencieusement.

## Mon processus de déploiement ACTUEL (manuel, local)

Pas de flou à entretenir : voici l'état réel, tel quel.

```bash
docker compose up -d                       # 1. base de données
cd etl && python run_all.py                # 2. ETL (CSV Kaggle déposés manuellement dans data/raw/)
cd ../analytics && python rfm_olist.py ...  # 3. modules d'analyse, dans l'ordre du README
cd ../api && python create_admin.py ...     # 4. premier compte admin
uvicorn main:app --reload --port 8000       # 5. API
cd ../dashboard && npm install && npm run dev  # 6. dashboard
```

Je n'ai automatisé aucune étape au-delà de `etl/run_all.py` (qui enchaîne déjà mes 3 scripts ETL) et
du recalcul à la demande depuis le dashboard (page Administration, voir
[limitations-methodologiques.md](limitations-methodologiques.md#recalcul-à-la-demande)). Mettre à
jour l'API ou le dashboard en "production" (au sens : sur la machine qui fait tourner ma
démonstration) veut dire, chez moi : arrêter le processus, `git pull`, relancer — manuel, pas
scripté.

## Ce qu'un vrai déploiement me demanderait (non fait, je le documente honnêtement)

Pour transformer ceci en un déploiement réel (pas seulement ma démo locale), il me faudrait :

- une cible d'hébergement (VM, PaaS type Render/Railway pour l'API, hébergement statique pour le
  dashboard buildé, PostgreSQL managé) ;
- une image Docker pour l'API (que je lance actuellement directement via `uvicorn`, pas
  conteneurisée — seul PostgreSQL l'est chez moi) ;
- une vraie file de tâches pour le recalcul à la demande (Celery/RQ) plutôt que le suivi en mémoire
  que j'utilise actuellement, qui ne survit pas à un redémarrage et ne fonctionne pas avec plusieurs
  workers (limite que je documente déjà dans
  [limitations-methodologiques.md](limitations-methodologiques.md)) ;
- des secrets gérés par la plateforme d'hébergement plutôt que mon fichier `.env` local ;
- un vrai pare-feu réseau côté hébergeur (groupes de sécurité) : base de données dans un sous-réseau
  privé non routable depuis l'extérieur, seule l'API exposée publiquement -- j'ai déjà restreint
  l'exposition locale de PostgreSQL et Vault à `127.0.0.1` (voir
  [securite.md](securite.md#exposition-réseau-de-postgresql-et-vault-retour-de-soutenance)), mais ça
  ne couvre que ma machine de développement, pas un vrai périmètre réseau d'hébergement ;
- un job de déploiement continu (`.github/workflows/cd.yml`) que je déclencherais après que la CI
  passe sur `main`, avec une étape de migration de schéma (`sql/*.sql`) explicite plutôt qu'appliquée
  à la main.

Rien de tout cela n'est nécessaire pour ma soutenance elle-même ; je le documente ici pour montrer
que l'absence de CD est un choix de périmètre que j'assume, pas un point aveugle de ma part.
