# Journal de bord

Chronologie des décisions que j'ai prises et des incidents que j'ai rencontrés pendant mon
développement. Utile pour justifier mes choix en soutenance ("pourquoi avez-vous fait X plutôt que
Y ?").

## Mise en route

- J'ai fait une revue de cohérence du repo existant (SQL, ETL) avant de démarrer : aucune
  incohérence bloquante trouvée, mon ordre de chargement des tables Olist respecte les contraintes
  de clé étrangère.
- Python 3.14 (plus récent que le 3.11+ que je visais initialement) : toutes mes dépendances (dont
  `psycopg2-binary` et, plus tard, `torch`) se sont installées sans problème.
- Docker Desktop non démarré à mon premier essai de `docker compose up` — je l'ai relancé
  manuellement.

## Modules d'analyse

- **RFM** : j'ai décidé de filtrer sur `order_status = 'delivered'` uniquement (commande annulée ≠
  comportement d'achat réel). J'ai découvert le problème de fréquence mono-achat (97%) → j'ai fait
  un mapping manuel du F-score plutôt que des quintiles.
- **Market basket** : j'ai choisi le niveau catégorie plutôt que produit individuel (3197 commandes
  multi-produits diluées sur 32 951 produits → support quasi nul). J'ai abaissé le seuil de support
  itérativement (0,0003 → 0,00008) pour obtenir des paires exploitables. J'ai décidé de ne pas
  filtrer sur lift ≥ 1 pour l'écriture finale (une seule règle aurait survécu) : j'écris toutes les
  règles, avec le lift en colonne pour un filtrage en aval.
- **Reco collaborative** : **incident** — ma première requête SQL (filtrage par sous-requête
  GROUP BY/HAVING imbriquée) a tourné 1h30 sans terminer (plan d'exécution pathologique). J'ai tué
  la requête (`pg_terminate_backend`) et je l'ai réécrite en séparant extraction SQL simple +
  filtrage pandas : je descends à 15 secondes. J'ai détecté et exclu les visiteurs à >200 produits
  distincts (bots).
- **Scoring churn** : j'ai comparé Random Forest vs régression logistique (écart net : AUC 0,92 vs
  0,80) → j'ai retenu Random Forest. **Incident** — mon scoring initial in-sample donnait des
  probabilités artificiellement bimodales (sur-apprentissage) ; je l'ai corrigé par validation
  croisée (`cross_val_predict`, 5 plis).
- **Sentiment (deep learning)** : je l'ai ajouté suite à ma volonté explicite d'intégrer du deep
  learning et de combler un trou de mon plan initial ("sentiment sur avis" jamais construit).
  PyTorch s'est installé sans problème sur Python 3.14 (wheel `cp314` disponible). J'ai choisi un
  réseau simple (Embedding + mean pooling + denses) plutôt qu'un transformer pré-entraîné : ça
  m'évite un téléchargement de plusieurs Go et reste entraînable en quelques minutes sur CPU. J'ai
  fait ma validation croisée manuellement (pas de `cross_val_predict`, incompatible avec un modèle
  PyTorch hors wrapper scikit-learn).

## API et sécurité

- J'ai choisi un RBAC à 2 rôles (`admin`/`analyst`) plutôt qu'un modèle plus fin, pour rester
  proportionné à la portée de mon projet.
- **Incident** — `passlib[bcrypt]` incompatible avec les versions récentes de la librairie `bcrypt`
  (bibliothèque non maintenue) : je l'ai remplacé par un usage direct de `bcrypt.hashpw`/`checkpw`.
- **Incident** — dépendance manquante `python-multipart` (requise par
  `OAuth2PasswordRequestForm`) : je l'ai ajoutée.
- J'ai implémenté le RGPD d'abord sur `churn` seul (schéma le plus simple), un patron que je
  réutilise ensuite pour Olist/Retailrocket. J'ai retenu l'anonymisation plutôt que la suppression
  complète (voir [rgpd.md](rgpd.md)).
- Ordre de mes routes FastAPI : plusieurs endpoints littéraux (`/churn/summary`,
  `/churn/feature-importance`, `/rfm/summary`...) doivent être déclarés **avant** leurs routes
  paramétrées homonymes (`/churn/{customer_id}`), sous peine d'erreur 422 (FastAPI/Starlette
  matche les routes dans l'ordre de déclaration).

## Dashboard

- J'ai choisi React + Vite plutôt que Streamlit (décision que j'ai prise explicitement, malgré le
  coût de développement plus élevé, pour démontrer mes compétences full-stack).
- Palette de couleurs et règles de graphiques issues du skill dataviz de mon projet (que j'ai
  validée pour l'accessibilité daltonisme) plutôt que les couleurs par défaut de `recharts`.
- CORS initialement restreint à `http://localhost:5173`, que j'ai élargi à
  `http://127.0.0.1:5173` après un problème de connexion (l'origine exacte compte pour le
  navigateur).
- **Incident** — clés React dupliquées dans mes tables Sentiment et Recommandations : les clés
  primaires réelles de `analytics.review_sentiment` et `analytics.item_recommendations` sont
  composites (`review_id`+`order_id`, `item_id`+`recommended_item_id`+`method`) ; une seule colonne
  utilisée comme clé React pouvait collisionner. Corrigé.
- **Incident** — `TypeError` sur mon calculateur de rétention : PostgreSQL renvoie un `Decimal` pour
  `SUM(lifetime_value)`, incompatible avec la multiplication par un `float` Python sans conversion
  explicite.
- Je n'avais au départ aucun outil d'automatisation navigateur dans mon environnement de
  développement : j'ai d'abord vérifié le rendu visuel du dashboard moi-même (build de production +
  tests d'API systématiquement vérifiés, rendu visuel non automatisé). J'ai corrigé ça plus tard via
  Playwright — voir "Documentation illustrée" ci-dessous.

## Fonctionnalités "intelligentes" (itération finale)

- Calculateur de rétention, gestion des utilisateurs, recalcul à la demande : je les ai ajoutés
  suite à ma volonté explicite de séparer les fonctionnalités par rôle.
- Plan d'action marketing par client et détection d'anomalies : je les ai ajoutés suite à ma volonté
  explicite de rendre ma plateforme "plus intelligente". J'ai volontairement limité leur portée
  (heuristique explicable plutôt que boîte noire, détection sur la période la plus récente plutôt
  qu'un scan rétroactif complet) — voir [limitations-methodologiques.md](limitations-methodologiques.md).

## Documentation illustrée (captures d'écran + document Word)

- J'ai installé Playwright (piloté sur le Chrome déjà installé, `channel="chrome"`, pas de
  téléchargement de navigateur séparé) pour générer des captures d'écran réelles de chaque page de
  mon dashboard, connecté en admin, destinées à un document Word pour mon encadrant.
- **Incident, diagnostic en plusieurs étapes** — mon graphique "Variables les plus déterminantes"
  (page Scoring churn) restait invisible sur mes captures, de façon reproductible (3/3 essais),
  malgré des données propres (que j'ai vérifiées directement via l'API) et un DOM correct
  (rectangles SVG bien présents, couleur/opacité/géométrie toutes correctes à l'inspection). J'ai
  identifié la cause après inspection du `clipPath` SVG : une capture en `full_page=True` force
  Playwright à redimensionner la fenêtre pour capturer toute la hauteur de page, ce qui déclenche un
  `ResizeObserver` côté `ResponsiveContainer` (Recharts) et relance l'animation d'entrée du
  graphique — parfois interrompue par la capture. J'ai corrigé ça en fixant une fenêtre haute dès le
  départ (pas de redimensionnement dynamique). J'ai aussi ajouté une mémoïsation (`useMemo`) des
  données transformées par robustesse sur la page Churn (ça n'a pas résolu ce bug précis, mais reste
  une bonne pratique qui m'évite des recalculs/animations inutiles sur une page à 5 requêtes
  indépendantes).
- Une fois corrigé, ma vérification visuelle a confirmé que **l'ensemble de mon dashboard s'affiche
  correctement** — première confirmation directe (pas seulement via build + tests API) depuis le
  début de mon projet.
- J'ai généré mon document Word avec `python-docx` (page de titre, sommaire, une section par module
  avec définition/rôle/justification/capture d'écran/limite), avec des captures que je rogne
  automatiquement à leur contenu réel (`Pillow`, en excluant la sidebar de ma détection de zone vide
  — sa couleur de fond légèrement différente de la zone de contenu faussait mon premier essai de
  rognage).

## Vue client 360° — ma réponse à la remarque de mon encadrant ("fusionner les données")

- Mon encadrant m'a demandé de fusionner les 3 datasets. J'ai apporté une clarification :
  impossible techniquement (aucun identifiant commun) — voir
  [architecture.md](architecture.md#pourquoi-je-nai-pas-fait-de-fusion-brute-des-3-datasets).
  J'ai proposé une alternative, validée avec mon encadrant : fusionner les *résultats* d'analyse sur
  les clients Olist plutôt que les lignes brutes.
- **Seuil de non-réachat que j'ai dérivé empiriquement**, pas choisi au hasard (remarque n°1 de mon
  encadrant) : j'ai calculé la distribution réelle du délai de réachat chez les 2 801 clients Olist
  ayant racheté (médiane 29j, P75 126j, P90 246j) ; j'ai retenu le seuil P75 = 126 jours, après avoir
  comparé chiffre à l'appui l'impact de P75 vs P90 sur le volume de données exploitables et
  l'équilibre des classes.
- **Incident méthodologique que j'ai corrigé moi-même** : dans une première version, ma logique de
  censure excluait à tort des clients ayant déjà racheté (leur issue est pourtant déjà connue),
  simplement parce que pas assez de temps calendaire ne s'était écoulé depuis leur première
  commande. J'ai corrigé ça : je considère un client "évaluable" dès que son issue est connue (a
  racheté dans la fenêtre) OU que suffisamment de temps s'est écoulé sans rachat — principe standard
  de la censure à droite en analyse de survie.
- **Déséquilibre des classes que j'ai vérifié avec mes vrais chiffres** (remarque n°3) : 97,3% "à
  risque" / 2,7% "retenus" sur les 67 993 clients évaluables — encore plus extrême que le dataset
  churn (71%/29%), que je gère avec les mêmes techniques (`class_weight='balanced'`, validation
  croisée 5 plis).
- **Résultat négatif que j'ai obtenu et que j'assume** (remarque n°2) : ROC-AUC = 0,57 (quasi
  hasard). J'ai décidé, avec mon encadrant, de documenter honnêtement et de déployer avec un
  avertissement de fiabilité visible en permanence dans mon dashboard, plutôt que de cacher le
  résultat ou d'itérer indéfiniment sur mes features pour forcer un meilleur score. Interprétation
  que je retiens : cohérent avec les limites RFM et market basket que je documente déjà, le réachat
  sur une marketplace comme Olist me semble structurellement peu prévisible à partir des seules
  données de la première commande.
- **Pourquoi je garde Retailrocket et le dataset churn séparés** (remarque n°4), que je documente
  explicitement dans architecture.md : aucune fusion de données réelle n'est possible chez moi, mais
  je réutilise ou je transfère leur méthodologie (funnel/CF pour Retailrocket, technique de
  modélisation pour churn) — un choix réfléchi de ma part, pas un abandon.

## Auto-critique et améliorations (revue que j'ai demandée moi-même)

Suite à ma volonté explicite de me livrer à une critique honnête de mon projet, j'ai identifié
plusieurs faiblesses réelles et je les ai corrigées plutôt que de les lister sans suite :

- **Proxy churn (customer_360) que j'ai remodélisé (v1 → v2)** : ma v1 concluait à "quasiment aucun
  signal" après un seul essai (Random Forest, une seule config) — insuffisant pour l'affirmer avec
  confiance. Dans ma v2 : j'ai retiré les features connues seulement après le 1er achat (note d'avis,
  délai de livraison — fuite temporelle qui rendait mon module peu déployable même s'il avait mieux
  marché) ; j'ai comparé 3 configurations (RF avec/sans `class_weight`, Gradient Boosting) au lieu
  d'une seule. **Incident** — `HistGradientBoostingClassifier` a fait échouer mon premier essai
  (`TypeError: Sparse data was passed... dense data is required`) : contrairement à Random Forest,
  il n'accepte pas les matrices creuses produites par `OneHotEncoder` ; j'ai corrigé ça avec
  `sparse_output=False`. Résultat : Gradient Boosting légèrement meilleur (ROC-AUC 0,586 vs
  0,564/0,557), mon diagnostic de pouvoir prédictif quasi nul confirmé et renforcé par la
  comparaison, pas juste réaffirmé.
- **J'ai ajouté la table `analytics.model_metrics_history`** (append-only, jamais vidée,
  contrairement à toutes mes autres tables `analytics.*`) pour combler l'absence totale d'historique
  des métriques dans mon projet — fondation pour le monitoring de drift que j'avais prévu au plan
  initial mais jamais préparée jusqu'ici. J'ai ajouté la journalisation à `customer_360_olist.py` et
  `churn_model.py`. La note de fiabilité que j'affiche dans le dashboard (page Vue client 360°) est
  maintenant lue dynamiquement depuis cette table plutôt que codée en dur dans l'API — elle reste
  juste après un futur recalcul.
- **J'ai ajouté un repli de recommandation de catégorie**, puis j'ai immédiatement identifié et
  documenté sa limite : la catégorie de repli (`bed_bath_table`, la plus vendue globalement) se
  trouve être la même que l'unique cible de règle réelle, donc 90% de mes recommandations affichées
  sont en fait la même suggestion générique. J'ai corrigé ça côté affichage (dashboard) : je
  distingue visuellement recommandation "(règle)" avec lift réel et "(populaire)" sans lift, pour ne
  pas laisser croire à une personnalisation qui n'existe pas.
- **Bug que j'ai corrigé** : `customer_360` était absent de ma liste de modules relançables depuis
  la page Administration (`MODULE_SCRIPTS` dans `api/routers/admin.py`) — pur oubli de ma part lors
  de sa construction.
- **Incident mineur** : j'ai retrouvé une ligne `return anomalies` orpheline en toute fin de
  `api/routers/analytics.py` (résidu de copier-coller lors de mon ajout de la section
  customer-360). Ne provoquait pas d'erreur (code mort après un autre `return`, syntaxiquement
  valide en Python), mais aurait pu m'induire en erreur lors d'une future relecture. Je l'ai
  supprimée.
- Non retenu, que je documente comme limite assumée plutôt que corrigée (arbitrage temps/bénéfice de
  ma part) : une vraie analyse de survie (Kaplan-Meier) pour le calcul du seuil de non-réachat, qui
  traiterait la censure plus rigoureusement que le percentile simple que j'utilise actuellement.

## Retours de soutenance que j'ai traités (21/09/2026)

Mon jury m'a fait cinq remarques, que j'ai traitées une par une plutôt que de les reporter :

- **"Aucun test automatisé, comment la fiabilité a-t-elle été vérifiée jusqu'à présent ?"** —
  Ma réponse honnête d'abord (manuellement, voir [tests.md](tests.md)), puis ma correction : dossier
  `tests/` (pytest), 24 tests (RBAC, qualité de données, garde-fou de versioning de modèle). En
  mettant en place la CI qui en découle (voir plus bas), j'ai immédiatement révélé un bug réel et
  jusque-là invisible chez moi : `/analytics/overview` plantait (500) sur une base sans données
  (`GROUP BY`/`LIMIT 1` renvoyant zéro ligne, pas une ligne de `NULL`) — je ne l'avais jamais
  remarqué en développement car ma base de travail a toujours eu des données. Je l'ai corrigé dans
  `api/routers/analytics.py`.
- **"Droit à l'oubli par anonymisation : à rattacher explicitement au texte RGPD."** — J'ai réécrit
  [rgpd.md](rgpd.md) : base légale explicite (article 17(3)(d) + garanties de l'article 89(1)), et
  j'ai corrigé une affirmation trop forte de ma version précédente ("la ligne cesse d'être une
  donnée personnelle") en distinguant anonymisation démontrée vs pseudonymisation — mon traitement
  actuel est plus honnêtement le second, en l'absence d'analyse de k-anonymat que je n'ai pas menée
  sur les attributs comportementaux restants.
- **"Rien sur le versioning des modèles : un modèle moins bon écrase-t-il l'ancien sans rollback ?"**
  — C'était le cas chez moi. J'ai ajouté `analytics/model_registry.py` : promotion conditionnée à
  une métrique non significativement inférieure à la version active (tolérance 0,01 AUC),
  sauvegarde automatique avant chaque promotion, rollback d'un niveau depuis ma page Administration.
  Je l'ai intégré à `churn_model.py` et `customer_360_olist.py`. **Incident** — ma première exécution
  a échoué : `TypeError: unsupported operand type(s) for -: 'decimal.Decimal' and 'float'` (colonnes
  PostgreSQL `NUMERIC` remontées en `decimal.Decimal` par psycopg2, pas en `float`) ; j'ai corrigé ça
  par conversion explicite dans `model_registry.get_active`. J'ai testé de bout en bout (deux
  recalculs successifs + rollback + tentative de second rollback correctement refusée en 409) avant
  de le considérer fonctionnel.
- **"Absence de CI/CD confirmée, déploiement flou."** — J'ai ajouté `.github/workflows/ci.yml`
  (tests à chaque push, sur une base PostgreSQL fraîche — schéma seul, mes CSV Kaggle ne sont pas
  commités) ; je l'ai validé localement en simulant l'environnement CI (conteneur PostgreSQL vierge,
  schéma seul) avant tout push. J'ai ajouté [deploiement.md](deploiement.md), honnête sur ce qui me
  manque encore (CD réel : je n'ai pas de cible d'hébergement pour ce projet, que je documente comme
  choix de périmètre que j'assume, pas comme angle mort).
- **"Le seuil de 200 produits n'est justifié par aucune analyse de la distribution réelle."** —
  Exact, ma v1 se contentait d'une phrase. J'ai ajouté `analytics/analyse_seuil_bot.py` : je trace la
  distribution complète (échelle log + fonction de survie log-log), et je recalcule le pipeline de
  recommandation en entier pour 5 seuils candidats (100/150/200/300/500). Résultat honnête dans les
  deux sens : pas de cassure nette dans mes données (queue continue, pas un mélange de deux
  populations séparables), mais mon résultat final (couverture catalogue, volume de recommandations)
  est stable sur toute la plage testée (+0,7 point de couverture entre 100 et 500). 200 est donc un
  choix robuste dans une plage stable chez moi, pas une valeur "optimale" dérivée d'une cassure qui
  n'existe pas — ma v1 le laissait croire à tort, je corrige ça dans
  [limitations-methodologiques.md](limitations-methodologiques.md).

## Sécurité : 4 lacunes identifiées, traitées (09/11/2026)

En répondant à une question sur l'état de la sécurité, j'avais moi-même listé 4 lacunes connues.
Je les ai corrigées plutôt que de les laisser comme limites déclarées :

- **Révocation de jeton** : `api/deps.py` revérifie maintenant l'existence du compte en base à
  chaque requête au lieu de faire confiance au jeton jusqu'à son expiration. Testé
  (`test_deleted_account_token_is_revoked_immediately`).
- **Anti-bruteforce sur `/auth/login`** : nouveau `api/rate_limit.py` (verrouillage par compte et
  par IP après trop d'échecs, remise à zéro après un succès). Testé.
- **Gestion des secrets via Vault** : `api/secrets_provider.py` (+ jumeau côté `analytics/`) lit
  `DATABASE_URL`/`JWT_SECRET_KEY` depuis HashiCorp Vault quand disponible, avec repli sur `.env`.
  **Incident non résolu localement** : le conteneur Vault plante au démarrage sur ma machine
  (bug runtime Go lié à `mlock`/`IPC_LOCK` sous Docker Desktop/WSL2, confirmé indépendant de ma
  configuration après plusieurs tentatives ciblées) ; a aussi fait planter le démon Docker Desktop
  deux fois pendant le diagnostic (système de fichiers interne corrompu, résolu par redémarrage
  complet). J'ai déplacé la validation de bout en bout vers la CI (vrai Linux), où Vault démarre
  normalement — voir [securite.md](securite.md) pour le détail complet du diagnostic.
- **Analyse de k-anonymat** : nouveau `analytics/analyse_k_anonymat.py`. Résultat honnête : stable
  avec 2 à 4 attributs comportementaux (k minimum ≥ 20), mais 0,93% des clients deviennent
  uniquement identifiables (k=1) en combinant 6 attributs — je documente ça comme une vraie limite
  de mon anonymisation plutôt qu'une anonymisation garantie, voir
  [rgpd.md](rgpd.md#analyse-de-k-anonymat-sur-les-attributs-restants-retour-de-soutenance).

Nombre de tests : 24 → 27 (3 nouveaux tests de sécurité dans `tests/test_auth_rbac.py`).

## Ce qui me reste à faire (non commencé)

CD (déploiement continu) — je n'ai pas de cible d'hébergement pour ce projet, voir
[deploiement.md](deploiement.md). Mon monitoring de drift dispose d'une fondation
(`analytics.model_metrics_history`, `analytics.model_registry`) mais je n'ai encore aucun tableau de
bord ni alerte automatique qui l'exploite.

## Tests : unitaires analytics, dashboard, performance (09/11/2026)

Trois manques que j'avais moi-même listés ci-dessus (logique `analytics/*.py` non testée
isolément, dashboard React sans aucun test, aucun test de charge) — j'ai décidé de ne pas héberger
ce projet (donc pas de CD), mais j'ai comblé les trois manques de tests :

- **49 nouveaux tests unitaires purs sur `analytics/*.py`** (`tests/unit/`) : pour pouvoir charger
  chaque script sans base de données, j'ai déplacé `from config import get_engine` de l'en-tête de
  chaque script vers l'intérieur de `main()`, et j'ai extrait 4 fonctions pures qui étaient
  mélangées avec du code d'accès base : `compute_rules` (`market_basket_olist.py`),
  `proba_to_risk_level` (`churn_model.py`), `label_and_censor` et `apply_category_fallback`
  (`customer_360_olist.py`). Changement mécanique, comportement inchangé — revérifié en relançant
  chaque script en conditions réelles après coup. Nouveau helper `load_analytics_module()` dans
  `tests/conftest.py` : charge un module par chemin direct (`importlib`) et l'enregistre dans
  `sys.modules` sous son propre nom, sans jamais toucher `sys.path` (`api/config.py` et
  `analytics/config.py` portent le même nom de module mais un contenu différent — les mélanger
  aurait fait résoudre le mauvais `config` selon l'ordre d'exécution des tests).
- **45 nouveaux tests dashboard** (Vitest + React Testing Library) : `utils/csv.js`, `api.js`,
  `AuthContext`, `useApiQuery`, et les composants `StatTile`, `AlertBanner` (les 4 règles de seuils
  métier une par une), `AnomalyBanner`, `ExportCsvButton`, `ProtectedRoute`.
- **Test de charge (Locust)** : a trouvé un vrai bug, pas juste produit des chiffres. À 20
  utilisateurs simulés, `api/config.py` utilisait les réglages de pool SQLAlchemy par défaut (15
  connexions au total) → 8,2% d'échecs et jusqu'à 34 secondes de latence
  (`sqlalchemy.exc.TimeoutError: QueuePool limit ... reached`). Corrigé avec `pool_size=20,
  max_overflow=20`. Après correctif : 0% d'échecs, latence max 5,2 secondes. Détail complet :
  [performance.md](performance.md).

Nombre de tests : 27 → 76 côté Python (+ 45 côté dashboard, nouveau).

Détour non prévu pendant cette session : mon disque C: s'est retrouvé à 0 octet libre (conséquence
des crash-loops Vault d'une session précédente), ce qui a bloqué Docker/Postgres pendant un moment —
résolu en vidant la corbeille Windows et en nettoyant le cache Docker (`docker system prune -af`),
sans toucher à aucune donnée de travail.

## Simulation d'attaque sur mon API (09/11/2026)

Documenter mes défenses de sécurité (voir [securite.md](securite.md)) ne prouve pas qu'elles
tiennent sous tentative réelle d'exploitation — je me suis mis à la place d'un attaquant et j'ai
écrit `tests/test_security_attacks.py` (40 tests) sur quatre familles de vecteurs : bruteforce /
anti-bruteforce (énumération de comptes, credential stuffing contre mon seuil par IP), falsification
de JWT (signature altérée, mauvais secret, attaque `alg: none`, claim `role` remonté à `admin`,
jeton expiré), injection SQL (payloads classiques sur les identifiants de connexion et sur un
paramètre de chemin/requête de `/analytics/rfm`), et élévation de privilèges (balayage systématique
de tous mes endpoints admin avec un jeton `analyst` et sans jeton).

Résultat honnête : les 40 tentatives échouent proprement, rien à exploiter. Je documente ça comme
une validation réelle de mes défenses plutôt qu'une description de leur intention — voir
[securite.md#simulation-dattaque-pentest-interne](securite.md#simulation-dattaque-pentest-interne).

Nombre de tests : 76 → 116 côté Python.

## Exposition réseau de PostgreSQL et Vault corrigée (09/11/2026)

En me demandant si des pare-feu avaient du sens pour ce projet, j'ai vérifié mon
`docker-compose.yml` : `5432` (PostgreSQL) et `8200` (Vault) étaient publiés sans adresse d'écoute
précisée, donc sur `0.0.0.0` par défaut -- accessibles depuis n'importe où sur mon réseau local, pas
seulement depuis ma machine. Corrigé en restreignant les deux mappings à `127.0.0.1`. Un vrai
pare-feu réseau (groupes de sécurité côté hébergeur) reste pertinent pour un vrai déploiement, mais
n'a pas d'objet concret tant que je n'héberge pas ce projet (voir
[deploiement.md](deploiement.md)) -- ce correctif-ci, en revanche, concernait ma machine de
développement elle-même, indépendamment de toute question d'hébergement. Détail :
[securite.md](securite.md#exposition-réseau-de-postgresql-et-vault-retour-de-soutenance).

## Hébergement réel : Oracle Cloud Always Free + déploiement continu (11/11/2026)

J'ai tranché la question du CD : pas de nom de domaine payant, donc je retiens
[DuckDNS](https://www.duckdns.org/) (sous-domaine gratuit) + Let's Encrypt via Caddy, et Oracle
Cloud Infrastructure Always Free comme hébergeur (vraie VM gratuite durablement, forme Ampere A1 en
ARM64, jusqu'à 4 OCPU/24 Go de RAM gratuits). Voir [deploiement.md](deploiement.md) pour le détail
complet (mise en place du serveur, les deux pare-feu à synchroniser chez Oracle -- Security List du
VCN *et* `iptables` du système, un piège que je n'ai découvert qu'en le faisant) et
[securite.md](securite.md) pour la suite de la question du pare-feu réseau.

J'ai conteneurisé mon API (nouveau `api/Dockerfile`, elle tournait jusqu'ici directement via
`uvicorn` sur l'hôte) et mon dashboard (nouveau `dashboard/Dockerfile`, multi-étapes : build React
puis servi par Caddy, qui gère aussi le reverse proxy vers l'API et le HTTPS automatique). Nouveau
`docker-compose.prod.yml`, distinct de mon fichier de dev local : `db` et `vault` n'y exposent plus
aucun port sur l'hôte (même pas `127.0.0.1`), puisque l'API tourne elle aussi en conteneur sur le
même réseau Docker désormais -- seul Caddy publie 80/443.

**Incident, trouvé en testant la construction de mon image dashboard avant de déployer** :
`npm ci` échouait dans le conteneur (`Missing: @emnapi/core@1.11.3 from lock file`), alors que
`npm install` fonctionnait normalement sur ma machine. Diagnostic : mon `package-lock.json`
contenait une sous-arborescence de dépendances optionnelles (liée à des binaires natifs de Rollup)
légèrement désynchronisée de `package.json` -- `npm install` tolère ça silencieusement, `npm ci`
(strict, utilisé dans mon Dockerfile comme en CI) non. J'ai d'abord suspecté un problème
musl/Alpine (incompatibilité native connue entre Rollup et Alpine), changé pour une image
`node:20-slim`, mais l'erreur persistait à l'identique -- ce n'était donc pas la cause. Corrigé en
régénérant `package-lock.json` entièrement à partir de zéro (suppression puis `npm install`), ce
qui a aussi fait disparaître 6 vulnérabilités signalées par `npm audit` qui traînaient dans
l'ancienne arborescence. Mes 45 tests dashboard repassent à l'identique après régénération.

**Vérification de la compatibilité ARM64**, le vrai risque technique du choix Ampere A1 : j'ai
lancé une construction croisée de mon image API pour `linux/arm64` (émulation QEMU via `docker
buildx`) -- très lente (`torch` sous émulation complète, chaque instruction Python simulée), donc
je l'ai complétée par une vérification directe et rapide auprès de l'index PyPI : `torch` 2.15.0 et
`psycopg2-binary` 2.9.13 publient tous les deux de vraies roues précompilées pour
`linux/aarch64` en Python 3.12 (ma version dans `api/Dockerfile`) -- pas de compilation depuis les
sources nécessaire sur le serveur réel (ARM natif, sans la lenteur de l'émulation).

## Déploiement réel sur Scaleway : bascule, incidents et mise en ligne vérifiée (12/11/2026)

**Je n'ai pas pu aller au bout d'Oracle Cloud** : leur vérification de paiement a rejeté ma carte
(néobanque), un problème documenté comme fréquent chez ce fournisseur, indépendant de ma
configuration. Plutôt que d'insister, j'ai basculé sur **Scaleway** (société française) -- carte
acceptée sans friction, architecture x86_64 (plus simple que l'ARM64 que je visais côté Oracle),
instance `DEV1-S` (2 vCPU, 2 Go RAM, ~12 €/mois si elle tourne en continu -- je renonce ici à la
gratuité permanente d'Oracle Always Free, choix budgétaire assumé pour la durée de mon projet).

**Incident de quota sur un compte tout juste créé** : ma première tentative de création d'instance
`DEV1-S` a été refusée ("quota(s) exceeded"), alors même que paiement et identité venaient d'être
validés. J'ai diagnostiqué en créant d'abord une instance minimale (`STARDUST1-S`) dans une autre
zone, qui est passée -- preuve que mon compte n'était pas bloqué à zéro instance. J'ai ensuite
utilisé "Change offer" pour upgrader cette instance déjà créée vers `DEV1-S`, ce qui a fonctionné
alors que la création directe d'une nouvelle instance `DEV1-S` échouait toujours -- contournement
qui m'a évité d'attendre une réponse du support.

**Mise en place du serveur** : contrairement à Oracle, l'image Ubuntu Scaleway n'a aucun pare-feu
système actif par défaut (`ufw status` = `inactive`) -- pas le piège à deux niveaux que j'avais
anticipé. Je l'ai quand même activé moi-même par principe de défense en profondeur. Avec seulement
2 Go de RAM et aucun swap par défaut, j'ai ajouté 2 Go de swap persistant avant de déployer quoi que
ce soit, pour ne pas risquer un arrêt brutal d'un conteneur sous pression mémoire.

**Allègement de mon image API** : à 2,78 Go pour l'image construite, j'ai créé `api/requirements.txt`
(sous-ensemble du fichier racine, sans `jupyter`/`pytest`/`locust`, jamais utilisés à l'exécution) --
gain modeste mais réel (2,43 Go), `torch`/`scipy`/`pandas` restant l'essentiel du poids, légitimement
nécessaire.

**Deux bugs Caddy trouvés en déployant pour de vrai, invisibles à la simple lecture de ma config** :
1. Mes directives top-level (`reverse_proxy`, `try_files`, `file_server`) ne s'exécutent pas dans
   l'ordre où je les ai écrites -- Caddy applique un ordre interne fixe où `try_files` passe avant
   `reverse_proxy`, donc toute requête (y compris `/auth/login`) était réécrite vers `index.html`
   avant même que ma règle `@api` ne soit évaluée. `/health` renvoyait du HTML, pas mon JSON attendu.
2. Ma première correction (blocs `handle` explicitement ordonnés) a introduit une deuxième erreur :
   `handle` n'accepte qu'un chemin unique ou un matcher nommé, pas une liste de chemins brute --
   Caddy plantait en boucle au démarrage (erreur de parsing visible dans ses logs).

Corrigé avec un matcher nommé `@api` réutilisé par `handle @api { ... }`, validé localement avec
`caddy validate` avant tout redéploiement (pour ne plus refaire d'aller-retour serveur sur une
simple erreur de syntaxe).

**Résultat, vérifié de bout en bout, pas juste supposé** : https://plateforme-ecommerce.duckdns.org
répond en HTTPS avec un vrai certificat Let's Encrypt (émis automatiquement par Caddy, vérifié avec
`openssl s_client`), `/health` renvoie `{"status":"ok"}`, `/auth/login` atteint bien l'API (422 sur
un corps vide, pas une redirection HTML), le dashboard se charge. Ce n'est plus une infrastructure
"prête à déployer" comme je le documentais avant cette session -- c'est un déploiement réel,
observé en fonctionnement.

**Incident sur le pipeline de déploiement continu lui-même, découvert en le testant pour de vrai.**
Mon premier déclenchement réel (push sur `main`) a échoué en 6 secondes sur le job `deploy`, alors
que mon script fonctionne parfaitement en exécution manuelle identique -- la différence ne venait
donc pas de `deploy.sh`. Le log exact de l'action (`ssh: ParsePrivateKey: ssh: no key found`)
pointait vers le secret GitHub `DEPLOY_SSH_KEY` lui-même, pas vers ma configuration serveur :
collé manuellement depuis un terminal, son contenu avait dû perdre un caractère ou inclure une
ligne de prompt parasite -- un risque inhérent au copier-coller manuel d'un secret multi-lignes,
que je n'avais pas anticipé. Corrigé en recopiant la clé directement dans le presse-papier
(`Get-Content ... -Raw | Set-Clipboard`) plutôt qu'en la sélectionnant à la main dans un terminal,
pour éliminer cette classe d'erreur plutôt que de la corriger au cas par cas.
