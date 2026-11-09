"""Analyse de sentiment (deep learning) sur les commentaires d'avis Olist.

Réseau de neurones (PyTorch) : Embedding -> mean pooling -> couches denses ->
3 classes (négatif/neutre/positif). Entraîné sur les commentaires texte
(portugais) des avis clients.

Point méthodologique important : il n'existe pas d'étiquette de sentiment
annotée par un humain dans ce dataset. On dérive un label faible ("weak
supervision") depuis la note review_score déjà donnée par le client :
1-2 étoiles -> négatif, 3 -> neutre, 4-5 -> positif. Le modèle apprend donc à
prédire la note à partir du texte, utilisé ici comme proxy du sentiment.
C'est une pratique reconnue (bootstrapping depuis une note), mais elle doit
être présentée comme telle, pas comme du sentiment "vérité terrain".

Comme pour le churn : les scores finaux sont produits par validation croisée
(K-fold manuel) plutôt que par un modèle réentraîné puis réappliqué aux
mêmes données, pour éviter le biais de sur-apprentissage déjà rencontré et
corrigé sur le module churn.
"""
import logging
import re

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import classification_report
from sklearn.model_selection import StratifiedKFold
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("analytics.sentiment_olist")

VOCAB_SIZE = 8000
MAX_LEN = 40
EMBED_DIM = 64
BATCH_SIZE = 128
EPOCHS = 6
N_FOLDS = 5
LABELS = ["negative", "neutral", "positive"]

QUERY = """
SELECT review_id, order_id, review_score, review_comment_message
FROM olist.order_reviews
WHERE review_comment_message IS NOT NULL AND TRIM(review_comment_message) != ''
"""

def score_to_label(score: int) -> int:
    if score <= 2:
        return 0  # negative
    if score == 3:
        return 1  # neutral
    return 2      # positive

def tokenize(text_value: str) -> list[str]:
    text_value = text_value.lower()
    text_value = re.sub(r"[^a-zà-ÿ0-9\s]", " ", text_value)
    return text_value.split()

def build_vocab(token_lists) -> dict:
    freq = {}
    for tokens in token_lists:
        for tok in tokens:
            freq[tok] = freq.get(tok, 0) + 1
    # index 0 = padding, 1 = mot inconnu (hors vocabulaire)
    most_common = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:VOCAB_SIZE - 2]
    return {tok: i + 2 for i, (tok, _) in enumerate(most_common)}

def encode(tokens, vocab) -> list[int]:
    ids = [vocab.get(tok, 1) for tok in tokens[:MAX_LEN]]
    ids += [0] * (MAX_LEN - len(ids))
    return ids

class SentimentNet(nn.Module):
    def __init__(self, vocab_size, embed_dim, num_classes):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.fc1 = nn.Linear(embed_dim, 64)
        self.dropout = nn.Dropout(0.3)
        self.fc2 = nn.Linear(64, num_classes)

    def forward(self, x):
        emb = self.embedding(x)          # (batch, seq_len, embed_dim)
        pooled = emb.mean(dim=1)         # moyenne des embeddings de mots du commentaire
        h = torch.relu(self.fc1(pooled))
        h = self.dropout(h)
        return self.fc2(h)

def train_one_fold(X_train, y_train, class_weights, vocab_size):
    model = SentimentNet(vocab_size, EMBED_DIM, num_classes=3)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss(weight=class_weights)

    X_train_t = torch.tensor(X_train, dtype=torch.long)
    y_train_t = torch.tensor(y_train, dtype=torch.long)
    n = len(X_train_t)

    model.train()
    for epoch in range(EPOCHS):
        perm = torch.randperm(n)
        total_loss = 0.0
        for i in range(0, n, BATCH_SIZE):
            idx = perm[i:i + BATCH_SIZE]
            xb, yb = X_train_t[idx], y_train_t[idx]
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(idx)
        log.info("  epoch %d/%d - loss=%.4f", epoch + 1, EPOCHS, total_loss / n)
    return model

@torch.no_grad()
def predict_proba(model, X) -> np.ndarray:
    model.eval()
    X_t = torch.tensor(X, dtype=torch.long)
    logits = model(X_t)
    return torch.softmax(logits, dim=1).numpy()

def main():
    # Import local, voir commentaire équivalent dans rfm_olist.py.
    from config import get_engine

    engine = get_engine()
    df = pd.read_sql(QUERY, engine)
    log.info("%d avis avec commentaire texte", len(df))

    df["label"] = df["review_score"].apply(score_to_label)
    df["tokens"] = df["review_comment_message"].apply(tokenize)

    vocab = build_vocab(df["tokens"])
    log.info("Vocabulaire : %d mots retenus (sur %d rencontrés)", len(vocab) + 2,
             len({t for toks in df["tokens"] for t in toks}))

    X = np.array([encode(toks, vocab) for toks in df["tokens"]])
    y = df["label"].to_numpy()

    class_counts = np.bincount(y, minlength=3)
    class_weights = torch.tensor(len(y) / (3 * class_counts), dtype=torch.float32)
    log.info("Répartition des classes (depuis review_score) : %s",
             dict(zip(LABELS, class_counts.tolist())))

    # Validation croisée manuelle (5 plis) : chaque avis est scoré par un
    # modèle qui ne l'a pas vu à l'entraînement -> métriques et scores finaux
    # honnêtes, comme pour le churn.
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=42)
    oof_proba = np.zeros((len(y), 3))

    for fold, (train_idx, test_idx) in enumerate(skf.split(X, y), start=1):
        log.info("=== Pli %d/%d ===", fold, N_FOLDS)
        model = train_one_fold(X[train_idx], y[train_idx], class_weights, len(vocab) + 2)
        oof_proba[test_idx] = predict_proba(model, X[test_idx])

    oof_pred = oof_proba.argmax(axis=1)
    log.info("Rapport de classification (out-of-fold, vs label dérivé de review_score) :\n%s",
             classification_report(y, oof_pred, target_names=LABELS))

    sentiment = pd.DataFrame({
        "review_id": df["review_id"],
        "order_id": df["order_id"],
        "review_score": df["review_score"],
        "sentiment": [LABELS[i] for i in oof_pred],
        "sentiment_proba": oof_proba[np.arange(len(oof_pred)), oof_pred],
    })

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE analytics.review_sentiment"))
        sentiment.to_sql("review_sentiment", conn, schema="analytics",
                         if_exists="append", index=False, chunksize=5_000)
    log.info("%d avis scorés et écrits dans analytics.review_sentiment", len(sentiment))

if __name__ == "__main__":
    main()
