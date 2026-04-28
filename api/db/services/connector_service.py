# Stub for connector_service — connector/datasource features not included in this fork.

import logging


class Connector2KbService:
    """Stub service for knowledge base connector linking."""

    @staticmethod
    def link_connectors(kb_id, connectors, user_id):
        """Stub: no-op, returns empty error list."""
        return []

    @staticmethod
    def list_connectors(kb_id):
        """Stub: returns empty connector list."""
        return []
