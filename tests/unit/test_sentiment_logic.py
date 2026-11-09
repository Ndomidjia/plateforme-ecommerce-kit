"""Tests unitaires purs (pas de DB, pas d'entraînement) sur
analytics/sentiment_olist.py.

J'entraîne un vrai réseau PyTorch dans ce module (voir train_one_fold,
~3 min pour le dataset complet, voir docs/tests.md) -- hors de question de
le refaire dans un test. Je teste ici ce qui ne nécessite aucun
entraînement : le dérivation du label depuis la note (weak supervision),
la tokenisation, le vocabulaire, l'encodage, et la forme des sorties du
réseau sur un passage avant (poids aléatoires, juste pour vérifier que les
dimensions s'enchaînent correctement)."""
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import load_analytics_module

sentiment_olist = load_analytics_module("sentiment_olist")


def test_score_to_label_matches_documented_mapping():
    # 1-2 étoiles -> négatif (0), 3 -> neutre (1), 4-5 -> positif (2)
    assert sentiment_olist.score_to_label(1) == 0
    assert sentiment_olist.score_to_label(2) == 0
    assert sentiment_olist.score_to_label(3) == 1
    assert sentiment_olist.score_to_label(4) == 2
    assert sentiment_olist.score_to_label(5) == 2


def test_tokenize_lowercases_and_strips_punctuation():
    tokens = sentiment_olist.tokenize("Produto Ótimo!! Recomendo 100%.")
    assert tokens == ["produto", "ótimo", "recomendo", "100"]


def test_tokenize_handles_empty_string():
    assert sentiment_olist.tokenize("") == []


def test_build_vocab_orders_by_frequency():
    token_lists = [["bom"], ["bom"], ["bom"], ["ruim"], ["ruim"], ["raro"]]
    vocab = sentiment_olist.build_vocab(token_lists)
    # index 0=padding, 1=inconnu réservés -> "bom" (le plus fréquent) doit
    # avoir l'indice le plus bas parmi les mots réels (2).
    assert vocab["bom"] == 2
    assert vocab["ruim"] < vocab["raro"]


def test_encode_pads_short_sequences_and_truncates_long_ones():
    vocab = {"bom": 2, "ruim": 3}
    short = sentiment_olist.encode(["bom"], vocab)
    assert len(short) == sentiment_olist.MAX_LEN
    assert short[0] == 2
    assert short[1] == 0  # padding

    long_tokens = ["bom"] * (sentiment_olist.MAX_LEN + 10)
    truncated = sentiment_olist.encode(long_tokens, vocab)
    assert len(truncated) == sentiment_olist.MAX_LEN


def test_encode_maps_unknown_words_to_reserved_index_one():
    vocab = {"bom": 2}
    encoded = sentiment_olist.encode(["palavra_desconhecida"], vocab)
    assert encoded[0] == 1


def test_sentiment_net_forward_pass_has_expected_output_shape():
    """Pas d'entraînement : je vérifie juste que le réseau (poids
    aléatoires à l'initialisation) produit bien 3 logits par exemple, pour
    un batch de taille quelconque -- erreur de dimension fréquente à ce
    niveau si l'embedding/pooling est mal branché."""
    model = sentiment_olist.SentimentNet(vocab_size=50, embed_dim=8, num_classes=3)
    batch = torch.randint(0, 50, (4, sentiment_olist.MAX_LEN))
    logits = model(batch)
    assert logits.shape == (4, 3)


def test_predict_proba_rows_sum_to_one():
    model = sentiment_olist.SentimentNet(vocab_size=50, embed_dim=8, num_classes=3)
    batch = torch.randint(0, 50, (3, sentiment_olist.MAX_LEN)).numpy()
    proba = sentiment_olist.predict_proba(model, batch)
    assert proba.shape == (3, 3)
    for row_sum in proba.sum(axis=1):
        assert abs(row_sum - 1.0) < 1e-5
