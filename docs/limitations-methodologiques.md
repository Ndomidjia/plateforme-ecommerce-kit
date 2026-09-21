# Limites méthodologiques connues

Je rassemble dans ce document les limites que j'ai identifiées pendant mon développement, module
par module. Je considère toutes ces limites comme des résultats légitimes à interpréter et à citer
en soutenance, pas des anomalies à cacher — elles disent quelque chose de réel sur mes données.

## RFM (Olist)

**97% des clients Olist n'ont passé qu'une seule commande.** La composante Fréquence de mon RFM est
donc très peu discriminante (quasi tout le monde a F=1). Conséquence technique : un scoring par
quintiles (`pd.qcut`) est inutilisable pour F chez moi — je l'ai remplacé par un mapping manuel à 3
niveaux (1 commande / 2 commandes / 3+ commandes). Les segments nécessitant F≥4 (Champions, Fidèles,
À risque) sont donc mécaniquement très petits (0,04% à 0,13% de ma base), mais économiquement
cohérents : leur panier moyen est 3× supérieur aux clients mono-achat.

**Validation** : cette limite justifie a posteriori la stratégie B que j'avais envisagée (RFM comme
proxy churn plutôt que pilier central de mon analyse comportementale sur Olist).

## Market basket (Olist)

**99,25% des commandes livrées ne portent que sur une seule catégorie.** Sur les 18 paires de
catégories les plus fréquentes en compte brut, une seule a un lift ≥ 1 (`bed_bath_table` ↔
`home_confort`, lift = 1,13, association faible). Ma conclusion analytique : il n'existe quasiment
pas de vrai signal de vente croisée entre catégories sur Olist — un résultat en soi, pas un échec de
ma méthode. J'écris les 36 règles générées (support/confidence/lift) toutes en base, sans filtrage
arbitraire, pour que le lift documente honnêtement l'absence de signal plutôt que de le masquer.

## Reco collaborative item-item (Retailrocket)

**79,5% des visiteurs n'ont interagi qu'avec un seul produit** — aucune contribution à la
co-occurrence. Après avoir nettoyé les visiteurs atypiques (>200 produits distincts, probables
bots/crawlers — 118 visiteurs mais des millions de paires mécaniques si je les garde), ma couverture
finale est de **11,6% du catalogue** (27 259 produits sur 235 061 recommandés). C'est un problème
classique de "cold start catalogue" en filtrage collaboratif, pas un défaut de mon implémentation.

**Le seuil de 200 produits, que j'ai testé — pas juste affirmé (retour de soutenance).** Dans une
première version de mon code, je justifiais ce seuil par une phrase ("118 visiteurs sur 1,4M") sans
montrer la distribution réelle ni vérifier la sensibilité du résultat final à ce choix — mon jury
avait raison, ce n'était pas une justification. J'ai comblé ce manque avec
`analytics/analyse_seuil_bot.py` : je trace la distribution complète du nombre de produits distincts
par visiteur et je recalcule mon pipeline de recommandation en entier pour 5 seuils candidats
(100/150/200/300/500).

![Distribution du nombre de produits distincts consultés par visiteur](assets/seuil_bot_distribution.png)

Deux constats que je tire, honnêtes dans les deux sens :

- **Il n'existe pas de cassure nette dans mes données.** La fonction de survie en échelle log-log
  (graphique de droite) est une courbe lisse, sans coude ni rupture de pente marquée autour de 200 —
  ma queue de distribution est continue (comportement classique de navigation web à longue traîne),
  pas un mélange visible de deux populations (humains vs bots) séparables objectivement. **200 n'a
  donc pas été "trouvé" par une cassure dans mes données — c'était une affirmation implicite
  inexacte dans ma v1, que je corrige ici.**
- **Mon résultat final est en revanche stable sur toute la plage testée**, ce qui est la vraie
  question posée en soutenance :

  | Seuil | Visiteurs exclus | Paires générées | Couverture catalogue |
  |---:|---:|---:|---:|
  | 100 | 79,549% | 110 662 | 11,37% |
  | 150 | 79,545% | 112 640 | 11,48% |
  | **200** | **79,542%** | **114 481** | **11,60%** |
  | 300 | 79,539% | 117 330 | 11,75% |
  | 500 | 79,537% | 124 515 | 12,07% |

  Sur une plage de seuil ×5 (100 à 500), ma couverture catalogue varie de 11,37% à 12,07% (+0,7
  point, +6% relatif) et mon volume de recommandations de +12,5% — une variation graduelle et
  monotone, sans saut. Mon taux de visiteurs exclus, lui, ne bouge quasiment pas (79,54% ± 0,01
  point) : l'essentiel de l'exclusion vient chez moi du plancher `MIN_ITEMS_PER_VISITOR = 2`
  (visiteurs à un seul produit, sans aucune contribution possible à une co-occurrence), pas de la
  borne haute que je teste ici.

**Conclusion que j'assume** : 200 est un choix raisonnable *dans une plage robuste* (mon résultat ne
dépend pas fortement de la valeur exacte entre 100 et 500), mais ce n'est pas une valeur
scientifiquement optimale dérivée d'une cassure objective — parce que cette cassure n'existe pas
dans mes données. Tableau complet reproductible : `docs/assets/seuil_bot_sensibilite.csv` (généré
par `analytics/analyse_seuil_bot.py`, que je peux relancer si mon dataset change).

## Scoring churn

**Biais de sur-apprentissage que j'ai identifié et corrigé** : scorer tous les clients avec un
modèle entraîné sur ces mêmes clients donne des probabilités in-sample artificiellement extrêmes
(proches de 0/1 — répartition initiale que j'avais obtenue : 34 660 low / 890 medium / 14 450 high,
quasi bimodale). J'ai corrigé ça par validation croisée (`cross_val_predict`, 5 plis) : chaque
client est scoré par un modèle qui ne l'a pas vu à l'entraînement, ce qui me donne une répartition
honnête (30 455 / 7 717 / 11 828) cohérente avec l'AUC que je mesure (0,92). Mon modèle est bien
calibré : taux de churn réel de 5,2% (low) à 25,4% (medium) à 92,2% (high).

## Vue client 360° / proxy de risque de non-réachat (Olist)

J'ai ajouté ce module en réponse à une remarque de mon encadrant me demandant de "fusionner les
données" — voir [architecture.md](architecture.md) pour mon explication complète de pourquoi une
fusion brute des 3 datasets est impossible, et ce que j'ai fait à la place (fusion des
**résultats** d'analyse sur les clients Olist, pas des lignes brutes des 3 sources).

**Ce n'est pas un vrai churn.** Il n'existe aucune étiquette de départ client réelle pour les
clients Olist (contrairement au dataset churn labellisé). Le "risque" que je calcule est un
**proxy** entièrement fabriqué à partir du comportement d'achat observé : je classe un client "à
risque" s'il n'a pas racheté dans une fenêtre de 126 jours après sa première commande. Ce chiffre,
je ne l'ai **pas choisi au hasard** : il correspond au 75ᵉ percentile du délai de réachat que j'ai
réellement observé chez les 2 801 clients Olist ayant effectivement racheté (médiane 29 jours,
moyenne 81 jours, tirée vers le haut par une distribution très étalée) — 75% des réachats réels ont
lieu dans cette fenêtre.

**Déséquilibre des classes, avec mes vrais chiffres** : sur 67 993 clients disposant d'assez de
recul pour être évalués (j'exclus de l'entraînement les 25 365 clients trop récents, pas
mal-étiquetés), ma répartition est de **1 859 "retenus" (2,7%) contre 66 134 "à risque" (97,3%)** —
un déséquilibre encore plus extrême que celui du dataset churn original (71%/29%). Je le gère avec
les mêmes techniques que mon scoring churn (`class_weight='balanced'`, validation croisée à 5 plis
pour un scoring honnête), mais avec les chiffres propres à Olist, pas ceux du dataset churn.

**Résultat négatif, que j'assume et documente — et que j'ai re-testé après ma propre revue
critique (v2).** Dans ma première version (v1), je testais une seule configuration (Random Forest,
features incluant la note de l'avis et le délai de livraison) et je concluais à un ROC-AUC de 0,57
après un seul essai — insuffisant pour affirmer "aucun signal n'existe" avec confiance. Ma version
corrigée (v2) :

- **J'ai retiré les features connues après coup** : la note de l'avis et le délai de livraison ne
  sont connus que des semaines après le 1er achat, donc inutilisables pour un usage marketing réel
  ("détecter tôt"). Je ne garde que des variables connues au moment même du 1er achat (montant,
  frais de port, mode de paiement, catégorie, état).
- **J'ai comparé 3 configurations** au lieu d'une seule : Random Forest avec/sans `class_weight`, et
  Gradient Boosting (`HistGradientBoostingClassifier`). Résultat : Gradient Boosting fait légèrement
  mieux (ROC-AUC test = 0,586, contre 0,564 et 0,557 pour les deux Random Forest) — `class_weight`
  aide un peu (0,564 > 0,557), mais l'écart entre algorithmes reste faible. Mon score honnête final
  (validation croisée, Gradient Boosting) : **ROC-AUC = 0,58**.
- Mon diagnostic reste le même malgré cette comparaison plus rigoureuse : pouvoir prédictif quasi
  nul. Mon interprétation, inchangée et renforcée : contrairement au churn "classique" (souvent lié
  à des signaux comportementaux récurrents — appels SAV, abandon panier répété), le réachat sur une
  marketplace comme Olist dépend probablement de facteurs extérieurs à une transaction isolée
  (besoin du produit, concurrence, etc.), non capturés par mes données disponibles. Cohérent avec les
  deux autres limites que je documente déjà ci-dessus (RFM mono-achat, absence de vente croisée).

Je déploie ce module (dashboard, page "Vue client 360°") avec un avertissement de fiabilité visible
en permanence — **calculé dynamiquement** depuis `analytics.model_metrics_history` (pas une valeur
codée en dur de ma part), donc il resterait juste même après un futur recalcul. Je juge la valeur
pédagogique de ce résultat négatif, mesuré avec plusieurs configurations plutôt qu'une seule,
supérieure à celle d'un module "qui a l'air de marcher" sans base réelle.

**Recommandation de catégorie — mon repli et sa limite.** Dans ma v1, je ne recommandais une
catégorie qu'à 9,9% des clients (règle d'association à lift ≥ 1 requise). J'ai ajouté un repli (v2) :
à défaut de règle, je recommande la catégorie la plus vendue globalement (`bed_bath_table`) — ma
couverture passe à 98,6%. **Limite de ce repli, que j'assume** : `bed_bath_table` est à la fois
l'unique cible de règle réelle chez moi et la catégorie la plus vendue globalement, donc 90% des
recommandations que j'affiche sont en réalité la même suggestion générique ("achetez ce qui est
populaire"), pas une vraie personnalisation. J'ai fait en sorte que mon dashboard distingue
visuellement les deux cas (`(règle)` avec le lift réel vs `(populaire)` sans lift) pour ne pas
laisser croire à une personnalisation qui n'existe pas.

**Historique des métriques.** Je journalise toutes mes métriques de comparaison (v1 et v2, RF et
Gradient Boosting, scores test et hors-échantillon) dans `analytics.model_metrics_history`
(append-only, jamais vidée contrairement à mes autres tables `analytics.*`) — fondation pour un
futur suivi de dérive dans le temps, que je n'avais pas jusqu'ici dans mon projet.

## Analyse de sentiment (deep learning)

**Pas d'étiquette de sentiment annotée par un humain dans ce dataset.** Je dérive le label par
apprentissage faible ("weak supervision") depuis la note laissée par le client (1-2★→négatif,
3★→neutre, 4-5★→positif) : mon modèle apprend donc à prédire la note à partir du texte, que
j'utilise comme proxy du sentiment — une pratique reconnue mais que je dois présenter comme telle.

Mes résultats (validation croisée, 5 plis) : très bon sur négatif (F1=0,79) et positif (F1=0,89),
nettement plus faible sur neutre (F1=0,30, précision 0,22). C'est un résultat attendu et documenté
dans la littérature : les avis 3★ sont intrinsèquement ambigus en texte (souvent proches d'un avis
2★ ou 4★ selon le rédacteur), pas un signe que mon implémentation serait défaillante.

## Détection d'anomalies

Mon détecteur (`/analytics/anomalies`) compare la **période la plus récente** à l'historique
(z-score), comme une alerte de monitoring en production. Je ne scanne pas rétroactivement tout
l'historique : un pic ponctuel déjà passé (ex. le pic à 68,6% d'avis négatifs que j'ai identifié en
décembre 2016 dans ma tendance sentiment) ne sera pas signalé s'il n'est plus la période la plus
récente. J'ai volontairement limité la portée à "l'état actuel est-il anormal", pas à une recherche
exhaustive d'anomalies passées.

## Plan d'action marketing par client

Le facteur de risque que je retiens par client est une **heuristique** (z-score de ses variables
comportementales, pondéré par l'importance globale de la variable dans mon modèle), pas un
diagnostic causal. J'identifie la variable où le client s'écarte le plus de la moyenne de la
population parmi 8 dimensions connues pour peser sur le churn — utile pour prioriser une action,
pas une preuve que cette variable *cause* le départ du client.

## Recalcul à la demande

Je fais un suivi des jobs en mémoire dans le processus API (voir [architecture.md](architecture.md)) :
il ne survit pas à un redémarrage de l'API, incompatible avec plusieurs workers uvicorn. Adapté à la
portée de mon projet à instance unique, pas à une mise en production telle quelle.

**Versioning et rollback des modèles (retour de soutenance).** Avant que j'ajoute
`analytics/model_registry.py`, un recalcul à la demande écrasait toujours
`analytics.churn_scores` / `analytics.customer_360` en place, sans comparaison avec la version en
production ni possibilité de revenir en arrière — un modèle moins bon pouvait silencieusement
remplacer un meilleur. J'ai corrigé ça : une nouvelle version n'est promue chez moi que si sa
métrique (AUC hors échantillon) n'est pas inférieure de plus de 0,01 à la version active ; sinon, je
garde la version active et j'écris le résultat rejeté à part (`*_candidate`) pour inspection plutôt
que de le jeter silencieusement. Un rollback d'**un seul niveau** est possible depuis ma page
Administration (table `*_previous`, que je sauvegarde à chaque promotion). Limite que j'assume : ce
n'est pas un historique complet versionné (type MLflow) — proportionné à l'échelle de mon projet ;
l'historique COMPLET des métriques de chaque exécution (promue ou non), lui, reste append-only et
jamais purgé dans `analytics.model_metrics_history`.

## RGPD — droit à l'oubli

Voir [rgpd.md](rgpd.md#droit-à-loubli--anonymisation-plutôt-que-suppression-complète) : j'y
explicite la justification de mon anonymisation par article du RGPD (17(3)(d), 89(1)) (retour de
soutenance), et je corrige une affirmation trop forte de ma version précédente ("la ligne cesse
d'être une donnée personnelle") en distinguant anonymisation démontrée et pseudonymisation — je n'ai
mené aucune analyse de k-anonymat sur les attributs comportementaux restants à ce stade.
