# Sécurité

Ce document rassemble tout ce que j'ai mis en place côté sécurité, et ce qui reste une limite
assumée. Avant ce document, plusieurs points n'étaient que des réponses orales à une question de
soutenance ("qu'est-ce qui est déjà fait côté sécurité ?") — je les formalise et je corrige ceux qui
n'étaient encore que des lacunes identifiées sans être traitées.

## Authentification et autorisation

- **JWT** (PyJWT) : à la connexion, j'émets un jeton signé (`create_access_token`), valable 60 min
  par défaut.
- **Mots de passe hashés** avec `bcrypt` (jamais stockés en clair).
- **RBAC à 2 rôles** (`admin`/`analyst`) : `require_role(*roles)` dans `api/deps.py` bloque l'accès
  (403) si le rôle ne correspond pas. Testé automatiquement (`tests/test_auth_rbac.py`).

### Révocation de jeton avant expiration (retour de soutenance)

Avant, `get_current_user` (voir `api/deps.py`) faisait confiance au contenu du jeton pendant toute
sa durée de vie, sans revérifier que le compte existait encore en base : si j'avais supprimé un
compte entre-temps, son jeton restait valide jusqu'à expiration naturelle (jusqu'à 60 min).

Corrigé : je revérifie maintenant l'existence du compte (et son rôle actuel) en base à **chaque
requête**, pas seulement à la connexion — une requête de plus par appel, négligeable à cette
échelle. Un compte supprimé voit son jeton rejeté (401) dès la requête suivante, pas à l'expiration.
Bonus : un changement de rôle est aussi pris en compte immédiatement, puisque je relis le rôle
depuis la base plutôt que depuis le jeton. Testé par
`tests/test_auth_rbac.py::test_deleted_account_token_is_revoked_immediately`.

### Protection anti-bruteforce sur `/auth/login` (retour de soutenance)

Avant, rien n'empêchait de tester des mots de passe en boucle sur `/auth/login`.

Corrigé dans `api/rate_limit.py` : je verrouille temporairement après trop d'échecs,
- **par compte** : 5 échecs en 15 min → verrouillage 15 min (empêche de bruteforcer un compte
  précis, même depuis des IP différentes) ;
- **par IP** : 20 échecs en 15 min → verrouillage 15 min (empêche de "sprayer" plusieurs comptes
  connus depuis une même source, seuil plus large pour ne pas bloquer un oubli de mot de passe
  isolé) ;
- une connexion réussie remet les compteurs à zéro (pas d'accumulation indéfinie vers un
  verrouillage injustifié).

Le endpoint renvoie `429 Too Many Requests` avec un en-tête `Retry-After`. Compteurs en mémoire dans
le processus API, comme le suivi des recalculs dans `api/routers/admin.py` -- même limite que
j'assume : ne survit pas à un redémarrage de l'API, ne fonctionnerait pas avec plusieurs workers
uvicorn (une vraie solution partagée type Redis serait nécessaire en production). Testé par
`tests/test_auth_rbac.py::test_login_locks_out_after_too_many_failed_attempts` et
`test_login_resets_failed_attempts_after_success`.

## Gestion des secrets (Vault)

Avant, mes deux secrets sensibles (mot de passe PostgreSQL dans l'URL de connexion, clé de
signature JWT) vivaient uniquement en clair dans un fichier `.env` local.

J'ai ajouté un vrai gestionnaire de secrets, **HashiCorp Vault**, comme service dans
`docker-compose.yml` :

- `api/secrets_provider.py` (et son jumeau `analytics/secrets_provider.py`, dupliqué pour la même
  raison que `MODEL_LIVE_TABLES` dans `api/routers/admin.py` : deux répertoires/process distincts)
  lit `DATABASE_URL` et `JWT_SECRET_KEY` depuis Vault (`secret/ecommerce/api`, KV v2) quand Vault
  est configuré et accessible, et retombe sur `.env` sinon.
- `scripts/vault_init.py` pousse les valeurs de `.env` dans Vault une fois celui-ci démarré.
- Le repli sur `.env` est **délibéré**, pas un filet de sécurité paresseux : en CI
  (`.github/workflows/ci.yml`), Vault tourne réellement (service dédié) et le point précédent est
  vérifié explicitement (étape *"Vérifier que les secrets viennent bien de Vault"*, qui force des
  valeurs d'environnement volontairement fausses pour prouver que ce qui est lu vient bien de
  Vault). En développement local, je peux travailler sans avoir démarré le conteneur `vault`.

### Limite rencontrée et assumée : Vault ne démarre pas sur ma machine de développement

En essayant de lancer le conteneur `vault` localement (Docker Desktop + WSL2, Windows), le binaire
Vault plante au démarrage avec une erreur de runtime Go (`fatal error: mallocgc called without a P
or outside bootstrapping`), précédée du message `Couldn't start vault with IPC_LOCK`. J'ai
diagnostiqué et exclu plusieurs pistes avant de conclure :
- pas un problème de configuration `cap_add`/`IPC_LOCK` : le crash est identique avec ou sans la
  capacité accordée, et même en appelant le binaire `vault` directement (en contournant
  `docker-entrypoint.sh`) ;
- pas un problème de version d'image : identique sur plusieurs tags ;
- c'est un plantage très bas niveau du runtime Go lui-même, avant l'initialisation du scheduler --
  cohérent avec une incompatibilité connue entre le `mlock`/`IPC_LOCK` de Vault et la virtualisation
  Docker Desktop/WSL2 sur certaines configurations Windows, indépendante de mon docker-compose.

Je n'ai donc **jamais pu faire tourner Vault localement sur cette machine** pour une démonstration
en direct. Je ne l'ai pas caché en retirant discrètement l'intégration : le code reste, testé et
validé différemment -- sur un vrai Linux (runner GitHub Actions), où Vault démarre et fonctionne
normalement. C'est ma CI, pas ma machine locale, qui est la preuve que cette intégration fonctionne
réellement de bout en bout. Pendant le diagnostic, le crash en boucle du conteneur a aussi fait
planter deux fois le démon Docker Desktop lui-même (système de fichiers interne corrompu,
`read-only file system`), résolu par un redémarrage complet de Docker Desktop + WSL2 à chaque fois
-- incident purement local, sans lien avec le code du projet.

## Simulation d'attaque (pentest interne)

Documenter des défenses ne prouve pas qu'elles tiennent sous tentative réelle d'exploitation —
alors je me suis mis à la place d'un attaquant et j'ai écrit une suite dédiée,
`tests/test_security_attacks.py` (40 tests, intégrée à ma suite pytest et donc à ma CI), qui
attaque mon API sur les quatre familles de vecteurs qu'un pentest manuel ciblerait en priorité sur
une API à authentification par jeton :

- **Bruteforce / anti-bruteforce** : en complément des tests de verrouillage par compte déjà
  présents (`test_auth_rbac.py`), je vérifie qu'un message d'erreur identique empêche l'énumération
  de comptes existants (même code, même `detail` pour "compte inconnu" et "mauvais mot de passe"),
  et qu'un credential stuffing qui vise 20 comptes différents (une tentative chacun, sous mon seuil
  par compte de 5) se fait bloquer par mon seuil par IP.
- **Falsification de JWT** : signature altérée, jeton signé avec un mauvais secret, attaque
  classique `alg: none` (jeton sans signature), claim `role` remonté à `admin` puis re-signé avec un
  secret deviné (donc invalide), jeton expiré signé avec le vrai secret.
- **Injection SQL** : payloads classiques (`' OR '1'='1`, `UNION SELECT`, `DROP TABLE`, commentaire
  `--`) injectés dans les identifiants de connexion, un paramètre de chemin (`/analytics/rfm/{id}`)
  et un paramètre de requête (`/analytics/rfm?segment=`).
- **Élévation de privilèges** : balayage systématique de tous mes endpoints réservés à l'admin avec
  un jeton `analyst` et sans jeton du tout, pour qu'un futur endpoint oublié dans `require_role(...)`
  se fasse détecter automatiquement par ce test plutôt que de rester une lacune silencieuse.

**Résultat** : les 40 tentatives échouent proprement (401/403/404 selon le cas), sans jamais
d'erreur 500 ni de contournement — c'est un résultat honnête à montrer tel quel, y compris le fait
que je n'ai rien trouvé à exploiter : ça valide que mes requêtes paramétrées, mon RBAC et ma
vérification JWT (`algorithms=[JWT_ALGORITHM]` explicite dans `api/security.py`, qui empêche
justement l'attaque `alg: none`) tiennent sous tentative réelle, pas seulement à la lecture du code.

Ce que cette suite ne couvre pas : c'est une simulation ciblée sur la logique applicative que
j'écris moi-même (auth, RBAC, requêtes SQL), pas un audit de sécurité externe ni un scan généraliste
(type OWASP ZAP) qui couvrirait aussi la configuration serveur, les en-têtes HTTP, ou des failles de
bibliothèques tierces — voir la limite ci-dessous.

## Protection des données et des requêtes

- Toutes les requêtes SQL passent par des requêtes paramétrées (`sqlalchemy.text()` + paramètres
  liés) : protégées contre l'injection SQL.
- CORS restreint explicitement aux origines de mon dashboard (`localhost:5173` /
  `127.0.0.1:5173`), pas un `allow_origins=["*"]`.

## RGPD

Voir [rgpd.md](rgpd.md) : droit d'accès, droit à l'oubli avec sa base légale explicite (article
17(3)(d) + 89(1) du RGPD), traçabilité, et mon analyse de k-anonymat sur les attributs restants
après anonymisation (nouveau, voir
[rgpd.md#analyse-de-k-anonymat-sur-les-attributs-restants-retour-de-soutenance](rgpd.md#analyse-de-k-anonymat-sur-les-attributs-restants-retour-de-soutenance)).

## Ce qui n'est toujours pas fait (limites que j'assume)

- **Pas de HTTPS** : développement local uniquement -- à gérer par l'hébergeur en cas de
  déploiement réel (voir [deploiement.md](deploiement.md)).
- **Vault en mode dev uniquement** : auto-unseal, un seul nœud, token root fixe -- pas un
  déploiement Vault de production (qui demanderait un stockage persistant, un vrai init/unseal, et
  des politiques d'accès par rôle plutôt qu'un unique token root).
- **Rate limiting en mémoire, mono-process** : ne protège pas contre un attaquant distribué sur
  plusieurs IP en dessous du seuil par IP, et ne survit pas à un redémarrage de l'API.
- **Pas d'audit de sécurité externe** : ma simulation d'attaque (`tests/test_security_attacks.py`,
  voir plus haut) est un pentest interne que j'ai écrit et exécuté moi-même sur ma propre logique
  applicative -- pas un audit indépendant, pas un scan généraliste de type OWASP ZAP (configuration
  serveur, en-têtes HTTP, failles de bibliothèques tierces). Proportionné à l'échelle d'un projet de
  soutenance, mais à mentionner comme limite si le projet devait aller plus loin.
