"""
Tests for RAG vector store.
"""

import tempfile
from unittest.mock import patch

from src.rag.store import VectorStore


class TestVectorStore:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        with patch("src.rag.store.settings") as mock_settings:
            mock_settings.chroma_persist_directory = self.temp_dir
            self.store = VectorStore()

    def test_init(self):
        assert self.store.client is not None
        assert self.store.collection is not None

    def test_add_documents(self):
        self.store.add_documents(
            documents=["Hello world", "Test document"],
            metadatas=[
                {"channel_id": "C123"},
                {"channel_id": "C123"},
            ],
            ids=["doc1", "doc2"],
        )
        assert self.store.collection.count() >= 2

    def test_query(self):
        self.store.add_documents(
            documents=["Python programming language"],
            metadatas=[{"channel_id": "C123"}],
            ids=["doc_py"],
        )
        results = self.store.query("Python", n_results=1)
        assert len(results["documents"][0]) == 1

    def test_query_with_filter(self):
        self.store.add_documents(
            documents=["Channel A msg", "Channel B msg"],
            metadatas=[
                {"channel_id": "C_A"},
                {"channel_id": "C_B"},
            ],
            ids=["a1", "b1"],
        )
        results = self.store.query("msg", n_results=5, where={"channel_id": "C_A"})
        assert len(results["documents"][0]) >= 1

    def test_delete_by_channel(self):
        self.store.add_documents(
            documents=["To delete"], metadatas=[{"channel_id": "C_DEL"}], ids=["del1"]
        )
        self.store.delete_by_channel("C_DEL")
        results = self.store.query("delete", n_results=5, where={"channel_id": "C_DEL"})
        assert len(results["documents"][0]) == 0
