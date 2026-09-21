# Tests automatisés

## Avant ce dossier : comment la fiabilité était-elle vérifiée ? (retour de soutenance)

Honnêtement : **manuellement**, et c'est bien la limite pointée en soutenance. Concrètement,
jusqu'ici :

- **Qualité des données** : `sql/99_controles.sql` (volumes par table, commandes orphelines)
  exécuté à la main après chaque ETL, résultat relu à l'œil.
- **Qualité des modèles** : métriques de validation croisée (ROC-AUC, PR-AUC) affichées dans les
  logs de chaque script (`analytics/*.py`) et recopiées à la main dans la documentation — voir
  [limitations-methodologiques.md](limitations-methodologiques.md). Aucune régression automatique
  ne bloquait un mauvais résultat.
- **API et dashboard** : test manuel via `/docs` (Swagger) et clic dans le dashboard pendant le
  développement. Plusieurs incidents ont été trouvés ainsi, après coup — voir
  [journal-de-bord.md](journal-de-bord.md) (ex. le pool de connexions invalide après un redémarrage
  de PostgreSQL, corrigé le 28/07).
- **Aucune régression de sécurité (RBAC) n'était vérifiée automatiquement** : un changement de code
  cassant l'isolation admin/analyst ne se serait découvert qu'en cliquant dans les deux rôles à la
  main, ou pas du tout.

Ce n'était pas suffisant, et c'est précisément ce que ce dossier `tests/` corrige en partie — pas
totalement (voir "Ce qui n'est toujours pas couvert" plus bas).

## Lancer les tests

```bash
pip install -r requirements.txt   # inclut désormais pytest + httpx
docker compose up -d              # PostgreSQL doit tourner : les tests lisent la vraie base
pytest                            # depuis la racine du dépôt
```

## Ce qui est couvert

- **`tests/test_auth_rbac.py`** — authentification JWT (succès, mot de passe/utilisateur invalide,
  jeton invalide/absent) et cloisonnement des rôles admin/analyst sur les endpoints `/admin` et
  `/rgpd` (un analyst qui y accéderait serait une faille de sécurité directe sur des données
  personnelles ou des actions d'administration).
- **`tests/test_data_quality.py`** — volumes minimums par table source, absence de commandes
  orphelines (repris de `sql/99_controles.sql`), plages de valeurs valides pour les scores produits
  par les modèles (`churn_proba`, `sentiment_proba`, `proxy_risk_proba` ∈ [0,1]), cohérence des
  bornes `risk_level` avec les probabilités.
- **`tests/test_model_registry.py`** — le garde-fou de promotion de modèle (voir
  [architecture.md](architecture.md) et `analytics/model_registry.py`) : une première exécution est
  toujours promue, une régression au-delà de la tolérance est rejetée, une variation dans la
  tolérance (bruit naturel d'un ré-entraînement) est acceptée, et l'état "rollback disponible" est
  correctement enregistré après une deuxième promotion.

24 tests, quelques secondes d'exécution.

## Choix assumés (proportionnés à l'échelle du projet)

- **Pas de base de données de test isolée** : les tests tournent contre la même base PostgreSQL que
  le développement. Ils ne font que lire (contrôles qualité, RBAC) ou nettoient explicitement ce
  qu'ils écrivent (utilisateurs et entrées de registre `pytest_*` jetables, supprimés en fin de
  test/session). Un vrai environnement de test isolé (conteneur PostgreSQL éphémère par run) serait
  la suite logique avec une vraie CI multi-environnements — voir [deploiement.md](deploiement.md).
- **Pas de mock de la base ou de l'API** : les tests de qualité de données n'ont de sens que contre
  de vraies données (voir la remarque du retour de soutenance sur le seuil de 200 produits — un mock
  aurait caché exactement ce genre de problème). Les tests RBAC utilisent le vrai `TestClient`
  FastAPI, pas de simulation.

## Ce qui n'est toujours pas couvert

- **Les scripts `analytics/*.py` eux-mêmes** (RFM, market basket, funnel, reco, sentiment) ne sont
  pas testés unitairement — seul leur résultat final en base l'est (`test_data_quality.py`). Un bug
  dans la logique de calcul qui produirait quand même des valeurs dans les bonnes plages ne serait
  pas détecté.
- **Le dashboard React** n'a aucun test (unitaire ou end-to-end). Les captures d'écran de
  `docs/Documentation_Plateforme.docx` sont un contrôle visuel manuel au moment où elles sont prises,
  pas une garantie continue.
- **Les notebooks d'EDA** (`notebooks/`) ne sont pas testés — usage exploratoire, pas de production.
- **Pas de test de charge/performance.**

Périmètre volontairement resserré sur ce qui protège le plus (sécurité RBAC, intégrité des données
servies, non-régression des modèles) plutôt qu'une couverture exhaustive mais superficielle.
