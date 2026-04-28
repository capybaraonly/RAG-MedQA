# Stub for rag.utils.tavily_conn — Tavily web search not configured in this fork.

import logging


class Tavily:
    """Stub Tavily web search client — returns empty results."""

    def __init__(self, api_key=None, *args, **kwargs):
        self.api_key = api_key

    def search(self, query, *args, **kwargs):
        return {"results": []}

    def get_search_context(self, query, *args, **kwargs):
        return ""
