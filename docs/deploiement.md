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

J'ai choisi **Oracle Cloud Infrastructure (OCI) — offre Always Free** comme cible d'hébergement :
un vrai serveur distant, gratuit de façon permanente (pas un essai limité dans le temps), sur
lequel je gère moi-même le pare-feu réseau — le point précis qui manquait pour que "CD" ait un sens
concret chez moi.

### Pourquoi Oracle Cloud Always Free plutôt qu'une alternative

- **Gratuit durablement**, pas un crédit de lancement qui expire : adapté à un projet de
  soutenance que je veux pouvoir montrer en ligne sans budget récurrent.
- **Une vraie VM** (pas un PaaS qui masque l'infrastructure) : je gère moi-même le système
  d'exploitation, le pare-feu, Docker — cohérent avec l'objectif pédagogique de ce projet
  (comprendre chaque couche plutôt que déléguer).
- **Ressources Always Free généreuses** sur la forme de calcul Ampere A1 (ARM) : jusqu'à 4 OCPU et
  24 Go de RAM gratuits, largement suffisant pour PostgreSQL + Vault + API + dashboard sur une seule
  machine, là où l'alternative x86 Always Free (forme Micro) ne propose qu'1 Go de RAM.

**Contrepartie assumée** : la forme Ampere A1 est en architecture **ARM64**, pas x86_64. J'ai
vérifié la compatibilité de mes dépendances (notamment `torch`, la plus susceptible de poser
problème) en construisant mon image API pour `linux/arm64` avant de déployer — voir
[securite.md](securite.md) et le résultat ci-dessous.

### Nom de domaine : DuckDNS plutôt qu'un domaine payant

Je n'ai pas de nom de domaine, et un certificat HTTPS valide (Let's Encrypt) exige un nom de domaine
résolvable publiquement — une IP seule ne suffit pas. [DuckDNS](https://www.duckdns.org/) fournit un
sous-domaine gratuit (`moncompte.duckdns.org`) que je pointe une fois vers l'IP publique **réservée**
de mon instance OCI (Always Free inclut une IPv4 publique réservée gratuite — je l'utilise
précisément pour ne pas avoir à remettre à jour ce sous-domaine à chaque redémarrage de la VM, pas
besoin d'un script de mise à jour dynamique).

### Mise en place du serveur (étapes que j'exécute moi-même dans la console OCI, pas automatisables depuis mon poste)

1. **Créer le compte OCI** (si pas déjà fait) et, dans la console, **Compute → Instances → Create
   instance**.
2. **Image** : Ubuntu 24.04 (Always Free eligible, image ARM disponible).
3. **Forme (shape)** : changer pour `VM.Standard.A1.Flex` (Ampere, ARM) et régler à 2-4 OCPU / 12-24
   Go de RAM selon le quota Always Free disponible sur mon compte.
4. **Clé SSH** : générer une paire de clés (`ssh-keygen -t ed25519`) et coller la **clé publique**
   dans le formulaire de création — je garde la clé privée pour me connecter, jamais partagée.
5. **Réseau** : laisser le VCN par défaut créé automatiquement. Une fois l'instance créée, noter son
   **IP publique**, puis **réserver** cette IP (Networking → IP Management → Reserved Public IPs →
   associer à l'instance) pour qu'elle ne change jamais.
6. **Pare-feu réseau (ce que je cherchais à gérer moi-même)** : dans **Networking → Virtual Cloud
   Networks → (mon VCN) → Security Lists** (ou Network Security Groups pour un filtrage plus fin),
   j'ajoute des règles d'entrée (*Ingress Rules*) :
   - port 22 (SSH) — source : mon IP personnelle si possible, sinon `0.0.0.0/0` à restreindre plus
     tard ;
   - port 80 (HTTP, requis par Let's Encrypt pour valider le domaine) — source `0.0.0.0/0` ;
   - port 443 (HTTPS) — source `0.0.0.0/0`.

   **Piège spécifique à OCI que j'ai dû documenter** : la Security List du VCN ne suffit pas. Les
   images Ubuntu d'Oracle embarquent **en plus** un pare-feu au niveau du système d'exploitation
   (`iptables`, déjà configuré pour bloquer la plupart du trafic entrant par défaut) — un second
   niveau de filtrage, invisible dans la console, qui bloque le trafic même quand la Security List
   l'autorise. Je dois donc **aussi** ouvrir les ports côté système, une fois connecté en SSH :
   ```bash
   sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT
   sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT
   sudo netfilter-persistent save
   ```
   Deux pare-feu à gérer pour un seul serveur (cloud + système) : exactement le genre de détail
   qu'on ne découvre qu'en le faisant, pas en le lisant — je le documente ici pour ne pas le refaire
   deviner à qui reprendrait ce projet.
7. **Docker** sur le serveur :
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 git
   sudo usermod -aG docker $USER   # puis se reconnecter en SSH
   ```
8. **Cloner le dépôt et configurer `.env`** (jamais commité, voir `.env.example`) :
   ```bash
   git clone https://github.com/Ndomidjia/plateforme-ecommerce-kit.git
   cd plateforme-ecommerce-kit
   cp .env.example .env && nano .env   # vrais mots de passe/tokens + DUCKDNS_DOMAIN
   ```
9. **Premier déploiement manuel** (les suivants sont automatiques, voir plus bas) :
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
personnelle), `DEPLOY_HOST` (IP réservée ou domaine DuckDNS), `DEPLOY_USER` (`ubuntu`).

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
- **IPv4 réservée Always Free** : gratuite mais liée à mon compte OCI ; si je supprimais le compte,
  je perdrais cette IP (et donc devrais mettre à jour mon enregistrement DuckDNS) — un risque
  accepté, pas pertinent pour la durée d'un projet de soutenance.
