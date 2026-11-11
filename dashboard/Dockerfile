# Construit depuis la racine du dépôt (contexte = racine) -- image finale :
# mon dashboard buildé (fichiers statiques), servi par Caddy, qui gère aussi
# le HTTPS automatique (voir deploy/Caddyfile et docs/deploiement.md).
# node:20-slim (Debian/glibc) plutôt que node:20-alpine : Rollup (utilisé par
# Vite) résout des dépendances natives optionnelles différentes selon la
# libc (musl sur Alpine vs glibc), ce qui a fait échouer `npm ci` avec une
# erreur de lockfile désynchronisé (`@emnapi/core` manquant) -- un problème
# connu de Rollup/Vite sur Alpine, pas une erreur de mon côté.
FROM node:20-slim AS build

WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci

COPY dashboard/ ./

# Même domaine que l'API en production (Caddy route par chemin, voir
# deploy/Caddyfile) : URL relative, pas de CORS à gérer côté navigateur.
ENV VITE_API_BASE_URL=""
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY deploy/Caddyfile /etc/caddy/Caddyfile
