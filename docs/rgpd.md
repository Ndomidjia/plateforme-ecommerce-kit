# Approche RGPD

## Périmètre

Le patron RGPD (droit d'accès, droit à l'oubli, traçabilité) est implémenté sur le schéma
**`churn`** en premier (une seule table, PII évidentes : âge, genre, ville). Il n'a pas encore été
répliqué sur `olist` (via `customer_unique_id`) ni `retailrocket` (via `visitor_id`) — prochaine
étape si le temps le permet, en réutilisant le même patron (voir `api/routers/rgpd.py`).

## Droit d'accès et de portabilité

`GET /rgpd/churn/{customer_id}/export` (admin uniquement) renvoie l'intégralité de la ligne
`churn.customer_profiles` correspondante en JSON.

## Droit à l'oubli : anonymisation plutôt que suppression complète

`DELETE /rgpd/churn/{customer_id}` retire les champs identifiants (`age`, `gender`, `country`,
`city` → `NULL`) plutôt que de supprimer la ligne entièrement.

### Base légale explicite (retour de soutenance : ce choix devait être rattaché au texte RGPD, pas
### seulement présenté comme un arbitrage d'ingénierie)

Le RGPD prévoit lui-même une exception au droit à l'oubli, pas seulement un principe général
d'"intégrité des statistiques" invoqué de façon informelle :

- **Article 17(1)** pose le droit à l'effacement ("droit à l'oubli").
- **Article 17(3)(d)** en exclut explicitement les traitements *"à des fins archivistiques dans
  l'intérêt public, à des fins de recherche scientifique ou historique ou à des fins statistiques
  [...] dans la mesure où le droit visé au paragraphe 1 est susceptible de rendre impossible ou de
  compromettre gravement la réalisation des objectifs dudit traitement"*. C'est exactement le cas
  ici : les scores de risque déjà calculés (`analytics.churn_scores`) et les métriques agrégées du
  dashboard dépendent de l'intégrité référentielle avec `churn.customer_profiles` — une suppression
  complète casserait cette clé étrangère et fausserait rétroactivement des statistiques déjà
  publiées à d'autres utilisateurs.
- **Article 89(1)**, auquel l'article 17(3)(d) renvoie, conditionne cette exception à des
  *"garanties appropriées [...], en particulier [...] la pseudonymisation"* — pas à l'absence de
  toute garantie. Retirer les identifiants directs (`age`, `gender`, `country`, `city`) au moment de
  la demande d'effacement EST cette garantie : c'est la mise en œuvre concrète de l'article 89(1),
  pas un choix technique déconnecté du texte.

### Anonymisation ou pseudonymisation ? Une distinction à ne pas trancher par excès de confiance

La version précédente de cette documentation affirmait que la ligne *"cesse d'être une donnée
personnelle au sens RGPD"* après ce traitement — affirmation trop forte, corrigée ici. Le RGPD
(considérant 26) et la doctrine de la CNIL distinguent :

- une donnée **anonymisée** : le risque de réidentification est négligeable *de façon démontrée*
  (aucun moyen raisonnable de rattacher la donnée à une personne) → sort entièrement du champ du
  RGPD ;
- une donnée **pseudonymisée** : des identifiants directs sont retirés, mais un identifiant stable
  subsiste (ici `customer_id`) et/ou une combinaison d'attributs restants pourrait, en théorie,
  permettre un ré-appariement (singling-out) → **reste une donnée personnelle** au sens du RGPD,
  simplement soumise à un traitement plus protecteur.

Ce que fait `DELETE /rgpd/churn/{customer_id}` est, honnêtement, plus proche de la **seconde**
catégorie : `customer_id` est conservé (clé technique nécessaire à l'intégrité référentielle), et
aucune analyse de k-anonymat n'a été menée sur les métriques comportementales restantes
(`lifetime_value`, `login_frequency`, etc.) pour démontrer qu'elles ne permettent pas, combinées, de
ré-identifier un individu dans une base de 50 000 profils. La base légale ne repose donc pas sur
l'affirmation "ce n'est plus une donnée personnelle", mais bien sur l'exception explicite de
l'article 17(3)(d) + les garanties de l'article 89(1) — un traitement qui **reste** dans le
périmètre du RGPD mais que le RGPD autorise lui-même à poursuivre, à condition des garanties
apportées ici. Limite assumée, dans le même esprit que les autres limites documentées dans
[limitations-methodologiques.md](limitations-methodologiques.md) : une vraie anonymisation
(garantie, pas seulement supposée) nécessiterait une analyse de k-anonymat/l-diversité sur les
attributs comportementaux restants, non réalisée à ce stade.

## Traçabilité (principe de responsabilité / accountability)

Chaque export et chaque anonymisation est journalisé dans `app.rgpd_audit_log` :
`action` (export/erasure), `schema_name`, `subject_id`, `requested_by` (compte admin), `requested_at`.
Visible dans le dashboard (page Vue d'ensemble, section Administration → "Dernières actions RGPD").

## Contrôle d'accès

Les endpoints RGPD sont réservés au rôle `admin` (contrairement aux endpoints `/analytics/*`,
accessibles aussi à `analyst`) : ce sont les seuls à manipuler des données personnelles brutes non
agrégées.

## Sécurité des secrets

- Mots de passe API hashés avec `bcrypt` (jamais stockés en clair)
- Clé secrète JWT générée aléatoirement (256 bits), stockée en variable d'environnement (`.env`,
  jamais commitée)
- Mot de passe PostgreSQL généré aléatoirement, jamais la valeur par défaut du template
