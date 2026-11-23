"""
Offline embeddings for RAG unit tests.

ChromaDB's default embedder downloads an ONNX model on first use, which makes
tests depend on the network. This swaps in a deterministic bag-of-words
hashing embedder so the store, indexer and retriever are tested offline.
"""
import hashlib
import re

import numpy as np
import pytest
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

_DIM = 256


def _embed(self, input):
    vectors = []
    for text in input:
        vec = np.zeros(_DIM, dtype=np.float32)
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % _DIM] += 1.0
        norm = np.linalg.norm(vec)
        vectors.append(vec / norm if norm else vec)
    return vectors


@pytest.fixture(autouse=True)
def offline_embeddings(monkeypatch):
    monkeypatch.setattr(ONNXMiniLM_L6_V2, "__call__", _embed)
