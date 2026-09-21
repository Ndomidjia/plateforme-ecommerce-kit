# Architecture

## Principe général (Plan A)

Trois sources de données indépendantes, chacune avec son rôle propre, convergeant vers une seule
zone de résultats (`analytics`) consommée par une seule API et un seul dashboard.

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

## Pourquoi une fusion brute des 3 datasets est impossible

Les 3 populations de clients sont **distinctes** : clients Olist (Brésil, transactions réelles
2016-2018) ≠ visiteurs Retailrocket (plateforme anonyme, clickstream 2015) ≠ profils du dataset
churn (données synthétiques/génériques, sans lien avec une vraie plateforme). Il n'existe **aucune
colonne commune** entre ces 3 sources — pas d'email, pas d'identifiant utilisateur partagé, pas de
référence produit commune. Un `JOIN` SQL entre elles ne relierait rien de réel : soit il ne
retournerait aucune ligne, soit il produirait des correspondances arbitraires sans signification
(fabriquer une fausse donnée plutôt que fusionner une vraie donnée). Toute tentative de fusion
ligne-à-ligne serait donc scientifiquement malhonnête, quelle que soit la méthode utilisée.

## Ce qui a été fait à la place : fusion au niveau des résultats, sur Olist (`analytics.customer_360`)

Remarque reçue en cours de projet : *"il faut fusionner les données"*. Interprétation retenue,
validée avec l'encadrant : fusionner non pas les **lignes** des 3 datasets (impossible, voir
ci-dessus), mais les **résultats d'analyse** produits sur **une même population** — les clients
Olist, seule source avec assez de profondeur (vraies transactions, avis texte, géographie) pour
porter une vue client unifiée.

Concrètement (`analytics/customer_360_olist.py`), pour chaque client Olist :
- son **segment RFM** (déjà calculé)
- un **proxy de risque de non-réachat** — pas un vrai churn, une estimation dérivée du comportement
  d'achat lui-même (seuil de 126 jours dérivé empiriquement de la distribution réelle des délais de
  réachat, pas choisi au hasard), en réutilisant la **méthodologie** validée sur le dataset churn
  (Random Forest, gestion du déséquilibre de classes, validation croisée) — la technique est
  transférée, pas les données
- le **sentiment moyen** de ses avis (déjà calculé)
- une **recommandation de catégorie** (dérivée des règles d'association, uniquement quand une règle
  a un lift ≥ 1 — cohérent avec la limite déjà documentée sur le market basket)

Résultat combiné dans une seule table, exposée via `/analytics/customer-360` et la page dashboard
"Vue client 360°". Voir [limitations-methodologiques.md](limitations-methodologiques.md) pour
l'évaluation honnête de ce module (résultat négatif : AUC = 0,57, quasi non prédictif — assumé et
documenté plutôt que caché).

## Pourquoi Retailrocket et le dataset churn ne sont PAS fusionnés directement

Choix réfléchi, pas un abandon :

- **Retailrocket** reste un module de recherche comportementale à part (funnel, filtrage
  collaboratif item-item). Aucune fusion possible avec Olist : autre plateforme, autre pays, autre
  période, aucun identifiant partagé. Sa valeur est **méthodologique et comparative** (mesurer un
  funnel de conversion, du filtrage collaboratif sur du clickstream) — des techniques transférables
  conceptuellement à d'autres contextes, mais pas des données transférables.
- **Le dataset churn** change de rôle plutôt que d'être fusionné : il reste la **base
  d'apprentissage de la méthode** (le seul dataset du projet avec une vraie étiquette de départ
  client), utilisé pour valider l'approche Random Forest + gestion du déséquilibre + validation
  croisée sur des données où l'on connaît la bonne réponse, **avant** de transférer cette méthode
  (pas les données) au proxy construit sur Olist où l'on ne l'a pas.

Fusionner ces deux sources aux clients Olist aurait exigé d'inventer une correspondance entre des
populations sans aucun lien réel — donc de fabriquer de la donnée. Le choix retenu (garder leur
rôle propre, transférer la méthode plutôt que les lignes) est plus rigoureux et plus défendable en
soutenance qu'une fusion forcée.

## Pourquoi ce découpage par module

| Dataset | Modules | Raison du choix |
|---|---|---|
| Olist | RFM, market basket, sentiment | `customer_unique_id` permet de suivre un client réel (contrairement à `customer_id`, qui change par commande) ; commentaires texte disponibles pour le NLP |
| Retailrocket | Funnel, reco collaborative | Événements `view/addtocart/transaction` horodatés, volume suffisant (2,76M événements) pour du filtrage collaboratif |
| Churn | Scoring + plan d'action | Dataset déjà labellisé (`Churned`), conçu pour la classification supervisée |

## Stack technique

- **Python 3.11+** (testé sur 3.14), **pandas/SQLAlchemy** pour l'ETL et les modules analytics
- **PostgreSQL 16** (Docker) — un schéma par domaine, pas d'ORM applicatif : SQL explicite via
  `sqlalchemy.text()`, choisi pour rester lisible et compréhensible ligne à ligne (objectif
  pédagogique du projet) plutôt qu'une couche d'abstraction ORM
- **scikit-learn** (Random Forest churn), **mlxtend** (règles d'association), **PyTorch** (réseau
  de neurones pour l'analyse de sentiment)
- **FastAPI** — API Core SQLAlchemy (pas d'ORM déclaratif), JWT (PyJWT) + bcrypt, RBAC à 2 rôles
- **React + Vite** — dashboard, pas de framework UI lourd, palette de couleurs validée
  (voir skill dataviz du projet) pour l'accessibilité daltonisme

## RBAC (2 rôles)

- `admin` : tout ce que voit `analyst`, plus RGPD (export/anonymisation), gestion des comptes API,
  recalcul à la demande des modules ML
- `analyst` : lecture des résultats analytics (RFM, churn, funnel, reco, règles, sentiment) +
  calculateur de rétention

Décision : un modèle à 2 rôles a été préféré à un modèle plus fin (ex. rôle marketing séparé) pour
rester proportionné à la portée du projet, la distinction structurante étant "peut agir sur des
données personnelles / le système" vs "consulte des résultats agrégés".

## Recalcul à la demande (limite connue)

Le endpoint `/admin/recompute/{module}` lance un script `analytics/*.py` via `subprocess.Popen`,
suivi par un dictionnaire en mémoire dans le processus API. Cette approche est volontairement
simple pour un projet à instance unique (un seul worker uvicorn) : elle ne survivrait pas à un
redémarrage de l'API ni à plusieurs workers. Une vraie file de tâches (Celery, RQ, ou équivalent)
serait nécessaire en production — bonne piste d'amélioration à mentionner en soutenance.
