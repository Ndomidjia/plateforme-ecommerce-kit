-- Mon registre de versions de modèles : quelle version est actuellement
-- "promue" en production pour chaque modèle, avec un point de retour en
-- arrière (rollback) d'un niveau -- ma réponse à la question "un nouveau
-- modèle moins bon écrase-t-il l'ancien sans rollback possible ?" (retour
-- de soutenance, voir docs/journal-de-bord.md).
--
-- Pourquoi j'ai choisi un rollback à un niveau plutôt qu'un historique
-- complet versionné (type MLflow) : proportionné à l'échelle de mon projet.
-- L'historique COMPLET des métriques de chaque exécution (promue ou non)
-- reste lui append-only et jamais purgé dans analytics.model_metrics_history
-- (une ligne metric_name='promoted' -- 1.0/0.0 -- y est désormais écrite à
-- chaque exécution) -- mon audit et mon suivi de dérive ne dépendent donc
-- pas de la profondeur du rollback.
--
-- Les tables de sauvegarde (<table>_previous) et de résultats rejetés
-- (<table>_candidate) sont créées à la volée par mon analytics/model_registry.py
-- au premier recalcul suivant ce déploiement (CREATE TABLE ... LIKE ...),
-- pas ici : leur schéma doit être identique à celui de la table live au
-- moment du déploiement.

CREATE TABLE IF NOT EXISTS analytics.model_registry (
    model_name       VARCHAR(50) PRIMARY KEY,
    active_version   VARCHAR(50) NOT NULL,
    active_metric    NUMERIC(12,6),
    has_backup       BOOLEAN NOT NULL DEFAULT FALSE,
    previous_version VARCHAR(50),
    previous_metric  NUMERIC(12,6),
    promoted_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
