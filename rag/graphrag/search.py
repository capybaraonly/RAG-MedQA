# Stub for rag.graphrag.search — KnowledgeGraph retrieval not implemented in this fork.

import logging


class KGSearch:
    """Stub KnowledgeGraph searcher — always returns empty results."""

    def __init__(self, doc_store_conn, *args, **kwargs):
        self.doc_store_conn = doc_store_conn

    def search(self, *args, **kwargs):
        return []

    def retrieval(self, *args, **kwargs):
        return [], []
