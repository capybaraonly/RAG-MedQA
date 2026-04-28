# Stub for rag.advanced_rag — deep research / advanced RAG features not included in this fork.

import logging


class DeepResearcher:
    """Stub DeepResearcher — always yields empty results."""

    def __init__(self, chat_mdl, prompt_config, retrieval_fn, *args, **kwargs):
        self.chat_mdl = chat_mdl
        self.prompt_config = prompt_config
        self.retrieval_fn = retrieval_fn

    async def run(self, question, queue, *args, **kwargs):
        """Stub: puts a single empty-result token and signals done."""
        await queue.put({"answer": "", "reference": {}})
        await queue.put(None)  # sentinel

    def __call__(self, *args, **kwargs):
        return self
