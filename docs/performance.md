# Tests de performance

## Avant ce document

Rien n'avait été fait : aucun test de charge, aucun benchmark, pas de mesure de temps de réponse
sous volume. C'est un gap que j'ai moi-même listé comme non traité (voir
[tests.md](tests.md)) avant de le combler ici.

## Outil et scénario

[Locust](https://locust.io/) (`scripts/locustfile.py`) : je simule un utilisateur qui enchaîne les
pages du dashboard (vue d'ensemble, RFM, churn, funnel, recommandations, règles d'association,
sentiment, vue client 360°, calculateur de rétention), pondérées pour refléter un usage réel (la
vue d'ensemble est consultée plus souvent que la vue client 360°, par exemple). Je n'inclus pas les
endpoints d'écriture (création de compte, RGPD, recalcul de modèle) : ils ont des effets de bord
réels qu'un test de charge répétable ne doit pas déclencher en boucle.

```bash
python api/create_admin.py perf_test "PerfTest!2026"   # une fois
cd api && uvicorn main:app --port 8000 &
locust -f scripts/locustfile.py --host=http://127.0.0.1:8000 \
    --headless -u 20 -r 5 -t 60s --csv=docs/assets/perf --html=docs/assets/perf_report.html
```

20 utilisateurs simulés, montée en charge à 5/s, pendant 60 secondes.

## Ce que j'ai trouvé — un vrai problème, pas juste des chiffres

Mon premier run a échoué à 8,2% (5 requêtes sur 61), avec des temps de réponse qui grimpaient
jusqu'à **34 secondes**. Les logs de l'API pointaient tous vers la même cause :

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached,
connection timed out, timeout 30.00
```

`api/config.py` créait son moteur SQLAlchemy avec les réglages de pool par défaut (5 connexions +
10 en débordement = 15 au total). Avec seulement 20 utilisateurs simulés, ce plafond était atteint :
les requêtes suivantes attendaient une connexion libre jusqu'à 30 secondes avant d'abandonner en
erreur 500. Ce n'est pas un cas extrême — 20 utilisateurs simultanés est un chiffre modeste pour un
dashboard d'équipe.

**Corrigé** dans `api/config.py` : `pool_size=20, max_overflow=20` (40 connexions max — PostgreSQL
accepte par défaut jusqu'à 100 connexions simultanées, ça laisse de la marge pour les scripts
`analytics/` et une connexion `psql` manuelle en parallèle).

## Avant / après

Même scénario (20 utilisateurs, 60 secondes), avant et après le correctif :

| | Avant | Après |
|---|---:|---:|
| Requêtes totales | 61 | 81 |
| Échecs | 5 (8,2%) | **0 (0%)** |
| Temps de réponse médian | 1 200 ms | 1 300 ms |
| Temps de réponse max | **33 749 ms** | 5 157 ms |
| `/analytics/churn/summary` (p95) | 34 000 ms | 1 400 ms |

Le nombre de requêtes traitées augmente (81 vs 61 sur la même durée) précisément parce que les
requêtes ne restent plus bloquées à attendre une connexion. Rapport complet :
[`docs/assets/perf_report.html`](assets/perf_report.html), données brutes :
[`docs/assets/perf_stats.csv`](assets/perf_stats.csv).

## Ce qui reste honnêtement lent (pas un bug, documenté comme tel)

- **`POST /auth/login` (~2,9 s en moyenne)** : attendu, pas un problème. `bcrypt` est volontairement
  coûteux en calcul (c'est tout l'intérêt pour résister au bruteforce hors ligne, voir
  [securite.md](securite.md)) — réduire son facteur de coût irait à l'encontre de la sécurité pour
  gagner en vitesse, un compromis que je ne fais pas.
- **`GET /analytics/sentiment/trend` (~4,3 s en moyenne)** : la requête la plus lente du lot, pas
  encore investiguée en détail (candidate à un index ou une agrégation pré-calculée si le volume de
  données augmentait) — limite que j'assume, pas résolue à ce stade.

## Limites de ce test (proportionné à l'échelle du projet)

- **Une seule machine** : client Locust et serveur API tournent sur le même poste que PostgreSQL
  (voir [deploiement.md](deploiement.md), pas d'environnement hébergé) — pas représentatif d'un
  déploiement réseau réel, mais suffisant pour révéler et corriger un vrai goulot d'étranglement
  applicatif (le pool de connexions), qui lui se serait reproduit n'importe où.
- **Pas intégré à la CI** : contrairement à `pytest` (voir [tests.md](tests.md)), ce test n'est pas
  relancé à chaque push — un test de charge de 60 secondes n'a pas sa place dans une CI qui doit
  rester rapide. Outil manuel, à relancer après un changement structurel (comme
  `analytics/analyse_seuil_bot.py` ou `analytics/analyse_k_anonymat.py`).
- **Lecture seule** : je ne charge pas les endpoints d'écriture (voir "Outil et scénario"
  ci-dessus) — leurs effets de bord réels (recalcul de modèle de plusieurs minutes, notamment) les
  rendent inadaptés à un test de charge répété.
