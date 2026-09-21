# Déploiement et intégration continue

## Avant ce document : le retour de soutenance

*"Absence de CI/CD confirmée en fin de document : le processus de déploiement des mises à jour
reste flou."* Exact. Ce document répond aux deux volets séparément, parce que ce sont deux choses
différentes :

- **CI (intégration continue)** : maintenant en place (`.github/workflows/ci.yml`) — voir plus bas.
- **CD (déploiement continu)** : **toujours absent, assumé.** Il n'y a pas d'environnement hébergé
  (serveur, cloud) vers lequel déployer pour ce projet — c'est un projet de soutenance exécuté en
  local (`docker compose` + `uvicorn --reload` + `npm run dev`), pas un service en production. Un
  vrai pipeline de déploiement continu n'aurait pas de cible concrète tant que cette question
  (héberger où, avec quel budget, quelle disponibilité) n'est pas tranchée — ajouter un CD pour un
  déploiement qui n'existe pas serait de la complexité gratuite, pas une amélioration. La section
  "Ce qu'un vrai déploiement demanderait" ci-dessous documente ce que ça impliquerait, sans le faire.

## Ce qui existe : intégration continue (CI)

`.github/workflows/ci.yml` s'exécute à chaque `push`/`pull request` :

1. démarre un conteneur PostgreSQL 16 propre (service GitHub Actions) ;
2. applique le schéma SQL complet (`sql/01_schemas.sql` → `sql/11_model_registry.sql`) — **sans les
   données** : les CSV Kaggle sources (`data/raw/`) ne sont pas commités (volumineux, redistribution
   hors périmètre de licence — voir `.gitignore`), donc aucun ETL ne peut tourner sur le runner ;
3. installe les dépendances (`requirements.txt`, qui inclut désormais `pytest`) ;
4. lance `pytest` — voir [tests.md](tests.md) pour ce qui est testé. Les tests de qualité de
   données (`tests/test_data_quality.py`) se `skip` proprement sur un schéma vide (normal en CI) ;
   les tests RBAC et le garde-fou de versioning de modèle (`tests/test_auth_rbac.py`,
   `tests/test_model_registry.py`), eux, tournent réellement à chaque push ;
5. démarre l'API (`uvicorn`) et vérifie que `/health` répond — un test de fumée minimal qui aurait,
   par exemple, attrapé une erreur d'import ou de configuration avant que la question ne se pose en
   soutenance.

**Effet de bord positif direct** : mettre en place cette CI a fait tourner l'API pour la première
fois contre un schéma sans aucune donnée. Ça a immédiatement révélé un bug réel (non lié aux points
ci-dessus) : `/analytics/overview` renvoyait une erreur 500 quand `analytics.rfm_segments` ou
`analytics.funnel_stats` étaient vides (`GROUP BY`/`ORDER BY ... LIMIT 1` renvoie zéro ligne sur une
table vide, pas une ligne de `NULL` comme un agrégat simple) — jamais remarqué en développement
parce que ces tables ont toujours eu des données dès les premiers tests manuels. Corrigé dans
`api/routers/analytics.py` (garde-fous + champs `Optional` sur les KPIs qui peuvent légitimement
manquer avant qu'un module ait tourné). Exactement le genre de régression que l'absence de CI
laissait passer silencieusement.

## Processus de déploiement ACTUEL (manuel, local)

Pas de flou à entretenir : voici l'état réel, tel quel.

```bash
docker compose up -d                       # 1. base de données
cd etl && python run_all.py                # 2. ETL (CSV Kaggle déposés manuellement dans data/raw/)
cd ../analytics && python rfm_olist.py ...  # 3. modules d'analyse, dans l'ordre du README
cd ../api && python create_admin.py ...     # 4. premier compte admin
uvicorn main:app --reload --port 8000       # 5. API
cd ../dashboard && npm install && npm run dev  # 6. dashboard
```

Aucune étape n'est automatisée au-delà de `etl/run_all.py` (qui enchaîne déjà les 3 scripts ETL) et
du recalcul à la demande depuis le dashboard (page Administration, voir
[limitations-methodologiques.md](limitations-methodologiques.md#recalcul-à-la-demande)). Mettre à
jour l'API ou le dashboard en "production" (au sens : sur la machine qui fait tourner la
démonstration) veut dire : arrêter le processus, `git pull`, relancer — manuel, pas scripté.

## Ce qu'un vrai déploiement demanderait (non fait, documenté honnêtement)

Pour transformer ceci en un déploiement réel (pas seulement une démo locale) :

- une cible d'hébergement (VM, PaaS type Render/Railway pour l'API, hébergement statique pour le
  dashboard buildé, PostgreSQL managé) ;
- une image Docker pour l'API (actuellement lancée directement via `uvicorn`, pas conteneurisée —
  seul PostgreSQL l'est) ;
- une vraie file de tâches pour le recalcul à la demande (Celery/RQ) plutôt que le suivi en mémoire
  actuel, qui ne survit pas à un redémarrage et ne fonctionne pas avec plusieurs workers (limite déjà
  documentée dans [limitations-methodologiques.md](limitations-methodologiques.md)) ;
- des secrets gérés par la plateforme d'hébergement plutôt qu'un fichier `.env` local ;
- un job de déploiement continu (`.github/workflows/cd.yml`) déclenché après que la CI passe sur
  `main`, avec une étape de migration de schéma (`sql/*.sql`) explicite plutôt qu'appliquée à la main.

Rien de tout cela n'est nécessaire pour la soutenance elle-même ; documenté ici pour montrer que
l'absence de CD est un choix de périmètre assumé, pas un point aveugle.
