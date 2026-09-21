-- Schéma OLIST : fidèle aux 9 CSV du dataset Kaggle olistbr/brazilian-ecommerce

CREATE TABLE IF NOT EXISTS olist.customers (
    customer_id             VARCHAR(50) PRIMARY KEY,   -- change à chaque commande
    customer_unique_id      VARCHAR(50) NOT NULL,      -- identifie le vrai client !
    customer_zip_code_prefix VARCHAR(10),
    customer_city           VARCHAR(100),
    customer_state          VARCHAR(5)
);
CREATE INDEX IF NOT EXISTS idx_customers_unique ON olist.customers(customer_unique_id);

CREATE TABLE IF NOT EXISTS olist.orders (
    order_id                        VARCHAR(50) PRIMARY KEY,
    customer_id                     VARCHAR(50) REFERENCES olist.customers(customer_id),
    order_status                    VARCHAR(30),
    order_purchase_timestamp        TIMESTAMP,
    order_approved_at               TIMESTAMP,
    order_delivered_carrier_date    TIMESTAMP,
    order_delivered_customer_date   TIMESTAMP,
    order_estimated_delivery_date   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS olist.products (
    product_id                  VARCHAR(50) PRIMARY KEY,
    product_category_name       VARCHAR(100),
    product_name_lenght         INT,
    product_description_lenght  INT,
    product_photos_qty          INT,
    product_weight_g            INT,
    product_length_cm           INT,
    product_height_cm           INT,
    product_width_cm            INT
);

CREATE TABLE IF NOT EXISTS olist.sellers (
    seller_id               VARCHAR(50) PRIMARY KEY,
    seller_zip_code_prefix  VARCHAR(10),
    seller_city             VARCHAR(100),
    seller_state            VARCHAR(5)
);

CREATE TABLE IF NOT EXISTS olist.order_items (
    order_id            VARCHAR(50) REFERENCES olist.orders(order_id),
    order_item_id       INT,
    product_id          VARCHAR(50) REFERENCES olist.products(product_id),
    seller_id           VARCHAR(50) REFERENCES olist.sellers(seller_id),
    shipping_limit_date TIMESTAMP,
    price               NUMERIC(10,2),
    freight_value       NUMERIC(10,2),
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS olist.order_payments (
    order_id             VARCHAR(50) REFERENCES olist.orders(order_id),
    payment_sequential   INT,
    payment_type         VARCHAR(30),
    payment_installments INT,
    payment_value        NUMERIC(10,2),
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS olist.order_reviews (
    review_id               VARCHAR(50),
    order_id                VARCHAR(50) REFERENCES olist.orders(order_id),
    review_score            INT CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP,
    PRIMARY KEY (review_id, order_id)
);

CREATE TABLE IF NOT EXISTS olist.geolocation (
    geolocation_zip_code_prefix VARCHAR(10),
    geolocation_lat             DOUBLE PRECISION,
    geolocation_lng             DOUBLE PRECISION,
    geolocation_city            VARCHAR(100),
    geolocation_state           VARCHAR(5)
);

CREATE TABLE IF NOT EXISTS olist.category_translation (
    product_category_name         VARCHAR(100) PRIMARY KEY,
    product_category_name_english VARCHAR(100)
);
