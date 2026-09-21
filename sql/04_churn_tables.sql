-- Schéma CHURN : profils clients agrégés labellisés (dataset fourni)

CREATE TABLE IF NOT EXISTS churn.customer_profiles (
    customer_id                   SERIAL PRIMARY KEY,  -- identifiant technique ajouté
    age                           NUMERIC(5,1),
    gender                        VARCHAR(20),
    country                       VARCHAR(50),
    city                          VARCHAR(100),
    membership_years              NUMERIC(5,1),
    login_frequency               NUMERIC(6,1),
    session_duration_avg          NUMERIC(6,1),
    pages_per_session             NUMERIC(6,1),
    cart_abandonment_rate         NUMERIC(5,1),
    wishlist_items                NUMERIC(6,1),
    total_purchases               NUMERIC(8,1),
    average_order_value           NUMERIC(10,2),
    days_since_last_purchase      NUMERIC(6,1),
    discount_usage_rate           NUMERIC(6,2),
    returns_rate                  NUMERIC(5,1),
    email_open_rate               NUMERIC(5,1),
    customer_service_calls        NUMERIC(5,1),
    product_reviews_written       NUMERIC(6,1),
    social_media_engagement_score NUMERIC(6,1),
    mobile_app_usage              NUMERIC(6,1),
    payment_method_diversity      NUMERIC(4,1),
    lifetime_value                NUMERIC(12,2),
    credit_balance                NUMERIC(12,2),
    churned                       SMALLINT NOT NULL CHECK (churned IN (0,1)),
    signup_quarter                VARCHAR(2)
);
