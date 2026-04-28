# Stub for MCP tool call connection
# The full implementation is not included in this fork.
# MCP server tool-call features will be unavailable.

import logging


class MCPToolCallSession:
    """Stub MCP tool call session — returns empty tool list."""

    def __init__(self, mcp_server, variables):
        self.mcp_server = mcp_server
        self.variables = variables

    def get_tools(self, timeout=10):
        return []

    def close(self):
        pass


def close_multiple_mcp_toolcall_sessions(sessions):
    for s in sessions:
        try:
            s.close()
        except Exception:
            pass
