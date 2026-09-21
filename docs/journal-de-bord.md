# Journal de bord

Chronologie des décisions prises et des incidents rencontrés pendant le développement. Utile pour
justifier des choix en soutenance ("pourquoi avez-vous fait X plutôt que Y ?").

## Mise en route

- Revue de cohérence du repo existant (SQL, ETL) avant de démarrer : aucune incohérence bloquante
  trouvée, ordre de chargement des tables Olist respecte les contraintes de clé étrangère.
- Python 3.14 (plus récent que le 3.11+ visé initialement) : toutes les dépendances (dont
  `psycopg2-binary` et, plus tard, `torch`) se sont installées sans problème.
- Docker Desktop non démarré au premier essai de `docker compose up` — relancé manuellement.

## Modules d'analyse

- **RFM** : décision de filtrer sur `order_status = 'delivered'` uniquement (commande annulée ≠
  comportement d'achat réel). Découverte du problème de fréquence mono-achat (97%) → mapping manuel
  du F-score plutôt que quintiles.
- **Market basket** : niveau catégorie choisi plutôt que produit individuel (3197 commandes
  multi-produits diluées sur 32 951 produits → support quasi nul). Seuil de support abaissé
  itérativement (0,0003 → 0,00008) pour obtenir des paires exploitables. Décision de ne pas filtrer
  sur lift ≥ 1 pour l'écriture finale (une seule règle aurait survécu) : toutes les règles écrites,
  lift en colonne pour filtrage en aval.
- **Reco collaborative** : **incident** — première requête SQL (filtrage par sous-requête
  GROUP BY/HAVING imbriquée) a tourné 1h30 sans terminer (plan d'exécution pathologique). Requête
  tuée (`pg_terminate_backend`), réécrite en séparant extraction SQL simple + filtrage pandas :
  descend à 15 secondes. Détection et exclusion des visiteurs à >200 produits distincts (bots).
- **Scoring churn** : comparaison Random Forest vs régression logistique (écart net : AUC 0,92 vs
  0,80) → Random Forest retenu. **Incident** — scoring initial in-sample donnant des probabilités
  artificiellement bimodales (sur-apprentissage) ; corrigé par validation croisée
  (`cross_val_predict`, 5 plis).
- **Sentiment (deep learning)** : ajouté suite à une demande explicite d'intégrer du deep learning
  et de combler un trou du plan initial ("sentiment sur avis" jamais construit). PyTorch installé
  sans problème sur Python 3.14 (wheel `cp314` disponible). Réseau simple (Embedding + mean pooling
  + denses) choisi plutôt qu'un transformer pré-entraîné : évite un téléchargement de plusieurs Go
  et reste entraînable en quelques minutes sur CPU. Validation croisée manuelle (pas de
  `cross_val_predict`, incompatible avec un modèle PyTorch hors wrapper scikit-learn).

## API et sécurité

- RBAC à 2 rôles (`admin`/`analyst`) choisi plutôt qu'un modèle plus fin, pour rester proportionné
  à la portée du projet.
- **Incident** — `passlib[bcrypt]` incompatible avec les versions récentes de la librairie `bcrypt`
  (bibliothèque non maintenue) : remplacé par un usage direct de `bcrypt.hashpw`/`checkpw`.
- **Incident** — dépendance manquante `python-multipart` (requise par
  `OAuth2PasswordRequestForm`) : ajoutée.
- RGPD implémenté d'abord sur `churn` seul (schéma le plus simple), pattern réutilisable ensuite
  pour Olist/Retailrocket. Anonymisation retenue plutôt que suppression complète (voir
  [rgpd.md](rgpd.md)).
- Ordre des routes FastAPI : plusieurs endpoints littéraux (`/churn/summary`,
  `/churn/feature-importance`, `/rfm/summary`...) doivent être déclarés **avant** leurs routes
  paramétrées homonymes (`/churn/{customer_id}`), sous peine d'erreur 422 (FastAPI/Starlette
  matche les routes dans l'ordre de déclaration).

## Dashboard

- React + Vite choisi plutôt que Streamlit (décision explicite de l'utilisateur, malgré le coût de
  développement plus élevé, pour démontrer des compétences full-stack).
- Palette de couleurs et règles de graphiques issues du skill dataviz du projet (validée
  accessibilité daltonisme) plutôt que les couleurs par défaut de `recharts`.
- CORS initialement restreint à `http://localhost:5173`, élargi à `http://127.0.0.1:5173` après un
  problème de connexion (l'origine exacte compte pour le navigateur).
- **Incident** — clés React dupliquées dans les tables Sentiment et Recommandations : les clés
  primaires réelles de `analytics.review_sentiment` et `analytics.item_recommendations` sont
  composites (`review_id`+`order_id`, `item_id`+`recommended_item_id`+`method`) ; une seule colonne
  utilisée comme clé React pouvait collisionner. Corrigé.
- **Incident** — `TypeError` sur le calculateur de rétention : PostgreSQL renvoie un `Decimal` pour
  `SUM(lifetime_value)`, incompatible avec la multiplication par un `float` Python sans conversion
  explicite.
- Aucun outil d'automatisation navigateur disponible au départ dans l'environnement de
  développement : les vérifications visuelles du dashboard ont d'abord été laissées à la charge de
  l'utilisateur (build de production + tests d'API systématiquement vérifiés côté assistant, rendu
  visuel non confirmé directement). Corrigé plus tard via Playwright — voir "Documentation
  illustrée" ci-dessous.

## Fonctionnalités "intelligentes" (itération finale)

- Calculateur de rétention, gestion des utilisateurs, recalcul à la demande : ajoutés suite à une
  demande explicite de séparer les fonctionnalités par rôle.
- Plan d'action marketing par client et détection d'anomalies : ajoutés suite à une demande
  explicite de rendre la plateforme "plus intelligente". Portée volontairement limitée
  (heuristique explicable plutôt que boîte noire, détection sur la période la plus récente plutôt
  qu'un scan rétroactif complet) — voir [limitations-methodologiques.md](limitations-methodologiques.md).

## Documentation illustrée (captures d'écran + document Word)

- Installation de Playwright (piloté sur le Chrome déjà installé, `channel="chrome"`, pas de
  téléchargement de navigateur séparé) pour générer des captures d'écran réelles de chaque page du
  dashboard, connecté en admin, destinées à un document Word pour l'encadrant.
- **Incident, diagnostic en plusieurs étapes** — le graphique "Variables les plus déterminantes"
  (page Scoring churn) restait invisible sur les captures, de façon reproductible (3/3 essais),
  malgré des données propres (vérifiées directement via l'API) et un DOM correct (rectangles SVG
  bien présents, couleur/opacité/géométrie toutes correctes à l'inspection). Cause identifiée après
  inspection du `clipPath` SVG : une capture en `full_page=True` force Playwright à redimensionner
  la fenêtre pour capturer toute la hauteur de page, ce qui déclenche un `ResizeObserver` côté
  `ResponsiveContainer` (Recharts) et relance l'animation d'entrée du graphique — parfois
  interrompue par la capture. Corrigé en fixant une fenêtre haute dès le départ (pas de
  redimensionnement dynamique). Mémoïsation (`useMemo`) des données transformées ajoutée par
  robustesse sur la page Churn (n'a pas résolu ce bug précis, mais reste une bonne pratique évitant
  des recalculs/animations inutiles sur une page à 5 requêtes indépendantes).
- Une fois corrigé, la vérification visuelle a confirmé que **l'ensemble du dashboard s'affiche
  correctement** — première confirmation directe (pas seulement via build + tests API) depuis le
  début du projet.
- Document Word généré avec `python-docx` (page de titre, sommaire, une section par module avec
  définition/rôle/justification/capture d'écran/limite), captures rognées automatiquement à leur
  contenu réel (`Pillow`, en excluant la sidebar de la détection de zone vide — sa couleur de fond
  légèrement différente de la zone de contenu faussait un premier essai de rognage).

## Vue client 360° — réponse à la remarque de l'encadrant ("fusionner les données")

- L'encadrant a demandé de fusionner les 3 datasets. Clarification apportée : impossible
  techniquement (aucun identifiant commun) — voir
  [architecture.md](architecture.md#pourquoi-une-fusion-brute-des-3-datasets-est-impossible).
  Proposition alternative validée avec l'utilisateur puis avec l'encadrant : fusionner les
  *résultats* d'analyse sur les clients Olist plutôt que les lignes brutes.
- **Seuil de non-réachat dérivé empiriquement**, pas choisi au hasard (remarque n°1 de
  l'encadrant) : calcul de la distribution réelle du délai de réachat chez les 2 801 clients Olist
  ayant racheté (médiane 29j, P75 126j, P90 246j) ; seuil retenu = P75 = 126 jours, après
  comparaison chiffrée de l'impact de P75 vs P90 sur le volume de données exploitables et
  l'équilibre des classes.
- **Incident méthodologique auto-corrigé** : une première version de la logique de censure excluait
  à tort des clients ayant déjà racheté (leur issue est pourtant déjà connue), simplement parce que
  pas assez de temps calendaire ne s'était écoulé depuis leur première commande. Corrigé : un client
  est "évaluable" dès que son issue est connue (a racheté dans la fenêtre) OU que suffisamment de
  temps s'est écoulé sans rachat — principe standard de la censure à droite en analyse de survie.
- **Déséquilibre des classes vérifié avec les vrais chiffres** (remarque n°3) : 97,3% "à risque" /
  2,7% "retenus" sur les 67 993 clients évaluables — encore plus extrême que le dataset churn
  (71%/29%), géré avec les mêmes techniques (`class_weight='balanced'`, validation croisée 5 plis).
- **Résultat négatif obtenu et assumé** (remarque n°2) : ROC-AUC = 0,57 (quasi hasard). Décision
  prise avec l'utilisateur (pas décidée seule) : documenter honnêtement et déployer avec un
  avertissement de fiabilité visible en permanence dans le dashboard, plutôt que de cacher le
  résultat ou d'itérer indéfiniment sur les features pour forcer un meilleur score. Interprétation
  retenue : cohérent avec les limites RFM et market basket déjà documentées, le réachat sur une
  marketplace comme Olist semble structurellement peu prévisible à partir des seules données de la
  première commande.
- **Pourquoi Retailrocket et le dataset churn restent séparés** (remarque n°4), documenté
  explicitement dans architecture.md : aucune fusion de données réelle possible, mais leur
  méthodologie (funnel/CF pour Retailrocket, technique de modélisation pour churn) reste réutilisée
  ou transférée — un choix réfléchi, pas un abandon.

## Auto-critique et améliorations (revue experte demandée explicitement)

Suite à une demande explicite de critique honnête du projet, plusieurs faiblesses réelles ont été
identifiées et corrigées plutôt que listées sans suite :

- **Proxy churn (customer_360) remodélisé (v1 → v2)** : la v1 concluait à "quasiment aucun signal"
  après un seul essai (Random Forest, une seule config) — insuffisant pour l'affirmer avec
  confiance. v2 : retrait des features connues seulement après le 1er achat (note d'avis, délai de
  livraison — fuite temporelle qui rendait le module peu déployable même s'il avait mieux marché) ;
  comparaison de 3 configurations (RF avec/sans `class_weight`, Gradient Boosting) au lieu d'une
  seule. **Incident** — `HistGradientBoostingClassifier` a fait échouer le premier essai (`TypeError:
  Sparse data was passed... dense data is required`) : contrairement à Random Forest, il n'accepte
  pas les matrices creuses produites par `OneHotEncoder` ; corrigé avec `sparse_output=False`.
  Résultat : Gradient Boosting légèrement meilleur (ROC-AUC 0,586 vs 0,564/0,557), diagnostic de
  pouvoir prédictif quasi nul confirmé et renforcé par la comparaison, pas juste réaffirmé.
- **Table `analytics.model_metrics_history` ajoutée** (append-only, jamais vidée, contrairement à
  toutes les autres tables `analytics.*`) pour combler l'absence totale d'historique des métriques
  dans le projet — fondation pour le monitoring de drift prévu au plan initial mais jamais préparée
  jusqu'ici. Journalisation ajoutée à `customer_360_olist.py` et `churn_model.py`. La note de
  fiabilité affichée dans le dashboard (page Vue client 360°) est maintenant lue dynamiquement
  depuis cette table plutôt que codée en dur dans l'API — reste juste après un futur recalcul.
- **Repli de recommandation de catégorie ajouté**, puis sa limite immédiatement identifiée et
  documentée : la catégorie de repli (`bed_bath_table`, la plus vendue globalement) se trouve être
  la même que l'unique cible de règle réelle, donc 90% des recommandations affichées sont en fait
  la même suggestion générique. Corrigé côté affichage (dashboard) : distinction visuelle claire
  entre recommandation "(règle)" avec lift réel et "(populaire)" sans lift, pour ne pas laisser
  croire à une personnalisation qui n'existe pas.
- **Bug corrigé** : `customer_360` était absent de la liste des modules relançables depuis la page
  Administration (`MODULE_SCRIPTS` dans `api/routers/admin.py`) — pur oubli lors de sa construction.
- **Incident mineur** : ligne `return anomalies` orpheline retrouvée en toute fin de
  `api/routers/analytics.py` (résidu de copier-coller lors de l'ajout de la section customer-360).
  Ne provoquait pas d'erreur (code mort après un autre `return`, syntaxiquement valide en Python),
  mais aurait pu induire en erreur lors d'une future relecture. Supprimée.
- Non retenu, documenté comme limite assumée plutôt que corrigé (arbitrage temps/bénéfice) : une
  vraie analyse de survie (Kaplan-Meier) pour le calcul du seuil de non-réachat, qui traiterait la
  censure plus rigoureusement que le percentile simple actuellement utilisé.

## Retours de soutenance traités (21/09/2026)

Cinq remarques reçues, traitées une par une plutôt que reportées :

- **"Aucun test automatisé, comment la fiabilité a-t-elle été vérifiée jusqu'à présent ?"** —
  Réponse honnête d'abord (manuellement, voir [tests.md](tests.md)), puis correction : dossier
  `tests/` (pytest), 24 tests (RBAC, qualité de données, garde-fou de versioning de modèle). Mettre
  en place la CI qui en découle (voir plus bas) a immédiatement révélé un bug réel et jusque-là
  invisible : `/analytics/overview` plantait (500) sur une base sans données (`GROUP BY`/`LIMIT 1`
  renvoyant zéro ligne, pas une ligne de `NULL`) — jamais remarqué en développement car la base de
  travail a toujours eu des données. Corrigé dans `api/routers/analytics.py`.
- **"Droit à l'oubli par anonymisation : à rattacher explicitement au texte RGPD."** —
  [rgpd.md](rgpd.md) réécrit : base légale explicite (article 17(3)(d) + garanties de l'article
  89(1)), et une affirmation trop forte de la version précédente ("la ligne cesse d'être une donnée
  personnelle") corrigée en distinguant anonymisation démontrée vs pseudonymisation — le traitement
  actuel est plus honnêtement le second, en l'absence d'analyse de k-anonymat sur les attributs
  comportementaux restants.
- **"Rien sur le versioning des modèles : un modèle moins bon écrase-t-il l'ancien sans rollback ?"**
  — C'était le cas. `analytics/model_registry.py` ajouté : promotion conditionnée à une métrique non
  significativement inférieure à la version active (tolérance 0,01 AUC), sauvegarde automatique
  avant chaque promotion, rollback d'un niveau depuis la page Administration. Intégré à
  `churn_model.py` et `customer_360_olist.py`. **Incident** — première exécution en échec :
  `TypeError: unsupported operand type(s) for -: 'decimal.Decimal' and 'float'` (colonnes
  PostgreSQL `NUMERIC` remontées en `decimal.Decimal` par psycopg2, pas en `float`) ; corrigé par
  conversion explicite dans `model_registry.get_active`. Testé de bout en bout (deux recalculs
  successifs + rollback + tentative de second rollback correctement refusée en 409) avant d'être
  considéré fonctionnel.
- **"Absence de CI/CD confirmée, déploiement flou."** — `.github/workflows/ci.yml` ajouté (tests à
  chaque push, sur une base PostgreSQL fraîche — schéma seul, les CSV Kaggle ne sont pas commités) ;
  validé localement en simulant l'environnement CI (conteneur PostgreSQL vierge, schéma seul) avant
  tout push. [deploiement.md](deploiement.md) ajouté, honnête sur ce qui manque encore (CD réel :
  pas de cible d'hébergement pour ce projet, documenté comme choix de périmètre assumé, pas comme
  angle mort).
- **"Le seuil de 200 produits n'est justifié par aucune analyse de la distribution réelle."** —
  Exact, la v1 se contentait d'une phrase. `analytics/analyse_seuil_bot.py` ajouté : distribution
  complète tracée (échelle log + fonction de survie log-log), et le pipeline de recommandation
  recalculé en entier pour 5 seuils candidats (100/150/200/300/500). Résultat honnête dans les deux
  sens : pas de cassure nette dans les données (queue continue, pas un mélange de deux populations
  séparables), mais le résultat final (couverture catalogue, volume de recommandations) est stable
  sur toute la plage testée (+0,7 point de couverture entre 100 et 500). 200 est donc un choix
  robuste dans une plage stable, pas une valeur "optimale" dérivée d'une cassure qui n'existe pas —
  la v1 le laissait croire à tort, corrigé dans
  [limitations-methodologiques.md](limitations-methodologiques.md).

## Reste à faire (non commencé)

CD (déploiement continu) — pas de cible d'hébergement pour ce projet, voir
[deploiement.md](deploiement.md). Couverture de tests étendue aux scripts `analytics/*.py`
eux-mêmes (seul leur résultat en base est testé actuellement) et au dashboard React (aucun test).
Le monitoring de drift dispose d'une fondation (`analytics.model_metrics_history`,
`analytics.model_registry`) mais aucun tableau de bord ni alerte automatique ne l'exploite encore.
