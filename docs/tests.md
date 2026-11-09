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
- **Je ne vérifiais aucune régression de sécurité (RBAC) automatiquement**, aucune logique de calcul
  des scripts `analytics/*.py` isolément, rien côté dashboard React, et aucune charge/performance.

Ce dossier (et son équivalent côté dashboard, `dashboard/src/**/*.test.jsx`) corrige ça en grande
partie désormais — pas totalement, voir "Ce que je ne couvre toujours pas" plus bas.

## Lancer les tests

```bash
pip install -r requirements.txt   # inclut pytest + httpx
docker compose up -d              # PostgreSQL doit tourner : mes tests lisent la vraie base
pytest                            # depuis la racine du dépôt -- tests Python (API + analytics)

cd dashboard && npm install && npm test   # tests du dashboard React (Vitest)
```

Le test de charge (Locust) est un outil à part, pas relancé à chaque `pytest` — voir
[performance.md](performance.md).

## Ce que je couvre

### Côté Python (`pytest`, 116 tests)

- **`tests/test_auth_rbac.py`** (14) — authentification JWT, cloisonnement des rôles admin/analyst,
  révocation immédiate du jeton d'un compte supprimé, verrouillage anti-bruteforce de
  `/auth/login` (voir [securite.md](securite.md)).
- **`tests/test_data_quality.py`** (8) — volumes minimums par table source, absence de commandes
  orphelines (repris de `sql/99_controles.sql`), plages de valeurs valides pour mes scores
  (`churn_proba`, `sentiment_proba`, `proxy_risk_proba` ∈ [0,1]), cohérence des bornes `risk_level`.
- **`tests/test_model_registry.py`** (5) — mon garde-fou de promotion de modèle (voir
  [architecture.md](architecture.md)) : promotion/rejet, tolérance au bruit, rollback.
- **`tests/test_security_attacks.py`** (40, nouveau) — simulation d'attaque sur quatre vecteurs
  (bruteforce/anti-bruteforce, falsification de JWT, injection SQL, élévation de privilèges) : voir
  [securite.md](securite.md#simulation-dattaque-pentest-interne) pour le détail et le résultat.
- **`tests/unit/`** (49, nouveau) — logique interne pure de mes scripts `analytics/*.py`, avec des
  données fabriquées à la main plutôt qu'en relisant le résultat final en base (complémentaire à
  `test_data_quality.py`, pas redondant : ça détecte un bug de calcul qui produirait quand même une
  valeur dans la bonne plage). Un fichier par module : `test_rfm_logic.py`, `test_funnel_logic.py`,
  `test_market_basket_logic.py`, `test_recommend_logic.py`, `test_churn_model_logic.py`,
  `test_sentiment_logic.py`, `test_customer_360_logic.py`, `test_seuil_bot_logic.py`,
  `test_k_anonymat_logic.py`. Pour que ça marche sans base de données, j'ai dû déplacer
  `from config import get_engine` de l'en-tête de chaque script vers l'intérieur de `main()`, et
  extraire quelques fonctions pures qui étaient mélangées avec du code d'accès base (`compute_rules`
  dans market_basket_olist.py, `proba_to_risk_level` dans churn_model.py, `label_and_censor` et
  `apply_category_fallback` dans customer_360_olist.py) — changement mécanique, comportement
  inchangé, revérifié en relançant chaque script en conditions réelles après coup.

### Côté dashboard (`npm test`, Vitest + React Testing Library, 45 tests)

- `utils/csv.test.js` — l'échappement CSV (virgules, guillemets, retours à la ligne, valeurs
  nulles) : la partie la plus facile à casser silencieusement dans `rowsToCsv`.
- `api.test.js` — construction des requêtes (`api.js`) : en-têtes, encodage form vs JSON, gestion
  des erreurs HTTP (`ApiError`), des réponses `204`, des paramètres de requête optionnels.
- `components/StatTile.test.jsx`, `AlertBanner.test.jsx`, `AnomalyBanner.test.jsx` — rendu, et pour
  `AlertBanner` les 4 règles de seuils métier de la page Vue d'ensemble (churn élevé, chute de
  conversion, faible couverture reco, avis négatifs) une par une, bornes incluses/exclues.
- `components/ExportCsvButton.test.jsx`, `ProtectedRoute.test.jsx` — export CSV déclenché au clic ;
  redirection vers `/login` si non connecté, vers `/` si rôle insuffisant (sécurité côté UI).
- `auth/AuthContext.test.jsx` — connexion/déconnexion, persistance du jeton en `localStorage`,
  décodage des claims JWT (username/rôle).
- `hooks/useApiQuery.test.jsx` — états loading/data/error, et surtout la déconnexion automatique
  sur une erreur 401 (pas transformée en simple message d'erreur affiché).

### Charge / performance (Locust, manuel)

Voir [performance.md](performance.md) : a trouvé un vrai problème (pool de connexions SQLAlchemy
saturé dès 20 utilisateurs simulés, 8,2% d'échecs et jusqu'à 34 secondes de latence), corrigé dans
`api/config.py`.

## Choix que j'assume (proportionnés à l'échelle de mon projet)

- **Pas de base de données de test isolée** : mes tests Python tournent contre la même base
  PostgreSQL que mon environnement de développement. Ils ne font que lire (contrôles qualité, RBAC)
  ou nettoient explicitement ce qu'ils écrivent (utilisateurs et entrées `pytest_*` jetables). Un
  vrai environnement de test isolé (conteneur PostgreSQL éphémère par run) serait la suite logique
  avec une vraie CI multi-environnements — voir [deploiement.md](deploiement.md).
- **Pas de mock de la base ou de l'API côté Python** : mes tests de qualité de données n'ont de sens
  que contre de vraies données (voir la remarque de mon jury sur le seuil de 200 produits — un mock
  aurait caché exactement ce genre de problème). Côté dashboard en revanche, je mocke `fetch` et
  `AuthContext` (convention standard en test de composants React) : ce qui est testé là, c'est le
  comportement du composant face à une réponse donnée, pas l'intégration bout en bout avec l'API
  (déjà couverte côté Python).

## Ce que je ne couvre toujours pas

- **Mes notebooks d'EDA** (`notebooks/`) ne sont pas testés — usage exploratoire, pas de production.
- **Pas de test end-to-end navigateur** (type Playwright/Cypress) du dashboard : mes tests Vitest
  sont des tests de composants (rendu + interactions simulées en jsdom), pas un vrai navigateur qui
  cliquerait à travers plusieurs pages. Les captures d'écran de
  `docs/Documentation_Plateforme.docx` restent un contrôle visuel manuel, pas une garantie continue.
- **Le test de charge n'est pas intégré à la CI** (voir [performance.md](performance.md)) — outil
  manuel, à relancer après un changement structurel.

J'ai volontairement resserré mon périmètre sur ce qui protège le plus (sécurité RBAC, intégrité des
données servies, non-régression des modèles et de la logique de calcul) plutôt que de viser une
couverture exhaustive mais superficielle.
