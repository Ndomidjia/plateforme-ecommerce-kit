# Tests automatisés

## Avant ce dossier : comment vérifiais-je la fiabilité ? (retour de soutenance)

Honnêtement : **manuellement**, et c'est bien la limite que mon jury a pointée. Concrètement,
jusqu'ici :

- **Qualité des données** : je lançais `sql/99_controles.sql` (volumes par table, commandes
  orphelines) à la main après chaque ETL, et je relisais le résultat à l'œil.
- **Qualité des modèles** : je regardais les métriques de validation croisée (ROC-AUC, PR-AUC)
  affichées dans les logs de chaque script (`analytics/*.py`) et je les recopiais à la main dans ma
  documentation — voir [limitations-methodologiques.md](limitations-methodologiques.md). Aucune
  régression automatique ne bloquait un mauvais résultat.
- **API et dashboard** : je testais manuellement via `/docs` (Swagger) et en cliquant dans le
  dashboard pendant le développement. J'ai trouvé plusieurs incidents ainsi, après coup — voir
  [journal-de-bord.md](journal-de-bord.md) (ex. le pool de connexions invalide après un redémarrage
  de PostgreSQL, que j'ai corrigé le 28/07).
- **Je ne vérifiais aucune régression de sécurité (RBAC) automatiquement** : un changement de code
  cassant l'isolation admin/analyst, je ne l'aurais découvert qu'en cliquant dans les deux rôles à
  la main, ou pas du tout.

Ce n'était pas suffisant, et c'est précisément ce que je corrige en partie avec ce dossier
`tests/` — pas totalement (voir "Ce qui n'est toujours pas couvert" plus bas).

## Lancer les tests

```bash
pip install -r requirements.txt   # inclut désormais pytest + httpx
docker compose up -d              # PostgreSQL doit tourner : mes tests lisent la vraie base
pytest                            # depuis la racine du dépôt
```

## Ce que je couvre

- **`tests/test_auth_rbac.py`** — authentification JWT (succès, mot de passe/utilisateur invalide,
  jeton invalide/absent) et cloisonnement des rôles admin/analyst sur les endpoints `/admin` et
  `/rgpd` (un analyst qui y accéderait serait une faille de sécurité directe sur des données
  personnelles ou des actions d'administration). Couvre aussi, depuis le retour de soutenance sur
  la sécurité (voir [securite.md](securite.md)) : la révocation immédiate du jeton d'un compte
  supprimé, et le verrouillage anti-bruteforce de `/auth/login` (verrouillage après trop d'échecs,
  remise à zéro après un succès).
- **`tests/test_data_quality.py`** — volumes minimums par table source, absence de commandes
  orphelines (repris de `sql/99_controles.sql`), plages de valeurs valides pour les scores que je
  produis (`churn_proba`, `sentiment_proba`, `proxy_risk_proba` ∈ [0,1]), cohérence des bornes
  `risk_level` avec les probabilités.
- **`tests/test_model_registry.py`** — mon garde-fou de promotion de modèle (voir
  [architecture.md](architecture.md) et `analytics/model_registry.py`) : je vérifie qu'une première
  exécution est toujours promue, qu'une régression au-delà de ma tolérance est rejetée, qu'une
  variation dans la tolérance (bruit naturel d'un ré-entraînement) est acceptée, et que l'état
  "rollback disponible" est correctement enregistré après une deuxième promotion.

J'ai écrit 27 tests, quelques secondes d'exécution.

## Choix que j'assume (proportionnés à l'échelle de mon projet)

- **Pas de base de données de test isolée** : mes tests tournent contre la même base PostgreSQL que
  mon environnement de développement. Ils ne font que lire (contrôles qualité, RBAC) ou nettoient
  explicitement ce qu'ils écrivent (utilisateurs et entrées de registre `pytest_*` jetables, que je
  supprime en fin de test/session). Un vrai environnement de test isolé (conteneur PostgreSQL
  éphémère par run) serait la suite logique avec une vraie CI multi-environnements — voir
  [deploiement.md](deploiement.md).
- **Pas de mock de la base ou de l'API** : mes tests de qualité de données n'ont de sens que contre
  de vraies données (voir la remarque de mon jury sur le seuil de 200 produits — un mock aurait
  caché exactement ce genre de problème). Mes tests RBAC utilisent le vrai `TestClient` FastAPI, pas
  de simulation.

## Ce que je ne couvre toujours pas

- **Les scripts `analytics/*.py` eux-mêmes** (RFM, market basket, funnel, reco, sentiment) : je ne
  les teste pas unitairement — seul leur résultat final en base l'est (`test_data_quality.py`). Un
  bug dans ma logique de calcul qui produirait quand même des valeurs dans les bonnes plages ne
  serait pas détecté.
- **Mon dashboard React** n'a aucun test (unitaire ou end-to-end). Les captures d'écran de
  `docs/Documentation_Plateforme.docx` sont un contrôle visuel que j'ai fait manuellement au moment
  où je les ai prises, pas une garantie continue.
- **Mes notebooks d'EDA** (`notebooks/`) ne sont pas testés — usage exploratoire, pas de production.
- **Pas de test de charge/performance.**

J'ai volontairement resserré mon périmètre sur ce qui protège le plus (sécurité RBAC, intégrité des
données servies, non-régression des modèles) plutôt que de viser une couverture exhaustive mais
superficielle.
