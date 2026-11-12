# Déploiement et intégration continue

## Avant ce document : le retour de soutenance

*"Absence de CI/CD confirmée en fin de document : le processus de déploiement des mises à jour
reste flou."* J'ai d'abord répondu en deux temps : une CI mise en place tout de suite
(`.github/workflows/ci.yml`), un CD assumé comme absent tant que je n'avais pas de cible
d'hébergement réelle. J'ai ensuite tranché cette question et mis en place un vrai déploiement
continu — ce document décrit l'état actuel, pas une intention.

## Ce que j'ai mis en place : intégration continue (CI)

`.github/workflows/ci.yml`, job `test`, s'exécute à chaque `push`/`pull request` :

1. je démarre un conteneur PostgreSQL 16 propre (service GitHub Actions) ;
2. j'applique le schéma SQL complet (`sql/01_schemas.sql` → `sql/11_model_registry.sql`) — **sans
   les données** : je n'ai pas commité les CSV Kaggle sources (`data/raw/`, volumineux,
   redistribution hors périmètre de licence — voir `.gitignore`), donc aucun ETL ne peut tourner sur
   le runner ;
3. j'installe les dépendances (`requirements.txt`, qui inclut désormais `pytest`) ;
4. je lance `pytest` (116 tests) — voir [tests.md](tests.md). Mes tests de qualité de données
   (`tests/test_data_quality.py`) se `skip` proprement sur un schéma vide (normal en CI) ; mes
   tests RBAC, sécurité et mon garde-fou de versioning de modèle, eux, tournent réellement à chaque
   push ;
5. je démarre l'API (`uvicorn`) et vérifie que `/health` répond — un test de fumée minimal.

**Effet de bord positif direct** : en mettant en place cette CI, j'ai fait tourner l'API pour la
première fois contre un schéma sans aucune donnée. Ça a immédiatement révélé un bug réel que
j'avais jusque-là laissé passer : `/analytics/overview` renvoyait une erreur 500 quand
`analytics.rfm_segments` ou `analytics.funnel_stats` étaient vides (`GROUP BY`/`ORDER BY ... LIMIT
1` renvoie zéro ligne sur une table vide, pas une ligne de `NULL` comme un agrégat simple) — corrigé
dans `api/routers/analytics.py`.

## Ce que j'ai mis en place : déploiement continu (CD)

J'ai choisi **Scaleway** comme hébergeur : un vrai serveur distant (VPS), sur lequel je gère
moi-même le pare-feu réseau — le point précis qui manquait pour que "CD" ait un sens concret chez
moi.

### Pourquoi Scaleway plutôt qu'Oracle Cloud Always Free (changement de cible en cours de projet)

J'avais initialement retenu **Oracle Cloud Infrastructure (OCI), offre Always Free**, pour sa
gratuité permanente. Je n'ai pas pu aller au bout : la vérification de paiement d'Oracle a rejeté
ma carte (néobanque), un problème documenté comme fréquent chez ce fournisseur et indépendant de ma
configuration technique. Plutôt que de m'acharner sur cette vérification, j'ai basculé sur
**Scaleway**, hébergeur français :

- **carte bancaire acceptée sans friction** (société française, vérification d'identité standard,
  passée en quelques minutes) ;
- **une vraie VM**, comme Oracle, avec contrôle complet du système d'exploitation et du pare-feu —
  pas un PaaS qui l'abstrairait ;
- **coût modeste mais réel** (contrairement à Oracle Always Free) : instance `DEV1-S` (2 vCPU, 2 Go
  de RAM) + 20 Go de stockage bloc + une adresse IPv4 flexible, environ **12 €/mois** si elle tourne
  en continu — un choix assumé, proportionné à la durée de vie d'un projet de soutenance, pas à un
  service permanent.
- **architecture x86_64** (contrairement à l'Ampere A1/ARM64 d'Oracle que j'avais initialement
  prévue) : plus simple, c'est l'architecture la mieux couverte par toutes mes dépendances sans
  aucune vérification supplémentaire nécessaire.

**Incident rencontré et résolu — quota de compte neuf.** Ma première tentative de création d'une
instance `DEV1-S` a été bloquée par un message "quota(s) exceeded", alors même que paiement et
identité venaient d'être validés. Diagnostic en deux temps : j'ai d'abord créé une instance minimale
(`STARDUST1-S`, 1 Go de RAM) dans une autre zone disponible, qui a réussi — ce qui prouvait que mon
compte n'était pas bloqué à zéro instance, seulement sur les offres plus importantes. J'ai ensuite
utilisé la fonction "Change offer" pour **upgrader cette instance déjà créée** vers `DEV1-S`, ce qui
a fonctionné alors que la création directe d'une nouvelle instance `DEV1-S` ne passait pas — un
contournement qui a évité d'attendre une réponse du support.

### Nom de domaine : DuckDNS plutôt qu'un domaine payant

Je n'ai pas de nom de domaine, et un certificat HTTPS valide (Let's Encrypt) exige un nom de domaine
résolvable publiquement — une IP seule ne suffit pas. [DuckDNS](https://www.duckdns.org/) fournit un
sous-domaine gratuit (`moncompte.duckdns.org`) que je pointe vers l'**IP flexible** de mon instance
Scaleway (persistante tant que je ne la détache pas, équivalent fonctionnel d'une IP réservée).

### Mise en place du serveur (étapes exécutées dans la console Scaleway puis en SSH)

1. **Compute → Instances → Create Instance**, type **CPU Instance** (pas GPU — `torch` tourne en
   CPU dans ce projet, volontairement, voir [architecture.md](architecture.md)).
2. **Taille** : `DEV1-S` (2 vCPU, 2 Go de RAM) — j'ai écarté `STARDUST1-S` (1 Go), trop juste pour
   PostgreSQL + Vault + l'API (qui charge `torch`/`scikit-learn`) + Caddy simultanément.
3. **Image** : Ubuntu 24.04 LTS (Noble Numbat) — la version LTS la plus mature et documentée au
   moment du déploiement.
4. **Stockage** : 20 Go (volume unique, pas deux volumes séparés — un second volume bloc ne serait
   pas automatiquement monté, inutile de complexifier).
5. **Réseau** : IPv4 flexible activée (payante, ~3,65 €/mois, c'est elle que DuckDNS pointera),
   IPv6 gratuite activée aussi.
6. **Clé SSH** : générée localement (`ssh-keygen -t ed25519`), clé publique collée dans la console.
7. **Pare-feu réseau (Security Group Scaleway)** : règles d'entrée pour les ports 22 (SSH), 80
   (HTTP, requis par Let's Encrypt) et 443 (HTTPS).

   **Différence avec Oracle que j'ai vérifiée** : sur Scaleway, l'image Ubuntu standard n'embarque
   **pas** de second pare-feu système pré-configuré pour bloquer le trafic (`sudo ufw status` renvoie
   `inactive` à la première connexion, `iptables -L` ne montre aucune règle) — contrairement au piège
   à deux niveaux que j'avais documenté pour Oracle. J'ai néanmoins activé `ufw` moi-même, par
   principe de défense en profondeur plutôt que par nécessité corrective :
   ```bash
   sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp
   sudo ufw --force enable
   ```
8. **Swap de sécurité** : avec seulement 2 Go de RAM et aucun swap par défaut, j'ai ajouté 2 Go de
   swap persistant pour absorber un pic mémoire plutôt que de risquer un arrêt brutal d'un conteneur
   (`OOM kill`) :
   ```bash
   sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile
   sudo swapon /swapfile
   echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
   ```
9. **Docker** :
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
   ```
10. **Cloner le dépôt et configurer `.env`** (jamais commité, voir `.env.example`) :
    ```bash
    git clone https://github.com/Ndomidjia/plateforme-ecommerce-kit.git
    cd plateforme-ecommerce-kit
    cp .env.example .env && nano .env   # vrais mots de passe/tokens + DUCKDNS_DOMAIN
    ```
11. **Premier déploiement manuel** (les suivants sont automatiques, voir plus bas) :
    ```bash
    docker compose -f docker-compose.prod.yml up -d --build
    docker compose -f docker-compose.prod.yml exec api python /app/scripts/vault_init.py
    ```

### Architecture de production (différente de mon architecture de développement local)

`docker-compose.prod.yml` (nouveau, distinct de `docker-compose.yml` utilisé en dev local) décrit
quatre services :

- `db` et `vault` : identiques à mon environnement local, mais **sans aucun port publié sur
  l'hôte** — en dev local, je les expose sur `127.0.0.1` parce que mon API tourne directement sur
  la machine hôte (voir [securite.md](securite.md)) ; en production, mon API tourne elle aussi en
  conteneur sur le même réseau Docker, donc `db`/`vault` n'ont même plus besoin d'un port publié : ils
  ne sont atteignables que par les autres conteneurs, via le réseau interne Docker, par nom de
  service (`db:5432`, `vault:8200`) — une exposition encore plus restreinte que mon correctif local.
- `api` (nouveau `api/Dockerfile`) : mon API, désormais conteneurisée (elle tournait directement via
  `uvicorn` sur l'hôte jusqu'ici — lacune que je comblais déjà dans la liste "ce qu'un vrai
  déploiement demanderait" d'une version précédente de ce document).
- `web` (nouveau `dashboard/Dockerfile`, multi-étapes) : construit mon dashboard React (`npm run
  build`) puis le sert avec **Caddy**, qui gère aussi le reverse proxy vers `api` et le certificat
  HTTPS automatique (Let's Encrypt) pour mon domaine DuckDNS — voir `deploy/Caddyfile`. Dashboard et
  API partagent le même domaine (routage par chemin : `/auth`, `/analytics`, `/admin`, `/rgpd`,
  `/health`, `/docs` vers l'API ; tout le reste vers les fichiers statiques du dashboard), ce qui
  m'évite d'avoir à gérer le CORS en production.

Seul `web` publie des ports sur l'hôte (80 et 443) : c'est le seul point d'entrée public de toute
l'infrastructure, exactement ce que recommande un vrai pare-feu applicatif.

### Pipeline de déploiement continu

`.github/workflows/ci.yml`, job `deploy` : se déclenche uniquement sur un push sur `main`, et
uniquement si le job `test` a réussi — un changement qui casse mes tests n'atteint jamais le
serveur de production. Il se connecte en SSH au serveur et exécute `deploy/deploy.sh` (`git pull` +
reconstruction des images + redémarrage). Secrets nécessaires, déclarés dans les paramètres du
dépôt GitHub (jamais commités) : `DEPLOY_SSH_KEY` (clé privée dédiée, différente de ma clé
personnelle), `DEPLOY_HOST` (IP flexible ou domaine DuckDNS), `DEPLOY_USER` (`root`, utilisateur par
défaut des images Ubuntu Scaleway).

## Limites que j'assume encore sur ce déploiement

- **Vault toujours en mode développement** (voir [securite.md](securite.md)) : auto-unseal, token
  racine fixe. Un vrai déploiement Vault de production (stockage persistant, init/unseal réel,
  politiques d'accès par rôle) reste une amélioration non faite, proportionnée à l'échelle de ce
  projet.
- **Une seule instance, pas de haute disponibilité** : si le serveur tombe, rien ne bascule
  automatiquement vers une autre machine — cohérent avec l'objectif (une démonstration accessible en
  ligne), pas un service commercial à disponibilité garantie.
- **Recalcul à la demande toujours suivi en mémoire** dans le conteneur `api` (voir
  [limitations-methodologiques.md](limitations-methodologiques.md)) : ne survit pas à un redémarrage
  du conteneur, ne fonctionnerait pas avec plusieurs workers.
- **Coût récurrent assumé, pas un hébergement gratuit permanent** : contrairement à mon plan
  initial (Oracle Always Free), Scaleway facture environ 12 €/mois si l'instance tourne en continu —
  un choix budgétaire que j'assume pour la durée de mon projet, pas un service que je prévois de
  maintenir indéfiniment. L'IP flexible reste liée à mon compte : si je le supprimais, je perdrais
  cette IP et devrais mettre à jour mon enregistrement DuckDNS.
