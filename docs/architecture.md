# Architecture

## Principe général (Plan A)

J'ai conçu trois sources de données indépendantes, chacune avec son rôle propre, convergeant vers
une seule zone de résultats (`analytics`) que je consomme via une seule API et un seul dashboard.

```
olistbr/brazilian-ecommerce (Kaggle)     retailrocket/ecommerce-dataset (Kaggle)     ecommerce_customer_churn_dataset.csv
            │                                          │                                          │
            ▼                                          ▼                                          ▼
      schéma olist                            schéma retailrocket                          schéma churn
   (9 tables relationnelles)                  (clickstream events)                    (50 000 profils labellisés)
            │                                          │                                          │
   ┌────────┴────────┐                        ┌────────┴────────┐                                 │
   ▼                 ▼                        ▼                 ▼                                 ▼
  RFM          market basket                funnel        reco collaborative                 scoring churn
  sentiment (deep learning)               conversion         item-item CF                  + plan d'action marketing
   │                 │                        │                 │                                 │
   └─────────────────┴────────────────────────┴─────────────────┴─────────────────────────────────┘
                                              ▼
                                    schéma analytics (zone de convergence)
                                              ▼
                                       API FastAPI (JWT + RBAC)
                                              ▼
                                    Dashboard React (admin / analyst)
```

## Pourquoi je n'ai pas fait de fusion brute des 3 datasets

Les 3 populations de clients sont **distinctes** : clients Olist (Brésil, transactions réelles
2016-2018) ≠ visiteurs Retailrocket (plateforme anonyme, clickstream 2015) ≠ profils du dataset
churn (données synthétiques/génériques, sans lien avec une vraie plateforme). Il n'existe **aucune
colonne commune** entre ces 3 sources — pas d'email, pas d'identifiant utilisateur partagé, pas de
référence produit commune. Un `JOIN` SQL entre elles ne relierait rien de réel : soit il ne
retournerait aucune ligne, soit il produirait des correspondances arbitraires sans signification
(fabriquer une fausse donnée plutôt que fusionner une vraie donnée). Toute tentative de fusion
ligne-à-ligne aurait donc été scientifiquement malhonnête de ma part, quelle que soit la méthode
utilisée.

## Ce que j'ai fait à la place : fusion au niveau des résultats, sur Olist (`analytics.customer_360`)

J'ai reçu une remarque en cours de projet : *"il faut fusionner les données"*. Interprétation que
j'ai retenue, validée avec mon encadrant : fusionner non pas les **lignes** des 3 datasets
(impossible, voir ci-dessus), mais les **résultats d'analyse** que je produis sur **une même
population** — les clients Olist, seule source avec assez de profondeur (vraies transactions, avis
texte, géographie) pour porter une vue client unifiée.

Concrètement (`analytics/customer_360_olist.py`), je calcule pour chaque client Olist :
- son **segment RFM** (déjà calculé)
- un **proxy de risque de non-réachat** — pas un vrai churn, une estimation que je dérive du
  comportement d'achat lui-même (seuil de 126 jours dérivé empiriquement de la distribution réelle
  des délais de réachat, pas choisi au hasard), en réutilisant la **méthodologie** que j'ai validée
  sur le dataset churn (Random Forest, gestion du déséquilibre de classes, validation croisée) — je
  transfère la technique, pas les données
- le **sentiment moyen** de ses avis (déjà calculé)
- une **recommandation de catégorie** (dérivée des règles d'association, uniquement quand une règle
  a un lift ≥ 1 — cohérent avec la limite que je documente déjà sur le market basket)

Je combine le résultat dans une seule table, exposée via `/analytics/customer-360` et la page
dashboard "Vue client 360°". Voir [limitations-methodologiques.md](limitations-methodologiques.md)
pour mon évaluation honnête de ce module (résultat négatif : AUC = 0,58, quasi non prédictif — que
j'assume et documente plutôt que de le cacher).

## Pourquoi je n'ai PAS fusionné Retailrocket et le dataset churn directement

Choix réfléchi de ma part, pas un abandon :

- **Retailrocket** reste chez moi un module de recherche comportementale à part (funnel, filtrage
  collaboratif item-item). Aucune fusion possible avec Olist : autre plateforme, autre pays, autre
  période, aucun identifiant partagé. Sa valeur est **méthodologique et comparative** (mesurer un
  funnel de conversion, du filtrage collaboratif sur du clickstream) — des techniques que je peux
  transférer conceptuellement à d'autres contextes, mais pas des données transférables.
- **Le dataset churn** change de rôle chez moi plutôt que d'être fusionné : il reste ma **base
  d'apprentissage de la méthode** (le seul dataset du projet avec une vraie étiquette de départ
  client), que j'utilise pour valider mon approche Random Forest + gestion du déséquilibre +
  validation croisée sur des données où je connais la bonne réponse, **avant** de transférer cette
  méthode (pas les données) au proxy que je construis sur Olist où je ne l'ai pas.

Fusionner ces deux sources aux clients Olist m'aurait obligé à inventer une correspondance entre des
populations sans aucun lien réel — donc à fabriquer de la donnée. Le choix que j'ai retenu (garder
leur rôle propre, transférer la méthode plutôt que les lignes) est plus rigoureux et plus
défendable en soutenance qu'une fusion forcée.

## Pourquoi j'ai découpé le projet ainsi, module par module

| Dataset | Modules | Raison du choix |
|---|---|---|
| Olist | RFM, market basket, sentiment | `customer_unique_id` me permet de suivre un client réel (contrairement à `customer_id`, qui change par commande) ; commentaires texte disponibles pour le NLP |
| Retailrocket | Funnel, reco collaborative | Événements `view/addtocart/transaction` horodatés, volume suffisant (2,76M événements) pour du filtrage collaboratif |
| Churn | Scoring + plan d'action | Dataset déjà labellisé (`Churned`), conçu pour la classification supervisée |

## Ma stack technique

- **Python 3.11+** (testé sur 3.14), **pandas/SQLAlchemy** pour mon ETL et mes modules analytics
- **PostgreSQL 16** (Docker) — un schéma par domaine, pas d'ORM applicatif : j'écris du SQL explicite
  via `sqlalchemy.text()`, un choix que j'ai fait pour rester lisible et compréhensible ligne à ligne
  (objectif pédagogique de mon projet) plutôt qu'une couche d'abstraction ORM
- **scikit-learn** (Random Forest churn), **mlxtend** (règles d'association), **PyTorch** (réseau
  de neurones pour mon analyse de sentiment)
- **FastAPI** — API Core SQLAlchemy (pas d'ORM déclaratif), JWT (PyJWT) + bcrypt, RBAC à 2 rôles
- **React + Vite** — mon dashboard, pas de framework UI lourd, palette de couleurs que j'ai validée
  (voir skill dataviz du projet) pour l'accessibilité daltonisme

## RBAC (2 rôles)

- `admin` : tout ce que voit `analyst`, plus RGPD (export/anonymisation), gestion des comptes API,
  recalcul à la demande des modules ML
- `analyst` : lecture des résultats analytics (RFM, churn, funnel, reco, règles, sentiment) +
  calculateur de rétention

Décision : j'ai préféré un modèle à 2 rôles à un modèle plus fin (ex. rôle marketing séparé) pour
rester proportionné à la portée de mon projet, la distinction structurante étant "peut agir sur des
données personnelles / le système" vs "consulte des résultats agrégés".

## Recalcul à la demande (limite que je connais)

Mon endpoint `/admin/recompute/{module}` lance un script `analytics/*.py` via `subprocess.Popen`,
suivi par un dictionnaire en mémoire dans le processus API. J'ai volontairement gardé cette approche
simple pour un projet à instance unique (un seul worker uvicorn) : elle ne survivrait pas à un
redémarrage de l'API ni à plusieurs workers. Une vraie file de tâches (Celery, RQ, ou équivalent) me
serait nécessaire en production — bonne piste d'amélioration que je mentionne en soutenance.

## Versioning et rollback des modèles (`analytics/model_registry.py`)

Un recalcul à la demande relance chez moi un script d'entraînement complet (`churn_model.py`,
`customer_360_olist.py`) — donc un nouveau modèle, potentiellement moins bon que celui en
production (mauvais tirage aléatoire, dérive des données, régression introduite par un changement
de code). Sans garde-fou, le comportement par défaut de mes scripts (TRUNCATE + réécriture des
tables `analytics.*`) écraserait silencieusement le modèle actif, sans comparaison ni retour
arrière possible — c'était le cas jusqu'à ce que j'ajoute ce module.

Mon principe (voir docstring de `analytics/model_registry.py` pour le détail) :

1. **Décision de promotion** — je compare la métrique hors échantillon (AUC) de la nouvelle
   exécution à celle de la version active (`analytics.model_registry`). Je la promeus si elle n'est
   pas inférieure de plus de 0,01 (je tolère le bruit naturel d'un ré-entraînement sans laisser
   passer une vraie régression) ; sinon je la rejette.
2. **Si je la rejette** : je ne touche pas aux tables live (`churn_scores`, `customer_360`...) — la
   version active continue de servir l'API/le dashboard. J'écris le résultat rejeté à part
   (`<table>_candidate`) pour inspection plutôt que de le jeter silencieusement.
3. **Si je la promeus** : je sauvegarde d'abord l'état sortant (`<table>_previous`), puis je mets à
   jour les tables live. Un rollback **d'un seul niveau** est possible depuis ma page Administration
   (`POST /admin/models/{model_name}/rollback`), qui restaure ce snapshot.

J'ai choisi un rollback à un niveau plutôt qu'un historique complet versionné (type MLflow) :
proportionné à l'échelle de mon projet — voir
[limitations-methodologiques.md](limitations-methodologiques.md). L'historique COMPLET des
métriques de chaque exécution (promue ou non), lui, reste append-only et jamais purgé dans
`analytics.model_metrics_history`, indépendamment de la profondeur du rollback.
