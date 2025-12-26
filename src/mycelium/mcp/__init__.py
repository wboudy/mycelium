"""
Mycelium MCP Server Package.

Exposes tools for filesystem access and mission state management
via the Model Context Protocol (MCP).
"""

from mycelium.mcp.server import mcp

__all__ = ["mcp"]
