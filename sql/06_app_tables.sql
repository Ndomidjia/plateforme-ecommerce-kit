-- Schéma APP : comptes de l'API (authentification/RBAC) + journal d'audit RGPD.
-- Distinct des schémas métier : ce sont des utilisateurs internes (staff),
-- pas des clients.

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.users (
    user_id         SERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role            VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'analyst')),
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Traçabilité des actions RGPD (export / suppression) : qui a demandé quoi,
-- sur quel client, quand. Principe de responsabilité (accountability) du RGPD.
CREATE TABLE IF NOT EXISTS app.rgpd_audit_log (
    log_id       SERIAL PRIMARY KEY,
    action       VARCHAR(20) NOT NULL CHECK (action IN ('export', 'erasure')),
    schema_name  VARCHAR(50) NOT NULL,
    subject_id   VARCHAR(50) NOT NULL,  -- customer_id / customer_unique_id / visitor_id selon le schéma
    requested_by VARCHAR(50) NOT NULL,  -- username de l'utilisateur API
    requested_at TIMESTAMP DEFAULT NOW()
);
