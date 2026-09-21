-- Schéma RETAILROCKET : clickstream (dataset Kaggle retailrocket/ecommerce-dataset)

CREATE TABLE IF NOT EXISTS retailrocket.events (
    event_time    TIMESTAMP NOT NULL,   -- converti depuis timestamp epoch ms
    visitor_id    BIGINT NOT NULL,
    event_type    VARCHAR(20) NOT NULL, -- view | addtocart | transaction
    item_id       BIGINT NOT NULL,
    transaction_id BIGINT               -- NULL sauf pour les achats
);
CREATE INDEX IF NOT EXISTS idx_events_visitor ON retailrocket.events(visitor_id);
CREATE INDEX IF NOT EXISTS idx_events_item    ON retailrocket.events(item_id);
CREATE INDEX IF NOT EXISTS idx_events_type    ON retailrocket.events(event_type);

CREATE TABLE IF NOT EXISTS retailrocket.item_properties (
    property_time TIMESTAMP NOT NULL,
    item_id       BIGINT NOT NULL,
    property      VARCHAR(50) NOT NULL,
    value         TEXT
);
CREATE INDEX IF NOT EXISTS idx_itemprop_item ON retailrocket.item_properties(item_id);

CREATE TABLE IF NOT EXISTS retailrocket.category_tree (
    category_id BIGINT PRIMARY KEY,
    parent_id   BIGINT
);
