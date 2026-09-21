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

## Ce qui me reste à faire (non commencé)

CD (déploiement continu) — je n'ai pas de cible d'hébergement pour ce projet, voir
[deploiement.md](deploiement.md). Étendre ma couverture de tests aux scripts `analytics/*.py`
eux-mêmes (seul leur résultat en base est testé actuellement chez moi) et à mon dashboard React
(aucun test). Mon monitoring de drift dispose d'une fondation (`analytics.model_metrics_history`,
`analytics.model_registry`) mais je n'ai encore aucun tableau de bord ni alerte automatique qui
l'exploite.
